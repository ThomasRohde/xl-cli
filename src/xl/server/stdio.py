"""stdio server mode — JSON line-delimited protocol over stdin/stdout."""

from __future__ import annotations

import json
import sys
from typing import Any

from xl.engine.context import WorkbookContext


# Commands that do not require a 'file' argument.
_NO_FILE_COMMANDS = frozenset({"version", "guide", "close"})

_SUPPORTED_COMMANDS = [
    "version", "guide", "close",
    "wb.inspect", "sheet.ls", "table.ls",
    "cell.get", "cell.set", "query",
    "formula.find", "formula.lint",
    "range.stat",
    "validate.workbook",
    "diff.compare",
]


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
            # -- Commands that do not require a file --
            if command == "version":
                import xl
                return {"id": req_id, "ok": True, "result": {"version": xl.__version__}}

            elif command == "guide":
                return {"id": req_id, "ok": True, "result": {
                    "supported_commands": _SUPPORTED_COMMANDS,
                    "protocol": "JSON line-delimited over stdin/stdout",
                }}

            elif command == "close":
                self._close_all()
                return {"id": req_id, "ok": True, "result": "closed"}

            # -- All remaining commands require a file --
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
                from xl.engine.workflow import _run_query
                ctx = self._get_ctx(file, data_only=True)
                sql = args.get("sql", "")
                result = _run_query(ctx, sql)
                return {"id": req_id, "ok": True, "result": result}

            elif command == "formula.find":
                ctx = self._get_ctx(file)
                from xl.adapters.openpyxl_engine import formula_find
                pattern = args.get("pattern", "")
                sheet = args.get("sheet")
                matches = formula_find(ctx, pattern, sheet_name=sheet)
                return {"id": req_id, "ok": True, "result": matches}

            elif command == "formula.lint":
                ctx = self._get_ctx(file)
                from xl.adapters.openpyxl_engine import formula_lint
                sheet = args.get("sheet")
                findings = formula_lint(ctx, sheet_name=sheet)
                return {"id": req_id, "ok": True, "result": findings}

            elif command == "range.stat":
                ctx = self._get_ctx(file, data_only=args.get("data_only", False))
                ref = args.get("ref", "")
                sheet_name, range_ref = ref.split("!", 1) if "!" in ref else ("", ref)
                from xl.adapters.openpyxl_engine import range_stat
                result = range_stat(ctx, sheet_name, range_ref)
                return {"id": req_id, "ok": True, "result": result}

            elif command == "validate.workbook":
                ctx = self._get_ctx(file)
                from xl.validation.validators import validate_workbook
                vr = validate_workbook(ctx)
                return {"id": req_id, "ok": True, "result": vr.model_dump()}

            elif command == "diff.compare":
                from xl.diff.differ import diff_workbooks
                file_a = args.get("file_a", file)
                file_b = args.get("file_b", "")
                sheet = args.get("sheet")
                result = diff_workbooks(file_a, file_b, sheet_filter=sheet)
                return {"id": req_id, "ok": True, "result": result}

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
