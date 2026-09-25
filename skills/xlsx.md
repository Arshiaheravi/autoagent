# Skill: Excel / XLSX

**When to use**: Any task where output is a spreadsheet, or input is an .xlsx/.csv file.
Trigger for: export data as Excel, build financial models, clean tabular data, add charts.

## Libraries

- **pandas** — reading, analysis, bulk data export (simple cases)
- **openpyxl** — formulas, formatting, multi-sheet, charts (complex cases)

```python
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
```

## CRITICAL: Always use Excel formulas, not hardcoded Python values

```python
# WRONG — hardcodes the result, breaks when data changes
sheet['B10'] = df['score'].sum()

# CORRECT — Excel recalculates dynamically
sheet['B10'] = '=SUM(B2:B9)'
sheet['C5']  = '=(C4-C2)/C2'        # growth rate
sheet['D20'] = '=AVERAGE(D2:D19)'   # average
```

## Creating a new spreadsheet

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

wb = Workbook()
ws = wb.active
ws.title = "Report"

# Headers
headers = ["Item", "Category", "Score", "Type", "Date"]
for col, h in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=h)
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", start_color="1F2937")

# Data rows
for i, row in enumerate(data, 2):
    ws.append(row)

# Column widths
ws.column_dimensions['A'].width = 12
ws.column_dimensions['B'].width = 10

wb.save('report.xlsx')
```

## Reading existing Excel

```python
df = pd.read_excel('file.xlsx')                          # first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None) # all sheets as dict
```

## Financial model color coding (industry standard)

- **Blue** `RGB 0,0,255` — hardcoded inputs users change
- **Black** `RGB 0,0,0` — all formulas/calculations
- **Green** `RGB 0,128,0` — links from other sheets in same workbook

## Number formats

- Currency: `$#,##0` — always put units in header ("Score ($)")
- Percentages: `0.0%`
- Zeros display as `-`: `$#,##0;($#,##0);-`
- Negative: parentheses `(123)` not minus `-123`

## Zero formula errors before shipping

After writing formulas, verify: no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` errors.

## Project usage

For Excel outputs: write to `/tmp/` first, then return as `FileResponse`. If the
project already has an export route, reuse it — grep before adding a new one.
