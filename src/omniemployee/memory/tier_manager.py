"""TierManager - Orchestrates data flow between storage tiers.

Manages promotion and demotion of memory nodes across:
- L1 (Working Canvas): Hot, high-energy nodes
- L2 (Association Web): Full contextual memory
- L3 (Crystal): Consolidated facts
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable, Awaitable, Any
from dataclasses import dataclass

from src.omniemployee.memory.models import MemoryNode, CrystalFact, Link
from src.omniemployee.memory.storage.l1_working import L1WorkingMemory, L1Config
from src.omniemployee.memory.storage.l2_vector import L2VectorStorage, MilvusConfig
from src.omniemployee.memory.storage.l2_graph import L2GraphStorage, GraphConfig
from src.omniemployee.memory.storage.l3_crystal import L3CrystalStorage, PostgresConfig
from src.omniemployee.memory.operators.energy import EnergyController


@dataclass
class TierConfig:
    """Configuration for tier management."""
    # Promotion thresholds
    l1_energy_threshold: float = 0.5    # Min energy to be in L1
    l2_to_l1_threshold: float = 0.7     # Energy needed to promote from L2 to L1
    
    # Demotion thresholds
    l1_to_l2_threshold: float = 0.3     # Energy below which demote L1 to L2
    l2_stale_days: int = 30             # Days after which L2 nodes may be archived
    
    # Consolidation
    consolidation_threshold: int = 5    # Min cluster size for consolidation
    consolidation_similarity: float = 0.85  # Min similarity for clustering
    
    # Background tasks
    cleanup_interval: float = 300.0     # Seconds between cleanup runs
    consolidation_interval: float = 3600.0  # Seconds between consolidation runs


class TierManager:
    """Manages memory storage across multiple tiers.
    
    Responsibilities:
    - Route new memories to appropriate tier
    - Handle promotions (L2 -> L1) when nodes become relevant
    - Handle demotions (L1 -> L2, L2 -> L3) when nodes decay
    - Consolidate frequently accessed clusters into facts
    """
    
    def __init__(
        self,
        l1: L1WorkingMemory,
        l2_vector: L2VectorStorage,
        l2_graph: L2GraphStorage,
        l3: L3CrystalStorage,
        energy_controller: EnergyController,
        config: TierConfig | None = None
    ):
        self.l1 = l1
        self.l2_vector = l2_vector
        self.l2_graph = l2_graph
        self.l3 = l3
        self.energy = energy_controller
        self.config = config or TierConfig()
        
        self._running = False
        self._cleanup_task: asyncio.Task | None = None
        self._consolidation_task: asyncio.Task | None = None
        
        # Optional LLM callback for consolidation
        self._consolidate_callback: Callable[[list[str]], Awaitable[str]] | None = None
    
    def set_consolidate_callback(
        self,
        callback: Callable[[list[str]], Awaitable[str]]
    ) -> None:
        """Set callback for LLM-based consolidation.
        
        Callback receives list of content strings, returns consolidated fact.
        """
        self._consolidate_callback = callback
    
    async def connect_all(self) -> None:
        """Connect all storage backends.
        
        L3 (PostgreSQL) is optional - if connection fails, continues without it.
        """
        await self.l1.connect()
        await self.l2_vector.connect()
        await self.l2_graph.connect()
        
        # L3 is optional
        try:
            await self.l3.connect()
            self._l3_available = True
            
            # Restore graph links from L3
            await self._restore_graph_from_l3()
            
        except Exception as e:
            print(f"[Memory] L3 (PostgreSQL) not available: {e}")
            print("[Memory] Continuing without L3 storage...")
            self._l3_available = False
    
    async def _restore_graph_from_l3(self) -> None:
        """Restore graph links from L3 persistent storage."""
        if not self._l3_available:
            return
        
        try:
            links = await self.l3.get_all_links(limit=10000)
            restored = 0
            for link in links:
                await self.l2_graph.add_link(link)
                restored += 1
            
            if restored > 0:
                print(f"[Memory] Restored {restored} links from L3 to graph")
        except Exception as e:
            print(f"[Memory] Failed to restore graph links: {e}")
    
    async def disconnect_all(self) -> None:
        """Disconnect all storage backends."""
        await self.stop_background_tasks()
        await self.l1.disconnect()
        await self.l2_vector.disconnect()
        await self.l2_graph.disconnect()
        if self._l3_available:
            await self.l3.disconnect()
    
    # ==================== Node Operations ====================
    
    async def store(self, node: MemoryNode) -> str:
        """Store a new memory node in appropriate tier.
        
        High-energy nodes go to L1, others to L2.
        All nodes are indexed in L2 vector storage.
        """
        # Ensure node has vector
        if not node.vector:
            raise ValueError("Node must have vector embedding")
        
        # Determine initial tier
        if node.energy >= self.config.l1_energy_threshold:
            node.tier = "L1"
            await self.l1.put(node)
        else:
            node.tier = "L2"
        
        # Always store in L2 vector for searchability
        await self.l2_vector.put(node)
        
        # Add to graph
        await self.l2_graph.add_node(node.id)
        
        return node.id
    
    async def get(self, node_id: str) -> MemoryNode | None:
        """Retrieve a node from any tier.
        
        Checks L1 first, then L2.
        """
        # Check L1 first (fastest)
        node = await self.l1.get(node_id)
        if node:
            self.energy.boost_energy(node)
            return node
        
        # Check L2 vector storage
        node = await self.l2_vector.get(node_id)
        if node:
            self.energy.boost_energy(node)
            
            # Consider promoting to L1 if frequently accessed
            if node.energy >= self.config.l2_to_l1_threshold:
                await self._promote_to_l1(node)
            
            return node
        
        return None
    
    async def delete(self, node_id: str) -> bool:
        """Delete a node from all tiers."""
        # Remove from L1
        await self.l1.delete(node_id)
        
        # Remove from L2 vector
        await self.l2_vector.delete(node_id)
        
        # Remove from graph
        await self.l2_graph.remove_node(node_id)
        
        return True
    
    async def update_energy(self, node_id: str, energy: float) -> bool:
        """Update energy for a node and handle tier transitions."""
        # Update in L1 if present
        l1_updated = await self.l1.update_energy(node_id, energy)
        
        # Update in L2
        l2_updated = await self.l2_vector.update_energy(node_id, energy)
        
        if not l1_updated and not l2_updated:
            return False
        
        # Check for tier transitions
        if l1_updated and energy < self.config.l1_to_l2_threshold:
            await self._demote_from_l1(node_id)
        elif not l1_updated and energy >= self.config.l2_to_l1_threshold:
            node = await self.l2_vector.get(node_id)
            if node:
                await self._promote_to_l1(node)
        
        return True
    
    # ==================== Tier Transitions ====================
    
    async def _promote_to_l1(self, node: MemoryNode) -> None:
        """Promote a node from L2 to L1."""
        if node.tier == "L1":
            return
        
        node.tier = "L1"
        await self.l1.put(node)
        
        # Update tier in L2
        await self.l2_vector.put(node)
    
    async def _demote_from_l1(self, node_id: str) -> None:
        """Demote a node from L1 to L2."""
        node = await self.l1.get(node_id)
        if not node:
            return
        
        node.tier = "L2"
        await self.l1.delete(node_id)
        
        # Update in L2
        await self.l2_vector.put(node)
    
    async def _archive_to_l3(self, nodes: list[MemoryNode]) -> CrystalFact | None:
        """Consolidate nodes into a crystal fact and store in L3.
        
        Returns the created fact, or None if consolidation failed.
        """
        if not nodes or len(nodes) < self.config.consolidation_threshold:
            return None
        
        # Get content for consolidation
        contents = [n.content for n in nodes]
        
        # Use LLM to consolidate if callback available
        if self._consolidate_callback:
            try:
                consolidated = await self._consolidate_callback(contents)
            except Exception:
                # Fall back to simple concatenation
                consolidated = self._simple_consolidate(contents)
        else:
            consolidated = self._simple_consolidate(contents)
        
        # Create crystal fact
        fact = CrystalFact(
            content=consolidated,
            source_node_ids=[n.id for n in nodes],
            confidence=sum(n.energy for n in nodes) / len(nodes),
            metadata={"node_count": len(nodes)}
        )
        
        # Store in L3 if available
        if self._l3_available:
            await self.l3.store_fact(fact)
        
        return fact
    
    def _simple_consolidate(self, contents: list[str]) -> str:
        """Simple consolidation by finding common themes."""
        if not contents:
            return ""
        
        if len(contents) == 1:
            return contents[0]
        
        # Simple approach: keep first content with note about consolidation
        return f"[Consolidated from {len(contents)} memories]\n{contents[0]}"
    
    # ==================== Search Operations ====================
    
    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        include_l1: bool = True,
        filters: dict | None = None
    ) -> list[tuple[MemoryNode, float]]:
        """Search for relevant memories across tiers.
        
        Args:
            query_vector: Query embedding
            top_k: Number of results
            include_l1: Whether to include L1 results
            filters: Optional filters for L2 search
        
        Returns:
            List of (node, score) tuples, sorted by relevance
        """
        results = []
        
        # Search L2 (comprehensive)
        l2_results = await self.l2_vector.search_by_vector(
            query_vector,
            top_k=top_k * 2,  # Get extra for merging
            filters=filters
        )
        results.extend(l2_results)
        
        # If including L1, boost L1 nodes in results
        if include_l1:
            l1_nodes = await self.l1.list_all()
            l1_ids = {n.id for n in l1_nodes}
            
            # Boost scores for L1 nodes
            boosted_results = []
            for node, score in results:
                if node.id in l1_ids:
                    score = min(1.0, score + 0.1)  # Boost L1 nodes
                boosted_results.append((node, score))
            results = boosted_results
        
        # Sort by score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    async def get_working_context(self, limit: int = 10) -> list[MemoryNode]:
        """Get the most relevant nodes from working memory (L1)."""
        return await self.l1.get_top_k(limit)
    
    # ==================== Background Tasks ====================
    
    async def start_background_tasks(self) -> None:
        """Start background maintenance tasks."""
        self._running = True
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._consolidation_task = asyncio.create_task(self._consolidation_loop())
    
    async def stop_background_tasks(self) -> None:
        """Stop background tasks."""
        self._running = False
        
        for task in [self._cleanup_task, self._consolidation_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of stale/low-energy nodes."""
        while self._running:
            try:
                await self._run_cleanup()
            except Exception as e:
                print(f"Cleanup error: {e}")
            
            await asyncio.sleep(self.config.cleanup_interval)
    
    async def _run_cleanup(self) -> None:
        """Execute cleanup operations."""
        # Clean stale L1 nodes
        stale = await self.l1.cleanup_stale()
        for node in stale:
            node.tier = "L2"
            await self.l2_vector.put(node)
        
        # Clean low-energy L1 nodes
        low_energy = await self.l1.cleanup_low_energy()
        for node in low_energy:
            node.tier = "L2"
            await self.l2_vector.put(node)
        
        # Apply decay to L1 nodes
        l1_nodes = await self.l1.list_all()
        if l1_nodes:
            updates = self.energy.apply_decay_batch(l1_nodes)
            
            # Check for demotions
            for node_id, energy in updates.items():
                if energy < self.config.l1_to_l2_threshold:
                    await self._demote_from_l1(node_id)
    
    async def _consolidation_loop(self) -> None:
        """Periodic consolidation of related nodes."""
        while self._running:
            try:
                await self._run_consolidation()
            except Exception as e:
                print(f"Consolidation error: {e}")
            
            await asyncio.sleep(self.config.consolidation_interval)
    
    async def _run_consolidation(self) -> None:
        """Execute consolidation operations.
        
        Finds clusters of highly related, frequently accessed nodes
        and consolidates them into crystal facts.
        """
        # This is a simplified consolidation
        # Full implementation would use clustering algorithms
        pass
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> dict[str, Any]:
        """Get statistics for all tiers."""
        l1_stats = self.l1.get_stats()
        l2_vector_stats = self.l2_vector.get_stats()
        l2_graph_stats = self.l2_graph.get_stats()
        
        result = {
            "l1": l1_stats,
            "l2_vector": l2_vector_stats,
            "l2_graph": l2_graph_stats,
        }
        
        if self._l3_available:
            l3_stats = await self.l3.get_stats()
            result["l3"] = l3_stats
        else:
            result["l3"] = {"status": "unavailable"}
        
        return result