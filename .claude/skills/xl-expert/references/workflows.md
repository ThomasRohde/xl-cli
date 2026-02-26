# Workflow YAML Reference

## Full Schema

```yaml
schema_version: "1.0"
name: "workflow-name"
target:
  file: "workbook.xlsx"

defaults:
  output: json           # always json
  recalc: cached         # only mode in v1
  dry_run: false         # set true to preview all steps
  stop_on_error: false   # set true to halt on first failure

steps:
  - id: unique_step_id    # required, must be unique within workflow
    run: command.name      # required, from supported commands below
    args:                  # command-specific arguments
      key: value
```

## Supported Step Commands

### Inspection (read-only)
- `wb.inspect` — args: `{}`
- `sheet.ls` — args: `{}`
- `table.ls` — args: `{ sheet?: string }`
- `cell.get` — args: `{ ref: string }`
- `range.stat` — args: `{ ref: string }`
- `query` — args: `{ sql: string }`
- `formula.find` — args: `{ pattern: string, sheet?: string }`
- `formula.lint` — args: `{ sheet?: string }`

### Mutation
- `table.create` — args: `{ sheet: string, table: string, ref: string, columns?: string[], style?: string }`
- `table.add_column` — args: `{ table: string, name: string, formula?: string, default_value?: string }`
- `table.append_rows` — args: `{ table: string, rows: object[], schema_mode?: string }`
- `table.delete` — args: `{ table: string }`
- `table.delete_column` — args: `{ table: string, name: string }`
- `sheet.delete` — args: `{ name: string }`
- `sheet.rename` — args: `{ name: string, new_name: string }`
- `cell.set` — args: `{ ref: string, value: any, type?: string, force_overwrite_formulas?: bool }`
- `formula.set` — args: `{ ref: string, formula: string, fill_mode?: string, force_overwrite_values?: bool, force_overwrite_formulas?: bool }`
- `format.number` — args: `{ ref: string, style?: string, decimals?: int }`
- `format.width` — args: `{ sheet: string, columns: string, width: number }`
- `format.freeze` — args: `{ sheet: string, ref?: string }`
- `range.clear` — args: `{ ref: string, contents?: bool, formats?: bool }`

### Validation & Verification
- `validate.plan` — args: `{ plan: string }`
- `validate.workbook` — args: `{}`
- `validate.refs` — args: `{ ref: string }`
- `verify.assert` — args: `{ assertions: object[] }`

### Other
- `apply` — args: `{ plan: string }`
- `diff.compare` — args: `{ file_a: string, file_b: string, sheet?: string }`

## Step Arguments

Each step's `args` map to the workflow engine's internal parameter names, which may differ from CLI flag names. For example:
- CLI `--default` → workflow arg `default_value`
- CLI `--name` for delete-column → workflow arg `name`
- CLI `--file-a`/`--file-b` → workflow args `file_a`/`file_b`

The `--file` flag is inherited from the workflow's `target.file` and should not be repeated in step args.

Required arguments vary by command — if a step is missing a required argument, `xl validate workflow` will catch it.

**Note:** `sheet.create` is available as a CLI command but is **not** supported as a workflow step.

## Example: Multi-Step Data Pipeline

```yaml
schema_version: "1.0"
name: "quarterly-report-pipeline"
target:
  file: "q4_data.xlsx"

steps:
  - id: check_structure
    run: wb.inspect
    args: {}

  - id: verify_inputs
    run: verify.assert
    args:
      assertions:
        - type: table.exists
          table: Revenue
        - type: table.column_exists
          table: Revenue
          column: Amount
        - type: table.row_count
          table: Revenue
          min: 1

  - id: add_margin_calc
    run: table.add_column
    args:
      table: Revenue
      name: GrossMargin
      formula: "=[@Amount]-[@COGS]"

  - id: format_margin
    run: format.number
    args:
      ref: "Revenue[GrossMargin]"
      style: currency
      decimals: 2

  - id: verify_output
    run: verify.assert
    args:
      assertions:
        - type: table.column_exists
          table: Revenue
          column: GrossMargin
```

## Validation

```bash
# Syntax-only check (no workbook needed)
uv run xl validate workflow --workflow pipeline.yaml
```

**Note:** `xl run` does **not** accept a `--dry-run` CLI flag. To preview all steps without writing changes, set `dry_run: true` in the workflow's `defaults` block:

```yaml
defaults:
  dry_run: true
```
