"""Knowledge Learning Plugin Integration.

Provides the main interface for integrating knowledge learning
with the agent's conversation flow.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.omniemployee.memory.knowledge.models import (
    KnowledgeTriple,
    KnowledgeIntent,
    KnowledgeSource,
    ExtractionResult,
    ConflictResult,
    PendingUpdate,
)
from src.omniemployee.memory.knowledge.extractor import KnowledgeExtractor, ExtractorConfig
from src.omniemployee.memory.knowledge.store import KnowledgeStore, KnowledgeStoreConfig
from src.omniemployee.memory.knowledge.conflict import (
    KnowledgeConflictDetector,
    ConfirmationManager,
    ConflictConfig,
)
from src.omniemployee.memory.knowledge.vector_store import (
    KnowledgeVectorStore,
    KnowledgeVectorConfig,
)


@dataclass
class ProcessResult:
    """Result of processing a message for knowledge."""
    action: str = "none"  # "none", "stored", "conflict", "question"
    triples_stored: list[KnowledgeTriple] = field(default_factory=list)
    conflicts: list[ConflictResult] = field(default_factory=list)
    confirmation_prompts: list[str] = field(default_factory=list)
    pending_keys: list[str] = field(default_factory=list)
    
    def has_pending_confirmation(self) -> bool:
        """Check if there are pending confirmations."""
        return len(self.pending_keys) > 0


@dataclass
class KnowledgePluginConfig:
    """Configuration for the knowledge learning plugin."""
    store_config: KnowledgeStoreConfig = field(default_factory=KnowledgeStoreConfig)
    vector_config: KnowledgeVectorConfig = field(default_factory=KnowledgeVectorConfig)
    extractor_config: ExtractorConfig = field(default_factory=ExtractorConfig)
    conflict_config: ConflictConfig = field(default_factory=ConflictConfig)
    
    # Auto-store triples that have no conflicts
    auto_store: bool = True
    # Extract from both user and agent messages
    extract_from_agent: bool = False
    # Maximum knowledge items to include in context
    max_context_items: int = 10
    # Enable vector search (requires Milvus)
    enable_vector_search: bool = True
    # User ID for this session (for multi-user support)
    user_id: str = ""
    # Session ID
    session_id: str = ""


class KnowledgeLearningPlugin:
    """Main integration point for knowledge learning.
    
    Usage:
        plugin = KnowledgeLearningPlugin(config)
        await plugin.initialize(llm_provider, encoder)
        
        # Process user message
        result = await plugin.process_message("GPT-4 now has 128k context")
        
        if result.has_pending_confirmation():
            # Show confirmation prompt to user
            for prompt in result.confirmation_prompts:
                print(prompt)
        
        # Handle user confirmation
        await plugin.confirm_update(key, confirmed=True)
        
        # Get knowledge context for LLM
        context = await plugin.get_context_for_query("What's GPT-4's context size?")
    """
    
    def __init__(self, config: KnowledgePluginConfig | None = None):
        self.config = config or KnowledgePluginConfig()
        
        self._store = KnowledgeStore(self.config.store_config)
        self._vector_store = KnowledgeVectorStore(self.config.vector_config) if self.config.enable_vector_search else None
        self._extractor = KnowledgeExtractor(config=self.config.extractor_config)
        self._conflict_detector = KnowledgeConflictDetector(
            self._store, self.config.conflict_config
        )
        self._confirmation = ConfirmationManager(self._store)
        
        self._initialized = False
        self._llm = None
        self._encoder = None
    
    async def initialize(self, llm_provider: Any = None, encoder: Any = None) -> None:
        """Initialize the plugin with LLM provider and encoder.
        
        Args:
            llm_provider: LLMProvider instance for knowledge extraction
            encoder: Encoder instance for generating embeddings
        """
        self._llm = llm_provider
        self._encoder = encoder
        
        # Connect to PostgreSQL
        try:
            await self._store.connect()
        except Exception as e:
            print(f"[Knowledge] PostgreSQL connection failed: {e}")
            print("[Knowledge] Knowledge learning will be disabled")
            return
        
        # Connect to Milvus for vector search
        if self._vector_store:
            try:
                await self._vector_store.connect()
                if encoder:
                    await self._vector_store.set_encoder(encoder)
                print("[Knowledge] Vector search enabled")
            except Exception as e:
                print(f"[Knowledge] Milvus connection failed: {e}")
                print("[Knowledge] Vector search will be disabled")
                self._vector_store = None
        
        # Initialize extractor with LLM
        if llm_provider:
            await self._extractor.initialize(llm_provider)
        
        self._initialized = True
        print("[Knowledge] Knowledge learning plugin initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        if self._store.is_available():
            await self._store.disconnect()
        if self._vector_store and self._vector_store.is_available():
            await self._vector_store.disconnect()
        self._initialized = False
    
    def is_available(self) -> bool:
        """Check if plugin is ready."""
        return self._initialized and self._store.is_available()
    
    # ==================== Message Processing ====================
    
    async def process_message(
        self,
        message: str,
        role: str = "user",
    ) -> ProcessResult:
        """Process a message for knowledge extraction and storage.
        
        Args:
            message: The message content
            role: "user" or "assistant"
            
        Returns:
            ProcessResult with actions taken
        """
        if not self.is_available():
            return ProcessResult(action="none")
        
        # Skip agent messages if not configured
        if role == "assistant" and not self.config.extract_from_agent:
            return ProcessResult(action="none")
        
        # Extract knowledge
        extraction = await self._extractor.extract(
            message,
            session_id=self.config.session_id,
            user_id=self.config.user_id,
        )
        
        if not extraction.is_factual or not extraction.triples:
            return ProcessResult(action="none")
        
        # Process each triple
        stored = []
        conflicts = []
        prompts = []
        pending_keys = []
        
        for triple in extraction.triples:
            triple.user_id = self.config.user_id
            triple.session_id = self.config.session_id
            
            # Check for conflicts
            conflict = await self._conflict_detector.check(triple)
            
            if conflict.has_conflict:
                # Add to pending confirmations
                key = self._confirmation.add_pending(
                    triple, conflict.existing_triple
                )
                prompt = self._confirmation.generate_confirmation_prompt(conflict)
                
                conflicts.append(conflict)
                prompts.append(prompt)
                pending_keys.append(key)
                
            elif self.config.auto_store:
                # No conflict, auto-store
                await self._store.store(triple)
                # Also store vector for semantic search
                if self._vector_store:
                    await self._vector_store.store(triple)
                stored.append(triple)
        
        # Determine action
        if conflicts:
            action = "conflict"
        elif stored:
            action = "stored"
        else:
            action = "none"
        
        return ProcessResult(
            action=action,
            triples_stored=stored,
            conflicts=conflicts,
            confirmation_prompts=prompts,
            pending_keys=pending_keys,
        )
    
    async def process_confirmation_response(
        self,
        message: str,
    ) -> tuple[bool, str]:
        """Process user's response to a confirmation prompt.
        
        Args:
            message: User's response message
            
        Returns:
            Tuple of (handled, response_message)
            - handled: True if message was a confirmation response
            - response_message: Message to show user
        """
        if not self._confirmation.has_pending():
            return False, ""
        
        # Check if user confirmed
        msg_lower = message.lower().strip()
        positive_responses = ["是", "是的", "对", "对的", "确认", "更新", "yes", "y", "确定", "好的", "ok"]
        negative_responses = ["不", "不是", "否", "取消", "no", "n", "算了", "不用"]
        
        is_positive = any(r in msg_lower for r in positive_responses)
        is_negative = any(r in msg_lower for r in negative_responses)
        
        if not is_positive and not is_negative:
            # Not a clear confirmation response
            return False, ""
        
        # Process all pending updates
        keys = self._confirmation.get_all_pending_keys()
        
        if is_positive:
            for key in keys:
                await self._confirmation.confirm(key, self.config.session_id)
            return True, "好的，知识已更新！"
        else:
            for key in keys:
                await self._confirmation.reject(key)
            return True, "好的，保持原有记录。"
    
    async def confirm_update(self, key: str, confirmed: bool) -> bool:
        """Explicitly confirm or reject a pending update.
        
        Args:
            key: The pending update key
            confirmed: Whether user confirmed the update
            
        Returns:
            True if action was taken
        """
        if confirmed:
            return await self._confirmation.confirm(key, self.config.session_id)
        else:
            return await self._confirmation.reject(key)
    
    # ==================== Knowledge Retrieval ====================
    
    async def get_context_for_query(
        self,
        query: str,
        max_items: int | None = None,
    ) -> str:
        """Get relevant knowledge context for a query.
        
        Uses vector search if available, falls back to text search.
        
        Args:
            query: The user's query
            max_items: Maximum items to include
            
        Returns:
            Formatted knowledge context string
        """
        if not self.is_available():
            return ""
        
        max_items = max_items or self.config.max_context_items
        triples = []
        
        # Try vector search first
        if self._vector_store and self._vector_store.is_available():
            results = await self._vector_store.search(
                query, self.config.user_id, max_items
            )
            # Fetch full triples from PostgreSQL
            for triple_id, score in results:
                triple = await self._store.get(triple_id)
                if triple:
                    triples.append(triple)
        
        # Fall back to text search if vector search yielded nothing
        if not triples:
            triples = await self._store.search(query, self.config.user_id, max_items)
        
        if not triples:
            return ""
        
        # Format as context
        lines = ["## Learned Knowledge"]
        for t in triples:
            source_tag = f"[{t.source.value}]" if t.confidence < 1.0 else "[verified]"
            lines.append(f"- {t.display()} {source_tag}")
        
        return "\n".join(lines)
    
    async def get_all_knowledge(
        self,
        limit: int = 50,
    ) -> list[KnowledgeTriple]:
        """Get all stored knowledge for current user.
        
        Args:
            limit: Maximum items to return
            
        Returns:
            List of knowledge triples
        """
        if not self.is_available():
            return []
        
        return await self._store.get_all(self.config.user_id, limit)
    
    async def get_knowledge_about(
        self,
        subject: str,
    ) -> list[KnowledgeTriple]:
        """Get all knowledge about a specific subject.
        
        Args:
            subject: The subject to query
            
        Returns:
            List of knowledge triples
        """
        if not self.is_available():
            return []
        
        return await self._store.query_by_subject(subject, self.config.user_id)
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> dict[str, Any]:
        """Get knowledge store statistics."""
        if not self.is_available():
            return {"status": "unavailable"}
        
        stats = await self._store.get_stats(self.config.user_id)
        stats["pending_confirmations"] = len(self._confirmation.get_all_pending_keys())
        
        # Add vector store stats
        if self._vector_store and self._vector_store.is_available():
            vector_stats = await self._vector_store.get_stats()
            stats["vector_store"] = vector_stats
        else:
            stats["vector_store"] = {"status": "disabled"}
        
        return stats


# Convenience function to create a configured plugin
def create_knowledge_plugin(
    db_host: str = "localhost",
    db_port: int = 5432,
    db_name: str = "biem",
    db_user: str = "",
    db_password: str = "",
    milvus_host: str = "localhost",
    milvus_port: int = 19530,
    enable_vector_search: bool = True,
    user_id: str = "",
    session_id: str = "",
) -> KnowledgeLearningPlugin:
    """Create a knowledge learning plugin with common configuration.
    
    Args:
        db_host: PostgreSQL host
        db_port: PostgreSQL port
        db_name: Database name
        db_user: Database user
        db_password: Database password
        milvus_host: Milvus host
        milvus_port: Milvus port
        enable_vector_search: Enable vector-based semantic search
        user_id: User identifier for multi-user support
        session_id: Session identifier
        
    Returns:
        Configured KnowledgeLearningPlugin
    """
    config = KnowledgePluginConfig(
        store_config=KnowledgeStoreConfig(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password,
        ),
        vector_config=KnowledgeVectorConfig(
            host=milvus_host,
            port=milvus_port,
        ),
        enable_vector_search=enable_vector_search,
        user_id=user_id,
        session_id=session_id,
    )
    return KnowledgeLearningPlugin(config)
