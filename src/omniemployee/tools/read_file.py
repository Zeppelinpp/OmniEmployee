"""Read file tool with smart chunking and line number support."""

import asyncio
from pathlib import Path
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class ReadFileTool(BaseTool):
    """Read file contents with optional line range."""
    
    # Token estimation: ~4 chars per token
    MAX_CHARS_DEFAULT = 32000  # ~8k tokens
    
    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return """Read file contents. Supports reading entire file or specific line ranges.
For large files, use start_line and end_line to read specific sections.
Returns content with line numbers for easy reference."""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read (relative to workspace or absolute)."
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-based). Optional."
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive). Optional."
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to return. Default: 500."
                }
            },
            "required": ["path"],
            "additionalProperties": False
        }
    
    async def execute(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        max_lines: int = 500
    ) -> ToolResult:
        """Read file contents."""
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.workspace_root / file_path
        
        if not file_path.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"File not found: {path}"
            )
        
        if not file_path.is_file():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Path is not a file: {path}"
            )
        
        try:
            # Check file size first
            file_size = file_path.stat().st_size
            
            # Read file
            content = await self._read_file_async(file_path)
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)
            
            # Apply line range
            actual_start = (start_line or 1) - 1  # Convert to 0-based
            actual_end = end_line or total_lines
            
            # Validate range
            if actual_start >= total_lines:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"start_line {start_line} exceeds file length ({total_lines} lines)"
                )
            
            actual_end = min(actual_end, total_lines)
            
            # Check if we need to truncate
            requested_lines = actual_end - actual_start
            if requested_lines > max_lines:
                actual_end = actual_start + max_lines
                truncated = True
            else:
                truncated = False
            
            # Extract lines
            selected_lines = lines[actual_start:actual_end]
            
            # Format with line numbers
            formatted_lines = []
            for i, line in enumerate(selected_lines, start=actual_start + 1):
                # Right-align line numbers
                line_content = line.rstrip('\n\r')
                formatted_lines.append(f"{i:6}| {line_content}")
            
            output = "\n".join(formatted_lines)
            
            # Add metadata header
            rel_path = file_path.relative_to(self.workspace_root) if file_path.is_relative_to(self.workspace_root) else file_path
            header = f"File: {rel_path} (lines {actual_start + 1}-{actual_end} of {total_lines})"
            if truncated:
                header += f"\n[Truncated: showing {max_lines} lines, {requested_lines - max_lines} more available]"
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"{header}\n{'─' * 60}\n{output}",
                metadata={
                    "path": str(rel_path),
                    "total_lines": total_lines,
                    "start_line": actual_start + 1,
                    "end_line": actual_end,
                    "truncated": truncated,
                    "file_size": file_size
                }
            )
            
        except UnicodeDecodeError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Cannot read file: {path} (binary or non-UTF-8 encoding)"
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Error reading file: {e}"
            )
    
    async def _read_file_async(self, path: Path) -> str:
        """Read file asynchronously."""
        import aiofiles
        async with aiofiles.open(path, 'r', encoding='utf-8') as f:
            return await f.read()

