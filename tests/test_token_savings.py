"""Estimate token savings of TOON help vs Rich help output.

Uses tiktoken (cl100k_base) if available, otherwise falls back to
a chars/4 approximation. Run with:

    uv run pytest tests/test_token_savings.py -v -s
"""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from xl.cli import app

runner = CliRunner()

# Try tiktoken for accurate token counts; fall back to char/4 heuristic
try:
    import tiktoken
    _enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_enc.encode(text))

    TOKEN_METHOD = "tiktoken cl100k_base"
except ImportError:
    def count_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    TOKEN_METHOD = "chars/4 approximation"


# Commands to benchmark: (args, label)
_COMMANDS: list[tuple[list[str], str]] = [
    (["--help"], "xl --help"),
    (["wb", "--help"], "xl wb --help"),
    (["table", "--help"], "xl table --help"),
    (["table", "add-column", "--help"], "xl table add-column --help"),
    (["cell", "--help"], "xl cell --help"),
    (["formula", "--help"], "xl formula --help"),
    (["format", "--help"], "xl format --help"),
    (["validate", "--help"], "xl validate --help"),
    (["plan", "--help"], "xl plan --help"),
    (["verify", "--help"], "xl verify --help"),
    (["diff", "--help"], "xl diff --help"),
    (["sheet", "--help"], "xl sheet --help"),
    (["range", "--help"], "xl range --help"),
    (["table", "ls", "--help"], "xl table ls --help"),
    (["table", "append-rows", "--help"], "xl table append-rows --help"),
    (["cell", "get", "--help"], "xl cell get --help"),
    (["cell", "set", "--help"], "xl cell set --help"),
    (["formula", "set", "--help"], "xl formula set --help"),
    (["formula", "lint", "--help"], "xl formula lint --help"),
    (["format", "number", "--help"], "xl format number --help"),
    (["format", "width", "--help"], "xl format width --help"),
]


def _get_outputs(args: list[str]) -> tuple[str, str]:
    """Return (rich_output, toon_output) for a command."""
    rich = runner.invoke(app, args, env={"LLM": "false"})
    toon = runner.invoke(app, args, env={"LLM": "true"})
    assert rich.exit_code == 0, f"Rich help failed for {args}: {rich.output}"
    assert toon.exit_code == 0, f"TOON help failed for {args}: {toon.output}"
    return rich.output, toon.output


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestTokenSavings:
    """Estimate and report token savings across all help commands."""

    @pytest.fixture(autouse=True, scope="class")
    def _collect(self, request):
        """Run once per class — gather all measurements."""
        rows: list[dict] = []
        total_rich = 0
        total_toon = 0

        for args, label in _COMMANDS:
            rich_out, toon_out = _get_outputs(args)
            rich_clean = _strip_ansi(rich_out)
            toon_clean = _strip_ansi(toon_out)

            rich_tokens = count_tokens(rich_clean)
            toon_tokens = count_tokens(toon_clean)
            saved = rich_tokens - toon_tokens
            pct = (saved / rich_tokens * 100) if rich_tokens else 0

            rows.append({
                "label": label,
                "rich_chars": len(rich_clean),
                "toon_chars": len(toon_clean),
                "rich_tokens": rich_tokens,
                "toon_tokens": toon_tokens,
                "saved": saved,
                "pct": pct,
            })
            total_rich += rich_tokens
            total_toon += toon_tokens

        request.cls.rows = rows
        request.cls.total_rich = total_rich
        request.cls.total_toon = total_toon

    def test_overall_savings_at_least_30_pct(self):
        """TOON should save at least 30% of tokens overall."""
        saved_pct = (self.total_rich - self.total_toon) / self.total_rich * 100
        assert saved_pct >= 30, f"Only {saved_pct:.1f}% savings — expected >= 30%"

    def test_every_command_saves_tokens(self):
        """Every help page should be smaller in TOON than Rich."""
        for row in self.rows:
            assert row["toon_tokens"] < row["rich_tokens"], (
                f"{row['label']}: TOON ({row['toon_tokens']}) >= Rich ({row['rich_tokens']})"
            )

    def test_print_report(self, capsys):
        """Print a detailed report (visible with -s flag)."""
        total_saved = self.total_rich - self.total_toon
        total_pct = (total_saved / self.total_rich * 100) if self.total_rich else 0

        lines = [
            "",
            f"Token Savings Report  (method: {TOKEN_METHOD})",
            "=" * 78,
            f"{'Command':<35} {'Rich':>7} {'TOON':>7} {'Saved':>7} {'%':>6}",
            "-" * 78,
        ]
        for r in self.rows:
            lines.append(
                f"{r['label']:<35} {r['rich_tokens']:>7} {r['toon_tokens']:>7} "
                f"{r['saved']:>7} {r['pct']:>5.1f}%"
            )
        lines.append("-" * 78)
        lines.append(
            f"{'TOTAL':<35} {self.total_rich:>7} {self.total_toon:>7} "
            f"{total_saved:>7} {total_pct:>5.1f}%"
        )
        lines.append("=" * 78)
        lines.append("")

        report = "\n".join(lines)
        print(report)
