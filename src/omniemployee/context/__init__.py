"""Context management for the agent."""

from src.omniemployee.context.manager import ContextManager, ContextConfig
from src.omniemployee.context.message import Message, MessageRole, ToolCall, ToolResult

__all__ = [
    "ContextManager",
    "ContextConfig", 
    "Message",
    "MessageRole",
    "ToolCall",
    "ToolResult"
]
