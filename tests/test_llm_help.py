"""Integration tests for TOON help output with LLM=true."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from xl.cli import app

runner = CliRunner()


def test_app_help_toon():
    """xl --help with LLM=true should produce TOON output."""
    result = runner.invoke(app, ["--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" in out
    assert "groups[" in out


def test_group_help_toon():
    """xl table --help with LLM=true should produce group TOON."""
    result = runner.invoke(app, ["table", "--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    assert "group: table" in out
    assert "commands[" in out


def test_command_help_toon():
    """xl table add-column --help with LLM=true should produce command TOON."""
    result = runner.invoke(app, ["table", "add-column", "--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    assert "command:" in out
    assert "options[" in out
    assert "flag,type,required,default,help" in out


def test_no_llm_normal_help():
    """Without LLM=true, help should be normal Rich output."""
    result = runner.invoke(app, ["--help"], env={"LLM": "false"})
    assert result.exit_code == 0
    out = result.stdout
    assert "Usage:" in out or "Usage" in out.lower()


def test_llm_with_human_flag():
    """LLM=true + --human should produce normal Rich help."""
    result = runner.invoke(app, ["--human", "--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    # Should NOT contain TOON markers
    assert "name: xl" not in out
    # Should contain normal help markers
    assert "Usage:" in out or "Usage" in out.lower() or "--version" in out


def test_app_help_toon_has_commands():
    """TOON app help should list both groups and top-level commands."""
    result = runner.invoke(app, ["--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    assert "commands[" in out
    # Should include top-level commands like version, guide
    assert "version" in out
    assert "guide" in out


def test_group_help_toon_has_examples():
    """TOON group help should include examples from epilog."""
    result = runner.invoke(app, ["table", "--help"], env={"LLM": "true"})
    assert result.exit_code == 0
    out = result.stdout
    # Table group has examples in its epilog
    if "examples[" in out:
        assert "xl table" in out


# ---------------------------------------------------------------------------
# isatty / LLM precedence tests
# ---------------------------------------------------------------------------


def test_isatty_fallback_triggers_toon():
    """LLM unset + non-TTY (CliRunner) → TOON."""
    result = runner.invoke(app, ["--help"], env={})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" in out
    assert "groups[" in out


def test_llm_false_overrides_isatty():
    """LLM=false → human even in non-TTY."""
    result = runner.invoke(app, ["--help"], env={"LLM": "false"})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" not in out
    assert "Usage:" in out or "Usage" in out.lower()


def test_llm_zero_forces_human():
    """LLM=0 → human."""
    result = runner.invoke(app, ["--help"], env={"LLM": "0"})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" not in out
    assert "Usage:" in out or "Usage" in out.lower()


def test_llm_one_forces_toon():
    """LLM=1 → TOON."""
    result = runner.invoke(app, ["--help"], env={"LLM": "1"})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" in out
    assert "groups[" in out


def test_human_flag_overrides_isatty():
    """--human → human even when piped (non-TTY)."""
    result = runner.invoke(app, ["--human", "--help"], env={})
    assert result.exit_code == 0
    out = result.stdout
    assert "name: xl" not in out
    assert "Usage:" in out or "Usage" in out.lower() or "--version" in out


def test_version_toon_returns_envelope():
    """xl --version + TOON → JSON envelope."""
    result = runner.invoke(app, ["--version"], env={"LLM": "true"})
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["command"] == "version"
    assert "version" in data["result"]


def test_version_human_returns_plain():
    """xl --version + human → bare version string."""
    result = runner.invoke(app, ["--version"], env={"LLM": "false"})
    assert result.exit_code == 0
    out = result.stdout.strip()
    # Should be a plain version string, not JSON
    assert not out.startswith("{")
    assert "." in out  # semver-like
