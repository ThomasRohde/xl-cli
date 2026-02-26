# XL-CLI Workspace Instructions

## Code Style
- **Python Version**: 3.12+ features (use `from __future__ import annotations`).
- **Typing**: Strict type hints required. Use `Annotated` for Typer CLI arguments.
- **Serialization**: Use `orjson` for high-performance JSON handling.
- **Models**: Use Pydantic v2 models for all data contracts (`src/xl/contracts/`).
- **Docstrings**: Concise Google-style docstrings.

## Architecture
- **Agent-First Design**: The CLI is designed to be driven by agents. All commands output machine-readable JSON wrapped in a `ResponseEnvelope`.
- **Dispatcher Pattern**: `src/xl/engine/dispatcher.py` handles the standardized response formatting and exit codes.
- **Context**: `WorkbookContext` (`src/xl/engine/context.py`) manages the state of the loaded workbook.
- **Adapters**: Interactions with Excel are isolated in `src/xl/adapters/` (primarily `openpyxl_engine.py`).
- **IO**: Atomic writes and file operations in `src/xl/io/fileops.py`.

## Build and Test
- **Package Manager**: `uv` (preferred) or `pip`.
- **Install**: `uv sync`
- **Test**: `uv run pytest tests/ -v`
- **Lint**: Follow existing patterns (ruff/black implied by code style).

## Project Conventions
- **Response Format**: EVERY command must return a `ResponseEnvelope` (see `src/xl/contracts/common.py`).
  - Fields: `ok`, `command`, `result`, `errors`, `warnings`, `metrics`.
- **Exit Codes**: Strict taxonomy (0=success, 10=validation, 40=conflict, 50=io, etc.). See `src/xl/engine/dispatcher.py`.
- **Boolean Flags**: Use Typer's `Annotated[bool, typer.Option("--feature/--no-feature")]` pattern for boolean toggles (e.g., `--backup/--no-backup`).
- **Fingerprinting**: Use SHA-256 (`sha256:...`) to uniquely identify workbook state.
- **Safety**:
  - Implement `--dry-run` for all mutating commands.
  - Implement `--backup` for file writes.
- **OpenPyXL**:
  - Iterate defined names via `wb.defined_names.values()`.
  - Access tables via `ws._tables.values()` (internal API required for object access).
  - Note: `table.tableColumns` may be empty until saved/reloaded in tests.

## Integration Points
- **Excel**: strict isolation via `openpyxl`.
- **DuckDB**: (Planned) usage for SQL querying of table data.
