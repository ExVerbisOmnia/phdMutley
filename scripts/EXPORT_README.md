# Database Export to Excel

## Overview

The `export_to_excel.py` script exports the entire PostgreSQL database to an Excel file, with each table becoming a separate tab.

## Features

- ✅ Exports all database tables to a single Excel file
- ✅ Each table becomes a separate sheet (tab) in Excel
- ✅ Automatic text truncation for large text fields (configurable)
- ✅ Timestamped output files
- ✅ Database summary statistics
- ✅ Detailed logging

## Usage

### Basic Export

```bash
# Activate virtual environment
source venv/bin/activate

# Run export with default settings (truncates text to 1000 chars)
python scripts/export_to_excel.py
```

### View Database Summary Only

```bash
python scripts/export_to_excel.py --summary
```

### Custom Output File

```bash
python scripts/export_to_excel.py --output /path/to/output.xlsx
```

### Export Full Text (No Truncation)

⚠️ **Warning**: This may create very large files!

```bash
python scripts/export_to_excel.py --full-text
```

### Custom Truncation Length

```bash
# Truncate text fields to 2000 characters instead of 1000
python scripts/export_to_excel.py --truncate-length 2000
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `--output`, `-o` | Specify output file path (default: auto-generated with timestamp) |
| `--full-text` | Export full text without truncation (may create very large files) |
| `--truncate-length` | Maximum length for text fields (default: 1000 characters) |
| `--summary` | Print database summary and exit (no export) |

## Output

### Default Location

Exports are saved to: `data/exports/climate_litigation_export_YYYYMMDD_HHMMSS.xlsx`

### File Structure

Each table in the database becomes a separate sheet in the Excel file:

- **cases**: Case metadata (6 rows)
- **documents**: Document information (31 rows)
- **extracted_text**: Extracted text with truncation (31 rows)
- **extracted_texts**: Alternative extracted text table (31 rows)
- **citation_extraction_phased**: Citation extraction results (28 rows)
- **citation_extraction_phased_summ**: Citation extraction summaries (13 rows)
- **citations**: Citation relationships (empty)
- **text_sections**: Text sections (empty)
- **processing_log**: Processing logs (empty)
- And other tables...

### Text Truncation

By default, the following fields are truncated to **1000 characters** to keep file sizes manageable:

- `extracted_text.raw_text`
- `extracted_text.processed_text`

All other fields (including citations, citation paragraphs, metadata, etc.) are **fully exported** without truncation.

## Inspecting Exports

Use the inspection script to view the contents of an exported file:

```bash
# Inspect most recent export
python scripts/inspect_export.py

# Inspect specific file
python scripts/inspect_export.py /path/to/file.xlsx
```

## Examples

### Example 1: Quick Export for Review

```bash
python scripts/export_to_excel.py
```

Output:
```
✓ Success! Excel file created at:
  /home/gusrodgs/Gus/cienciaDeDados/phdMutley/data/exports/climate_litigation_export_20251124_070329.xlsx
```

### Example 2: Export with More Text Context

```bash
python scripts/export_to_excel.py --truncate-length 5000
```

### Example 3: Check Database Status

```bash
python scripts/export_to_excel.py --summary
```

Output:
```
============================================================
DATABASE SUMMARY
============================================================

Database: climate_litigation
Total tables: 12

Table Statistics:
------------------------------------------------------------
Table Name                                     Row Count
------------------------------------------------------------
extracted_texts                                       31
documents                                             31
extracted_text                                        31
citation_extraction_phased                            28
citation_extraction_phased_summary                    13
cases                                                  6
...
------------------------------------------------------------
TOTAL                                                140
============================================================
```

## Logging

All export operations are logged to: `logs/export_to_excel.log`

## Notes

- The script preserves all data types (UUIDs, timestamps, JSON, etc.)
- Empty tables are still exported (with column headers only)
- Sheet names are limited to 31 characters (Excel limitation)
- The script handles special characters in table names
- All citations and citation paragraphs are fully exported without truncation

## Troubleshooting

### Error: "No module named 'openpyxl'"

```bash
pip install openpyxl
```

### Error: "Connection refused"

Check that PostgreSQL is running and the `.env` file has correct credentials.

### File too large

Use `--truncate-length` with a smaller value, or export specific tables only.
