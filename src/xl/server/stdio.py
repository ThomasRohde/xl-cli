"""stdio server mode — JSON line-delimited protocol over stdin/stdout."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from xl.engine.context import WorkbookContext
from xl.engine.dispatcher import error_envelope, output_json, success_envelope
from xl.contracts.common import Target


class StdioServer:
    """Simple JSON-RPC-like server over stdin/stdout."""

    def __init__(self) -> None:
        self._contexts: dict[str, WorkbookContext] = {}

    def _get_ctx(self, file: str, *, data_only: bool = False) -> WorkbookContext:
        key = f"{file}:{data_only}"
        if key not in self._contexts:
            self._contexts[key] = WorkbookContext(file, data_only=data_only)
        return self._contexts[key]

    def _close_all(self) -> None:
        for ctx in self._contexts.values():
            ctx.close()
        self._contexts.clear()

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        req_id = request.get("id", "")
        command = request.get("command", "")
        args = request.get("args", {})

        try:
            file = args.get("file", "")
            if not file:
                return {"id": req_id, "ok": False, "error": "Missing 'file' in args"}

            if command == "wb.inspect":
                ctx = self._get_ctx(file)
                meta = ctx.get_workbook_meta()
                return {"id": req_id, "ok": True, "result": meta.model_dump()}

            elif command == "sheet.ls":
                ctx = self._get_ctx(file)
                sheets = ctx.list_sheets()
                return {"id": req_id, "ok": True, "result": [s.model_dump() for s in sheets]}

            elif command == "table.ls":
                ctx = self._get_ctx(file)
                tables = ctx.list_tables(args.get("sheet"))
                return {"id": req_id, "ok": True, "result": [t.model_dump() for t in tables]}

            elif command == "cell.get":
                ctx = self._get_ctx(file, data_only=args.get("data_only", False))
                ref = args.get("ref", "")
                sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
                from xl.adapters.openpyxl_engine import cell_get
                result = cell_get(ctx, sheet_name, cell_ref)
                return {"id": req_id, "ok": True, "result": result}

            elif command == "cell.set":
                ctx = self._get_ctx(file)
                ref = args.get("ref", "")
                sheet_name, cell_ref = ref.split("!", 1) if "!" in ref else ("", ref)
                from xl.adapters.openpyxl_engine import cell_set
                change = cell_set(ctx, sheet_name, cell_ref, args.get("value"))
                ctx.save(file)
                return {"id": req_id, "ok": True, "result": change.model_dump()}

            elif command == "query":
                import duckdb
                ctx = self._get_ctx(file, data_only=True)
                sql = args.get("sql", "")
                conn = duckdb.connect()
                tables = ctx.list_tables()
                for tbl in tables:
                    ws = ctx.wb[tbl.sheet]
                    from xl.adapters.openpyxl_engine import _parse_ref
                    min_row, min_col, max_row, max_col = _parse_ref(tbl.ref)
                    col_names = [tc.name for tc in tbl.columns]
                    data_rows = []
                    for row_idx in range(min_row + 1, max_row + 1):
                        row_data = {}
                        for ci, col_name in enumerate(col_names):
                            cell = ws.cell(row=row_idx, column=min_col + ci)
                            row_data[col_name] = cell.value
                        data_rows.append(row_data)
                    if data_rows:
                        col_defs = []
                        for col_name in col_names:
                            sample = data_rows[0].get(col_name)
                            if isinstance(sample, int):
                                col_defs.append(f'"{col_name}" BIGINT')
                            elif isinstance(sample, float):
                                col_defs.append(f'"{col_name}" DOUBLE')
                            else:
                                col_defs.append(f'"{col_name}" VARCHAR')
                        conn.execute(f'CREATE TABLE "{tbl.name}" ({", ".join(col_defs)})')
                        placeholders = ", ".join(["?"] * len(col_names))
                        insert_sql = f'INSERT INTO "{tbl.name}" VALUES ({placeholders})'
                        for row_data in data_rows:
                            vals = [row_data.get(c) for c in col_names]
                            conn.execute(insert_sql, vals)
                cursor = conn.execute(sql)
                columns = [desc[0] for desc in cursor.description]
                raw_rows = cursor.fetchall()
                rows = [dict(zip(columns, row)) for row in raw_rows]
                conn.close()
                return {"id": req_id, "ok": True, "result": {"columns": columns, "rows": rows, "row_count": len(rows)}}

            elif command == "close":
                self._close_all()
                return {"id": req_id, "ok": True, "result": "closed"}

            else:
                return {"id": req_id, "ok": False, "error": f"Unknown command: {command}"}

        except Exception as e:
            return {"id": req_id, "ok": False, "error": str(e)}

    def run(self) -> None:
        """Main server loop: read JSON lines from stdin, write responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError as e:
                response = {"ok": False, "error": f"Invalid JSON: {e}"}
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
                continue

            response = self.handle_request(request)
            sys.stdout.write(json.dumps(response, default=str) + "\n")
            sys.stdout.flush()

        self._close_all()
