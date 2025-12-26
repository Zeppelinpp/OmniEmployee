"""Context manager with progressive disclosure and smart compression."""

from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any
from src.omniemployee.context.message import Message, MessageRole, ToolCall, ToolResult


@dataclass
class ContextConfig:
    """Configuration for context management."""
    max_tokens: int = 128000  # Model's context window (will be auto-detected)
    reserved_for_output: int = 4096  # Reserve for model output
    skill_token_budget: int = 8000  # Budget per loaded skill
    compress_threshold: float = 0.7  # Trigger LLM compression at 70% of max
    keep_recent_turns: int = 5  # Always keep N recent conversation turns
    summarize_tool_results: bool = True  # Summarize long tool outputs
    
    # LLM compression settings
    llm_compress_enabled: bool = True  # Enable LLM-based summarization
    llm_compress_model: str | None = None  # Model for compression (None = use same model)


class ContextManager:
    """Manages conversation context with progressive disclosure."""
    
    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self._messages: list[Message] = []
        self._system_prompt: str = ""
        self._loaded_skills: dict[str, str] = {}  # skill_name -> full instructions
        self._skill_metadata: dict[str, dict] = {}  # skill_name -> metadata only
        self._loaded_references: dict[str, str] = {}  # "skill:ref_path" -> content (Phase 3)
        self._current_tokens: int = 0
        
        # LLM compression callback (set by AgentLoop)
        self._llm_summarize_callback: Callable[[str], Awaitable[str]] | None = None
        self._compression_pending: bool = False
    
    @property
    def available_tokens(self) -> int:
        """Tokens available for new content."""
        return self.config.max_tokens - self.config.reserved_for_output - self._current_tokens
    
    @property
    def messages(self) -> list[Message]:
        """Get all messages."""
        return self._messages.copy()
    
    def set_system_prompt(self, prompt: str) -> None:
        """Set the base system prompt."""
        old_tokens = len(self._system_prompt) // 4
        self._system_prompt = prompt
        new_tokens = len(prompt) // 4
        self._current_tokens += (new_tokens - old_tokens)
    
    def add_message(self, message: Message) -> None:
        """Add a message to the context."""
        tokens = message.estimated_tokens
        
        # Check if we need to trigger compression
        if self._current_tokens + tokens > self.config.max_tokens * self.config.compress_threshold:
            self._compression_pending = True
        
        self._messages.append(message)
        self._current_tokens += tokens
    
    def set_llm_summarize_callback(self, callback: Callable[[str], Awaitable[str]]) -> None:
        """Set the callback for LLM-based summarization."""
        self._llm_summarize_callback = callback
    
    def needs_compression(self) -> bool:
        """Check if context compression is needed."""
        return self._compression_pending
    
    async def compress_context_async(self) -> str | None:
        """Compress context using LLM summarization.
        
        Returns:
            Summary of compressed content, or None if compression not needed/failed.
        """
        if not self._compression_pending:
            return None
        
        self._compression_pending = False
        
        # If LLM compression is enabled and callback is set
        if self.config.llm_compress_enabled and self._llm_summarize_callback:
            summary = await self._compress_with_llm()
            if summary:
                return summary
        
        # Fallback to simple compression
        self._compress_context()
        return None
    
    def add_user_message(self, content: str) -> Message:
        """Add a user message."""
        msg = Message(role=MessageRole.USER, content=content)
        self.add_message(msg)
        return msg
    
    def add_assistant_message(
        self, 
        content: str | None = None, 
        tool_calls: list[ToolCall] | None = None
    ) -> Message:
        """Add an assistant message."""
        msg = Message(role=MessageRole.ASSISTANT, content=content, tool_calls=tool_calls)
        self.add_message(msg)
        return msg
    
    def add_tool_result(self, tool_call_id: str, content: str, is_error: bool = False) -> Message:
        """Add a tool result message."""
        # Optionally summarize long tool results
        if self.config.summarize_tool_results and len(content) > 2000:
            content = self._summarize_tool_result(content)
        
        result = ToolResult(tool_call_id=tool_call_id, content=content, is_error=is_error)
        msg = Message(role=MessageRole.TOOL, tool_result=result)
        self.add_message(msg)
        return msg
    
    # ==================== Skill Progressive Disclosure ====================
    
    def register_skill_metadata(self, name: str, metadata: dict) -> None:
        """Register skill metadata for progressive disclosure (Phase 1)."""
        self._skill_metadata[name] = metadata
    
    def load_skill(self, name: str, instructions: str) -> bool:
        """Load full skill instructions (Phase 2 - on demand)."""
        if name in self._loaded_skills:
            return True  # Already loaded
        
        tokens = len(instructions) // 4
        
        # Check budget
        if tokens > self.config.skill_token_budget:
            return False
        
        if self._current_tokens + tokens > self.config.max_tokens * 0.9:
            # Try to make room by unloading unused skills
            self._unload_unused_skills()
        
        self._loaded_skills[name] = instructions
        self._current_tokens += tokens
        return True
    
    def unload_skill(self, name: str) -> None:
        """Unload a skill to free up context space."""
        if name in self._loaded_skills:
            tokens = len(self._loaded_skills[name]) // 4
            del self._loaded_skills[name]
            self._current_tokens -= tokens
        
        # Also unload any references for this skill
        refs_to_remove = [k for k in self._loaded_references if k.startswith(f"{name}:")]
        for ref_key in refs_to_remove:
            self.unload_skill_reference(ref_key)
    
    def get_skill_summary(self) -> str:
        """Get summary of available skills (for system prompt)."""
        if not self._skill_metadata:
            return ""
        
        lines = ["## Available Skills (use when needed)"]
        for name, meta in self._skill_metadata.items():
            loaded = "✓" if name in self._loaded_skills else "○"
            desc = meta.get("description", "No description")
            lines.append(f"- [{loaded}] **{name}**: {desc}")
        
        return "\n".join(lines)
    
    def get_loaded_skill_instructions(self) -> str:
        """Get instructions for all loaded skills."""
        if not self._loaded_skills and not self._loaded_references:
            return ""
        
        sections = []
        
        if self._loaded_skills:
            sections.append("## Loaded Skill Instructions")
            for name, instructions in self._loaded_skills.items():
                sections.append(f"\n### Skill: {name}\n{instructions}")
        
        if self._loaded_references:
            sections.append("\n## Loaded Skill References")
            for ref_key, content in self._loaded_references.items():
                skill_name, ref_path = ref_key.split(":", 1)
                sections.append(f"\n### {skill_name} - {ref_path}\n{content}")
        
        return "\n".join(sections)
    
    def add_skill_reference(self, ref_key: str, content: str) -> bool:
        """Add a skill reference to context (Phase 3).
        
        Args:
            ref_key: Key in format "skill_name:ref_path"
            content: Reference content
        
        Returns:
            True if added successfully
        """
        if ref_key in self._loaded_references:
            return True  # Already loaded
        
        tokens = len(content) // 4
        
        # Check if we have room
        if self._current_tokens + tokens > self.config.max_tokens * 0.9:
            self._compress_context()
        
        self._loaded_references[ref_key] = content
        self._current_tokens += tokens
        return True
    
    def unload_skill_reference(self, ref_key: str) -> None:
        """Unload a skill reference."""
        if ref_key in self._loaded_references:
            tokens = len(self._loaded_references[ref_key]) // 4
            del self._loaded_references[ref_key]
            self._current_tokens -= tokens
    
    # ==================== Context Building ====================
    
    def build_messages(self) -> list[dict]:
        """Build messages list for LLM API call."""
        messages = []
        
        # Build system message with skills
        system_content = self._system_prompt
        
        skill_summary = self.get_skill_summary()
        if skill_summary:
            system_content += f"\n\n{skill_summary}"
        
        skill_instructions = self.get_loaded_skill_instructions()
        if skill_instructions:
            system_content += f"\n\n{skill_instructions}"
        
        if system_content:
            messages.append({"role": "system", "content": system_content})
        
        # Add conversation messages
        for msg in self._messages:
            messages.append(msg.to_openai_format())
        
        return messages
    
    def get_context_stats(self) -> dict:
        """Get statistics about current context."""
        return {
            "total_messages": len(self._messages),
            "estimated_tokens": self._current_tokens,
            "max_tokens": self.config.max_tokens,
            "usage_percent": round(self._current_tokens / self.config.max_tokens * 100, 1),
            "loaded_skills": list(self._loaded_skills.keys()),
            "loaded_references": list(self._loaded_references.keys()),
            "available_skills": list(self._skill_metadata.keys())
        }
    
    # ==================== Context Compression ====================
    
    async def _compress_with_llm(self) -> str | None:
        """Use LLM to summarize older conversation turns."""
        if not self._llm_summarize_callback:
            return None
        
        keep_count = self.config.keep_recent_turns * 2
        if len(self._messages) <= keep_count:
            return None
        
        # Get messages to compress
        to_compress = self._messages[:-keep_count]
        to_keep = self._messages[-keep_count:]
        
        # Build conversation text for summarization
        conversation_parts = []
        for msg in to_compress:
            if msg.role == MessageRole.USER:
                conversation_parts.append(f"User: {msg.content or ''}")
            elif msg.role == MessageRole.ASSISTANT:
                content = msg.content or ""
                if msg.tool_calls:
                    tool_names = [tc.name for tc in msg.tool_calls]
                    content += f" [Called tools: {', '.join(tool_names)}]"
                conversation_parts.append(f"Assistant: {content}")
            elif msg.role == MessageRole.TOOL and msg.tool_result:
                result_preview = msg.tool_result.content[:200] + "..." if len(msg.tool_result.content) > 200 else msg.tool_result.content
                conversation_parts.append(f"Tool Result: {result_preview}")
        
        if not conversation_parts:
            return None
        
        conversation_text = "\n".join(conversation_parts)
        
        # Call LLM to summarize
        try:
            summary = await self._llm_summarize_callback(conversation_text)
            
            if summary:
                # Replace old messages with summary
                summary_msg = Message(
                    role=MessageRole.SYSTEM,
                    content=f"[Conversation Summary]\n{summary}",
                    metadata={"is_summary": True, "compressed_turns": len(to_compress)}
                )
                self._messages = [summary_msg] + to_keep
                self._recalculate_tokens()
                return summary
        except Exception:
            pass
        
        return None
    
    def _compress_context(self) -> None:
        """Compress context to free up space (synchronous fallback)."""
        # Strategy 1: Summarize old tool results
        self._summarize_old_tool_results()
        
        # Strategy 2: Remove old conversation turns (keep recent)
        if len(self._messages) > self.config.keep_recent_turns * 2:
            self._compress_old_turns()
        
        # Strategy 3: Unload unused skills
        self._unload_unused_skills()
        
        # Recalculate tokens
        self._recalculate_tokens()
    
    def _summarize_old_tool_results(self) -> None:
        """Summarize tool results from older turns."""
        # Keep recent turns intact
        cutoff = max(0, len(self._messages) - self.config.keep_recent_turns * 2)
        
        for i in range(cutoff):
            msg = self._messages[i]
            if msg.role == MessageRole.TOOL and msg.tool_result:
                content = msg.tool_result.content
                if len(content) > 500:
                    # Summarize long tool results
                    msg.tool_result.content = self._summarize_tool_result(content, max_length=200)
                    msg._estimated_tokens = None  # Reset cache
    
    def _compress_old_turns(self) -> None:
        """Compress old conversation turns into summaries."""
        keep_count = self.config.keep_recent_turns * 2
        if len(self._messages) <= keep_count:
            return
        
        # Get messages to compress
        to_compress = self._messages[:-keep_count]
        to_keep = self._messages[-keep_count:]
        
        # Create a summary of compressed messages
        summary_parts = []
        for msg in to_compress:
            if msg.role == MessageRole.USER:
                summary_parts.append(f"User: {msg.summarize(50)}")
            elif msg.role == MessageRole.ASSISTANT:
                summary_parts.append(f"Assistant: {msg.summarize(50)}")
        
        if summary_parts:
            summary = "[Earlier conversation summary]\n" + "\n".join(summary_parts[-10:])
            summary_msg = Message(
                role=MessageRole.SYSTEM,
                content=summary,
                metadata={"is_summary": True}
            )
            self._messages = [summary_msg] + to_keep
    
    def _unload_unused_skills(self) -> None:
        """Unload skills that haven't been used recently."""
        # Simple strategy: unload skills not mentioned in recent messages
        recent_content = " ".join(
            msg.content or "" 
            for msg in self._messages[-10:] 
            if msg.content
        )
        
        to_unload = []
        for skill_name in self._loaded_skills:
            if skill_name.lower() not in recent_content.lower():
                to_unload.append(skill_name)
        
        for name in to_unload:
            self.unload_skill(name)
    
    def _summarize_tool_result(self, content: str, max_length: int = 500) -> str:
        """Summarize a long tool result."""
        if len(content) <= max_length:
            return content
        
        # Keep first and last parts
        half = max_length // 2 - 20
        return f"{content[:half]}\n...[truncated {len(content) - max_length} chars]...\n{content[-half:]}"
    
    def _recalculate_tokens(self) -> None:
        """Recalculate total token count."""
        total = len(self._system_prompt) // 4
        
        for msg in self._messages:
            msg._estimated_tokens = None  # Reset cache
            total += msg.estimated_tokens
        
        for instructions in self._loaded_skills.values():
            total += len(instructions) // 4
        
        self._current_tokens = total
    
    def clear(self) -> None:
        """Clear all context."""
        self._messages.clear()
        self._loaded_skills.clear()
        self._loaded_references.clear()
        self._current_tokens = len(self._system_prompt) // 4

