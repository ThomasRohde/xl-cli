"""TOON (Token-Oriented Object Notation) serializer.

Compact text format optimized for LLM consumption — 30-60% fewer tokens than JSON.

Rules:
- key: value for scalars (no braces, no quotes unless value contains commas/newlines)
- key[N]: v1,v2,v3 for simple scalar arrays
- Uniform object arrays → header row + comma-separated value rows
- Nested dicts → indented key:value blocks
- None → omitted, booleans → true/false
"""

from __future__ import annotations

from typing import Any


def to_toon(data: dict[str, Any], *, indent: int = 0) -> str:
    """Convert a dict to TOON text."""
    lines: list[str] = []
    prefix = "  " * indent
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(to_toon(value, indent=indent + 1))
        elif isinstance(value, list):
            lines.extend(_format_list(key, value, indent))
        else:
            lines.append(f"{prefix}{key}: {_format_scalar(value)}")
    return "\n".join(lines)


def _format_scalar(value: Any) -> str:
    """Format a scalar value for TOON output."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    if "," in s or "\n" in s:
        return f'"{s}"'
    return s


def _format_list(key: str, items: list, indent: int) -> list[str]:
    """Format a list for TOON output."""
    prefix = "  " * indent
    if not items:
        return [f"{prefix}{key}[0]:"]
    if _is_uniform_objects(items):
        return _format_uniform_objects(key, items, indent)
    # Simple scalar array
    scalars = [_format_scalar(v) for v in items if v is not None]
    if all(isinstance(v, (str, int, float, bool)) for v in items if v is not None):
        return [f"{prefix}{key}[{len(scalars)}]: {','.join(scalars)}"]
    # Fallback: one item per line
    lines = [f"{prefix}{key}[{len(items)}]:"]
    for item in items:
        if item is None:
            continue
        if isinstance(item, dict):
            lines.append(to_toon(item, indent=indent + 1))
        else:
            lines.append(f"{prefix}  {_format_scalar(item)}")
    return lines


def _is_uniform_objects(items: list) -> bool:
    """Check if all items are dicts with the same keys."""
    if not items or not all(isinstance(item, dict) for item in items):
        return False
    keys = set(items[0].keys())
    return all(set(item.keys()) == keys for item in items)


def _format_uniform_objects(key: str, items: list[dict], indent: int) -> list[str]:
    """Format a list of uniform dicts as header + value rows."""
    prefix = "  " * indent
    # Preserve key order from first item
    headers = list(items[0].keys())
    lines = [f"{prefix}{key}[{len(items)}]:"]
    lines.append(f"{prefix}  {','.join(headers)}")
    for item in items:
        values = [_format_scalar(item[h]) for h in headers]
        lines.append(f"{prefix}  {','.join(values)}")
    return lines
