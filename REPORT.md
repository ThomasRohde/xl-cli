# xl CLI v1.4.2 — Blind Test Report

**Date:** 2026-02-26
**Tester:** Claude Opus 4.6
**Platform:** Windows 11 / Git Bash
**xl version:** 1.4.2 (via `uv run xl`)

---

## Executive Summary

xl v1.4.2 is a solid, well-structured agent-first CLI for Excel workbook manipulation. Every command returns a consistent JSON `ResponseEnvelope`, error messages are machine-readable with categorized exit codes, and safety rails (dry-run, backup, fingerprint conflict detection, formula overwrite protection) work reliably. The plan/compose/validate/apply lifecycle is clean and production-ready. YAML workflows execute multi-step pipelines correctly.

**Overall verdict:** xl is ready for agent-driven Excel automation. The handful of issues found are minor and mostly documentation gaps rather than functional bugs.

---

## Test Matrix

| Area | Commands Tested | Result |
|------|----------------|--------|
| Help & Discovery | `--help`, `--version`, `guide`, `--human`, group help | All pass |
| Workbook Creation | `wb create`, `wb create --force`, `wb inspect`, `wb lock-status` | All pass |
| Sheet Operations | `sheet ls`, `sheet create`, `sheet rename`, `sheet delete`, `sheet delete --backup` | All pass |
| Cell Operations | `cell set` (text, number, bool, date), `cell get`, `cell set --dry-run` | All pass |
| Range Operations | `range stat`, `range clear --contents --formats` | All pass |
| Table Operations | `table create`, `table ls`, `table add-column` (formula + default), `table append-rows` (inline + file), `table delete-column`, `table delete` | All pass |
| Schema Modes | `strict`, `allow-missing-null`, `map-by-header` | All pass |
| Formatting | `format number` (currency, percent), `format width`, `format freeze` | All pass |
| Formula Operations | `formula set`, `formula set --fill-mode fixed`, `formula find`, `formula lint`, `--force-overwrite-formulas` | All pass |
| Query & SQL | `query --sql` (GROUP BY, WHERE, ORDER BY, computed columns), `query --table --where`, `query --data-only` | All pass |
| Plan Workflow | `plan add-column`, `plan format`, `plan set-cells`, `plan delete-column`, `plan rename-sheet`, `plan delete-table`, `plan compose`, `plan show`, `validate plan`, `apply --dry-run`, `apply --backup`, fingerprint conflict | All pass |
| Verify | `verify assert` with `--assertions-file` (table.exists, table.column_exists, table.row_count, cell.not_empty, cell.value_equals) | All pass |
| YAML Workflows | `validate workflow`, `run --workflow` (6-step pipeline including mutation, query, verify) | All pass |
| Diff | `diff compare` (changed files, identical files) | All pass |
| Validation | `validate workbook`, `validate refs` | All pass |
| Error Paths | See error matrix below | All behave correctly |

---

## Error Path Matrix

| Scenario | Exit Code | Error Code | Correct? |
|----------|-----------|------------|----------|
| File not found | 50 | `ERR_WORKBOOK_NOT_FOUND` | Yes |
| File already exists (wb create) | 50 | `ERR_FILE_EXISTS` | Yes |
| Bad sheet reference | 10 | `ERR_RANGE_INVALID` | Yes |
| Delete last sheet | 10 | `ERR_LAST_SHEET` | Yes |
| Duplicate column name | 10 | `ERR_COLUMN_EXISTS` | Yes |
| Duplicate sheet name | 10 | `ERR_SHEET_EXISTS` | Yes |
| Table not found | 10 | `ERR_TABLE_NOT_FOUND` | Yes |
| Table overlap | 10 | `ERR_TABLE_OVERLAP` | Yes |
| Schema mismatch (strict) | 10 | `ERR_SCHEMA_MISMATCH` | Yes |
| Formula overwrite (formula.set) | 30 | `ERR_FORMULA_BLOCKED` | Yes |
| Formula overwrite (cell.set) | 30 | `ERR_FORMULA_OVERWRITE_BLOCKED` | Yes |
| Fingerprint conflict | 40 | `ERR_PLAN_FINGERPRINT_CONFLICT` | Yes |
| Assertion failure | 10 | `ERR_ASSERTION_FAILED` | Yes |
| Workflow step failure | 90 | `ERR_WORKFLOW_STEP_FAILED` | Yes |
| Invalid workflow command | 10 | `ERR_WORKFLOW_INVALID` | Yes |

All errors return proper JSON envelopes with `ok: false`, structured error codes, and meaningful messages.

---

## Bugs Found

### 1. `sheet delete --backup` — FIXED in v1.4.2
Previously broken in v1.4.0 (`NameError: make_backup`). Now works correctly — backup file is created and the sheet is deleted.

### 2. Query `--where` returns formula strings, not computed values
When using `--table SalesData --where "Revenue > 10000"`, formula columns (e.g., Margin) return the literal formula string `"=[@Revenue]-[@Cost]"` rather than a computed value or null. This is because the workbook was created programmatically and has no cached values.

**Workaround:** Use `--sql` with inline computation: `SELECT *, (Revenue - Cost) AS Margin FROM SalesData WHERE Revenue > 10000`

### 3. `xl run` does not support `--dry-run` flag
The skill reference mentions `xl run --workflow ... --dry-run` for full validation against a workbook, but `xl run` rejects `--dry-run` with `No such option`. Use `defaults: dry_run: true` in the YAML instead.

**Impact:** Minor — the YAML-level `dry_run` default achieves the same thing.

---

## Noteworthy Behaviors (Not Bugs)

| Behavior | Notes |
|----------|-------|
| `--data-only` returns `null` for formula columns | Expected — programmatically-created workbooks have no Excel-cached values. Only useful after opening/saving in Excel. |
| `table delete` preserves cell data | By design — only removes the ListObject definition, not the underlying cell values. |
| `wb create --force` silently overwrites | No confirmation or backup — use with care. |
| `formula.set` error codes differ from `cell.set` | `ERR_FORMULA_BLOCKED` vs `ERR_FORMULA_OVERWRITE_BLOCKED` — two different error codes for essentially the same protection. Consistent enough but worth noting. |
| Workflow exit code is 90 for step failures | Even when the step itself would be a 10 (validation) error, the workflow wraps it as exit 90. |
| `sheet.create` not supported in workflows | Documented and confirmed — must use CLI command directly. |
| `--data-file` flag for append-rows | Undocumented in the skill reference but works. Allows reading JSON row data from a file instead of inline. |
| Double JSON output on errors | Some error paths emit the error envelope twice on stderr. Not a functional issue but noisy. |
| `plan compose` merges preconditions + postconditions | Correctly deduplicates when composing multiple plans targeting the same table. |

---

## Mistakes I Made During Testing & Lessons Learned

### Mistake 1: Tried `python3` on Windows
**What happened:** I piped xl output to `python3 -c "..."` to filter JSON, but `python3` isn't available on Windows (it's `python` or `py`).

**Lesson for the skill/agent:** On Windows, avoid assuming `python3` is available. Use `python` or, better yet, avoid shell-level JSON filtering — xl's JSON output is structured enough to read directly.

### Mistake 2: Tried `xl run --dry-run`
**What happened:** The skill reference says to use `xl run --workflow pipeline.yaml -f data.xlsx --dry-run` for full validation, but `xl run` doesn't accept `--dry-run`.

**Lesson for the skill:** Update the workflow reference to clarify that `xl run` doesn't support `--dry-run` as a CLI flag. The correct approach is `defaults: dry_run: true` in the YAML file, or run individual steps manually.

### Mistake 3: Re-applied a stale plan
**What happened:** After applying a plan, I tried to re-apply the same plan. It failed with fingerprint mismatch. This was intentional (testing), but in a real workflow, you'd need to regenerate the plan.

**Lesson for the skill:** This is correct behavior. Always regenerate plans after any workbook modification. Plans are one-shot artifacts tied to a specific workbook state.

### Mistake 4: Used `wb create --force` then tried to reference a table from the old file
**What happened:** I used `--force` to recreate `edge.xlsx`, which destroyed the `EmptyTable` I'd created earlier. Then I tried to `table delete` the old table.

**Lesson for the skill/agent:** `--force` is destructive with no undo. Always think carefully before using it. If you need the old data, make a manual backup first.

### Mistake 5: Didn't anticipate formula columns in query results
**What happened:** When querying with `--where`, formula columns came back as raw formula strings instead of values. I expected computed values.

**Lesson for the skill:** For programmatically-created workbooks, formula columns have no cached values. Always use `--sql` with inline computation for formula-dependent queries, or accept nulls with `--data-only`.

---

## Recommendations for the xl Skill

1. **Document `--data-file` flag** for `table append-rows` — it's the safest way to pass row data (avoids shell escaping issues).

2. **Clarify `xl run --dry-run`** — update workflow reference to note that `--dry-run` is not a CLI flag for `xl run`; use YAML `defaults.dry_run` instead.

3. **Add guidance on formula columns in queries** — the skill should note that `--where` queries on formula columns return raw formula text in programmatically-created workbooks, and suggest `--sql` with computed columns as the workaround.

4. **Note `serve` command** — the skill doesn't mention `xl serve` (MCP/ACP stdio server). Could be useful for agent tool integration.

5. **Note `wb lock-status`** — useful for checking if Excel has a file locked before attempting mutations.

6. **Note all plan generation commands** — `plan format`, `plan delete-sheet`, `plan rename-sheet`, `plan delete-table`, `plan delete-column` are all available but not all listed in the skill reference commands.md.

7. **Note double error output** — some error paths emit the JSON envelope twice. Parsers should handle this (e.g., take the first valid JSON object).

---

## Command Coverage Summary

### Fully Tested (with success + error paths)
- `wb create`, `wb inspect`, `wb lock-status`
- `sheet ls`, `sheet create`, `sheet rename`, `sheet delete`
- `cell set`, `cell get`
- `range stat`, `range clear`
- `table create`, `table ls`, `table add-column`, `table append-rows`, `table delete-column`, `table delete`
- `formula set`, `formula find`, `formula lint`
- `format number`, `format width`, `format freeze`
- `query` (--sql, --table, --where, --data-only)
- `plan add-column`, `plan format`, `plan set-cells`, `plan delete-column`, `plan rename-sheet`, `plan delete-table`, `plan compose`, `plan show`
- `validate plan`, `validate workbook`, `validate refs`, `validate workflow`
- `apply` (--dry-run, --backup, --plan)
- `verify assert` (--assertions-file with multiple assertion types)
- `run` (--workflow)
- `diff compare`
- `guide`, `version`

### Checked but not deeply exercised
- `serve` (help only — requires stdio integration)
- `plan create-table` (help only — did table creation via direct command instead)

### Assertion types tested
- `table.exists`
- `table.column_exists`
- `table.row_count` (with `min`)
- `cell.not_empty`
- `cell.value_equals` (text + numeric + empty/null)

### Schema modes tested
- `strict` — rejects missing columns
- `allow-missing-null` — skips formula columns
- `map-by-header` — case-insensitive column matching

---

## Version Delta: v1.4.0 → v1.4.2

| Change | v1.4.0 | v1.4.2 |
|--------|--------|--------|
| `sheet delete --backup` | Broken (`NameError: make_backup`) | Fixed |
| Everything else tested | N/A (not tested in v1.4.0) | Working |
