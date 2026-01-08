"""MemoryManager - Main entry point for the BIEM memory system.

Provides the core API for ingesting, recalling, and managing memories
with energy decay, associative recall, and conflict detection.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Awaitable, Any
from dataclasses import dataclass

from src.omniemployee.memory.models import (
    MemoryNode,
    Link,
    LinkType,
    ConflictNode,
    DissonanceSignal,
    CrystalFact,
)
from src.omniemployee.memory.storage import (
    L1WorkingMemory,
    L1Config,
    L2VectorStorage,
    MilvusConfig,
    L2GraphStorage,
    GraphConfig,
    L3CrystalStorage,
    PostgresConfig,
)
from src.omniemployee.memory.operators import (
    EnergyController,
    EnergyConfig,
    Encoder,
    EncoderConfig,
    AssociationRouter,
    RouterConfig,
    ConflictChecker,
    ConflictConfig,
)
from src.omniemployee.memory.tier_manager import TierManager, TierConfig


@dataclass
class MemoryConfig:
    """Master configuration for the memory system."""
    # Storage configs
    l1_config: L1Config | None = None
    milvus_config: MilvusConfig | None = None
    graph_config: GraphConfig | None = None
    postgres_config: PostgresConfig | None = None
    
    # Operator configs
    energy_config: EnergyConfig | None = None
    encoder_config: EncoderConfig | None = None
    router_config: RouterConfig | None = None
    conflict_config: ConflictConfig | None = None
    tier_config: TierConfig | None = None
    
    # Recall settings
    default_recall_limit: int = 10
    spreading_activation_hops: int = 2
    spreading_decay_factor: float = 0.5
    
    # Auto-start background tasks
    auto_start_tasks: bool = True


class MemoryManager:
    """Main entry point for the BIEM memory system.
    
    Provides high-level API for:
    - Ingesting new memories
    - Recalling relevant memories (two-stage: graph spread + vector refine)
    - Recording events with feedback
    - Managing conflicts
    """
    
    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or MemoryConfig()
        
        # Initialize storage backends
        self._l1 = L1WorkingMemory(self.config.l1_config or L1Config())
        self._l2_vector = L2VectorStorage(self.config.milvus_config or MilvusConfig())
        self._l2_graph = L2GraphStorage(self.config.graph_config or GraphConfig())
        self._l3 = L3CrystalStorage(self.config.postgres_config or PostgresConfig())
        
        # Initialize operators
        self._energy = EnergyController(self.config.energy_config or EnergyConfig())
        self._encoder = Encoder(self.config.encoder_config or EncoderConfig())
        self._router = AssociationRouter(
            self._l2_graph,
            self.config.router_config or RouterConfig()
        )
        self._conflict = ConflictChecker(self.config.conflict_config or ConflictConfig())
        
        # Initialize tier manager
        self._tier = TierManager(
            self._l1,
            self._l2_vector,
            self._l2_graph,
            self._l3,
            self._energy,
            self.config.tier_config or TierConfig()
        )
        
        self._initialized = False
        self._pending_conflicts: list[DissonanceSignal] = []
    
    async def initialize(self) -> None:
        """Initialize all components and connect to backends."""
        if self._initialized:
            return
        
        # Connect storage backends
        await self._tier.connect_all()
        
        # Initialize encoder
        await self._encoder.initialize()
        
        # Start background tasks if configured
        if self.config.auto_start_tasks:
            await self._tier.start_background_tasks()
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the memory system."""
        await self._tier.disconnect_all()
        self._initialized = False
    
    # ==================== Core API ====================
    
    async def ingest(
        self,
        content: str,
        source: str = "user",
        importance: float | None = None,
        metadata: dict | None = None
    ) -> tuple[MemoryNode, list[DissonanceSignal]]:
        """Ingest new content into the memory system.
        
        Args:
            content: The content to remember
            source: Origin of the content (user, tool, agent, etc.)
            importance: Optional explicit importance (0-1)
            metadata: Optional additional metadata
        
        Returns:
            Tuple of (created node, list of conflict signals)
        """
        await self._ensure_initialized()
        
        # Encode content into a node
        node = await self._encoder.encode(
            content,
            source=source,
            location=metadata.get("location", "") if metadata else "",
            tags=metadata.get("tags", []) if metadata else []
        )
        
        # Estimate initial energy
        node.energy = await self._energy.estimate_initial_energy(
            content,
            explicit_importance=importance
        )
        node.initial_energy = node.energy
        
        # Check for conflicts with existing memories
        existing_similar = await self._find_similar_nodes(node.vector, limit=10)
        existing_nodes = [n for n, _ in existing_similar]
        
        conflicts = await self._conflict.check_conflicts(node, existing_nodes)
        self._pending_conflicts.extend(conflicts)
        
        # Store the node
        await self._tier.store(node)
        
        # Establish links
        await self._router.route_new_node(node, existing_nodes)
        
        return node, conflicts
    
    async def recall(
        self,
        query: str,
        top_k: int | None = None,
        use_spreading: bool = True,
        filters: dict | None = None
    ) -> list[MemoryNode]:
        """Recall relevant memories using two-stage retrieval.
        
        Stage 1: Graph-based spreading activation from initial matches
        Stage 2: Vector similarity refinement
        
        Args:
            query: The query string
            top_k: Number of results (defaults to config)
            use_spreading: Whether to use spreading activation
            filters: Optional filters (e.g., {"energy": {"$gte": 0.3}})
        
        Returns:
            List of relevant MemoryNode objects
        """
        await self._ensure_initialized()
        
        k = top_k or self.config.default_recall_limit
        
        # Encode query
        query_vector = await self._encoder.generate_embedding(query)
        
        if not query_vector or all(v == 0 for v in query_vector):
            # Fallback to L1 working memory if encoding fails
            return await self._l1.get_top_k(k)
        
        # Stage 1: Initial vector search
        initial_results = await self._l2_vector.search_by_vector(
            query_vector,
            top_k=k * 2,  # Get more for spreading
            filters=filters
        )
        
        if not initial_results:
            return await self._l1.get_top_k(k)
        
        # Stage 2: Spreading activation (if enabled)
        if use_spreading:
            initial_ids = [n.id for n, _ in initial_results[:5]]  # Seed with top 5
            
            activation_scores = await self._l2_graph.spread_activation(
                initial_ids,
                max_hops=self.config.spreading_activation_hops,
                decay_factor=self.config.spreading_decay_factor
            )
            
            # Combine vector similarity with activation scores
            combined_scores: dict[str, float] = {}
            
            for node, vec_score in initial_results:
                activation = activation_scores.get(node.id, 0)
                # Weighted combination: 70% vector, 30% activation
                combined = 0.7 * vec_score + 0.3 * activation
                combined_scores[node.id] = combined
            
            # Add activated nodes not in initial results
            for node_id, activation in activation_scores.items():
                if node_id not in combined_scores and activation > 0.1:
                    node = await self._tier.get(node_id)
                    if node:
                        combined_scores[node_id] = activation * 0.5
            
            # Sort by combined score
            sorted_ids = sorted(
                combined_scores.keys(),
                key=lambda x: combined_scores[x],
                reverse=True
            )[:k]
            
            # Fetch nodes
            results = []
            for node_id in sorted_ids:
                node = await self._tier.get(node_id)
                if node:
                    results.append(node)
            
            return results
        else:
            # Just return vector search results
            return [n for n, _ in initial_results[:k]]
    
    async def get_context(self, current_input: str, limit: int = 5) -> str:
        """Get formatted context for LLM prompt injection.
        
        Args:
            current_input: Current user input/task
            limit: Maximum memories to include
        
        Returns:
            Formatted string of relevant memories
        """
        await self._ensure_initialized()
        
        # Get relevant memories
        memories = await self.recall(current_input, top_k=limit)
        
        if not memories:
            return ""
        
        # Format for context
        lines = ["## Relevant Memories"]
        
        for i, node in enumerate(memories, 1):
            energy_indicator = "●" if node.energy > 0.7 else "○" if node.energy > 0.3 else "◌"
            content_preview = node.content[:200]
            if len(node.content) > 200:
                content_preview += "..."
            
            lines.append(f"{i}. [{energy_indicator} E={node.energy:.2f}] {content_preview}")
            
            if node.metadata.entities:
                lines.append(f"   Entities: {', '.join(node.metadata.entities[:5])}")
        
        return "\n".join(lines)
    
    async def record_event(
        self,
        event_type: str,
        content: str,
        feedback: float = 0.0,
        related_node_ids: list[str] | None = None
    ) -> MemoryNode:
        """Record an agent decision/event with optional feedback.
        
        Positive feedback strengthens related memories.
        Negative feedback weakens them.
        
        Args:
            event_type: Type of event (decision, action, observation)
            content: Event description
            feedback: Feedback score (-1 to 1)
            related_node_ids: IDs of related memories to reinforce
        
        Returns:
            The created event node
        """
        await self._ensure_initialized()
        
        # Calculate importance based on feedback magnitude
        importance = 0.5 + abs(feedback) * 0.5
        
        # Ingest the event
        node, _ = await self.ingest(
            content,
            source="agent",
            importance=importance,
            metadata={"event_type": event_type, "feedback": feedback}
        )
        
        # Apply feedback to related nodes
        if related_node_ids and feedback != 0:
            boost = feedback * 0.1  # Scale feedback to energy boost
            
            for node_id in related_node_ids:
                related = await self._tier.get(node_id)
                if related:
                    self._energy.boost_energy(related, boost)
                    await self._tier.update_energy(node_id, related.energy)
                    
                    # Create causal link if feedback is positive
                    if feedback > 0:
                        await self._router.create_causal_link(
                            related.id,
                            node.id,
                            confidence=abs(feedback)
                        )
        
        return node
    
    # ==================== Conflict Management ====================
    
    def get_pending_conflicts(self) -> list[DissonanceSignal]:
        """Get list of pending conflict signals."""
        return self._pending_conflicts.copy()
    
    async def resolve_conflict(
        self,
        conflict_id: str,
        action: str,
        keep_node_id: str | None = None
    ) -> bool:
        """Resolve a pending conflict.
        
        Args:
            conflict_id: ID of the conflict to resolve
            action: Resolution action (keep_new, keep_old, merge, ignore)
            keep_node_id: ID of node to keep (for keep_new/keep_old)
        
        Returns:
            True if conflict was resolved
        """
        # Find the conflict
        for i, signal in enumerate(self._pending_conflicts):
            if signal.conflict.id == conflict_id:
                conflict = signal.conflict
                
                if action == "keep_new":
                    # Delete old node
                    await self._tier.delete(conflict.node_a_id)
                elif action == "keep_old":
                    # Delete new node
                    await self._tier.delete(conflict.node_b_id)
                elif action == "ignore":
                    pass  # Keep both
                
                await self._conflict.resolve_conflict(conflict, action, keep_node_id)
                self._pending_conflicts.pop(i)
                return True
        
        return False
    
    # ==================== Direct Access ====================
    
    async def get_node(self, node_id: str) -> MemoryNode | None:
        """Get a specific node by ID."""
        await self._ensure_initialized()
        return await self._tier.get(node_id)
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a specific node."""
        await self._ensure_initialized()
        await self._router.remove_node_links(node_id)
        return await self._tier.delete(node_id)
    
    async def get_working_memory(self, limit: int = 10) -> list[MemoryNode]:
        """Get nodes currently in working memory (L1)."""
        await self._ensure_initialized()
        return await self._l1.get_top_k(limit)
    
    async def search_facts(self, query: str, limit: int = 10) -> list[CrystalFact]:
        """Search consolidated facts in L3."""
        await self._ensure_initialized()
        return await self._l3.search_facts_by_content(query, limit)
    
    # ==================== Utilities ====================
    
    async def _ensure_initialized(self) -> None:
        """Ensure the system is initialized."""
        if not self._initialized:
            await self.initialize()
    
    async def _find_similar_nodes(
        self,
        vector: list[float],
        limit: int = 10
    ) -> list[tuple[MemoryNode, float]]:
        """Find nodes similar to a given vector."""
        return await self._l2_vector.search_by_vector(vector, top_k=limit)
    
    async def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics."""
        await self._ensure_initialized()
        
        tier_stats = await self._tier.get_stats()
        
        return {
            **tier_stats,
            "pending_conflicts": len(self._pending_conflicts),
            "initialized": self._initialized,
        }
    
    # ==================== Callback Setters ====================
    
    def set_embedding_callback(
        self,
        callback: Callable[[str], Awaitable[list[float]]]
    ) -> None:
        """Set external embedding callback (e.g., using LLM API)."""
        self._encoder.set_embed_callback(callback)
    
    def set_importance_callback(
        self,
        callback: Callable[[str], Awaitable[float]]
    ) -> None:
        """Set LLM callback for importance evaluation."""
        self._energy.set_llm_evaluate_callback(callback)
    
    def set_conflict_verify_callback(
        self,
        callback: Callable[[str, str], Awaitable[dict]]
    ) -> None:
        """Set LLM callback for conflict verification."""
        self._conflict.set_verify_conflict_callback(callback)
    
    def set_consolidation_callback(
        self,
        callback: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        """Set LLM callback for memory consolidation."""
        self._tier.set_consolidate_callback(callback)
