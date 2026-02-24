# Implementation Plan: `xl` Agent-First Excel CLI

## Overview

Implement the `xl` CLI as described in `xl-agent-cli-prd.md`. This is a Python-based, agent-first CLI for Excel workbooks using `openpyxl`, `Typer`, `Pydantic v2`, and supporting libraries. The plan follows the PRD's milestone structure, targeting the v1 slice outlined in Section 30.

---

## Phase 1: Foundation (Milestone 0)

### Step 1.1 — Project scaffolding
- Create `pyproject.toml` with hatchling build system, `uv` compatibility, Python 3.12+ requirement
- Define dependencies: `openpyxl`, `typer`, `pydantic>=2`, `orjson`, `rich`, `pyyaml`, `duckdb`, `portalocker`, `xxhash`, `structlog`
- Define dev dependencies: `pytest`, `pytest-xdist`, `hypothesis`
- Configure CLI entrypoint: `xl = "xl.cli:app"`
- Create `src/xl/__init__.py` with version

### Step 1.2 — Source package structure
Create the full module layout per PRD Section 27:
```
src/xl/
├── __init__.py
├── cli.py                  # Typer app + top-level command groups
├── contracts/
│   ├── __init__.py
│   ├── common.py           # ResponseEnvelope, Target, Warning, Error, Metrics, RecalcInfo
│   ├── responses.py        # Command-specific result models
│   ├── plans.py            # PatchPlan, Operation, Precondition, Postcondition
│   └── workflow.py         # WorkflowSpec, WorkflowStep
├── engine/
│   ├── __init__.py
│   ├── context.py          # WorkbookContext (load, fingerprint, metadata)
│   └── dispatcher.py       # Command dispatch + envelope wrapping
├── adapters/
│   ├── __init__.py
│   ├── openpyxl_engine.py  # All openpyxl workbook operations
│   ├── query_duckdb.py     # DuckDB SQL query adapter
│   └── recalc/
│       ├── __init__.py
│       └── base.py         # Recalc strategy interface + cached/none modes
├── validation/
│   ├── __init__.py
│   └── validators.py       # Reference, schema, protection, threshold validators
├── diff/
│   ├── __init__.py
│   └── differ.py           # Workbook/patch diff logic
├── io/
│   ├── __init__.py
│   └── fileops.py          # Locking, backup, fingerprint, atomic write
├── observe/
│   ├── __init__.py
│   └── events.py           # Structured logging, event emission, trace support
└── server/
    ├── __init__.py
    └── stdio.py            # stdio server mode
```

### Step 1.3 — Response envelope and error taxonomy
- Implement `ResponseEnvelope` Pydantic model (Section 11): `ok`, `command`, `target`, `result`, `changes`, `warnings`, `errors`, `metrics`, `recalc`
- Implement structured error codes and exit codes (Section 19)
- Create `output_response()` helper using `orjson` for JSON, with `--json`/`--ndjson` flag support
- Create `format_human()` helper using `rich` for default human-readable output

### Step 1.4 — CLI framework + global flags
- Set up Typer app in `cli.py` with command groups: `wb`, `sheet`, `table`, `range`, `cell`, `formula`, `format`, `query`, `validate`, `plan`, `apply`, `verify`, `diff`, `run`, `serve`, `version`
- Implement global options callback: `--file`, `--json`, `--ndjson`, `--yaml`, `--quiet`, `--trace`, `--cwd`, `--config`, `--recalc`, `--fail-on-warning`, `--timeout`

### Step 1.5 — Workbook context and fingerprinting
- Implement `WorkbookContext` in `engine/context.py`: loads workbook via openpyxl, computes SHA-256 fingerprint, extracts basic metadata
- Implement file fingerprinting in `io/fileops.py` using `hashlib` SHA-256

### Step 1.6 — `xl wb inspect`
- Return `WorkbookMeta` (Section 23): sheets (name, hidden state, dimensions), named ranges, external links presence, macros presence, calc mode, fingerprint
- JSON output via envelope

### Step 1.7 — `xl sheet ls`
- Return list of `SheetMeta`: name, index, visibility, used range estimate, table count
- JSON output via envelope

### Step 1.8 — `xl version`
- Return version string from package metadata

### Step 1.9 — Test infrastructure
- Create `tests/` directory with `conftest.py`
- Create `tests/fixtures/workbooks/` with sample `.xlsx` files (simple workbook with sheets, tables, named ranges)
- Write tests for `wb inspect` and `sheet ls` with golden output validation

---

## Phase 2: Table Operations + Patch Plans (Milestone 1)

### Step 2.1 — `xl table ls`
- List tables per Section 15: sheet, table name, range, columns (names/order), style, totals row presence
- Implement `TableMeta` model (Section 23)

### Step 2.2 — `xl table add-column`
- Add column to Excel table via openpyxl
- Support: static default value, formula, number format preset, insert position
- Generate change record

### Step 2.3 — `xl table append-rows`
- Append rows from inline JSON or JSON file
- Schema matching modes: strict (default), allow-missing-null, map-by-header
- Validate row payloads against table column schema

### Step 2.4 — Patch plan schema + `xl plan show`
- Implement `PatchPlan` Pydantic model (Section 13): schema_version, plan_id, target, options, preconditions, operations, postconditions
- Implement operation types: `table.add_column`, `table.append_rows`, `format.number`, `cell.set`, `range.clear`
- `xl plan show` reads and pretty-prints a plan JSON file

### Step 2.5 — Plan generators
- `xl plan add-column` — generates patch plan for adding a table column
- `xl plan set-cells` — generates patch plan for setting cell values
- `xl plan format` — generates patch plan for formatting
- `xl plan compose` — merges multiple plans
- All generators support `--append` to extend existing plan files

### Step 2.6 — `xl apply --dry-run` and `xl apply`
- Parse and validate plan JSON
- Check preconditions (sheet exists, table exists, etc.)
- Fingerprint conflict detection
- Dry-run mode: simulate changes, return projected change records without writing
- Apply mode: execute operations, create backup if `--backup`, atomic write
- Return change records in envelope

### Step 2.7 — Tests for table operations and patch lifecycle
- Test table ls, add-column, append-rows
- Test full plan lifecycle: generate → show → validate → dry-run → apply
- Golden output fixtures

---

## Phase 3: Validation and Safety (Milestone 2)

### Step 3.1 — Validation framework
- Implement validation categories (Section 16): reference, schema, protection, mutation thresholds, formula safety, concurrency/conflict, workbook hygiene
- `xl validate workbook` — validates workbook health
- `xl validate plan` — validates plan against workbook + policy
- `xl validate refs` — validates specific references

### Step 3.2 — Policy engine
- Load `xl-policy.yaml` configuration
- Support: protected sheets/ranges, mutation thresholds, allowed commands, logging redaction rules
- Integrate policy checks into apply/validate commands

### Step 3.3 — File safety: locking, backups, atomic writes
- `portalocker`-based file locking
- Lock status detection: `xl wb lock-status`
- Backup creation (timestamped `.bak` files)
- Atomic write: temp file → fsync → replace
- `--wait-lock` flag with timeout

### Step 3.4 — Fingerprint conflict detection
- Compare fingerprint at plan generation time vs apply time
- `--fail-on-external-change` flag (default true for plan apply)
- Structured error on mismatch: `ERR_PLAN_FINGERPRINT_CONFLICT`

### Step 3.5 — Tests for validation and safety
- Test formula overwrite blocked without force flag
- Test fingerprint conflict detection
- Test backup creation and atomic write
- Test policy enforcement

---

## Phase 4: Formula, Formatting, and Query (Milestone 3)

### Step 4.1 — `xl formula set`
- Set formulas for cell/range/table column
- Support A1 and R1C1 input modes
- Autofill behavior
- Overwrite safeguards: `--force-overwrite-values`, `--force-overwrite-formulas`

### Step 4.2 — `xl formula lint`
- Heuristic checks (no evaluation): volatile functions, broken refs, mixed formula patterns, suspicious hardcoded literals

### Step 4.3 — `xl formula find`
- Search workbook for formulas matching a pattern

### Step 4.4 — `xl format` commands
- Number format presets
- Column width setting
- Style presets
- Freeze panes

### Step 4.5 — `xl query` via DuckDB
- Extract table data from workbook into DuckDB in-memory database
- Support `--sql` for raw SQL queries
- Support `--table`, `--where`, `--select` for structured queries
- Return results via JSON envelope

### Step 4.6 — `xl cell` and `xl range` commands
- `xl cell set` — set cell value/formula with type coercion
- `xl cell get` — read cell value
- `xl range stat` — statistics for a range
- `xl range clear` — clear range contents/formats

### Step 4.7 — `xl verify` post-apply assertions
- Assert conditions after apply: column exists, value equals, row count, etc.

### Step 4.8 — `xl diff` workbook comparison
- Compare two workbook states or a workbook vs a plan's expected outcome
- Output structured diff

### Step 4.9 — Tests for formula, formatting, query
- Test formula set with overwrite guards
- Test formula lint detection
- Test DuckDB query results
- Test formatting operations
- Test cell/range operations

---

## Phase 5: Workflows + Observability (Milestone 4)

### Step 5.1 — `xl run` workflow execution
- Parse YAML workflow spec (Section 14)
- Execute steps sequentially with step references (`from_step`)
- Support defaults (output format, recalc mode, dry_run)
- Collect and return combined results

### Step 5.2 — Event stream and observability
- `--emit-events` flag for NDJSON event stream (Section 20)
- Lifecycle events: workbook_opened, tables_detected, plan_validated, patch_applied, etc.
- Metrics collection: rows/cells/formulas/sheets touched, duration, warnings/errors count

### Step 5.3 — Trace mode
- `--trace` writes structured trace JSON file
- Contains: command args (sanitized), references, fingerprints, validation report, operations, timing

### Step 5.4 — `xl serve --stdio` machine server mode
- JSON-RPC or line-delimited JSON protocol over stdin/stdout
- Reuses same engine as CLI commands
- Session management with persistent workbook context

### Step 5.5 — Tests for workflows and observability
- Test YAML workflow execution end-to-end
- Test event stream output
- Test trace file generation

---

## Phase 6: Hardening (Milestone 5)

### Step 6.1 — Golden workbook fixtures
- Create comprehensive test workbooks covering edge cases
- Snapshot-based golden output tests

### Step 6.2 — Property-based tests
- Use `hypothesis` for patch/apply semantics
- Fuzz test plan generation and application

### Step 6.3 — Performance testing
- Test with large workbooks (10K+ rows)
- Optimize read-only mode usage where possible

### Step 6.4 — Cross-platform verification
- Verify core operations work on Linux (primary dev), macOS, Windows
- Test file locking behavior across platforms

---

## Implementation Notes

- **Develop on branch**: `claude/implement-prd-92M8L`
- **Python version**: 3.12+
- **Package manager**: `uv`
- **Build system**: `hatchling`
- **All commands** return the standard `ResponseEnvelope` JSON
- **Exit codes** follow the taxonomy in Section 19
- **Testing**: pytest with fixtures, golden outputs, and property-based tests

## Scope for This Session

Given the scale of the PRD, this implementation session will focus on **Phase 1 (Foundation)** and **Phase 2 (Table Operations + Patch Plans)** — getting the core scaffolding, response contract, basic inspection commands, table operations, and the patch plan lifecycle working end-to-end. This provides a functional, testable CLI that demonstrates the core agent-first workflow: `inspect → plan → validate → dry-run → apply → verify`.
