"""Grep tool using ripgrep for fast code search."""

import asyncio
from pathlib import Path
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class GrepTool(BaseTool):
    """Search file contents using ripgrep."""

    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return """Search file contents using ripgrep (rg). Supports regex patterns.
Use for finding code by content, function definitions, variable usages, etc.
Results include file path, line number, and matching content."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Search pattern (regex supported). Use \\b for word boundaries.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file to search in. Defaults to workspace root.",
                },
                "file_type": {
                    "type": "string",
                    "description": "File type filter (e.g., 'py', 'ts', 'js', 'rs'). Optional.",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before/after match. Default: 0.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results. Default: 50.",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case sensitive search. Default: false (smart case).",
                },
                "whole_word": {
                    "type": "boolean",
                    "description": "Match whole words only. Default: false.",
                },
            },
            "required": ["pattern"],
            "additionalProperties": False,
        }

    async def execute(
        self,
        pattern: str,
        path: str | None = None,
        file_type: str | None = None,
        context_lines: int = 0,
        max_results: int = 50,
        case_sensitive: bool = False,
        whole_word: bool = False,
    ) -> ToolResult:
        """Execute ripgrep search."""
        search_path = Path(path) if path else self.workspace_root
        if not search_path.is_absolute():
            search_path = self.workspace_root / search_path

        if not search_path.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Path does not exist: {search_path}",
            )

        # Build rg command
        cmd = ["rg", "--json", "--line-number"]

        if not case_sensitive:
            cmd.append("--smart-case")
        else:
            cmd.append("--case-sensitive")

        if whole_word:
            cmd.append("--word-regexp")

        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])

        if file_type:
            cmd.extend(["--type", file_type])

        cmd.extend(["--max-count", str(max_results)])
        cmd.append(pattern)
        cmd.append(str(search_path))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode == 1:
                # No matches found
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output="No matches found.",
                    metadata={"match_count": 0},
                )

            if proc.returncode != 0 and proc.returncode != 1:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    error=f"ripgrep error: {stderr.decode()}",
                )

            # Parse JSON output
            output = self._parse_rg_json(stdout.decode(), search_path)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output["formatted"],
                metadata={"match_count": output["count"], "files": output["files"]},
            )

        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error="Search timed out after 30 seconds",
            )
        except FileNotFoundError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="ripgrep (rg) not found. Please install it: brew install ripgrep",
            )

    def _parse_rg_json(self, output: str, base_path: Path) -> dict:
        """Parse ripgrep JSON output into formatted results."""
        import json

        matches = []
        files = set()

        for line in output.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data["type"] == "match":
                    match_data = data["data"]
                    file_path = match_data["path"]["text"]
                    # Make path relative to workspace
                    try:
                        rel_path = Path(file_path).relative_to(base_path)
                    except ValueError:
                        rel_path = file_path

                    line_num = match_data["line_number"]
                    line_text = match_data["lines"]["text"].rstrip()

                    files.add(str(rel_path))
                    matches.append(f"{rel_path}:{line_num}: {line_text}")
            except (json.JSONDecodeError, KeyError):
                continue

        formatted = "\n".join(matches) if matches else "No matches found."

        return {"formatted": formatted, "count": len(matches), "files": list(files)}
