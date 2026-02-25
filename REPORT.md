# xl CLI Blind Test Report

Date: 2026-02-25
Workspace: `C:\Users\thoma\Projects\xl-test`
Binary: `C:\Users\thoma\.local\bin\xl.exe`
Version tested: `1.0.0`
Mode: Blind test (no source inspection)

## Scope and Method

- Worked only in `C:\Users\thoma\Projects\xl-test`.
- Built deterministic fixtures (`baseline.xlsx`, `comparison.xlsx`) with:
  - 3 sheets (`Sheet1`, `SalesData`, `Notes`)
  - 1 Excel table (`Sales`)
  - formulas and a named range (`TaxRate`)
- Executed a broad command matrix via `run_blind_tests.ps1`.
- Captured outputs and exit codes in `test-results.json`.
- Ran targeted follow-up probes for ambiguous failures and parser/encoding behavior.

## Coverage

Tested command families:

- Top-level: `version`, `guide`, `--show-completion`, option/error behavior.
- Workbook/sheet/table inspection: `wb inspect`, `wb lock-status`, `sheet ls`, `table ls`.
- Reads: `cell get`, `range stat`, `formula find`, `formula lint`, `query` (SQL + shorthand).
- Direct mutation: `cell set`, `table add-column`, `table append-rows`, `formula set`, `format number/width/freeze`, `range clear`.
- Planning and execution: `plan set-cells`, `plan format`, `plan add-column`, `plan compose`, `plan show`, `validate plan`, `apply` (`--dry-run` and real).
- Validation and verification: `validate workbook`, `validate refs`, `verify assert`.
- Comparison and automation: `diff compare`, `run`, `serve --stdio`.

## Aggregate Results

Primary matrix (`test-results.json`):

- Total tests: 68
- Exit code 0: 52
- Non-zero exits: 16

Most non-zero exits were intentional negative tests and matched documented error classes.

Observed exit codes:

- `0` success
- `10` validation/input/schema/assertion failures
- `30` formula-overwrite protection
- `40` fingerprint conflict on stale plan
- `50` missing workbook
- `90` query/workflow internal-style failures
- `2` CLI parser option error (`xl -h` unsupported)

## What Worked Well

- JSON ResponseEnvelope is consistent across command families (`ok`, `command`, `result`, `errors`, `warnings`, `metrics`).
- Safety rails are effective:
  - `--dry-run` reports planned changes without writing.
  - `--backup` produced timestamped `.bak.xlsx` files.
  - formula overwrite guard correctly blocked writes unless `--force-overwrite-formulas`.
  - stale plan detection correctly blocked apply with `ERR_PLAN_FINGERPRINT_CONFLICT` (exit 40).
- Query engine worked for both explicit SQL and shorthand modes.
- Plan lifecycle works end-to-end (generate -> validate -> apply -> verify -> diff).
- `diff compare` correctly surfaced added/modified cells and fingerprints.
- `serve --stdio` processed line-delimited JSON requests and returned line-delimited JSON responses.

## Notable Findings

1. UTF-8 BOM sensitivity in file-based JSON/YAML inputs.
- Repro: files written with PowerShell `Set-Content -Encoding utf8` triggered parse errors for `--data-file`, `--assertions-file`, and `--workflow`.
- Symptoms included errors like `Cannot parse assertions: Expecting value: line 1 column 1` and workflow key `???target`.
- Same content written as ASCII (or otherwise no BOM) works.

2. `run` workflow schema is strict and under-documented in help text.
- `steps[].id` and `steps[].run` are required.
- Example invalid step (`command:` instead of `run:`) returns pydantic-style validation errors.

3. `run` supports only a subset of commands.
- `wb.inspect` and `table.ls` succeeded.
- A step with `run: query` returned `Unknown step command: query` and process exit `90`, despite top-level `xl query` being available.

4. `serve --stdio` command surface differs from top-level CLI.
- Sending `{"command":"version"}` returned `Missing 'file' in args`.
- `{"command":"wb.inspect","args":{"file":"baseline.xlsx"}}` succeeded.

5. `cell get --data-only` depends on cached formula values.
- For fixture formulas without cached results, return was `type: empty`, `value: null`.
- This is expected for cache-only retrieval but easy to misinterpret.

6. `diff compare` appears value-oriented rather than formula-text-oriented.
- Formula cell changes can appear as `before: null` / `after: <value>` if cached values are absent in source workbook.

## Representative Evidence

- Missing file:
  - `xl cell get -f missing.xlsx --ref "Sheet1!A1"` -> `ERR_WORKBOOK_NOT_FOUND`, exit `50`
- Formula protection:
  - `xl cell set -f work.xlsx --ref "Sheet1!D2" --value 999 --type number` -> `ERR_FORMULA_OVERWRITE_BLOCKED`, exit `30`
- Plan conflict:
  - `xl apply -f planwork.xlsx --plan p_stale.json` -> `ERR_PLAN_FINGERPRINT_CONFLICT`, exit `40`
- Bad SQL:
  - `xl query -f baseline.xlsx --sql "SELECT * FROM NotATable"` -> `ERR_QUERY_FAILED`, exit `90`

## Artifacts Produced

- `REPORT.md` (this report)
- `run_blind_tests.ps1`
- `test-results.json`
- `run_followup.ps1`
- `followup-results.json`
- Workbook fixtures and derived files (`baseline.xlsx`, `comparison.xlsx`, `work*.xlsx`, `plan*.xlsx`, plan JSON files, workflow YAML files)

## Bottom Line

`xl` core behavior is strong for inspection, planning, safe mutation, validation, and diffing. The main operational risks found are BOM handling for file-based JSON/YAML inputs, partial `run` command support, and `serve` command-set differences versus top-level CLI.
