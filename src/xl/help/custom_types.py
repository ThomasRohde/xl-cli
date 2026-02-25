"""Monkey-patch Typer help formatting to emit TOON when LLM=true."""

from __future__ import annotations

import os
import sys

import click


def _human_flag_set(ctx: click.Context | None) -> bool:
    """Check if --human was passed, walking up the context chain."""
    while ctx is not None:
        if ctx.params.get("human"):
            return True
        ctx = ctx.parent
    return False


def should_use_toon(ctx: click.Context | None = None) -> bool:
    """Check if TOON help output should be used."""
    if os.environ.get("LLM", "").lower() != "true":
        return False
    # Check both sys.argv (real CLI) and Click context (CliRunner)
    if "--human" in sys.argv:
        return False
    if ctx is not None and _human_flag_set(ctx):
        return False
    return True


def patch_typer_help() -> None:
    """Patch Typer/Click Group and Command format_help to emit TOON."""
    import typer.core

    _orig_group_format_help = typer.core.TyperGroup.format_help
    _orig_command_format_help = typer.core.TyperCommand.format_help

    def _toon_group_format_help(self: click.Group, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if not should_use_toon(ctx):
            _orig_group_format_help(self, ctx, formatter)
            return

        from xl.help.extractor import extract_app_help, extract_group_help
        from xl.help.toon import to_toon

        # Top-level app group vs subcommand group
        if ctx.parent is None:
            data = extract_app_help(self, ctx)
        else:
            data = extract_group_help(self, ctx)

        formatter.write(to_toon(data))
        formatter.write("\n")

    def _toon_command_format_help(self: click.Command, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        if not should_use_toon(ctx):
            _orig_command_format_help(self, ctx, formatter)
            return

        from xl.help.extractor import extract_command_help
        from xl.help.toon import to_toon

        data = extract_command_help(self, ctx)
        formatter.write(to_toon(data))
        formatter.write("\n")

    typer.core.TyperGroup.format_help = _toon_group_format_help
    typer.core.TyperCommand.format_help = _toon_command_format_help


def patch_typer_errors() -> None:
    """Patch TyperGroup.invoke to emit JSON envelopes for CLI usage errors."""
    import typer.core

    _orig_invoke = typer.core.TyperGroup.invoke

    def _json_invoke(self, ctx):
        try:
            return _orig_invoke(self, ctx)
        except click.exceptions.UsageError as e:
            from xl.engine.dispatcher import error_envelope, exit_code_for, print_response
            env = error_envelope("unknown", "ERR_USAGE", str(e.format_message()))
            print_response(env)
            raise SystemExit(exit_code_for(env)) from e

    typer.core.TyperGroup.invoke = _json_invoke
