# Common Patterns

## Create a Workbook From Scratch With Data and Formatting

**IMPORTANT:** All mutations to the same file must be chained sequentially with `&&`. Never run them as parallel/sibling tool calls — they will fail with `ERR_LOCK_HELD`.

```bash
# 1. Create the workbook with named sheets
uv run xl wb create --file report.xlsx --sheets "Sales,Summary"

# 2. Set up headers (chain with && — same file, must be sequential)
uv run xl cell set -f report.xlsx --ref "Sales!A1" --value "Region" && \
uv run xl cell set -f report.xlsx --ref "Sales!B1" --value "Product" && \
uv run xl cell set -f report.xlsx --ref "Sales!C1" --value "Revenue" && \
uv run xl cell set -f report.xlsx --ref "Sales!D1" --value "Cost"

# 3. Promote the range to an Excel Table
uv run xl table create -f report.xlsx -s Sales --ref "A1:D1" -t SalesData

# 4. Append rows of data
uv run xl table append-rows -f report.xlsx -t SalesData --data '[
  {"Region":"North","Product":"Widget","Revenue":12000,"Cost":8000},
  {"Region":"South","Product":"Gadget","Revenue":9500,"Cost":6200},
  {"Region":"East","Product":"Widget","Revenue":11000,"Cost":7100}
]'

# 5. Add a calculated column
uv run xl table add-column -f report.xlsx -t SalesData -n Margin \
  --formula "=[@Revenue]-[@Cost]"

# 6. Format the currency columns (chain with && — same file)
uv run xl format number -f report.xlsx --ref "SalesData[Revenue]" --style currency --decimals 2 && \
uv run xl format number -f report.xlsx --ref "SalesData[Cost]" --style currency --decimals 2 && \
uv run xl format number -f report.xlsx --ref "SalesData[Margin]" --style currency --decimals 2

# 7. Set column widths and freeze header row (chain with &&)
uv run xl format width -f report.xlsx --sheet Sales --columns A,B,C,D,E --width 15 && \
uv run xl format freeze -f report.xlsx --sheet Sales --ref "A2"

# 8. Verify the result
uv run xl verify assert -f report.xlsx --assertions '[
  {"type":"table.exists","table":"SalesData"},
  {"type":"table.column_exists","table":"SalesData","column":"Margin"},
  {"type":"table.row_count","table":"SalesData","min":3}
]'
```

## Add a Calculated Column and Verify

```bash
uv run xl table add-column -f data.xlsx -t Sales -n ProfitPct \
  --formula "=([@Revenue]-[@Cost])/[@Revenue]" --backup
uv run xl format number -f data.xlsx --ref "Sales[ProfitPct]" --style percent --decimals 1
uv run xl verify assert -f data.xlsx --assertions '[{"type":"table.column_exists","table":"Sales","column":"ProfitPct"}]'
```

## Bulk Data Insert

```bash
uv run xl table append-rows -f data.xlsx -t Inventory \
  --data '[{"SKU":"A001","Qty":100,"Price":9.99},{"SKU":"A002","Qty":50,"Price":19.99}]' \
  --schema-mode strict --backup
```

## Query and Analyze With SQL

```bash
uv run xl query -f data.xlsx --sql "SELECT Region, COUNT(*) as N, AVG(Revenue) as AvgRev FROM Sales GROUP BY Region ORDER BY AvgRev DESC"
```

## Workbook Health Check

```bash
uv run xl validate workbook -f data.xlsx   # checks for macros, external links, hidden sheets
uv run xl formula lint -f data.xlsx         # volatile functions, broken refs
```

## Multi-Step Workflow (YAML)

To automate a repeatable pipeline, write a YAML workflow file. See `workflows.md` for the full schema and all supported step commands.

```yaml
schema_version: "1.0"
name: "add-margin-column"
target:
  file: "budget.xlsx"
steps:
  - id: inspect
    run: table.ls
    args: {}
  - id: add_margin
    run: table.add_column
    args:
      table: "Sales"
      name: "Margin"
      formula: "=[@Sales]-[@Cost]"
  - id: verify
    run: verify.assert
    args:
      assertions:
        - type: table.column_exists
          table: Sales
          column: Margin
```

```bash
uv run xl run --workflow pipeline.yaml -f budget.xlsx
uv run xl validate workflow --workflow pipeline.yaml   # syntax check without workbook
```

## Concurrency and Sequential Mutations

### Critical: Never Parallelize Mutations to the Same File

Every mutating command acquires an exclusive `.xl.lock` sidecar file. Parallel mutations to the same workbook **will fail** with `ERR_LOCK_HELD` (exit 50). This is the #1 cause of errors for AI agents using `xl`.

**Always chain mutations to the same file with `&&`:**
```bash
# CORRECT — sequential via &&
uv run xl cell set -f data.xlsx --ref "Sheet1!A1" --value "Name" && \
uv run xl cell set -f data.xlsx --ref "Sheet1!B1" --value "Value" && \
uv run xl table create -f data.xlsx -s Sheet1 --ref "A1:B1" -t MyTable
```

**Or batch them in a YAML workflow (most efficient for 3+ operations):**
```yaml
schema_version: "1.0"
name: "setup-headers"
target:
  file: "data.xlsx"
steps:
  - id: set_a1
    run: cell.set
    args: { ref: "Sheet1!A1", value: "Name" }
  - id: set_b1
    run: cell.set
    args: { ref: "Sheet1!B1", value: "Value" }
  - id: create_table
    run: table.create
    args: { sheet: Sheet1, ref: "A1:B1", table: MyTable }
```

**What you CAN parallelize:**
- Read-only commands against the same file (never blocked)
- Mutations targeting **different** files (separate locks)

### Multi-Agent / Concurrent Access

When multiple agents or processes may mutate the same workbook simultaneously, use `--wait-lock` to serialize access:

```bash
# Agent A and Agent B both targeting the same file — use --wait-lock to queue
uv run xl table add-column -f shared.xlsx -t Sales -n Margin \
  --formula "=[@Revenue]-[@Cost]" --wait-lock 5

# Check lock status before a batch of operations
uv run xl wb lock-status -f shared.xlsx
```

Key points:
- All mutating commands hold an exclusive `.xl.lock` sidecar lock for the entire read-modify-write cycle
- `--wait-lock 0` (default) fails immediately with `ERR_LOCK_HELD` if locked
- `--wait-lock N` retries for up to N seconds before failing
- Read-only commands (`wb inspect`, `table ls`, `query`, etc.) are never blocked
- `xl run` workflows hold the lock for the entire workflow when it contains mutating steps
