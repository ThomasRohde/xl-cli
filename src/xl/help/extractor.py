"""Extract structured help data from Click/Typer command objects."""

from __future__ import annotations

import re
from typing import Any

import click


# Options to omit from TOON output (noise for LLMs)
_HIDDEN_OPTIONS = {"--help", "--install-completion", "--show-completion"}


def extract_app_help(group: click.Group, ctx: click.Context) -> dict[str, Any]:
    """Extract top-level app help data."""
    from xl import __version__

    groups: list[dict[str, str]] = []
    commands: list[dict[str, str]] = []

    for name, cmd in sorted(group.commands.items()):
        if cmd.hidden:
            continue
        short_help = cmd.get_short_help_str(limit=300)
        short_help = _strip_markdown(short_help)
        entry = {"name": name, "description": short_help}
        if isinstance(cmd, click.Group):
            groups.append(entry)
        else:
            commands.append(entry)

    data: dict[str, Any] = {
        "name": ctx.info_name or "xl",
        "version": __version__,
        "description": _strip_markdown(_get_short_description(group)),
    }
    options = _extract_options(group, ctx)
    if options:
        data["options"] = options
    if groups:
        data["groups"] = groups
    if commands:
        data["commands"] = commands
    return data


def extract_group_help(group: click.Group, ctx: click.Context) -> dict[str, Any]:
    """Extract group-level help data."""
    cmds: list[dict[str, str]] = []
    for name, cmd in sorted(group.commands.items()):
        if cmd.hidden:
            continue
        short_help = cmd.get_short_help_str(limit=300)
        cmds.append({"name": name, "description": _strip_markdown(short_help)})

    data: dict[str, Any] = {
        "group": ctx.info_name or group.name or "",
        "description": _strip_markdown(_get_short_description(group)),
    }
    if cmds:
        data["commands"] = cmds

    examples = _parse_examples(group.help or "")
    epilog_examples = _parse_examples(group.epilog or "")
    all_examples = examples + epilog_examples
    if all_examples:
        data["examples"] = all_examples
    return data


def extract_command_help(cmd: click.Command, ctx: click.Context) -> dict[str, Any]:
    """Extract command-level help data."""
    data: dict[str, Any] = {
        "command": ctx.command_path,
        "description": _strip_markdown(_get_short_description(cmd)),
    }

    options = _extract_options(cmd, ctx)
    if options:
        data["options"] = options

    examples = _parse_examples(cmd.help or "")
    epilog_examples = _parse_examples(cmd.epilog or "")
    all_examples = examples + epilog_examples
    if all_examples:
        data["examples"] = all_examples

    see_also = _parse_see_also(cmd.help or "")
    if see_also:
        data["see_also"] = see_also

    return data


def _extract_options(cmd: click.Command, ctx: click.Context) -> list[dict[str, Any]]:
    """Extract option metadata from a command."""
    options: list[dict[str, Any]] = []
    for param in cmd.get_params(ctx):
        if not isinstance(param, click.Option):
            continue
        # Build flag string
        flag = "/".join(param.opts + param.secondary_opts)
        if flag in _HIDDEN_OPTIONS or any(o in _HIDDEN_OPTIONS for o in param.opts):
            continue

        # Determine type
        is_flag = param.is_flag
        type_name = "flag" if is_flag else _click_type_name(param.type)

        required = param.required
        default = param.default
        if is_flag:
            default = "true" if default else "false"
        elif default is None:
            default = ""
        else:
            default = str(default)

        help_text = _strip_markdown(param.help or "")

        opt: dict[str, Any] = {
            "flag": flag,
            "type": type_name,
            "required": "true" if required else "false",
            "default": default,
            "help": help_text,
        }
        options.append(opt)
    return options


def _click_type_name(t: click.ParamType) -> str:
    """Get a short type name from a Click parameter type."""
    name = t.name.lower()
    mapping = {
        "string": "text",
        "int": "int",
        "float": "float",
        "bool": "flag",
        "path": "path",
        "choice": "choice",
    }
    return mapping.get(name, name)


def _get_short_description(cmd: click.BaseCommand) -> str:
    """Get the first line of a command's help text."""
    text = cmd.help or ""
    if not text:
        return ""
    # Take first sentence or first line
    first_line = text.strip().split("\n")[0]
    return first_line.strip()


def _strip_markdown(text: str) -> str:
    """Remove Rich/Markdown formatting from text."""
    # Remove backtick code spans
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    # Remove italic markers
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text.strip()


def _parse_examples(text: str) -> list[str]:
    """Extract example command lines from help text."""
    examples: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        # Match lines that look like example commands
        # e.g. "xl table add-column ..." or "`xl table add-column ...`"
        cleaned = re.sub(r"^`|`$", "", stripped)
        cleaned = re.sub(r"`\s*—.*$", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned.startswith("xl ") and not cleaned.startswith("xl is"):
            examples.append(cleaned)
    return examples


def _parse_see_also(text: str) -> list[str]:
    """Extract see-also references from help text."""
    refs: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip().lower()
        if "see also" in stripped or "see:" in stripped:
            # Extract xl commands from the line
            for match in re.finditer(r"xl\s+[\w\-]+(?:\s+[\w\-]+)*", line):
                refs.append(match.group())
    return refs
