# `xl` Agent Integration Guide

This guide explains how AI agents interact with the `xl` CLI to safely inspect, plan, and mutate Excel workbooks.

## Core Principles

1. **Every command returns JSON** — All responses use the `ResponseEnvelope` format
2. **Plan before mutate** — Use `xl plan` → `xl validate` → `xl apply --dry-run` → `xl apply`
3. **Fingerprint-based conflict detection** — The CLI tracks file hashes to prevent overwrites
4. **Table-first operations** — Prefer table-level operations over raw cell manipulation

## Response Envelope

Every command returns this JSON structure:

```json
{
  "ok": true,
  "command": "table.ls",
  "target": { "file": "budget.xlsx", "sheet": "Revenue" },
  "result": { ... },
  "changes": [],
  "warnings": [],
  "errors": [],
  "metrics": { "duration_ms": 42 },
  "recalc": { "mode": "cached", "performed": false }
}
```

**Agent parsing rules:**
- Check `ok` first — `false` means the command failed
- `errors[].code` provides a machine-readable error code (e.g., `ERR_TABLE_NOT_FOUND`)
- `warnings[]` may contain non-fatal issues to surface to users
- `result` contains the command-specific payload
- `metrics.duration_ms` tracks execution time

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 10 | Validation error |
| 20 | Protection/permission error |
| 30 | Formula parse/lint error |
| 40 | Conflict/fingerprint mismatch |
| 50 | IO/lock error |
| 90 | Internal error |

## Workflow: Inspect → Plan → Apply

### Step 1: Inspect the workbook

```bash
xl wb inspect --file budget.xlsx
```

Returns: sheets, tables, named ranges, fingerprint, macro/external link warnings.

### Step 2: List tables

```bash
xl table ls --file budget.xlsx
```

Returns: table names, columns, row counts, sheet locations.

### Step 3: Generate a plan

```bash
xl plan add-column --file budget.xlsx --table Sales \
  --name GrossMarginPct --formula "=[@GrossMargin]/[@Revenue]" \
  --out plan.json
```

### Step 4: Validate the plan

```bash
xl validate plan --file budget.xlsx --plan plan.json
```

Checks: fingerprint match, table/column existence, schema compatibility.

### Step 5: Dry-run

```bash
xl apply --file budget.xlsx --plan plan.json --dry-run
```

Preview changes without modifying the file.

### Step 6: Apply

```bash
xl apply --file budget.xlsx --plan plan.json --backup
```

Apply changes with automatic backup creation.

### Step 7: Verify

```bash
xl verify assert --file budget.xlsx --assertions '[
  {"type": "table.column_exists", "table": "Sales", "column": "GrossMarginPct"}
]'
```

## Query Data with SQL

```bash
xl query --file budget.xlsx \
  --sql "SELECT Region, SUM(Sales) as Total FROM Sales GROUP BY Region"
```

Tables are automatically loaded into DuckDB for SQL querying.

## Cell-Level Operations

```bash
# Read a cell
xl cell get --file budget.xlsx --ref "Revenue!B2"

# Write a cell
xl cell set --file budget.xlsx --ref "Revenue!B2" --value 42 --type number

# Range statistics
xl range stat --file budget.xlsx --ref "Revenue!C2:C100"
```

## Formula Operations

```bash
# Set a formula
xl formula set --file budget.xlsx --ref "Revenue!E2" --formula "=C2-D2"

# Lint formulas for issues
xl formula lint --file budget.xlsx

# Search for formula patterns
xl formula find --file budget.xlsx --pattern "VLOOKUP"
```

## Formatting

```bash
xl format number --file budget.xlsx --ref "Revenue!C2:C100" --style currency --decimals 2
xl format width --file budget.xlsx --sheet Revenue --columns A,B,C --width 15
xl format freeze --file budget.xlsx --sheet Revenue --ref B2
```

## Comparing Workbooks

```bash
xl diff compare --file-a original.xlsx --file-b modified.xlsx
```

Returns: cell-level changes, sheets added/removed, fingerprint comparison.

## Workflow Execution

Create a YAML workflow file and run it:

```bash
xl run --workflow workflow.yaml --file budget.xlsx
```

See `examples/workflows/` for sample workflow files.

## stdio Server Mode

For agent tool integration (MCP/ACP), use the stdio server:

```bash
xl serve --stdio
```

Send JSON commands on stdin, receive JSON responses on stdout:

```json
{"id": "1", "command": "wb.inspect", "args": {"file": "budget.xlsx"}}
{"id": "2", "command": "table.ls", "args": {"file": "budget.xlsx"}}
{"id": "3", "command": "cell.get", "args": {"file": "budget.xlsx", "ref": "Revenue!A1"}}
```

## Error Handling for Agents

When `ok` is `false`, agents should:

1. Read `errors[0].code` for the error category
2. Check if the error is retryable (e.g., `ERR_LOCK_HELD` → retry with backoff)
3. Check if the error needs user intervention (e.g., `ERR_PROTECTED_RANGE`)
4. Use the exit code for process-level error handling

## Safety Features

- **Formula overwrite protection**: `cell set` and `formula set` block overwriting existing formulas unless `--force-overwrite-formulas` is used
- **Fingerprint conflict detection**: `apply` rejects plans if the workbook changed since the plan was created
- **Backup creation**: `--backup` creates timestamped `.bak` copies before mutation
- **Dry-run mode**: `--dry-run` previews changes without writing to disk
- **Policy enforcement**: `xl-policy.yaml` can restrict protected sheets, ranges, and mutation thresholds
