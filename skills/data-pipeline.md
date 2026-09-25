# Data Pipeline — Image Processing & Storage

When to read: tasks involving drone image ingestion, georeferencing, NDVI/thermal computation, S3 storage, or audio/video processing from farmers.

Source agents: Data Engineer

## Owns

`src/<yourapp>/services/pipeline/` — e.g. ingest.py, process.py, storage.py

## Pipeline Flow

```
Drone SD card → Upload → Georeference → NDVI/Thermal compute → Store → Ready for Crop Analyst
```

## Pipeline Stages

1. **Ingest** (ingest.py): Upload images, validate format (TIFF/DNG multispectral, RJPEG thermal), extract GPS metadata
2. **Georeference** (process.py): Align to field boundaries, stitch multi-image flights, correct for altitude/lens distortion
3. **NDVI Compute** (process.py): `(NIR - Red) / (NIR + Red)` from multispectral bands
4. **Thermal Compute** (process.py): Raw thermal → temperature map (°C), normalize for ambient conditions
5. **Storage** (storage.py): Upload to S3, index in DB with farm/field/date metadata

## Data Formats

| Type | Raw | Processed | Storage |
|------|-----|-----------|---------|
| Multispectral | TIFF (4 bands) | GeoTIFF (NDVI float32) | S3 + DB reference |
| Thermal | RJPEG (radiometric) | GeoTIFF (°C float32) | S3 + DB reference |
| RGB | JPEG | Orthomosaic JPEG | S3 + DB reference |
| Flight log | CSV/JSON | Structured JSON | DB |
| Voice note | OGG/M4A (WhatsApp) | Transcribed text + structured observation | DB |

## Protocols

### Pipeline Health Monitor
After every pipeline run:
1. Did all images process successfully?
2. Flag: corrupted files, missing GPS, incomplete flights
3. Report: processing time, image count, coverage %
4. Alert if pipeline fails or takes >2x normal time

### Image Quality Validator
At ingest, before processing:
1. Sharpness check (blur detection)
2. Exposure check (over/underexposed bands)
3. GPS accuracy (drift > 10m = flag)
4. Completeness (expected image count vs actual)
5. Reject and re-request flight if >20% fail quality check

### Voice/Audio Pipeline
For WhatsApp voice notes and farmer recordings:
1. Receive audio (OGG/M4A from WhatsApp API)
2. Transcribe (speech-to-text, Spanish)
3. Extract structured observation (crop, field, issue, severity)
4. Store as knowledge entry linked to farm/field
5. Route to relevant service (treatment if problem, knowledge base if observation)

## All Data Sources (not just drone imagery)

| Source | Format | Frequency | Pipeline |
|--------|--------|-----------|----------|
| Drone multispectral | TIFF (4 bands) | Weekly | ingest → georeference → NDVI compute → store |
| Drone thermal | RJPEG | Bi-weekly | ingest → thermal compute → store |
| Drone RGB | JPEG | Per flight | ingest → orthomosaic → store |
| Soil sensors (IoT) | JSON/MQTT | Hourly | validate → store → feed health scoring |
| Weather API | JSON | Every 3h | fetch → store → feed irrigation |
| WhatsApp voice | OGG/M4A | On demand | transcribe → extract → store → route |
| Farmer text | WhatsApp text | On demand | parse → store → route |
| Lab soil analysis | Manual entry | Per sample | validate → store → feed recommendations |

## Error Recovery

When the pipeline fails mid-run:
1. **Partial flight**: Mark FlightLog status = "incomplete", flag missing images
2. **Corrupted file**: Skip file, log to pipeline health, continue with remaining
3. **S3 upload failure**: Retry 3x with exponential backoff, then store locally and flag
4. **Transcription failure**: Store raw audio, flag for manual review, don't block farmer reply
5. **Never lose raw data** — even if processing fails, the raw upload is preserved

## Data Retention

- **Raw imagery**: Keep 12 months hot (S3 standard), then archive to cold storage (S3 Glacier)
- **Processed NDVI/thermal**: Keep indefinitely (small — float32 GeoTIFFs)
- **Voice notes**: Keep 6 months hot, archive audio, keep transcription indefinitely
- **Flight logs**: Keep indefinitely (structured JSON, tiny)

## Downstream Consumers

Processed data is read by:
- `services/crop/ndvi.py` → NDVI interpretation
- `services/crop/thermal.py` → thermal stress detection
- `services/crop/health.py` → composite health scoring
- `services/intelligence/recommendations.py` → treatment logic
- `api/intel.py` → cross-farm analytics dashboard
- `api/dashboard.py` → per-farm aggregation

## Implementation Rules

- Processing functions are **pure** — arrays in, results out
- Storage operations are separate from computation
- Each flight produces 2-5 GB — storage must be cheap and scalable
- All S3 paths follow: `{farm_id}/{field_id}/{date}/{mission_type}/`
