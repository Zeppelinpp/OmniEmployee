"""Integration adapter for BIEM with ContextManager.

Provides the BIEMContextPlugin that augments ContextManager with
long-term memory capabilities.
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass

from src.omniemployee.memory.models import MemoryNode, DissonanceSignal
from src.omniemployee.memory.memory_manager import MemoryManager, MemoryConfig


@dataclass
class PluginConfig:
    """Configuration for BIEM Context Plugin."""
    # Automatic behavior
    auto_record_user_messages: bool = True
    auto_record_assistant_messages: bool = True
    auto_record_tool_results: bool = False
    
    # Context injection
    inject_memories_to_prompt: bool = True
    max_memories_in_context: int = 5
    memory_section_header: str = "## Relevant Memories"
    
    # Conflict handling
    report_conflicts: bool = True
    auto_resolve_low_priority: bool = True


class BIEMContextPlugin:
    """BIEM integration plugin for ContextManager.
    
    Augments the context management with:
    - Automatic recording of conversation turns
    - Memory injection into system prompt
    - Conflict detection and reporting
    - Event feedback recording
    
    Usage:
        # Create and attach to context manager
        memory_config = MemoryConfig(...)
        plugin = BIEMContextPlugin(memory_config)
        await plugin.initialize()
        
        # Before LLM call, inject memories
        memories_context = await plugin.prepare_context(user_input)
        
        # After conversation turn, record
        await plugin.record_turn(user_message, assistant_response)
    """
    
    def __init__(
        self,
        memory_config: MemoryConfig | None = None,
        plugin_config: PluginConfig | None = None
    ):
        self.memory = MemoryManager(memory_config or MemoryConfig())
        self.config = plugin_config or PluginConfig()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the memory system."""
        await self.memory.initialize()
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the memory system."""
        await self.memory.shutdown()
        self._initialized = False
    
    # ==================== Context Integration ====================
    
    async def prepare_context(self, current_input: str) -> str:
        """Prepare memory context for injection into system prompt.
        
        Args:
            current_input: Current user input or task
        
        Returns:
            Formatted memory context string
        """
        if not self.config.inject_memories_to_prompt:
            return ""
        
        return await self.memory.get_context(
            current_input,
            limit=self.config.max_memories_in_context
        )
    
    async def get_relevant_memories(
        self,
        query: str,
        limit: int | None = None
    ) -> list[MemoryNode]:
        """Get memories relevant to a query.
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of relevant MemoryNode objects
        """
        k = limit or self.config.max_memories_in_context
        return await self.memory.recall(query, top_k=k)
    
    # ==================== Recording ====================
    
    async def record_user_message(
        self,
        content: str,
        importance: float | None = None
    ) -> MemoryNode | None:
        """Record a user message to memory.
        
        Args:
            content: User message content
            importance: Optional explicit importance
        
        Returns:
            Created MemoryNode or None if disabled
        """
        if not self.config.auto_record_user_messages:
            return None
        
        node, conflicts = await self.memory.ingest(
            content,
            source="user",
            importance=importance
        )
        
        if conflicts and self.config.report_conflicts:
            await self._handle_conflicts(conflicts)
        
        return node
    
    async def record_assistant_message(
        self,
        content: str,
        related_memories: list[str] | None = None
    ) -> MemoryNode | None:
        """Record an assistant response to memory.
        
        Args:
            content: Assistant response content
            related_memories: IDs of memories that influenced this response
        
        Returns:
            Created MemoryNode or None if disabled
        """
        if not self.config.auto_record_assistant_messages:
            return None
        
        node, _ = await self.memory.ingest(
            content,
            source="assistant",
            importance=0.6  # Moderate importance for responses
        )
        
        return node
    
    async def record_tool_result(
        self,
        tool_name: str,
        result: str,
        importance: float = 0.5
    ) -> MemoryNode | None:
        """Record a tool execution result.
        
        Args:
            tool_name: Name of the tool
            result: Tool output
            importance: Importance score
        
        Returns:
            Created MemoryNode or None if disabled
        """
        if not self.config.auto_record_tool_results:
            return None
        
        content = f"[Tool: {tool_name}]\n{result}"
        
        node, _ = await self.memory.ingest(
            content,
            source="tool",
            importance=importance,
            metadata={"tool_name": tool_name}
        )
        
        return node
    
    async def record_turn(
        self,
        user_message: str,
        assistant_response: str,
        tool_calls: list[dict] | None = None
    ) -> dict[str, MemoryNode | None]:
        """Record a complete conversation turn.
        
        Args:
            user_message: User's input
            assistant_response: Assistant's response
            tool_calls: Optional list of tool calls made
        
        Returns:
            Dict with 'user', 'assistant', and 'tools' nodes
        """
        result = {
            "user": None,
            "assistant": None,
            "tools": []
        }
        
        # Record user message
        result["user"] = await self.record_user_message(user_message)
        
        # Record tool results
        if tool_calls and self.config.auto_record_tool_results:
            for tc in tool_calls:
                tool_node = await self.record_tool_result(
                    tc.get("name", "unknown"),
                    tc.get("result", "")
                )
                if tool_node:
                    result["tools"].append(tool_node)
        
        # Record assistant response
        related_ids = []
        if result["user"]:
            related_ids.append(result["user"].id)
        for tn in result["tools"]:
            related_ids.append(tn.id)
        
        result["assistant"] = await self.record_assistant_message(
            assistant_response,
            related_memories=related_ids if related_ids else None
        )
        
        return result
    
    # ==================== Feedback & Events ====================
    
    async def record_feedback(
        self,
        event_description: str,
        feedback_score: float,
        related_memory_ids: list[str] | None = None
    ) -> MemoryNode:
        """Record feedback for an interaction.
        
        Positive feedback strengthens related memories,
        negative feedback weakens them.
        
        Args:
            event_description: What happened
            feedback_score: Score from -1 (bad) to 1 (good)
            related_memory_ids: IDs of memories to reinforce
        
        Returns:
            Created event node
        """
        return await self.memory.record_event(
            event_type="feedback",
            content=event_description,
            feedback=feedback_score,
            related_node_ids=related_memory_ids
        )
    
    async def record_decision(
        self,
        decision: str,
        reasoning: str | None = None,
        related_memory_ids: list[str] | None = None
    ) -> MemoryNode:
        """Record an agent decision.
        
        Args:
            decision: The decision made
            reasoning: Optional reasoning
            related_memory_ids: IDs of memories that influenced decision
        
        Returns:
            Created event node
        """
        content = decision
        if reasoning:
            content = f"{decision}\n\nReasoning: {reasoning}"
        
        return await self.memory.record_event(
            event_type="decision",
            content=content,
            feedback=0.5,  # Neutral initially
            related_node_ids=related_memory_ids
        )
    
    # ==================== Conflict Handling ====================
    
    async def _handle_conflicts(self, conflicts: list[DissonanceSignal]) -> None:
        """Handle detected conflicts."""
        for signal in conflicts:
            if (self.config.auto_resolve_low_priority 
                and signal.priority < 0.5):
                # Auto-resolve low priority conflicts
                await self.memory.resolve_conflict(
                    signal.conflict.id,
                    action="ignore"
                )
    
    def get_pending_conflicts(self) -> list[DissonanceSignal]:
        """Get list of unresolved conflicts."""
        return self.memory.get_pending_conflicts()
    
    async def resolve_conflict(
        self,
        conflict_id: str,
        action: str
    ) -> bool:
        """Manually resolve a conflict.
        
        Args:
            conflict_id: ID of the conflict
            action: Resolution action (keep_new, keep_old, merge, ignore)
        
        Returns:
            True if resolved successfully
        """
        return await self.memory.resolve_conflict(conflict_id, action)
    
    # ==================== Direct Access ====================
    
    async def get_working_memory(self, limit: int = 10) -> list[MemoryNode]:
        """Get current working memory contents."""
        return await self.memory.get_working_memory(limit)
    
    async def forget(self, node_id: str) -> bool:
        """Explicitly forget a memory.
        
        Args:
            node_id: ID of memory to delete
        
        Returns:
            True if deleted
        """
        return await self.memory.delete_node(node_id)
    
    async def remember_explicitly(
        self,
        content: str,
        importance: float = 1.0
    ) -> MemoryNode:
        """Explicitly remember something with high importance.
        
        Use this when user says "remember this" or similar.
        
        Args:
            content: What to remember
            importance: Importance score (default: 1.0 = very important)
        
        Returns:
            Created MemoryNode
        """
        node, _ = await self.memory.ingest(
            content,
            source="user_explicit",
            importance=importance,
            metadata={"explicit_remember": True}
        )
        return node
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        return await self.memory.get_stats()
    
    def format_stats_summary(self, stats: dict) -> str:
        """Format stats as human-readable summary."""
        lines = ["Memory System Status:"]
        
        if "l1" in stats:
            l1 = stats["l1"]
            lines.append(f"  L1 (Working): {l1.get('count', 0)}/{l1.get('capacity', 0)} nodes")
        
        if "l2_vector" in stats:
            l2v = stats["l2_vector"]
            lines.append(f"  L2 (Vector): {l2v.get('row_count', 0)} nodes indexed")
        
        if "l2_graph" in stats:
            l2g = stats["l2_graph"]
            lines.append(f"  L2 (Graph): {l2g.get('node_count', 0)} nodes, {l2g.get('edge_count', 0)} edges")
        
        if "l3" in stats:
            l3 = stats["l3"]
            lines.append(f"  L3 (Crystal): {l3.get('facts_count', 0)} facts")
        
        lines.append(f"  Pending conflicts: {stats.get('pending_conflicts', 0)}")
        
        return "\n".join(lines)
