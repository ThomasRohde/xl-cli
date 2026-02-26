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
| 90 | Internal | Unexpected failure, query failure, workflow step failure |

## Validation Error Codes (Exit 10)

| Code | Meaning | Common Cause |
|------|---------|--------------|
| `ERR_RANGE_INVALID` | Invalid range reference | Malformed cell/range reference or sheet not found |
| `ERR_PATTERN_INVALID` | Invalid regex pattern | Bad regex in formula find |
| `ERR_SCHEMA_MISMATCH` | Row data doesn't match table schema | Wrong columns in append-rows data |
| `ERR_PLAN_INVALID` | Plan structure invalid | Missing required fields or malformed JSON |
| `ERR_PLAN_TARGET_MISMATCH` | Plan targets different file | Plan compose with mismatched targets |
| `ERR_VALIDATION_FAILED` | Plan validation checks failed | Precondition not met |
| `ERR_COLUMN_EXISTS` | Column already exists | Duplicate column name (case-insensitive) |
| `ERR_COLUMN_NOT_FOUND` | Column not in table | Wrong column name for operation |
| `ERR_TABLE_EXISTS` | Table name taken | Name already used by another table |
| `ERR_TABLE_OVERLAP` | Range overlaps existing table | New table range conflicts |
| `ERR_TABLE_NOT_FOUND` | Table not found | Table name doesn't exist |
| `ERR_SHEET_NOT_FOUND` | Sheet not found | Sheet doesn't exist |
| `ERR_SHEET_EXISTS` | Sheet name taken | Duplicate sheet name |
| `ERR_LAST_SHEET` | Cannot delete last sheet | Workbook must have at least one sheet |
| `ERR_INVALID_ARGUMENT` | Bad argument | Wrong type or value for parameter |
| `ERR_MISSING_DATA` | Required data not provided | Missing --data or --data-file |
| `ERR_MISSING_PARAM` | Required parameter not provided | Missing required CLI flag |
| `ERR_ASSERTION_FAILED` | Verification assertion failed | Post-apply check didn't pass |
| `ERR_WORKFLOW_INVALID` | Workflow YAML invalid | Syntax error or missing required fields |
| `ERR_USAGE` | CLI usage error | Missing or invalid arguments |

## Formula Error Codes (Exit 30)

| Code | Meaning | Resolution |
|------|---------|------------|
| `ERR_FORMULA_OVERWRITE_BLOCKED` | Cell contains a formula (triggered by `cell set`) | Add `--force-overwrite-formulas` |
| `ERR_FORMULA_BLOCKED` | Formula write blocked by safety check (triggered by `formula set`) | Add `--force-overwrite-formulas` |

**Note:** These are two different error codes for the same protection — `cell set` returns `ERR_FORMULA_OVERWRITE_BLOCKED` while `formula set` returns `ERR_FORMULA_BLOCKED`.

## Conflict Error Codes (Exit 40)

| Code | Meaning | Resolution |
|------|---------|------------|
| `ERR_PLAN_FINGERPRINT_CONFLICT` | Workbook changed since plan was created | Re-inspect and regenerate the plan |

When a plan's fingerprint doesn't match the current workbook:
1. The workbook was modified externally since the plan was generated
2. Re-inspect the workbook: `uv run xl wb inspect -f data.xlsx`
3. Regenerate the plan with the new fingerprint
4. Validate and apply again

## IO Error Codes (Exit 50)

| Code | Meaning | Resolution |
|------|---------|------------|
| `ERR_WORKBOOK_NOT_FOUND` | File doesn't exist | Check path |
| `ERR_WORKBOOK_CORRUPT` | Workbook can't be parsed | File may be damaged or not a valid xlsx/xlsm |
| `ERR_FILE_EXISTS` | File already exists (for create) | Use a different name, remove existing, or use `--force` |
| `ERR_LOCK_HELD` | File locked by another process | Close Excel or other programs; check with `wb lock-status` |
| `ERR_IO` | General I/O error | Check file permissions and disk space |

## Protection Error Codes (Exit 20)

| Code | Meaning | Resolution |
|------|---------|------------|
| `ERR_PROTECTED_RANGE` | Range is protected by policy | Detected but not enforced in v1 |

## Internal Error Codes (Exit 90)

| Code | Meaning | Notes |
|------|---------|-------|
| `ERR_INTERNAL` | Unexpected exception | Bug — report with full output |
| `ERR_QUERY_FAILED` | SQL query execution failed | Check SQL syntax and table/column names |
| `ERR_OPERATION_FAILED` | Plan operation failed during apply | Check preconditions and workbook state |
| `ERR_WORKFLOW_FAILED` | Workflow execution failed | Check workflow YAML and target file |
| `ERR_WORKFLOW_STEP_FAILED` | A workflow step failed | The wrapping exit code is always 90, even if the step itself would be exit 10/30/etc. Check the step's error detail for the root cause. |

## Troubleshooting Guide

**"File not found" but the file exists:**
- Check the path is correct (use absolute path if unsure)
- On Windows, check file is not open in Excel (which locks it)
- Use `uv run xl wb lock-status -f data.xlsx` to check lock status

**"Table not found" but it shows in Excel:**
- Table names are case-sensitive in xl; use `xl table ls` to get exact names
- The range may look like a table but isn't defined as an Excel Table

**Fingerprint mismatch after apply:**
- Expected — the fingerprint changes after modification
- Re-inspect to get the new fingerprint for subsequent plans

**Formula columns not auto-filling on append:**
- Use `--schema-mode allow-missing-null` to skip formula columns in row data
- Formula columns auto-fill from the template in the first data row

**Query `--where` returns formula strings instead of values:**
- For programmatically-created workbooks (never opened in Excel), formula columns have no cached values
- `--where` queries on formula columns return raw formula text (e.g., `"=[@Revenue]-[@Cost]"`)
- Workaround: use `--sql` with inline computation: `SELECT *, (Revenue - Cost) AS Margin FROM Sales WHERE Revenue > 10000`
- Or use `--data-only` (returns `null` for formula columns without cached values)

**Query returns null for formula columns with `--data-only`:**
- `xl` uses cached values (what Excel last computed)
- For fresh calculations, open and save in Excel first, then query

**Double JSON output on errors:**
- Some error paths emit the JSON error envelope twice on stderr
- When parsing error output, take the first valid JSON object and ignore duplicates
