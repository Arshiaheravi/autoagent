# Skill: PPTX (PowerPoint Presentations)

**When to use**: Creating or editing .pptx files — pitch decks, reports, investor slides, dashboards.

## Read existing presentation

```bash
python -m markitdown presentation.pptx   # extract text
# Slide thumbnails (for visual QA) — via LibreOffice headless if available:
soffice --headless --convert-to pdf presentation.pptx && pdftoppm -png presentation.pdf slide
```

## Create from scratch (PptxgenJS)

Use PptxgenJS when no template exists:

```bash
npm install -g pptxgenjs
```

```javascript
const pptx = new PptxGenJS();

// Set slide dimensions
pptx.layout = 'LAYOUT_WIDE'; // 16:9

const slide = pptx.addSlide();
slide.addText('Title Text', { x: 0.5, y: 0.5, w: 9, h: 1.5, fontSize: 36, bold: true, color: '2563EB' });
slide.addText('Body text here', { x: 0.5, y: 2.0, w: 9, h: 4, fontSize: 18 });

// Add image
slide.addImage({ path: 'chart.png', x: 1, y: 2, w: 8, h: 4 });

pptx.writeFile({ fileName: 'output.pptx' });
```

## Edit existing (unpack → edit XML → repack)

```bash
# Unpack
mkdir unpacked && cp presentation.pptx unpacked/presentation.zip
cd unpacked && unzip presentation.zip -d xml_content

# Edit ppt/slides/slide1.xml etc.

# Repack
cd xml_content && zip -r ../output.pptx .
```

## Design principles

- Every slide needs a visual element — no text-only slides
- Color palette: dominant primary (60-70%), supporting tone, sharp accent
- Topic-specific colors — not generic blues/grays
- 0.5" margins, 0.3-0.5" spacing between blocks
- Interesting typography pairings

## QA before shipping

- Convert slides to JPEGs and visually inspect each one
- Check for: overlapping text, overflow, low contrast, misaligned elements
- Fix at least one issue per slide before declaring done

## Project usage
For report decks or investor presentations.
Return as `FileResponse("/tmp/deck.pptx", media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")`.
