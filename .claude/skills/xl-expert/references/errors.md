# Error Code Reference

## Exit Codes

| Code | Category | Description |
|------|----------|-------------|
| 0 | Success | Operation completed |
| 10 | Validation | Bad input, schema mismatch, invalid plan, duplicate names |
| 20 | Protection | Protected range or sheet (detected but not enforced in v1) |
| 30 | Formula | Overwrite blocked without --force-overwrite-formulas, parse failure |
| 40 | Conflict | Fingerprint mismatch — workbook changed since plan was created |
| 50 | IO | File not found, locked by another process, permission denied, corrupt file |
| 60 | Recalc | Recalculation adapter unavailable |
| 70 | Unsupported | Feature not supported (preservation risk) |
| 90 | Internal | Unexpected failure |

## Validation Error Codes (Exit 10)

| Code | Meaning | Common Cause |
|------|---------|--------------|
| `VALIDATION` | Generic validation failure | Malformed input |
| `SCHEMA` | Schema validation failed | Wrong data types in plan/rows |
| `RANGE` | Invalid range reference | Malformed cell/range reference |
| `PLAN_INVALID` | Plan structure invalid | Missing required fields |
| `MISSING_TABLE` | Table not found | Typo in table name |
| `MISSING_SHEET` | Sheet not found | Typo in sheet name |
| `MISSING_COLUMN` | Column not found | Typo in column name |
| `COLUMN_EXISTS` | Column already exists | Duplicate column name (case-insensitive) |
| `COLUMN_NOT_FOUND` | Column not in table | Wrong column name for operation |
| `TABLE_EXISTS` | Table name taken | Name already used by another table |
| `TABLE_OVERLAP` | Range overlaps existing table | New table range conflicts |
| `TABLE_NOT_FOUND` | Table not found | Table name doesn't exist |
| `SHEET_EXISTS` | Sheet name taken | Duplicate sheet name |
| `SHEET_NOT_FOUND` | Sheet not found | Sheet doesn't exist |
| `LAST_SHEET` | Cannot delete last sheet | Workbook must have at least one sheet |
| `INVALID_ARGUMENT` | Bad argument | Wrong type or value for parameter |
| `TARGET_MISMATCH` | Plan targets different file | Plan's target.file doesn't match --file |
| `ASSERTION` | Verification assertion failed | Post-apply check didn't pass |
| `WORKFLOW_INVALID` | Workflow YAML invalid | Syntax error or missing required fields |

## IO Error Codes (Exit 50)

| Code | Meaning | Resolution |
|------|---------|------------|
| `NOT_FOUND` | File doesn't exist | Check path |
| `LOCK` | File locked by another process | Close Excel or other programs using the file |
| `FILE_EXISTS` | File already exists (for create) | Use a different name or remove existing |
| `CORRUPT` | Workbook can't be parsed | File may be damaged or not a valid xlsx/xlsm |

## Conflict Handling (Exit 40)

When a plan's fingerprint doesn't match the current workbook:
1. The workbook was modified externally since the plan was generated
2. Re-inspect the workbook: `uv run xl wb inspect -f data.xlsx`
3. Regenerate the plan with the new fingerprint
4. Validate and apply again

## Formula Error (Exit 30)

Triggered when:
- Trying to set a cell value that currently contains a formula (without `--force-overwrite-formulas`)
- Trying to set a formula on a cell that already has a formula (without `--force-overwrite-formulas`)
- Formula parse/lint failure

Resolution: Add `--force-overwrite-formulas` if intentional, or choose a different cell.

## Troubleshooting Guide

**"File not found" but the file exists:**
- Check the path is correct (use absolute path if unsure)
- On Windows, check file is not open in Excel (which locks it)

**"Table not found" but it shows in Excel:**
- Table names are case-sensitive in xl; use `xl table ls` to get exact names
- The range may look like a table but isn't defined as an Excel Table

**Fingerprint mismatch after apply:**
- Expected — the fingerprint changes after modification
- Re-inspect to get the new fingerprint for subsequent plans

**Formula columns not auto-filling on append:**
- Use `--schema-mode allow-missing-null` to skip formula columns in row data
- Formula columns auto-fill from the template in the first data row

**Query returns cached values, not calculated:**
- `xl` uses cached values (what Excel last computed); use `--data-only` flag
- For fresh calculations, open and save in Excel first, then query
