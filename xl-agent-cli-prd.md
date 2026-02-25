# PRD — `xl` Agent-First Excel CLI
Version: 1.0 (Developer-ready PRD)  
Date: 2026-02-24  
Author: ChatGPT (for Thomas)  
Status: **v1 Hardened** (all milestones 0–5 delivered)

## 1) Product summary

Build an **agent-first CLI for Excel workbooks** (`.xlsx` / `.xlsm`) that lets AI agents and humans inspect, plan, validate, and apply spreadsheet changes **deterministically**.

This is not a “macro recorder.” It is a **transactional spreadsheet execution layer** with:
- stable JSON outputs
- patch plans (diffs) as first-class artifacts
- dry-run and validation everywhere
- safety rails for governed environments
- optional server mode (`stdio` / HTTP) reusing the same execution engine

Primary use cases:
- AI agents updating models and reporting sheets safely
- Data and finance teams automating repetitive workbook maintenance
- Enterprise workflows requiring auditability and deterministic execution

---

## 2) Problem statement

Excel is still the execution surface for analysis, reporting, reconciliations, and operational work. AI agents can help, but direct cell-level manipulation is fragile:

- hidden sheets and formulas cause accidental breakage
- file locks and external edits create overwrite risks
- non-deterministic CLI output makes agent loops brittle
- lack of patch/diff abstractions prevents review/approval workflows

We need a CLI that behaves more like:
- `git` (diff/patch/apply/review)
- `jq` / `sql` (structured querying)
- `terraform` (plan before apply)

---

## 3) Product goals

### Primary goals (v1)
1. **Deterministic agent interface**
   - JSON output envelope for all commands
   - stable IDs/handles for sheets, tables, ranges, and named ranges

2. **Safe mutation workflow**
   - `inspect -> plan -> validate -> apply --dry-run -> apply -> verify`

3. **Table-first Excel UX**
   - promote Excel Tables and named ranges over raw coordinates

4. **Governance & auditability**
   - patch files, validation reports, operation traces, and file fingerprints

5. **Cross-platform local CLI**
   - Windows/macOS/Linux for `.xlsx/.xlsm` manipulation (no Excel install required for core ops)

### Non-goals (v1)
- Full Excel formula calculation engine parity
- VBA execution or macro authoring
- Perfect preservation/editing of all embedded objects (especially complex charts/pivots)
- `.xls` binary workbook support
- Live collaboration with open cloud workbooks (Graph API integration is v2+)

---

## 4) Key design principles (agent-first)

- **JSON-first, prose optional**
- **Dry-run by default for mutating workflows**
- **Patch plans are first-class**
- **Idempotent semantics where possible**
- **Explicit recalculation strategy**
- **Validation before mutation**
- **Structured error codes + exit codes**
- **Observable execution (events/metrics/traces)**

---

## 5) Why this tech stack (library selection)

## Decision: Python + `openpyxl` as the primary Excel engine

### Why `openpyxl` is the best fit for this product
`openpyxl` is the best primary library for this CLI because v1 needs to **read, inspect, and modify existing workbooks**, not just generate new ones. It supports the Office Open XML Excel formats (`.xlsx/.xlsm/...`) and is mature/stable in Python. It also supports read-only/write-only optimized modes and has built-in APIs for tables and chart objects (enough for introspection and selective creation in later phases).

### Why not `XlsxWriter` as the primary engine
`XlsxWriter` is excellent for **generating** new Excel files, and its docs explicitly note strong feature coverage and performance. However, it also explicitly states it **cannot read or modify existing XLSX files**. That disqualifies it as the primary engine for an agentic “inspect/plan/apply” CLI over existing workbooks.

### Why not `ExcelJS` as the primary engine
`ExcelJS` is good for JS/TS ecosystems and supports reading/writing data and styles, but chart support remains a long-standing area of limitation/ambiguity (e.g., open chart support issue and chart-loss issues on rewrite). For an enterprise-safe CLI that must preserve workbook fidelity, this creates risk in v1.

### Why not `EPPlus` as the primary default
`EPPlus` is powerful, but from v5 onward it uses a **Polyform Noncommercial / commercial dual licensing model**. For a broadly usable OSS-friendly CLI (and especially enterprise adoption without licensing friction during evaluation), this is a material constraint.

### Important caveat with `openpyxl` (design implication)
`openpyxl` does **not** recalculate Excel formulas; it can read formula text or the **cached value last stored by Excel** (`data_only=True`). Therefore, the CLI must treat recalculation as an explicit strategy (cached values, Excel desktop adapter, or best-effort external adapter).

---

## 6) Recommended v1 tech stack (developer-ready)

### Core runtime
- **Python 3.12+**
- Package/env: **uv**
- Build/publish: **hatchling**
- CLI entrypoint: `xl`

### Core libraries
- **openpyxl** — primary workbook read/write/inspect/mutate engine
- **Typer** — CLI command framework (excellent DX, type hints)
- **Pydantic v2** — command input/output models, patch schemas, validation reports
- **orjson** — fast deterministic JSON serialization
- **rich** (optional human mode) — readable tables/logs while preserving `--json` machine mode
- **PyYAML** — workflow spec (`xl run workflow.yaml`)
- **DuckDB** (recommended) — SQL query over extracted table data for `xl query`
- **portalocker** — cross-platform file locking
- **xxhash** or `hashlib` — workbook fingerprinting
- **structlog** (or standard logging + JSON formatter) — structured logs/events

### Optional adapters (v1 optional / v2)
- **pywin32** (Windows only) — Excel desktop recalc adapter (if Excel installed)
- **LibreOffice/UNO adapter** — best-effort recalc/export adapter (optional, experimental)
- **FastAPI** — HTTP server mode for remote orchestration (optional)
- **OpenTelemetry SDK** — traces/metrics for enterprise observability (optional)

### Testing
- **pytest**
- **pytest-xdist** (parallel)
- **hypothesis** (property-based tests for patch/apply semantics)
- Golden workbook fixtures + snapshot JSON outputs

---

## 7) Product scope (v1)

### v1 must-have capabilities
1. Workbook / sheet / table inspection
2. Table-first mutations (add/rename columns, append rows, update rows)
3. Low-level cell/range mutations (escape hatch)
4. Formula set/autofill/lint (no formula evaluation guarantee)
5. Basic formatting (number format, width, style presets, freeze panes)
6. Patch plan generation / merge / preview / apply
7. Validation (schema, references, protected ranges, thresholds)
8. File fingerprint + conflict detection
9. JSON/NDJSON outputs + structured exit codes
10. Workflow execution (`xl run workflow.yaml`)
11. Optional `stdio` machine-server mode sharing same execution engine

### v1 deferred (explicitly out of scope unless trivial)
- Pivot creation/editing
- Robust existing chart editing/preservation guarantees
- Macro/VBA editing
- External link update resolution
- Cloud workbook APIs (Microsoft Graph Excel)
- Real-time collaboration / workbook merge

---

## 8) Users and core workflows

### Primary users
- **AI coding/ops agents** (non-interactive, deterministic)
- **Power users / analysts** (human-in-the-loop review/apply)
- **Platform teams** (automation pipelines, governance)
- **Enterprise architects / controls teams** (auditability and change controls)

### Golden path workflow
1. `inspect` workbook and detect tables/named ranges
2. `plan` a patch (or multiple patches)
3. `validate` patch against workbook + rules
4. `apply --dry-run`
5. review diff / warnings
6. `apply`
7. `verify` expected outcomes
8. export summary/audit log artifact

---

## 9) CLI UX (v1 command surface)

Keep top-level verbs compact. Subcommands should map cleanly to execution primitives.

### Top-level commands
- `xl wb` — workbook operations
- `xl sheet` — sheet operations
- `xl table` — table inspection/mutations (preferred)
- `xl range` — range inspection/mutations
- `xl cell` — precise cell operations
- `xl formula` — formula authoring/lint/trace-lite
- `xl format` — formatting primitives/presets
- `xl query` — SQL-like table querying
- `xl validate` — workbook and patch validations
- `xl plan` — generate/show/merge patch plans
- `xl apply` — apply patch plans transactionally
- `xl verify` — post-apply assertions
- `xl diff` — compare workbook states / patches
- `xl run` — execute YAML workflow
- `xl serve` — `stdio`/HTTP machine server mode
- `xl version`

### Global flags (all commands)
- `--file PATH`
- `--json` / `--ndjson` / `--yaml`
- `--quiet`
- `--trace`
- `--cwd PATH`
- `--config PATH`
- `--recalc [none|cached|excel|libreoffice]`
- `--fail-on-warning`
- `--timeout SECONDS`

---

## 10) Example commands (agent-optimized)

### Inspect
```bash
xl wb inspect --file budget.xlsx --json
xl sheet ls --file budget.xlsx --json
xl table ls --file budget.xlsx --sheet Revenue --json
xl range stat --file budget.xlsx --ref Revenue!A1:F500 --json
xl formula find --file budget.xlsx --pattern "VLOOKUP" --json
```

### Query
```bash
xl query --file budget.xlsx --sql "select Region, sum(Sales) as Sales from Sales group by Region" --json
xl query --file budget.xlsx --table Sales --where "Date >= '2026-01-01'" --select Region,Amount --json
```

### Plan and apply
```bash
xl plan add-column --file budget.xlsx --table Sales --name GrossMarginPct --formula "=[@GrossMargin]/[@Revenue]" --json > plan.json
xl plan format --file budget.xlsx --ref Sales[GrossMarginPct] --percent 2 --append plan.json
xl plan show --plan plan.json --json
xl validate plan --file budget.xlsx --plan plan.json --json
xl apply --file budget.xlsx --plan plan.json --dry-run --json
xl apply --file budget.xlsx --plan plan.json --backup --json
```

### Low-level escape hatch
```bash
xl cell set --file inputs.xlsx --ref Inputs!B2 --value 0.12 --type number --json
xl range clear --file model.xlsx --ref Temp!A:Z --contents --json
```

---

## 11) Output contract (mandatory for all commands)

Every command returns the same top-level envelope to make agent parsing easy.

### Standard response envelope (JSON)
```json
{
  "ok": true,
  "command": "table.ls",
  "target": {
    "file": "budget.xlsx",
    "sheet": "Revenue"
  },
  "result": {},
  "changes": [],
  "warnings": [],
  "errors": [],
  "metrics": {
    "duration_ms": 42
  },
  "recalc": {
    "mode": "cached",
    "performed": false
  }
}
```

### Rules
- `ok=false` on any command failure
- `warnings[]` always structured (code/message/path)
- `errors[]` always structured (code/message/details)
- `changes[]` present for mutating commands (or dry-run projections)
- `result` is command-specific payload
- `metrics.duration_ms` always present

---

## 12) Stable identifiers and references

### Canonical reference forms
- Sheet ref: `sheet:Revenue`
- Table ref: `table:Sales`
- Named range: `name:InputRate`
- A1 range: `Revenue!A1:F500`
- Table column: `Sales[GrossMarginPct]`
- Cell handle (normalized): `cell:Revenue!B12`

### Internal IDs (generated)
The CLI should generate stable IDs for workbook objects (when possible), e.g.:
- `sheet_id`
- `table_id`
- `name_id`

These improve diffing and reduce ambiguity after renames.

---

## 13) Patch plan model (core abstraction)

Patch plans are JSON documents that describe intended changes without immediately applying them.

### Patch plan goals
- human reviewable
- machine mergeable
- deterministic apply ordering
- explicit preconditions
- reversible where possible

### Patch plan skeleton
```json
{
  "schema_version": "1.0",
  "plan_id": "pln_20260224_abc123",
  "target": {
    "file": "budget.xlsx",
    "fingerprint": "sha256:..."
  },
  "options": {
    "recalc_mode": "cached",
    "backup": true,
    "fail_on_external_change": true
  },
  "preconditions": [
    {"type": "sheet_exists", "sheet": "Revenue"},
    {"type": "table_exists", "table": "Sales"}
  ],
  "operations": [
    {
      "op_id": "op1",
      "type": "table.add_column",
      "table": "Sales",
      "name": "GrossMarginPct",
      "formula": "=[@GrossMargin]/[@Revenue]"
    },
    {
      "op_id": "op2",
      "type": "format.number",
      "ref": "Sales[GrossMarginPct]",
      "style": "percent",
      "decimals": 2
    }
  ],
  "postconditions": [
    {"type": "column_exists", "table": "Sales", "column": "GrossMarginPct"}
  ]
}
```

---

## 14) Workflow spec (`xl run`) for agent-generated automation

YAML workflows bundle multi-step operations with assertions.

### Example `workflow.xl.yaml`
```yaml
schema_version: "1.0"
name: "add-gross-margin-column"
target:
  file: "budget.xlsx"

defaults:
  output: json
  recalc: cached
  dry_run: false

steps:
  - id: inspect_tables
    run: table.ls
    args:
      sheet: "Revenue"

  - id: plan_changes
    run: plan.compose
    args:
      operations:
        - type: table.add_column
          table: "Sales"
          name: "GrossMarginPct"
          formula: "=[@GrossMargin]/[@Revenue]"
        - type: format.number
          ref: "Sales[GrossMarginPct]"
          style: percent
          decimals: 2

  - id: validate_plan
    run: validate.plan
    args:
      from_step: plan_changes

  - id: apply_plan
    run: apply.plan
    args:
      from_step: plan_changes
      backup: true

  - id: verify_col
    run: verify.assert
    args:
      assertions:
        - type: table.column_exists
          table: "Sales"
          column: "GrossMarginPct"
```

---

## 15) Command-level spec (v1 minimum)

## `xl wb`
### `xl wb inspect`
Returns workbook metadata:
- sheets (name, hidden state, dimensions if known)
- named ranges
- external links presence
- macros presence (flag only)
- calc mode metadata if accessible
- workbook fingerprint

## `xl sheet`
### `xl sheet ls`
List sheets with:
- name
- index
- visible/hidden/veryHidden (if detectable)
- used range estimate
- table count

## `xl table`
### `xl table create`
Creates an Excel Table (ListObject) from a cell range; supports:
- `--sheet` / `-s` — target sheet (required)
- `--table` / `-t` — display name for the table (required)
- `--ref` — cell range to promote (e.g. `A1:D5`) (required)
- `--columns` — comma-separated column headers (written if header row is empty)
- `--style` — table style name (default: `TableStyleMedium2`)
- `--dry-run`, `--backup` — standard safety flags

Validates: table name uniqueness, range overlap with existing tables, header row presence.

### `xl table ls`
Lists tables with:
- sheet
- table name
- range
- columns (names/order)
- style
- totals row presence

### `xl table add-column`
Adds a new column to a table; supports:
- static default value
- formula
- number format preset
- insert position (append/default)

### `xl table append-rows`
Append rows from:
- inline JSON
- JSON file
- CSV file (optional in v1.1)

Schema matching modes:
- strict (default)
- allow-missing-null
- map-by-header

## `xl formula`
### `xl formula set`
Set formulas for cell/range/table column.
Supports:
- A1 and R1C1 input modes
- autofill behavior
- overwrite safeguards (`--force-overwrite-values`, `--force-overwrite-formulas`)

### `xl formula lint`
Heuristic checks (no evaluation):
- volatile functions (`OFFSET`, `INDIRECT`, etc.)
- broken refs (`#REF!`) where present
- mixed formula patterns in adjacent ranges
- suspicious hardcoded literals in formula regions

## `xl plan`
### `xl plan ...`
Plan generators should emit valid patch JSON and optionally append/merge to existing plan:
- `add-column`
- `set-cells`
- `format`
- `rename-column`
- `compose`

## `xl apply`
### `xl apply`
Applies a plan with:
- precondition checks
- fingerprint conflict detection
- dry-run preview
- backup creation
- optional recalc adapter invocation
- postcondition verification

---

## 16) Validation model

Validation must be first-class because agents will make mistakes.

### Validation categories
1. **Reference validation**
   - missing sheet/range/table/name
2. **Schema validation**
   - row payload keys mismatch
3. **Protection validation**
   - protected sheet/range detected
4. **Mutation thresholds**
   - exceeds allowed cells/rows/columns touched
5. **Formula safety checks**
   - overwrite formulas without explicit force
6. **Concurrency/conflict checks**
   - file fingerprint changed since plan generated
7. **Workbook hygiene warnings**
   - external links
   - hidden sheets touched
   - macros present
   - unsupported object types detected

### Validation command examples
```bash
xl validate workbook --file budget.xlsx --json
xl validate plan --file budget.xlsx --plan plan.json --json
xl validate refs --file budget.xlsx --ref "Revenue!A1:D10" --json
```

---

## 17) Recalculation strategy (explicitly modeled)

### Why this exists
The CLI cannot assume a built-in Excel calculation engine. Recalculation must be explicit.

### Modes
- `none` — do not recalc; preserve formulas; rely on downstream Excel
- `cached` — read/write and inspect cached values if present
- `excel` — use Windows Excel desktop adapter (optional, if installed)
- `libreoffice` — experimental adapter (best effort; not parity-guaranteed)

### v1 product behavior
- Default: `cached`
- Any command that returns computed outputs must indicate recalc mode and whether values are cached vs freshly computed.
- Validation warns if postconditions depend on computed formulas but recalc mode is `none/cached`.

---

## 18) Conflict detection, locking, and transactional behavior

### File safety requirements
- open file lock detection (best-effort cross-platform)
- fingerprint check before apply
- optional `--fail-on-external-change` (default true for plan apply)
- backup on apply (`.bak` timestamped file)
- atomic write strategy:
  1. write temp workbook
  2. fsync where possible
  3. replace target
  4. retain backup if requested

### Commands
```bash
xl wb lock-status --file budget.xlsx --json
xl apply --file budget.xlsx --plan plan.json --wait-lock 10s --json
```

---

## 19) Error taxonomy and exit codes (agent critical)

### Exit codes
- `0` success
- `10` validation error
- `20` protection/permission error
- `30` formula parse/lint error
- `40` conflict/fingerprint mismatch
- `50` IO/lock error
- `60` recalc adapter error / timeout
- `70` unsupported workbook feature
- `90` internal error

### Structured error codes (examples)
- `ERR_WORKBOOK_NOT_FOUND`
- `ERR_SHEET_NOT_FOUND`
- `ERR_TABLE_NOT_FOUND`
- `ERR_RANGE_INVALID`
- `ERR_SCHEMA_MISMATCH`
- `ERR_PROTECTED_RANGE`
- `ERR_FORMULA_OVERWRITE_BLOCKED`
- `ERR_PLAN_FINGERPRINT_CONFLICT`
- `ERR_RECALC_ADAPTER_UNAVAILABLE`
- `ERR_UNSUPPORTED_OBJECT_PRESERVATION_RISK`

---

## 20) Observability (for agent loops and enterprise controls)

### Event stream (NDJSON)
Optional `--emit-events` streams lifecycle events:
- `workbook_opened`
- `workbook_scanned`
- `tables_detected`
- `plan_validated`
- `dry_run_completed`
- `patch_applied`
- `recalc_started`
- `recalc_finished`
- `workbook_saved`

### Metrics
- rows touched
- cells touched
- formulas changed
- sheets touched
- duration
- recalc duration
- warnings count
- errors count

### Trace mode
`--trace` writes a structured trace file (JSON) containing:
- command args (sanitized)
- normalized target references
- pre/post fingerprints
- validation report
- applied operations
- timing breakdown

---

## 21) Security and governance requirements (enterprise-friendly)

### Security baseline
- Never execute macros/VBA
- Macro presence detection and warnings
- External links detection and warnings
- Optional `defusedxml` hardening for XML parsing protection
- Path allowlist/denylist config for file operations
- Redaction of cell values in trace logs via policy (`mask_columns`, `mask_ranges`)
- Optional PII scan on export payloads (v1.1+)

### Governance features (v1/v1.1)
- `xl propose` mode (generate patch + human-readable summary)
- signed/approved plan apply hooks (v2)
- policy file (`xl-policy.yaml`) for:
  - protected sheets/ranges
  - mutation thresholds
  - allowed commands
  - logging redaction rules

---

## 22) Architecture (implementation design)

### High-level modules
- `xl.cli` — Typer app / command wiring
- `xl.contracts` — Pydantic models (requests/responses/plans)
- `xl.engine` — execution orchestrator (inspect/plan/apply/validate)
- `xl.adapters.openpyxl` — workbook CRUD + object mapping
- `xl.adapters.query` — table extraction + DuckDB SQL execution
- `xl.adapters.recalc` — `none/cached/excel/libreoffice`
- `xl.validation` — validators and policy engine
- `xl.diff` — workbook/patch diff logic
- `xl.io` — file locking, backups, fingerprinting, atomic write
- `xl.observe` — logs/events/metrics/tracing
- `xl.server` — stdio/HTTP mode (same engine)

### Internal execution pattern
1. Parse CLI args -> Pydantic request model
2. Normalize refs -> canonical handles
3. Load workbook context (read-only when possible)
4. Validate command and policy
5. Produce result or patch
6. If mutate:
   - generate change set
   - dry-run or apply
   - save atomically
7. Emit structured response envelope

---

## 23) Data model sketch (core objects)

### WorkbookMeta
- `path`
- `fingerprint`
- `sheets[]`
- `names[]`
- `has_macros`
- `has_external_links`
- `unsupported_objects[]`
- `warnings[]`

### TableMeta
- `table_id`
- `name`
- `sheet`
- `ref`
- `columns[]`
- `style`
- `totals_row`
- `row_count_estimate`

### ChangeRecord
- `op_id`
- `type`
- `target`
- `before` (optional summary)
- `after` (optional summary)
- `impact` (cells/rows/sheets touched)
- `warnings[]`

---

## 24) v1 acceptance criteria (must pass before release)

1. **Deterministic JSON contract**
   - Repeated identical inspect commands produce stable JSON ordering/shape.

2. **Patch lifecycle works**
   - Can generate -> validate -> dry-run -> apply a plan that adds a table column and formats it.

3. **Conflict protection**
   - Apply fails with explicit fingerprint conflict when workbook changes after plan generation.

4. **Validation safety**
   - Formula overwrite blocked by default unless force flag is provided.

5. **Table-first ops**
   - Append rows to table with strict schema validation.

6. **Observability**
   - `--trace` and `--emit-events ndjson` produce structured artifacts.

7. **Cross-platform core**
   - v1 commands work on Windows/macOS/Linux for core inspect/plan/apply without Excel installed.

8. **Non-destructive behavior**
   - Existing unsupported objects are detected and warned on; risky mutations can be blocked by policy.

---

## 25) Milestones (pragmatic implementation plan)

### Milestone 0 — Foundation ✅ COMPLETE
- [x] repo scaffold, uv/hatch, Typer app
- [x] response envelope + error taxonomy
- [x] basic `wb inspect`, `sheet ls`
- [x] `xl version`
- [x] IO utilities: SHA-256 fingerprinting, atomic write, backup, lock detection
- [x] Pydantic v2 contracts: ResponseEnvelope, Target, WorkbookMeta, SheetMeta, etc.
- [x] Exit code taxonomy (0/10/20/30/40/50/60/70/90)

### Milestone 1 — Table-first inspect/mutate ✅ COMPLETE
- [x] `table create`, `table ls`, `table add-column`, `table append-rows`
- [x] patch plan schema + `plan show`
- [x] `plan add-column`, `plan create-table`, `plan set-cells`, `plan format`, `plan compose`
- [x] `apply --dry-run` + `apply` with backup and fingerprint conflict detection
- [x] `cell set` with formula overwrite protection
- [x] `validate workbook` and `validate plan`
- [x] `query` via DuckDB table extraction
- [x] 49 tests passing (contracts, IO, context, adapter, validation, CLI integration)

### Milestone 2 — Validation and safety ✅ COMPLETE
- [x] policy file (`xl-policy.yaml` with protected sheets, mutation thresholds)
- [x] fingerprint conflict checks
- [x] backup + atomic write
- [x] thresholds/protected ranges
- [x] `validate refs`, `validate workbook`, `validate plan`
- [x] `wb lock-status`

### Milestone 3 — Formula + formatting + query ✅ COMPLETE
- [x] `formula set` (with overwrite guards), `formula lint` (volatile/broken ref detection), `formula find`
- [x] `format number`, `format width`, `format freeze` (freeze/unfreeze panes)
- [x] `query` via DuckDB extraction
- [x] `cell get`, `range stat`, `range clear`
- [x] `verify assert` (post-apply assertions: column exists, row count, cell value, etc.)
- [x] `diff compare` (cell-level workbook comparison)

### Milestone 4 — Workflows + observability ✅ COMPLETE
- [x] `xl run workflow.yaml` (YAML workflow execution with step sequencing)
- [x] `EventEmitter` — NDJSON lifecycle event stream to stderr
- [x] `TraceRecorder` — structured trace file generation
- [x] `serve --stdio` machine mode (JSON line-delimited server)

### Milestone 5 — Hardening ✅ COMPLETE
- [x] golden workbook fixtures (5 fixture workbooks + 32 snapshot tests)
- [x] fuzz/property tests (14 Hypothesis property-based tests covering envelope round-trip, plan models, fingerprint determinism, cell set/get, schema enforcement, dry-run safety)
- [x] performance tests on large workbooks (12 benchmarks: load, inspect, mutate, query, diff, lint — 1000+ row workbooks)
- [x] docs + examples for agents (`docs/agent-guide.md`, example plans, workflows, and policy file)
- [x] DuckDB query fix: removed pandas/numpy dependency from query path (use native fetchall)

---

## 26) Risks and mitigations

### Risk: Workbook fidelity loss (embedded objects/charts/pivots)
Mitigation:
- detect and classify unsupported/risky objects
- warn/block by policy
- scope chart/pivot editing out of v1
- preserve untouched parts where possible, with test fixtures

### Risk: Formula expectations vs no calc engine
Mitigation:
- explicit recalc mode in every response
- cached value semantics documented
- optional recalc adapters
- validation warnings when postconditions depend on recalculated values

### Risk: Agent misuse (mass destructive edits)
Mitigation:
- mutation thresholds
- dry-run default in workflows
- `--require-approval` mode (v1.1)
- strong exit codes and structured warnings

### Risk: File locks/concurrency
Mitigation:
- lock detection + retry/wait flags
- fingerprint conflict checks
- backups and atomic writes

---

## 27) Repo structure proposal (developer-ready)

```text
xl-agent-cli/
├─ pyproject.toml
├─ README.md
├─ src/
│  └─ xl/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ contracts/
│     │  ├─ common.py
│     │  ├─ responses.py
│     │  ├─ plans.py
│     │  └─ workflow.py
│     ├─ engine/
│     │  ├─ dispatcher.py
│     │  ├─ context.py
│     │  └─ operations/
│     ├─ adapters/
│     │  ├─ openpyxl_engine.py
│     │  ├─ query_duckdb.py
│     │  └─ recalc/
│     ├─ validation/
│     ├─ diff/
│     ├─ io/
│     ├─ observe/
│     └─ server/
├─ tests/
│  ├─ fixtures/
│  │  ├─ workbooks/
│  │  └─ plans/
│  ├─ golden/
│  └─ test_*.py
├─ docs/
│  ├─ cli/
│  ├─ schema/
│  └─ examples/
└─ examples/
   ├─ plans/
   └─ workflows/
```

---

## 28) Packaging and distribution

### Packaging
- `uv sync`
- `uv run xl ...`
- Build wheels via hatchling
- Publish to PyPI (optional)
- Optional single-file binaries via PyInstaller/Shiv/PEX in later phase

### Distribution strategy
- Start with Python package for fastest iteration
- Add `pipx` install docs
- Add Docker image for CI pipelines
- Add `xl serve --stdio` for agent tool integration (MCP/ACP wrappers can sit on top)

---

## 29) Future roadmap (v2+)

- chart creation helpers (`xl chart create`) with explicit preservation guarantees per type
- pivot support (creation + refresh metadata)
- Microsoft Graph Excel connector for cloud workbooks
- signed plan approvals / policy enforcement service
- richer formula tracing/dependency graph
- semantic workbook schema profiles (finance/risk/reporting)
- domain packs (`xl finance`, `xl risk`, `xl reconcile`)

---

## 30) Build decision summary (what to implement now)

**All v1 items below are implemented and tested (157 tests passing):**

1. ✅ `wb inspect`, `sheet ls`, `table ls`
2. ✅ `plan add-column`, `plan format`, `plan show`, `plan set-cells`, `plan compose`
3. ✅ `validate plan`, `validate workbook`, `validate refs`
4. ✅ `apply --dry-run` + `apply`
5. ✅ fingerprint conflict detection + backups
6. ✅ JSON envelope + exit codes
7. ✅ `table append-rows`
8. ✅ `formula set` + overwrite guards, `formula lint`, `formula find`
9. ✅ `query` (DuckDB)
10. ✅ `run workflow.yaml`

**Additionally delivered beyond the v1 slice:**
- ✅ `cell get`, `cell set` — read/write cell values with type detection
- ✅ `range stat`, `range clear` — range statistics and clearing
- ✅ `format number`, `format width`, `format freeze` — formatting commands
- ✅ `verify assert` — post-apply assertions (column exists, row count, cell value, etc.)
- ✅ `diff compare` — cell-level workbook comparison
- ✅ `wb lock-status` — file lock detection
- ✅ Policy engine (`xl-policy.yaml`) — protected sheets, mutation thresholds
- ✅ `EventEmitter` — NDJSON lifecycle event stream
- ✅ `TraceRecorder` — structured trace file generation
- ✅ `serve --stdio` — JSON line-delimited machine server mode

**Milestone 5 hardening deliverables:**
- ✅ Golden workbook fixtures (sales, multi-table, formulas, empty, hidden-sheets)
- ✅ Hypothesis property-based tests (envelope round-trip, fingerprint determinism, schema enforcement, dry-run invariants)
- ✅ Performance benchmarks (1000+ row workbooks for load, inspect, mutate, query, diff, lint)
- ✅ Agent integration guide (`docs/agent-guide.md`)
- ✅ Example plans, workflows, and policy files (`examples/`)
- ✅ DuckDB query bugfix: eliminated pandas/numpy dependency from query execution path

---

## 31) Reference notes (for implementation rationale)

This PRD’s library choice and constraints are grounded in the following publicly documented facts:
- `openpyxl` supports reading/writing Excel Open XML formats and is MIT licensed.
- `openpyxl` exposes `data_only` behavior as cached values last read by Excel, and has optimized read/write modes.
- `openpyxl` documents tables and chart APIs.
- `XlsxWriter` is strong for writing/generation and chart features, but explicitly cannot read/modify existing XLSX files.
- `ExcelJS` is capable for data/styles but chart support remains a long-standing open area/risk for fidelity.
- `EPPlus` uses a noncommercial/commercial licensing model from v5 onward.

(Use official docs/issues when converting this PRD into README/ADR docs.)
