# Command Reference

## Response Format

Every command returns a JSON `ResponseEnvelope`:

```json
{
  "ok": true,
  "command": "table.ls",
  "target": { "file": "data.xlsx", "sheet": "Revenue" },
  "result": { ... },
  "changes": [],
  "warnings": [],
  "errors": [],
  "metrics": { "duration_ms": 42 },
  "recalc": { "mode": "cached", "performed": false }
}
```

Check `ok` first. If `false`, read `errors[].code` for the machine-readable reason. Warnings are non-fatal but worth noting.

## Reference Syntax

| Pattern | Example | Notes |
|---------|---------|-------|
| Cell | `Sheet1!B2` | Always include sheet name |
| Range | `Sheet1!A1:D10` | Rectangular region |
| Table column | `Sales[Revenue]` | For formula/format targets |
| Structured ref | `=[@Revenue]-[@Cost]` | Inside table formulas |

## Discovery Commands (Read-Only)

These never modify the workbook.

```bash
# Workbook structure: sheets, tables, named ranges, fingerprint
uv run xl wb inspect -f data.xlsx

# List all sheets with dimensions and table counts
uv run xl sheet ls -f data.xlsx

# List tables with columns, row counts, styles
uv run xl table ls -f data.xlsx
uv run xl table ls -f data.xlsx --sheet Revenue   # filter by sheet

# Read a single cell
uv run xl cell get -f data.xlsx --ref "Sheet1!B2"

# Range statistics (min, max, mean, sum, count, stddev)
uv run xl range stat -f data.xlsx --ref "Sheet1!B2:B100"

# SQL query over table data via DuckDB
uv run xl query -f data.xlsx --sql "SELECT Region, SUM(Revenue) FROM Sales GROUP BY Region"
uv run xl query -f data.xlsx --table Sales --where "Revenue > 5000"

# Find formulas by regex pattern
uv run xl formula find -f data.xlsx --pattern "SUM|AVERAGE"

# Lint formulas for volatile functions, broken refs
uv run xl formula lint -f data.xlsx

# Compare two workbooks cell-by-cell
uv run xl diff compare --file-a original.xlsx --file-b modified.xlsx

# Check if a workbook is locked by another process (useful before mutations on Windows)
uv run xl wb lock-status -f data.xlsx

# Validate cell/range references within a workbook
uv run xl validate refs -f data.xlsx --ref "Sheet1!A1:D10"
```

## Table Operations

Tables are the preferred abstraction for structured data. Prefer table operations over raw cell manipulation.

```bash
# Create a table from a range (headers in first row)
uv run xl table create -f data.xlsx -s Sheet1 --ref "A1:D10" -t Sales

# Add a calculated column
uv run xl table add-column -f data.xlsx -t Sales -n Margin --formula "=[@Revenue]-[@Cost]"

# Add a column with a default value
uv run xl table add-column -f data.xlsx -t Sales -n Status --default "Active"

# Append rows (JSON array of objects keyed by column name)
uv run xl table append-rows -f data.xlsx -t Sales --data '[{"Region":"West","Product":"Widget","Revenue":5000,"Cost":3000}]'

# Append rows from a JSON file (avoids shell escaping issues — preferred for large payloads)
uv run xl table append-rows -f data.xlsx -t Sales --data-file rows.json --schema-mode allow-missing-null

# Delete a column
uv run xl table delete-column -f data.xlsx -t Sales -n OldColumn

# Delete a table (preserves cell data, removes table definition)
uv run xl table delete -f data.xlsx -t Sales
```

**Schema modes for append-rows:**
- `strict` (default) — all columns required, no extras
- `allow-missing-null` — missing columns become null (use for tables with formula columns)
- `map-by-header` — case-insensitive best-effort mapping

## Cell and Formula Operations

```bash
# Set a cell value (auto-detects type, or specify --type number|text|bool|date)
uv run xl cell set -f data.xlsx --ref "Sheet1!B2" --value 42

# Set a formula (adjusts references by default when filling a range)
uv run xl formula set -f data.xlsx --ref "Sheet1!C2:C10" --formula "=A2*B2"

# Fixed fill mode (copies formula literally, no adjustment)
uv run xl formula set -f data.xlsx --ref "Sheet1!C2:C10" --formula "=SUM(A:A)" --fill-mode fixed
```

**Formula safety:** Overwriting an existing formula requires `--force-overwrite-formulas`. This prevents accidental formula destruction.

## Formatting

```bash
# Number format (number, percent, currency, date, text)
uv run xl format number -f data.xlsx --ref "Sheet1!B2:B100" --style currency --decimals 2

# Column widths
uv run xl format width -f data.xlsx --sheet Sheet1 --columns A,B,C --width 15

# Freeze panes
uv run xl format freeze -f data.xlsx --sheet Sheet1 --ref "A2"
```

## Sheet Operations

```bash
uv run xl sheet create -f data.xlsx --name "NewSheet"
uv run xl sheet rename -f data.xlsx --name "OldName" --new-name "NewName"
uv run xl sheet delete -f data.xlsx --name "Obsolete"   # fails if last sheet
```

## Range Operations

```bash
uv run xl range clear -f data.xlsx --ref "Sheet1!A1:Z100" --contents --formats
```

## Plan Workflow Commands

### Generate a Plan

```bash
uv run xl plan add-column -f data.xlsx -t Sales -n Margin \
  --formula "=[@Revenue]-[@Cost]" --out plan.json

uv run xl plan set-cells -f data.xlsx \
  --ref "Sheet1!A1" --value "Header" --out plan.json

uv run xl plan create-table -f data.xlsx -s Sheet1 \
  --ref "A1:D10" -t Sales --out plan.json

# Plan: format a range
uv run xl plan format -f data.xlsx --ref "Sales[Revenue]" \
  --style currency --decimals 2 --out plan.json

# Plan: delete a column
uv run xl plan delete-column -f data.xlsx -t Sales -n OldColumn --out plan.json

# Plan: delete a table
uv run xl plan delete-table -f data.xlsx -t ObsoleteTable --out plan.json

# Plan: rename a sheet
uv run xl plan rename-sheet -f data.xlsx --name "OldName" --new-name "NewName" --out plan.json

# Plan: delete a sheet
uv run xl plan delete-sheet -f data.xlsx --name "Obsolete" --out plan.json
```

### Compose Multiple Plans

```bash
uv run xl plan compose --plan plan1.json --plan plan2.json --out combined.json
```

### Validate

```bash
uv run xl validate plan -f data.xlsx --plan plan.json
```

This checks fingerprint match, preconditions (tables/sheets/columns exist), and operation feasibility.

### Preview (Dry Run)

```bash
uv run xl apply -f data.xlsx --plan plan.json --dry-run
```

Returns a `DryRunSummary` with changes broken down by type and sheet.

### Apply

```bash
uv run xl apply -f data.xlsx --plan plan.json --backup
```

`--backup` creates a timestamped `.bak` copy before writing. For `xl apply`, backup is **on by default** (`--backup/--no-backup`). For all other mutation commands, backup is **off by default** — pass `--backup` explicitly.

### Verify

```bash
uv run xl verify assert -f data.xlsx --assertions '[
  {"type": "table.column_exists", "table": "Sales", "column": "Margin"},
  {"type": "cell.not_empty", "ref": "Sheet1!B2"},
  {"type": "table.row_count", "table": "Sales", "min": 10}
]'
```

## Workbook Creation

```bash
uv run xl wb create --file report.xlsx --sheets "Sales,Summary"
```

## Workbook Validation

```bash
uv run xl validate workbook -f data.xlsx   # checks for macros, external links, hidden sheets
```
