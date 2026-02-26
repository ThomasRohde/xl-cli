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

Every command returns a structured **JSON envelope**:

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

No Excel installation required — works entirely with openpyxl.

---

## Features

- **Inspect** — sheets, tables, named ranges, fingerprints, lock status
- **Read** — cell values, range statistics (min/max/mean/sum/count/stddev), formula search by regex
- **Query** — SQL over table data via DuckDB (`SELECT Region, SUM(Sales) FROM Sales GROUP BY Region`)
- **Mutate** — add/delete columns, append rows, set cells/formulas, number formats, column widths, freeze panes
- **Patch plans** — generate JSON plans, compose multi-step plans, validate before applying
- **Apply** — execute plans with `--dry-run` preview and `--backup` safety copy
- **Verify** — post-apply assertions (`table.column_exists`, `cell.value_equals`, `row_count.gte`, ...)
- **Diff** — cell-level comparison between two workbook files
- **Lint** — detect volatile functions, broken references, formula anti-patterns
- **Workflows** — multi-step YAML pipelines with `xl run`
- **Server mode** — stdio JSON server for agent tool integration (MCP/ACP)

## Safety rails

All mutating commands include built-in protections:

| Feature | Description |
|---|---|
| `--dry-run` | Preview every change without writing to disk |
| `--backup` | Timestamped `.bak` copy before any write |
| Fingerprint conflict detection | Plans record the file's xxhash; apply rejects if the workbook changed since the plan was created |
| Exclusive file locking | Sidecar `.xl.lock` prevents concurrent mutations; `--wait-lock N` retries for N seconds |
| Formula protection | Refuses to overwrite existing formulas unless `--force-overwrite-formulas` is set |
| Policy files | Optional `xl-policy.yaml` for protected sheets, ranges, mutation thresholds, and command restrictions |

---

## Installation

Requires **Python 3.12+** and [uv](https://docs.astral.sh/uv/).

### From PyPI (recommended)

```bash
uv tool install xl-cli

# Verify
xl version
xl --help
```

### Local development install

```bash
git clone https://github.com/ThomasRohde/xl-cli.git
cd xl-cli
uv sync

# Verify
uv run xl version
uv run xl --help
```

### Global install from source

```bash
git clone https://github.com/ThomasRohde/xl-cli.git
cd xl-cli
uv tool install --from . xl-agent-cli
```

If `xl` is not found, open a new terminal so your PATH refreshes.

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
| `xl wb` | `inspect`, `create`, `lock-status` | Workbook metadata, creation, fingerprint, lock check |
| `xl sheet` | `ls`, `create`, `delete`, `rename` | Sheet lifecycle and management |
| `xl table` | `create`, `ls`, `add-column`, `append-rows`, `delete`, `delete-column` | Table operations |
| `xl cell` | `get`, `set` | Read/write individual cells |
| `xl range` | `stat`, `clear` | Range statistics and clearing |
| `xl formula` | `set`, `lint`, `find` | Set formulas, lint for issues, search by regex |
| `xl format` | `number`, `width`, `freeze` | Number formats, column widths, freeze panes |
| `xl query` | _(top-level)_ | SQL queries over table data via DuckDB |
| `xl plan` | `show`, `add-column`, `create-table`, `set-cells`, `format`, `compose`, `delete-sheet`, `rename-sheet`, `delete-table`, `delete-column` | Generate and compose patch plans |
| `xl validate` | `workbook`, `plan`, `refs`, `workflow` | Validate health, plans, references, workflows |
| `xl apply` | _(top-level)_ | Apply patch plans with `--dry-run` and `--backup` |
| `xl verify` | `assert` | Post-apply assertions |
| `xl diff` | `compare` | Cell-level workbook comparison |
| `xl run` | _(top-level)_ | Execute multi-step YAML workflows |
| `xl serve` | _(top-level)_ | stdio server for agent tool integration |
| `xl guide` | _(top-level)_ | Machine-readable JSON orientation guide |

Use `xl <group> --help` or `xl <group> <command> --help` for detailed usage.

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
| `60` | Recalculation error |
| `70` | Unsupported operation |
| `90` | Internal error |

---

## Agent integration

`xl` is designed to be driven by AI coding agents. Every command returns machine-parseable JSON, uses deterministic exit codes, and provides progressive discovery:

```bash
xl guide                        # full structured JSON orientation (start here)
xl --help                       # command group overview
xl table --help                 # group detail with examples
xl table add-column --help      # command detail with usage examples
```

### Token-optimized help (TOON)

When an LLM drives the CLI, verbose Rich-formatted `--help` output wastes tokens. Set `LLM=true` to switch all help to **TOON** (Token-Oriented Object Notation) — a compact key:value format that cuts token usage by ~75%.

```bash
# Enable TOON for the session
export LLM=true          # bash/zsh
$env:LLM = "true"        # PowerShell

xl --help
```

```
name: xl
description: Agent-first CLI for reading transforming and validating Excel workbooks
options[2]:
  flag,type,required,default,help
  --version/-V,flag,false,false,Print version and exit.
  --human,flag,false,false,Force human-readable help (overrides LLM=true).
groups[11]:
  name,description
  cell,Read and write individual cell values.
  table,Table operations — list add columns append rows.
  ...
```

The `--human` flag overrides `LLM=true` for a single invocation:

```bash
xl --human --help         # Rich output even with LLM=true set
```

| Condition | Help format |
|---|---|
| Default (no env var) | Rich/Markdown (human-readable) |
| `LLM=true` | TOON (compact, token-optimized) |
| `LLM=true` + `--human` | Rich/Markdown (override) |

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

# Run all tests
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
| Terminal output | [Rich](https://github.com/Textualize/rich) |
| YAML parsing | [PyYAML](https://pyyaml.org/) |
| Structured logging | [structlog](https://www.structlog.org/) |
| File locking | [portalocker](https://github.com/WoLpH/portalocker) |
| Fingerprinting | [xxhash](https://github.com/ifduyue/python-xxhash) |
| Build | [hatchling](https://hatch.pypa.io/) |

### Project structure

```
src/xl/
├── cli.py                  # Typer CLI app, all command definitions
├── contracts/              # Pydantic models (ResponseEnvelope, PatchPlan, WorkflowSpec)
├── engine/                 # WorkbookContext, response dispatcher, verify, workflow runner
├── adapters/               # openpyxl engine, DuckDB queries
├── validation/             # Plan/workbook validators, policy engine
├── io/                     # Fingerprint, backup, atomic write, file locking
├── observe/                # Timer and event utilities
├── diff/                   # Workbook comparison logic
├── help/                   # TOON help output for LLM consumers
└── server/                 # stdio server mode

tests/                      # Unit, integration, golden, property, performance tests
```

---

## License

MIT
