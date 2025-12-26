"""Message types for conversation context."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """Represents a tool call from the assistant."""
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    """Represents a tool execution result."""
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """A message in the conversation."""
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_result: ToolResult | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    
    # Token estimation (rough: ~4 chars per token)
    _estimated_tokens: int | None = None
    
    @property
    def estimated_tokens(self) -> int:
        """Estimate token count for this message."""
        if self._estimated_tokens is not None:
            return self._estimated_tokens
        
        total_chars = 0
        if self.content:
            total_chars += len(self.content)
        if self.tool_calls:
            for tc in self.tool_calls:
                total_chars += len(tc.name) + len(str(tc.arguments))
        if self.tool_result:
            total_chars += len(self.tool_result.content)
        
        self._estimated_tokens = total_chars // 4 + 10  # Add overhead
        return self._estimated_tokens
    
    def to_openai_format(self) -> dict:
        """Convert to OpenAI message format."""
        msg = {"role": self.role.value}
        
        if self.role == MessageRole.TOOL:
            if self.tool_result:
                return {
                    "role": "tool",
                    "tool_call_id": self.tool_result.tool_call_id,
                    "content": self.tool_result.content
                }
        
        if self.content:
            msg["content"] = self.content
        
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": str(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments
                    }
                }
                for tc in self.tool_calls
            ]
        
        return msg
    
    def summarize(self, max_length: int = 100) -> str:
        """Get a summary of this message."""
        content = self.content or ""
        if self.tool_calls:
            tool_names = [tc.name for tc in self.tool_calls]
            content = f"[Tools: {', '.join(tool_names)}] {content}"
        if self.tool_result:
            content = f"[Tool Result] {self.tool_result.content[:50]}..."
        
        if len(content) > max_length:
            return content[:max_length - 3] + "..."
        return content

