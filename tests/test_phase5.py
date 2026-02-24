"""Tests for Phase 5: workflow execution, events, trace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from xl.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Workflow execution
# ---------------------------------------------------------------------------
def test_run_simple_workflow(simple_workbook: Path, tmp_path: Path):
    """Execute a simple workflow that inspects and lists tables."""
    workflow = {
        "schema_version": "1.0",
        "name": "test_inspect",
        "target": {"file": str(simple_workbook)},
        "defaults": {"output": "json", "recalc": "cached", "dry_run": True},
        "steps": [
            {"id": "step1", "run": "wb.inspect", "args": {}},
            {"id": "step2", "run": "table.ls", "args": {}},
        ],
    }
    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text(yaml.dump(workflow))

    result = runner.invoke(app, [
        "run", "--workflow", str(wf_path),
        "--file", str(simple_workbook),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["ok"] is True
    assert data["result"]["steps_total"] == 2
    assert data["result"]["steps_passed"] == 2


def test_run_workflow_with_mutation(simple_workbook: Path, tmp_path: Path):
    """Workflow that adds a column."""
    workflow = {
        "schema_version": "1.0",
        "name": "test_mutate",
        "target": {"file": str(simple_workbook)},
        "defaults": {"dry_run": False},
        "steps": [
            {
                "id": "add_col",
                "run": "table.add_column",
                "args": {"table": "Sales", "name": "Margin", "formula": "=[@Sales]-[@Cost]"},
            },
            {
                "id": "verify",
                "run": "verify.assert",
                "args": {
                    "assertions": [
                        {"type": "table.column_exists", "table": "Sales", "column": "Margin"},
                    ],
                },
            },
        ],
    }
    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text(yaml.dump(workflow))

    result = runner.invoke(app, [
        "run", "--workflow", str(wf_path),
        "--file", str(simple_workbook),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["result"]["steps_passed"] == 2


def test_run_workflow_step_failure(simple_workbook: Path, tmp_path: Path):
    """Workflow with a failing step."""
    workflow = {
        "schema_version": "1.0",
        "name": "test_fail",
        "target": {"file": str(simple_workbook)},
        "defaults": {"dry_run": True},
        "steps": [
            {"id": "bad", "run": "nonexistent.command", "args": {}},
        ],
    }
    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text(yaml.dump(workflow))

    result = runner.invoke(app, [
        "run", "--workflow", str(wf_path),
        "--file", str(simple_workbook),
    ])
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["result"]["steps_passed"] == 0


def test_run_workflow_target_from_file(simple_workbook: Path, tmp_path: Path):
    """Workflow uses target.file from the spec."""
    workflow = {
        "schema_version": "1.0",
        "name": "test_target",
        "target": {"file": str(simple_workbook)},
        "defaults": {"dry_run": True},
        "steps": [
            {"id": "step1", "run": "sheet.ls", "args": {}},
        ],
    }
    wf_path = tmp_path / "workflow.yaml"
    wf_path.write_text(yaml.dump(workflow))

    # Don't pass --file, let workflow target be used
    result = runner.invoke(app, ["run", "--workflow", str(wf_path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# Event emitter (unit test)
# ---------------------------------------------------------------------------
def test_event_emitter():
    """EventEmitter should write NDJSON to stderr when enabled."""
    import io
    import sys
    from xl.observe.events import EventEmitter

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        emitter = EventEmitter(enabled=True)
        emitter.emit("test_event", {"key": "value"})
        output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_stderr

    line = json.loads(output.strip())
    assert line["event"] == "test_event"
    assert line["data"]["key"] == "value"
    assert "timestamp" in line


def test_event_emitter_disabled():
    """Disabled emitter should not write anything."""
    import io
    import sys
    from xl.observe.events import EventEmitter

    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        emitter = EventEmitter(enabled=False)
        emitter.emit("test_event", {"key": "value"})
        output = sys.stderr.getvalue()
    finally:
        sys.stderr = old_stderr

    assert output == ""


# ---------------------------------------------------------------------------
# Trace recorder (unit test)
# ---------------------------------------------------------------------------
def test_trace_recorder(tmp_path: Path):
    """TraceRecorder should save a valid trace file."""
    from xl.observe.events import TraceRecorder

    recorder = TraceRecorder()
    recorder.record("command", {"args": {"file": "test.xlsx"}})
    recorder.record("operation", {"op_id": "op1", "type": "cell.set"})

    trace_path = tmp_path / "trace.json"
    saved = recorder.save(trace_path)
    assert Path(saved).exists()

    data = json.loads(Path(saved).read_text())
    assert data["trace_version"] == "1.0"
    assert len(data["entries"]) == 2
    assert data["entries"][0]["category"] == "command"


# ---------------------------------------------------------------------------
# stdio server (unit test)
# ---------------------------------------------------------------------------
def test_stdio_server_inspect(simple_workbook: Path):
    """StdioServer should handle wb.inspect requests."""
    from xl.server.stdio import StdioServer

    server = StdioServer()
    response = server.handle_request({
        "id": "req1",
        "command": "wb.inspect",
        "args": {"file": str(simple_workbook)},
    })
    assert response["ok"] is True
    assert response["id"] == "req1"
    assert "sheets" in response["result"]
    server._close_all()


def test_stdio_server_table_ls(simple_workbook: Path):
    from xl.server.stdio import StdioServer

    server = StdioServer()
    response = server.handle_request({
        "id": "req2",
        "command": "table.ls",
        "args": {"file": str(simple_workbook)},
    })
    assert response["ok"] is True
    assert len(response["result"]) == 1
    assert response["result"][0]["name"] == "Sales"
    server._close_all()


def test_stdio_server_cell_get(simple_workbook: Path):
    from xl.server.stdio import StdioServer

    server = StdioServer()
    response = server.handle_request({
        "id": "req3",
        "command": "cell.get",
        "args": {"file": str(simple_workbook), "ref": "Revenue!A2"},
    })
    assert response["ok"] is True
    assert response["result"]["value"] == "North"
    server._close_all()


def test_stdio_server_unknown_command(simple_workbook: Path):
    from xl.server.stdio import StdioServer

    server = StdioServer()
    response = server.handle_request({
        "id": "req4",
        "command": "unknown.cmd",
        "args": {"file": str(simple_workbook)},
    })
    assert response["ok"] is False
    assert "Unknown command" in response["error"]
    server._close_all()


def test_stdio_server_missing_file():
    from xl.server.stdio import StdioServer

    server = StdioServer()
    response = server.handle_request({
        "id": "req5",
        "command": "wb.inspect",
        "args": {},
    })
    assert response["ok"] is False
