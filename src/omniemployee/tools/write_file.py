"""Write file tool with atomic operations and backup support."""

import asyncio
from pathlib import Path
from datetime import datetime
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class WriteFileTool(BaseTool):
    """Write or edit file contents."""

    def __init__(self, workspace_root: str | None = None, create_backups: bool = True):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.create_backups = create_backups

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return """Write content to a file. Supports full file write or line-based edits.
For new files, creates parent directories automatically.
For existing files, can replace entire content or specific line ranges."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to write (relative to workspace or absolute).",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["overwrite", "append", "insert", "replace_lines"],
                    "description": "Write mode. Default: overwrite.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "For insert/replace_lines: starting line number (1-based).",
                },
                "end_line": {
                    "type": "integer",
                    "description": "For replace_lines: ending line number (inclusive).",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist. Default: true.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        }

    async def execute(
        self,
        path: str,
        content: str,
        mode: str = "overwrite",
        start_line: int | None = None,
        end_line: int | None = None,
        create_dirs: bool = True,
    ) -> ToolResult:
        """Write content to file."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_root / file_path

        # Validate mode
        if mode not in ["overwrite", "append", "insert", "replace_lines"]:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Invalid mode: {mode}. Must be one of: overwrite, append, insert, replace_lines",
            )

        # Validate line parameters for line-based modes
        if mode in ["insert", "replace_lines"] and start_line is None:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"start_line is required for mode: {mode}",
            )

        if mode == "replace_lines" and end_line is None:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="end_line is required for mode: replace_lines",
            )

        try:
            # Create parent directories if needed
            if create_dirs and not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle different modes
            if mode == "overwrite":
                result = await self._write_overwrite(file_path, content)
            elif mode == "append":
                result = await self._write_append(file_path, content)
            elif mode == "insert":
                result = await self._write_insert(file_path, content, start_line)
            elif mode == "replace_lines":
                result = await self._write_replace_lines(
                    file_path, content, start_line, end_line
                )
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR, error=f"Unknown mode: {mode}"
                )

            return result

        except PermissionError:
            return ToolResult(
                status=ToolResultStatus.ERROR, error=f"Permission denied: {path}"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR, error=f"Error writing file: {e}"
            )

    async def _write_overwrite(self, path: Path, content: str) -> ToolResult:
        """Overwrite entire file."""
        existed = path.exists()

        # Create backup if file exists
        if existed and self.create_backups:
            await self._create_backup(path)

        await self._write_atomic(path, content)

        lines = content.count("\n") + (
            1 if content and not content.endswith("\n") else 0
        )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"{'Updated' if existed else 'Created'} {path.name} ({lines} lines)",
            metadata={
                "path": str(path),
                "lines": lines,
                "bytes": len(content.encode("utf-8")),
                "created": not existed,
            },
        )

    async def _write_append(self, path: Path, content: str) -> ToolResult:
        """Append to file."""
        if path.exists():
            existing = await self._read_file(path)
            # Ensure newline before appending
            if existing and not existing.endswith("\n"):
                content = "\n" + content
            new_content = existing + content
        else:
            new_content = content

        await self._write_atomic(path, new_content)

        appended_lines = content.count("\n") + (
            1 if content and not content.endswith("\n") else 0
        )

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"Appended {appended_lines} lines to {path.name}",
            metadata={"path": str(path), "appended_lines": appended_lines},
        )

    async def _write_insert(
        self, path: Path, content: str, line_num: int
    ) -> ToolResult:
        """Insert content at specific line."""
        if not path.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"File not found: {path} (use mode='overwrite' to create)",
            )

        existing = await self._read_file(path)
        lines = existing.splitlines(keepends=True)

        # Adjust for 0-based index
        insert_idx = line_num - 1

        if insert_idx > len(lines):
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Line {line_num} exceeds file length ({len(lines)} lines)",
            )

        # Ensure content ends with newline
        if content and not content.endswith("\n"):
            content += "\n"

        # Insert content
        content_lines = content.splitlines(keepends=True)
        new_lines = lines[:insert_idx] + content_lines + lines[insert_idx:]

        if self.create_backups:
            await self._create_backup(path)

        await self._write_atomic(path, "".join(new_lines))

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"Inserted {len(content_lines)} lines at line {line_num} in {path.name}",
            metadata={
                "path": str(path),
                "inserted_at": line_num,
                "inserted_lines": len(content_lines),
            },
        )

    async def _write_replace_lines(
        self, path: Path, content: str, start_line: int, end_line: int
    ) -> ToolResult:
        """Replace specific line range."""
        if not path.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR, error=f"File not found: {path}"
            )

        existing = await self._read_file(path)
        lines = existing.splitlines(keepends=True)

        # Validate range
        if start_line > len(lines):
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"start_line {start_line} exceeds file length ({len(lines)} lines)",
            )

        if end_line > len(lines):
            end_line = len(lines)

        if start_line > end_line:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"start_line ({start_line}) must be <= end_line ({end_line})",
            )

        # Ensure content ends with newline
        if content and not content.endswith("\n"):
            content += "\n"

        # Replace lines
        content_lines = content.splitlines(keepends=True) if content else []
        new_lines = lines[: start_line - 1] + content_lines + lines[end_line:]

        if self.create_backups:
            await self._create_backup(path)

        await self._write_atomic(path, "".join(new_lines))

        replaced_count = end_line - start_line + 1

        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"Replaced lines {start_line}-{end_line} ({replaced_count} lines) with {len(content_lines)} lines in {path.name}",
            metadata={
                "path": str(path),
                "replaced_range": [start_line, end_line],
                "old_lines": replaced_count,
                "new_lines": len(content_lines),
            },
        )

    async def _read_file(self, path: Path) -> str:
        """Read file content."""
        import aiofiles

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return await f.read()

    async def _write_atomic(self, path: Path, content: str) -> None:
        """Write file atomically using temp file + rename."""
        import aiofiles

        temp_path = path.with_suffix(path.suffix + ".tmp")

        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            await f.write(content)

        # Atomic rename
        temp_path.rename(path)

    async def _create_backup(self, path: Path) -> None:
        """Create a backup of the file."""
        if not path.exists():
            return

        backup_dir = self.workspace_root / ".omniemployee" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{path.stem}_{timestamp}{path.suffix}"
        backup_path = backup_dir / backup_name

        import shutil

        shutil.copy2(path, backup_path)
