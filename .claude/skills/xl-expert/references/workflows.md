# Workflow YAML Reference

## Full Schema

```yaml
schema_version: "1.0"
name: "workflow-name"
target:
  file: "workbook.xlsx"

defaults:
  output: json        # always json
  recalc: cached      # only mode in v1
  dry_run: false      # set true to preview all steps

steps:
  - id: unique_step_id    # required, must be unique within workflow
    run: command.name      # required, from supported commands below
    args:                  # command-specific arguments
      key: value
```

## Supported Step Commands

### Inspection (read-only)
- `wb.inspect` — args: `{}`
- `sheet.ls` — args: `{ sheet?: string }`
- `table.ls` — args: `{ sheet?: string }`
- `cell.get` — args: `{ ref: string }`
- `range.stat` — args: `{ ref: string }`
- `query` — args: `{ sql?: string, table?: string, select?: string, where?: string }`
- `formula.find` — args: `{ pattern: string, sheet?: string }`
- `formula.lint` — args: `{ sheet?: string }`

### Mutation
- `table.create` — args: `{ sheet: string, ref: string, name: string, columns?: string[], style?: string }`
- `table.add_column` — args: `{ table: string, name: string, formula?: string, default?: string }`
- `table.append_rows` — args: `{ table: string, rows: object[], schema_mode?: string }`
- `table.delete` — args: `{ table: string }`
- `table.delete_column` — args: `{ table: string, column: string }`
- `sheet.create` — args: `{ name: string }`
- `sheet.delete` — args: `{ sheet: string }`
- `sheet.rename` — args: `{ sheet: string, new_name: string }`
- `cell.set` — args: `{ ref: string, value: any, cell_type?: string, force_overwrite_formulas?: bool }`
- `formula.set` — args: `{ ref: string, formula: string, fill_mode?: string, force_overwrite_formulas?: bool }`
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
- `apply` — args: `{ plan: string, dry_run?: bool, backup?: bool }`
- `diff.compare` — args: `{ other: string }`

## Step Arguments

Each step's `args` map directly to the corresponding CLI command's parameters. The `--file` flag is inherited from the workflow's `target.file` and should not be repeated in step args.

Required arguments vary by command — if a step is missing a required argument, `xl validate workflow` will catch it.

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

# Full validation against workbook
uv run xl run --workflow pipeline.yaml -f data.xlsx --dry-run
```
