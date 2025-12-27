"""Run shell commands or execute scripts via bash/uv run."""

import asyncio
import os
from pathlib import Path
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class RunCommandTool(BaseTool):
    """Execute shell commands or Python scripts."""

    def __init__(self, workspace_root: str | None = None, timeout: int = 120):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return """Execute shell commands or Python scripts.
Supports:
- Direct bash commands (e.g., 'ls -la', 'echo hello')
- Python scripts via uv run (e.g., 'uv run script.py')
- Any shell executable command

Use working_dir to specify execution directory. Commands run in workspace root by default."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute. Can be a bash command or 'uv run <script.py>' for Python scripts.",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for command execution. Defaults to workspace root.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds. Default: 120.",
                },
                "env": {
                    "type": "object",
                    "description": "Additional environment variables to set.",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        }

    async def execute(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
        env: dict[str, str] | None = None,
    ) -> ToolResult:
        """Execute the command."""
        exec_timeout = timeout if timeout is not None else self.timeout

        cwd = Path(working_dir) if working_dir else self.workspace_root
        if not cwd.is_absolute():
            cwd = self.workspace_root / cwd

        if not cwd.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Working directory does not exist: {cwd}",
            )

        # Prepare environment
        exec_env = os.environ.copy()
        if env:
            exec_env.update(env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=exec_env,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=exec_timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()

            # Build output with command info
            output_parts = []

            # Add command information at the top
            output_parts.append(f"$ {command}")
            if working_dir and str(cwd) != str(self.workspace_root):
                output_parts.append(f"(in {cwd})")
            output_parts.append("")  # Empty line separator

            # Add command output
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(f"[stderr]\n{stderr_text}")

            if not stdout_text and not stderr_text:
                output_parts.append("(no output)")

            output = "\n".join(output_parts)

            if proc.returncode == 0:
                return ToolResult(
                    status=ToolResultStatus.SUCCESS,
                    output=output,
                    metadata={
                        "exit_code": proc.returncode,
                        "command": command,
                        "cwd": str(cwd),
                    },
                )
            else:
                return ToolResult(
                    status=ToolResultStatus.ERROR,
                    output=output,
                    error=f"Command exited with code {proc.returncode}",
                    metadata={
                        "exit_code": proc.returncode,
                        "command": command,
                        "cwd": str(cwd),
                    },
                )

        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolResultStatus.TIMEOUT,
                error=f"Command timed out after {exec_timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to execute command: {str(e)}",
            )
