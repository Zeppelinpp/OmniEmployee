"""Tool registry for managing available tools."""

from typing import Any
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class ToolRegistry:
    """Registry for managing and executing tools."""
    
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
    
    def get(self, name: str) -> BaseTool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def get_definitions(self) -> list[dict]:
        """Get all tool definitions in OpenAI format."""
        return [tool.get_definition().to_openai_format() for tool in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Tool '{name}' not found"
            )
        
        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=str(e)
            )
    
    def get_tools_summary(self) -> str:
        """Get a summary of all tools for the system prompt."""
        lines = ["Available Tools:"]
        for tool in self._tools.values():
            lines.append(f"- {tool.name}: {tool.description}")
        return "\n".join(lines)

