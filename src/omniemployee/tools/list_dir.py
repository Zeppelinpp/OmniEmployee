"""List directory tool with tree-like output."""

import asyncio
from pathlib import Path
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class ListDirTool(BaseTool):
    """List directory contents with optional tree view."""
    
    def __init__(self, workspace_root: str | None = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
    
    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return """List directory contents. Shows files and subdirectories.
Use to explore project structure, find files, or understand codebase layout.
Respects .gitignore by default."""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Defaults to workspace root."
                },
                "depth": {
                    "type": "integer",
                    "description": "Maximum depth for recursive listing. Default: 1 (current dir only)."
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "Show hidden files (starting with dot). Default: false."
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py', '*.ts'). Optional."
                },
                "dirs_only": {
                    "type": "boolean",
                    "description": "Show only directories. Default: false."
                }
            },
            "required": [],
            "additionalProperties": False
        }
    
    async def execute(
        self,
        path: str | None = None,
        depth: int = 1,
        show_hidden: bool = False,
        pattern: str | None = None,
        dirs_only: bool = False
    ) -> ToolResult:
        """List directory contents."""
        target_path = Path(path) if path else self.workspace_root
        if not target_path.is_absolute():
            target_path = self.workspace_root / target_path
        
        if not target_path.exists():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Path does not exist: {target_path}"
            )
        
        if not target_path.is_dir():
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Path is not a directory: {target_path}"
            )
        
        try:
            # Use fd for fast directory listing if available, fallback to Python
            output = await self._list_with_fd(
                target_path, depth, show_hidden, pattern, dirs_only
            )
            
            if output is None:
                # Fallback to Python implementation
                output = self._list_with_python(
                    target_path, depth, show_hidden, pattern, dirs_only
                )
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output["formatted"],
                metadata={
                    "total_items": output["count"],
                    "path": str(target_path)
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e)
            )
    
    async def _list_with_fd(
        self,
        path: Path,
        depth: int,
        show_hidden: bool,
        pattern: str | None,
        dirs_only: bool
    ) -> dict | None:
        """Use fd for fast listing."""
        cmd = ["fd", "--base-directory", str(path)]
        
        if depth > 0:
            cmd.extend(["--max-depth", str(depth)])
        
        if show_hidden:
            cmd.append("--hidden")
        
        if dirs_only:
            cmd.extend(["--type", "d"])
        
        if pattern:
            # Convert glob to regex
            regex_pattern = pattern.replace("*", ".*").replace("?", ".")
            cmd.extend(["--regex", regex_pattern])
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            
            if proc.returncode != 0:
                return None
            
            items = [line for line in stdout.decode().strip().split("\n") if line]
            items.sort()
            
            return {
                "formatted": self._format_tree(items, path),
                "count": len(items)
            }
            
        except (FileNotFoundError, asyncio.TimeoutError):
            return None
    
    def _list_with_python(
        self,
        path: Path,
        depth: int,
        show_hidden: bool,
        pattern: str | None,
        dirs_only: bool
    ) -> dict:
        """Python fallback for directory listing."""
        items = []
        
        def collect_items(current_path: Path, current_depth: int, prefix: str = ""):
            if current_depth > depth:
                return
            
            try:
                entries = sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            except PermissionError:
                return
            
            for entry in entries:
                # Skip hidden files unless requested
                if not show_hidden and entry.name.startswith("."):
                    continue
                
                # Apply pattern filter
                if pattern and not entry.match(pattern) and not entry.is_dir():
                    continue
                
                # Skip files if dirs_only
                if dirs_only and not entry.is_dir():
                    continue
                
                rel_path = entry.relative_to(path)
                items.append(str(rel_path))
                
                # Recurse into directories
                if entry.is_dir() and current_depth < depth:
                    collect_items(entry, current_depth + 1, prefix + "  ")
        
        collect_items(path, 1)
        
        return {
            "formatted": self._format_tree(items, path),
            "count": len(items)
        }
    
    def _format_tree(self, items: list[str], base_path: Path) -> str:
        """Format items as a tree structure."""
        if not items:
            return f"Directory is empty: {base_path}"
        
        lines = [f"📁 {base_path.name}/"]
        
        # Build tree structure
        for item in items:
            parts = Path(item).parts
            indent = "  " * (len(parts) - 1)
            name = parts[-1]
            
            # Check if it's a directory
            full_path = base_path / item
            if full_path.is_dir():
                lines.append(f"{indent}├── 📁 {name}/")
            else:
                lines.append(f"{indent}├── {name}")
        
        return "\n".join(lines)

