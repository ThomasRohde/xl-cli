---
name: xl-expert
description: "Expert guidance for using the `xl` CLI to inspect, modify, query, and automate Excel workbooks (.xlsx/.xlsm). The agent should use this skill when the user wants to work with Excel files — adding columns, appending rows, querying data, formatting cells, comparing workbooks, running multi-step workflows, or any spreadsheet task. Trigger on: spreadsheet, Excel, workbook, .xlsx, .xlsm, table data, column, row, cell, formula, format cells, named range, or any column/row/cell operation even without naming xl directly. If the user has xl installed in their project, this skill applies."
---

# xl CLI Expert

`xl` is an agent-first CLI for Excel workbooks (.xlsx/.xlsm) with JSON output, plan-based transactions, dry-run, and safety rails. Run all commands via `uv run xl ...`.

## Golden Path: Discover → Plan → Apply → Verify

To modify any workbook safely, follow this sequence:

1. **Inspect** the workbook: `uv run xl wb inspect -f data.xlsx`
2. **List tables** to find data targets: `uv run xl table ls -f data.xlsx`
3. **Generate a plan**: `uv run xl plan add-column -f data.xlsx -t Sales -n Margin --formula "=[@Revenue]-[@Cost]" --out plan.json`
4. **Validate** the plan: `uv run xl validate plan -f data.xlsx --plan plan.json`
5. **Preview** with dry-run: `uv run xl apply -f data.xlsx --plan plan.json --dry-run`
6. **Apply** with backup: `uv run xl apply -f data.xlsx --plan plan.json --backup`
7. **Verify** the result: `uv run xl verify assert -f data.xlsx --assertions '[{"type":"table.column_exists","table":"Sales","column":"Margin"}]'`

For read-only tasks (inspect, query, list), use direct commands — skip plan/apply.
For quick single edits, use direct mutation commands with `--backup` — skip the plan.

## Choosing an Approach

| To do this... | Use this approach |
|---|---|
| Inspect, query, or list data | Direct read-only command (`wb inspect`, `table ls`, `query`) |
| Make a single quick edit | Direct mutation with `--backup` (`table add-column`, `cell set`) |
| Make multiple related changes | Plan workflow (plan → validate → dry-run → apply → verify) |
| Automate a repeatable pipeline | YAML workflow with `xl run` |
| Compare before/after states | `xl diff compare` |
| Analyze data with SQL | `xl query --sql "..."` |

## Non-Obvious Rules

- **Always inspect before modifying.** Never modify a workbook blind — run `wb inspect` and `table ls` first to understand its structure.
- **Prefer table operations over raw cell ops.** Tables are the primary data abstraction; use `table add-column`, `table append-rows`, etc.
- **Use `--force-overwrite-formulas` to overwrite existing formulas.** The CLI blocks formula overwrites by default to prevent accidental destruction.
- **Use `--schema-mode allow-missing-null` when appending rows to tables with formula columns.** Formula columns auto-fill from the first data row; don't include them in row data.
- **Plans carry fingerprints.** If the workbook changes externally after plan creation, apply rejects with exit code 40. Re-inspect and regenerate the plan.
- **Structured references use `[@ColumnName]` syntax** inside table formulas: `"=[@Revenue]-[@Cost]"`.
- **Cell/range refs require the sheet name:** `Sheet1!B2`, `Sheet1!A1:D10`. Table column refs use `TableName[Column]`.

## Command Discovery

To explore available commands, use progressive help:

1. `uv run xl guide` — full machine-readable orientation (JSON)
2. `uv run xl --help` — command group overview
3. `uv run xl <group> --help` — group detail (e.g., `xl table --help`)
4. `uv run xl <group> <cmd> --help` — full command detail with examples

## Reference Files

For full command listings, recipes, workflow schema, and error codes:

- `references/commands.md` — All commands with arguments and examples
- `references/patterns.md` — Common multi-step recipes (create workbook, add column, bulk insert, query, YAML workflow)
- `references/workflows.md` — YAML workflow schema and supported step commands
- `references/errors.md` — Exit codes, error codes, and troubleshooting guide
