# CLAUDE.md

## Project Overview

`xl` is an agent-first CLI for Excel workbooks (.xlsx/.xlsm). It provides a transactional spreadsheet execution layer with JSON outputs, patch plans, dry-run/validation, and safety rails. See `xl-agent-cli-prd.md` for the full PRD.

## Tech Stack

- **Python 3.12+** with `uv` for package management
- **openpyxl** — workbook read/write/inspect engine
- **Typer** — CLI framework
- **Pydantic v2** — data models and validation
- **orjson** — JSON serialization
- **DuckDB** — SQL query over table data
- **Build**: hatchling

## Repository Structure

```
src/xl/
├── cli.py                  # Typer CLI app, all command definitions
├── contracts/              # Pydantic models
│   ├── common.py           # ResponseEnvelope, Target, errors, warnings
│   ├── responses.py        # WorkbookMeta, SheetMeta, TableMeta, etc.
│   ├── plans.py            # PatchPlan, Operation, Precondition
│   └── workflow.py         # WorkflowSpec for xl run
├── engine/
│   ├── context.py          # WorkbookContext (load, fingerprint, metadata)
│   └── dispatcher.py       # Response envelope helpers, exit codes
├── adapters/
│   ├── openpyxl_engine.py  # Table mutations, cell ops, formatting
│   ├── query_duckdb.py     # (planned) DuckDB query adapter
│   └── recalc/             # Recalculation strategy adapters
├── validation/
│   └── validators.py       # Plan and workbook validation
├── io/
│   └── fileops.py          # Fingerprint, backup, atomic write, locking
├── observe/
│   └── events.py           # Timer utility
├── diff/                   # (planned) Workbook diff logic
└── server/                 # (planned) stdio/HTTP server mode
tests/
├── conftest.py             # Shared fixtures (simple_workbook, multi_table_workbook, sample_plan)
├── test_contracts.py
├── test_io.py
├── test_context.py
├── test_adapter.py
├── test_validation.py
└── test_cli.py             # CLI integration tests via Typer runner
```

## Common Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_cli.py -v

# Run the CLI
uv run xl --help
uv run xl wb inspect --file workbook.xlsx
uv run xl table ls --file workbook.xlsx
```

## Agent Discovery

To understand this CLI as a coding agent, use progressive discovery:

1. `uv run xl guide` — full machine-readable orientation (structured JSON with all commands, workflows, ref syntax, error codes, examples)
2. `uv run xl --help` — command group overview with workflow summary
3. `uv run xl <group> --help` — group detail with epilog examples (e.g. `uv run xl table --help`)
4. `uv run xl <group> <cmd> --help` — full command detail with usage examples and cross-references (e.g. `uv run xl table add-column --help`)

**Recommended starting workflow:** `xl wb inspect` → `xl table ls` → `xl plan ...` → `xl validate plan` → `xl apply --dry-run` → `xl apply --backup` → `xl verify assert`

## Key Conventions

- **Every command** returns a `ResponseEnvelope` JSON (see `contracts/common.py`)
- **openpyxl table access**: Use `ws._tables.values()` to get `Table` objects (not `ws.tables.items()` which returns `(name, ref_string)` pairs)
- **openpyxl defined names**: Use `wb.defined_names.values()` to iterate
- **Table columns** (`tbl.tableColumns`) are only populated after a save/reload roundtrip — test fixtures use `_save_and_reload()` in `conftest.py`
- Exit codes follow the taxonomy in PRD Section 19 (0=success, 10=validation, 40=conflict, 50=IO, 90=internal)
- Mutating commands support `--dry-run` and `--backup` flags
- The `--backup/--no-backup` flag pattern is used for boolean options with negation in Typer
