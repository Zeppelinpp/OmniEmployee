"""Base classes for tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class ToolResultStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    status: ToolResultStatus
    output: Any = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.status == ToolResultStatus.SUCCESS
    
    def to_message(self) -> str:
        """Convert result to a message for the LLM."""
        if self.success:
            return str(self.output) if self.output else "Operation completed successfully."
        return f"Error: {self.error}"


@dataclass
class ToolDefinition:
    """Tool definition for LLM."""
    name: str
    description: str
    input_schema: dict
    
    def to_openai_format(self) -> dict:
        """Convert to OpenAI function format.
        
        Ensures the schema is compatible with various LLM providers including DashScope.
        """
        # Ensure schema has required fields for strict JSON validation
        schema = dict(self.input_schema)
        if "type" not in schema:
            schema["type"] = "object"
        if "properties" not in schema:
            schema["properties"] = {}
        if "required" not in schema:
            schema["required"] = []
        if "additionalProperties" not in schema:
            schema["additionalProperties"] = False
            
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema
            }
        }


class BaseTool(ABC):
    """Base class for all tools."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    @property
    @abstractmethod
    def input_schema(self) -> dict:
        """JSON schema for tool input."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments."""
        pass
    
    def get_definition(self) -> ToolDefinition:
        """Get the tool definition."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema
        )

