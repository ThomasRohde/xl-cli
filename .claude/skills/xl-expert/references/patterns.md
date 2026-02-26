# Common Patterns

## Create a Workbook From Scratch With Data and Formatting

```bash
# 1. Create the workbook with named sheets
uv run xl wb create --file report.xlsx --sheets "Sales,Summary"

# 2. Set up headers
uv run xl cell set -f report.xlsx --ref "Sales!A1" --value "Region"
uv run xl cell set -f report.xlsx --ref "Sales!B1" --value "Product"
uv run xl cell set -f report.xlsx --ref "Sales!C1" --value "Revenue"
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

# 6. Format the currency columns
uv run xl format number -f report.xlsx --ref "SalesData[Revenue]" --style currency --decimals 2
uv run xl format number -f report.xlsx --ref "SalesData[Cost]" --style currency --decimals 2
uv run xl format number -f report.xlsx --ref "SalesData[Margin]" --style currency --decimals 2

# 7. Set column widths and freeze header row
uv run xl format width -f report.xlsx --sheet Sales --columns A,B,C,D,E --width 15
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
