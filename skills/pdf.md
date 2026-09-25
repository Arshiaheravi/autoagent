# Skill: PDF

**When to use**: Any task involving PDF files — reading, extracting text/tables, merging, splitting,
creating reports, adding watermarks, or producing downloadable PDF output.

## Libraries

```python
from pypdf import PdfReader, PdfWriter          # merge, split, rotate, encrypt
import pdfplumber                                # text + table extraction
from reportlab.pdfgen import canvas             # create PDFs from scratch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
```

## Read / Extract text

```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        tables = page.extract_tables()  # returns list of list of lists
```

## Extract tables → DataFrame

```python
import pdfplumber, pandas as pd

with pdfplumber.open("report.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        for table in page.extract_tables():
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

combined = pd.concat(all_tables, ignore_index=True)
```

## Merge PDFs

```python
from pypdf import PdfReader, PdfWriter

writer = PdfWriter()
for path in ["doc1.pdf", "doc2.pdf"]:
    for page in PdfReader(path).pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as f:
    writer.write(f)
```

## Create a PDF report (reportlab)

```python
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []

story.append(Paragraph("Report Title", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph("Report body content...", styles['Normal']))

doc.build(story)
```

**IMPORTANT**: Never use Unicode subscript/superscript chars (₀₁₂ etc.) in ReportLab —
use `<sub>2</sub>` and `<super>2</super>` XML tags inside `Paragraph()` instead.

## Password protect

```python
from pypdf import PdfReader, PdfWriter

writer = PdfWriter()
for page in PdfReader("input.pdf").pages:
    writer.add_page(page)
writer.encrypt("userpassword")
with open("encrypted.pdf", "wb") as f:
    writer.write(f)
```

## Quick reference

| Task | Tool |
|------|------|
| Extract text/tables | pdfplumber |
| Merge / split | pypdf |
| Create from scratch | reportlab |
| OCR scanned PDF | pytesseract + pdf2image |
| Command-line merge | `qpdf --empty --pages f1.pdf f2.pdf -- out.pdf` |

## Project usage

For downloadable PDF reports:
- Generate to `/tmp/report.pdf`
- Return as `FileResponse("/tmp/report.pdf", media_type="application/pdf")`
- Add route to `routes/export.py`
