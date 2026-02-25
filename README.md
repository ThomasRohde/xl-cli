# xl

**Agent-first CLI for Excel workbooks** (.xlsx / .xlsm)

A transactional spreadsheet execution layer that lets AI agents and humans inspect, plan, validate, and apply workbook changes deterministically — like `terraform` for Excel.

```
xl wb inspect -f budget.xlsx          # discover structure
xl plan add-column -f budget.xlsx \   # generate a plan (non-mutating)
   -t Sales -n Margin \
   --formula "=[@Revenue]-[@Cost]" \
   --out plan.json
xl validate plan -f budget.xlsx \     # check before applying
   --plan plan.json
xl apply -f budget.xlsx \             # preview changes
   --plan plan.json --dry-run
xl apply -f budget.xlsx \             # apply with safety backup
   --plan plan.json --backup
xl verify assert -f budget.xlsx \     # confirm expected state
   --assertions '[{"type":"table.column_exists","table":"Sales","column":"Margin"}]'
```

Every command returns a structured **JSON envelope** — no parsing of human-readable text required:

```json
{
  "ok": true,
  "command": "table.ls",
  "result": [...],
  "errors": [],
  "warnings": [],
  "metrics": { "duration_ms": 42 }
}
```

---

## Features

- **Inspect** — discover sheets, tables, named ranges, fingerprints, and lock status
- **Read** — get cell values, range statistics (min/max/mean/sum/count/stddev), search formulas
- **Query** — SQL over table data via DuckDB (`SELECT Region, SUM(Sales) FROM Sales GROUP BY Region`)
- **Mutate** — add columns, append rows, set cells/formulas, apply number formats, set column widths, freeze panes
- **Patch plans** — generate JSON plans, compose multi-step plans, validate before applying
- **Apply** — execute plans with `--dry-run` preview and `--backup` safety copy
- **Verify** — post-apply assertions (`table.column_exists`, `cell.value_equals`, `row_count.gte`, etc.)
- **Diff** — cell-level comparison between two workbook files
- **Lint** — detect volatile functions, broken references, and formula anti-patterns
- **Workflows** — multi-step YAML pipelines with `xl run`
- **Server mode** — stdio JSON server for agent tool integration (MCP/ACP)

## Safety rails

All mutating commands include built-in protections:

| Feature | Description |
|---|---|
| `--dry-run` | Preview every change without writing to disk |
| `--backup` | Timestamped `.bak` copy before any write |
| Fingerprint conflict detection | Plans record the file's xxhash; apply rejects if the workbook changed since the plan was created |
| Formula protection | Refuses to overwrite existing formulas unless `--force-overwrite-formulas` is explicitly set |
| Policy files | Optional `xl-policy.yaml` to restrict protected sheets, ranges, and mutation thresholds |

---

## Installation

Requires **Python 3.12+** and [uv](https://docs.astral.sh/uv/).

### Local repo install (development)

```bash
# Clone and install
git clone https://github.com/ThomasRohde/xl-cli.git
cd xl-cli
uv sync

# Verify
uv run xl version
uv run xl --help
```

No Excel installation required — works entirely with openpyxl.

### Global install on your PC

Install `xl` as a global user tool so you can run it from any folder:

```bash
# Clone once, then install globally from this repo
git clone https://github.com/ThomasRohde/xl-cli.git
cd xl-cli
uv tool install --from . xl-agent-cli

# Verify
xl version
xl --help
```

If `xl` is not found right away, open a new terminal so your PATH refreshes.

---

## Quick start

### 1. Inspect a workbook

```bash
xl wb inspect -f data.xlsx
```

Returns sheets, tables (with columns and row counts), named ranges, and a fingerprint hash.

### 2. List tables

```bash
xl table ls -f data.xlsx
```

### 3. Query with SQL

```bash
xl query -f data.xlsx \
  --sql "SELECT Region, SUM(Revenue) as Total FROM Sales GROUP BY Region ORDER BY Total DESC"
```

### 4. Add a calculated column (safe workflow)

```bash
# Generate a plan (does NOT modify the workbook)
xl plan add-column -f data.xlsx -t Sales -n GrossMarginPct \
  --formula "=[@GrossMargin]/[@Revenue]" \
  --out plan.json

# Validate the plan
xl validate plan -f data.xlsx --plan plan.json

# Preview what would change
xl apply -f data.xlsx --plan plan.json --dry-run

# Apply for real with backup
xl apply -f data.xlsx --plan plan.json --backup

# Verify the result
xl verify assert -f data.xlsx \
  --assertions '[{"type":"table.column_exists","table":"Sales","column":"GrossMarginPct"}]'
```

### 5. Format a report

```bash
xl format number -f report.xlsx --ref "Sales[Revenue]" --style currency --decimals 2
xl format width -f report.xlsx --sheet Sheet1 --columns A,B,C,D --width 15
xl format freeze -f report.xlsx --sheet Sheet1 --ref B2
```

### 6. Compare before and after

```bash
xl diff compare --file-a original.xlsx --file-b modified.xlsx
```

---

## Command reference

| Group | Commands | Description |
|---|---|---|
| `xl wb` | `inspect`, `lock-status` | Workbook metadata, fingerprint, lock status |
| `xl sheet` | `ls` | List sheets with dimensions |
| `xl table` | `ls`, `add-column`, `append-rows` | Table operations |
| `xl cell` | `get`, `set` | Read/write individual cells |
| `xl range` | `stat`, `clear` | Range statistics and clearing |
| `xl formula` | `set`, `lint`, `find` | Set formulas, lint for issues, search by regex |
| `xl format` | `number`, `width`, `freeze` | Number formats, column widths, freeze panes |
| `xl query` | _(top-level)_ | SQL queries over table data via DuckDB |
| `xl plan` | `show`, `add-column`, `set-cells`, `format`, `compose` | Generate and compose patch plans |
| `xl validate` | `workbook`, `plan`, `refs` | Validate health, plans, and references |
| `xl apply` | _(top-level)_ | Apply patch plans with `--dry-run` and `--backup` |
| `xl verify` | `assert` | Post-apply assertions |
| `xl diff` | `compare` | Cell-level workbook comparison |
| `xl run` | _(top-level)_ | Execute multi-step YAML workflows |
| `xl serve` | _(top-level)_ | stdio server for agent tool integration |
| `xl guide` | _(top-level)_ | Machine-readable JSON orientation guide |

Use `xl <group> --help` or `xl <group> <command> --help` for detailed usage with examples.

---

## Reference syntax

Commands that target cells, ranges, or table columns use **ref syntax**:

| Pattern | Example | Usage |
|---|---|---|
| `SheetName!Cell` | `Sheet1!B2` | Single cell |
| `SheetName!Start:End` | `Sheet1!A1:D10` | Cell range |
| `TableName[ColumnName]` | `Sales[Revenue]` | Table column (formula/format) |
| `=[@ColumnName]` | `=[@Revenue]-[@Cost]` | Structured ref inside table formulas |

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `10` | Validation error (bad input, schema mismatch, invalid plan) |
| `20` | Protection error (protected range or sheet) |
| `30` | Formula error (overwrite blocked, parse failure) |
| `40` | Conflict (fingerprint mismatch — workbook changed) |
| `50` | IO error (file not found, locked, permission denied) |
| `90` | Internal error |

---

## Agent integration

`xl` is designed to be driven by AI coding agents. Every command returns machine-parseable JSON, uses deterministic exit codes, and provides progressive discovery:

```bash
xl guide                        # Full structured JSON orientation (start here)
xl --help                       # Command group overview
xl table --help                 # Group detail with examples
xl table add-column --help      # Command detail with usage examples
```

The `xl guide` command returns a comprehensive JSON document covering all commands, workflows, ref syntax, error codes, safety features, and complete multi-step examples — ideal for agent onboarding.

### stdio server mode

For tool-use integrations (MCP, ACP, or custom):

```bash
xl serve --stdio
```

Reads JSON commands from stdin, writes JSON responses to stdout.

---

## Development

```bash
# Install with dev dependencies
uv sync

# Run all tests (158 tests)
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_cli.py -v

# Run the CLI directly
uv run xl --help
```

### Tech stack

| Component | Library |
|---|---|
| Excel engine | [openpyxl](https://openpyxl.readthedocs.io/) |
| CLI framework | [Typer](https://typer.tiangolo.com/) |
| Data models | [Pydantic v2](https://docs.pydantic.dev/) |
| JSON serialization | [orjson](https://github.com/ijl/orjson) |
| SQL queries | [DuckDB](https://duckdb.org/) |
| File locking | [portalocker](https://github.com/WoLpH/portalocker) |
| Fingerprinting | [xxhash](https://github.com/ifduyue/python-xxhash) |
| Build | [hatchling](https://hatch.pypa.io/) |

### Project structure

```
src/xl/
├── cli.py                  # Typer CLI app, all command definitions
├── contracts/              # Pydantic models (ResponseEnvelope, PatchPlan, etc.)
├── engine/                 # WorkbookContext, response dispatcher
├── adapters/               # openpyxl engine, DuckDB queries, recalc adapters
├── validation/             # Plan and workbook validators
├── io/                     # Fingerprint, backup, atomic write, file locking
├── observe/                # Timer and event utilities
├── diff/                   # Workbook comparison logic
└── server/                 # stdio/HTTP server mode

tests/                      # 158 tests: unit, integration, golden, property, performance
```

---

## License

MIT
