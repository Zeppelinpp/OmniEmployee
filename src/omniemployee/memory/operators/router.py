"""AssociationRouter - Manages link creation and graph routing.

Responsible for establishing and maintaining relationships between
memory nodes based on temporal, semantic, and causal connections.
"""

from __future__ import annotations

import time
from typing import Callable, Awaitable, Any
from dataclasses import dataclass
from enum import Enum

from src.omniemployee.memory.models import MemoryNode, Link, LinkType
from src.omniemployee.memory.storage.l2_graph import L2GraphStorage
from src.omniemployee.memory.storage.l3_crystal import L3CrystalStorage


class LinkStrategy(str, Enum):
    """Strategy for link creation."""
    AUTO = "auto"           # Automatically create based on rules
    DEFERRED = "deferred"   # Only create when explicitly requested
    DISABLED = "disabled"   # Never create automatically


@dataclass
class RouterConfig:
    """Configuration for AssociationRouter."""
    temporal_strategy: LinkStrategy = LinkStrategy.AUTO
    semantic_strategy: LinkStrategy = LinkStrategy.AUTO
    causal_strategy: LinkStrategy = LinkStrategy.DEFERRED
    
    # Temporal linking
    temporal_window: float = 300.0  # Seconds - link nodes created within this window
    max_temporal_links: int = 5     # Max temporal links per node
    
    # Semantic linking
    semantic_threshold: float = 0.7  # Min cosine similarity for semantic link
    max_semantic_links: int = 10     # Max semantic links per node
    
    # Causal linking
    causal_confidence_threshold: float = 0.8  # Min confidence for causal link


class AssociationRouter:
    """Routes and establishes links between memory nodes.
    
    Handles:
    - Temporal links (based on creation time proximity)
    - Semantic links (based on embedding similarity)
    - Causal links (explicitly created or inferred)
    
    Links are persisted to L3 storage (if available) for recovery on restart.
    """
    
    def __init__(
        self,
        graph_storage: L2GraphStorage,
        config: RouterConfig | None = None
    ):
        self.graph = graph_storage
        self.config = config or RouterConfig()
        
        # Optional L3 storage for link persistence
        self._l3: L3CrystalStorage | None = None
        self._l3_available = False
        
        # Recent nodes for temporal linking
        self._recent_nodes: list[tuple[str, float]] = []  # (node_id, timestamp)
        self._max_recent = 50
        
        # Optional LLM callback for causal inference
        self._infer_causal_callback: Callable[[str, str], Awaitable[float]] | None = None
    
    def set_l3_storage(self, l3: L3CrystalStorage, available: bool = True) -> None:
        """Set L3 storage for link persistence."""
        self._l3 = l3
        self._l3_available = available
    
    def set_causal_inference_callback(
        self,
        callback: Callable[[str, str], Awaitable[float]]
    ) -> None:
        """Set callback for LLM-based causal inference.
        
        Callback receives (content_a, content_b) and returns
        confidence score (0-1) that A causes B.
        """
        self._infer_causal_callback = callback
    
    async def route_new_node(
        self,
        node: MemoryNode,
        context_nodes: list[MemoryNode] | None = None
    ) -> list[Link]:
        """Establish links for a newly created node.
        
        Args:
            node: The new node to route
            context_nodes: Optional list of contextually relevant nodes
        
        Returns:
            List of created links
        """
        created_links = []
        
        # Temporal links
        if self.config.temporal_strategy == LinkStrategy.AUTO:
            temporal_links = await self._create_temporal_links(node)
            created_links.extend(temporal_links)
        
        # Semantic links (if context nodes provided)
        if self.config.semantic_strategy == LinkStrategy.AUTO and context_nodes:
            semantic_links = await self._create_semantic_links(node, context_nodes)
            created_links.extend(semantic_links)
        
        # Update recent nodes list
        self._update_recent_nodes(node.id, node.created_at)
        
        return created_links
    
    async def _create_temporal_links(self, node: MemoryNode) -> list[Link]:
        """Create temporal links to recently created nodes."""
        links = []
        current_time = node.created_at
        cutoff = current_time - self.config.temporal_window
        
        # Find nodes within temporal window
        recent_in_window = [
            (node_id, ts) for node_id, ts in self._recent_nodes
            if ts >= cutoff and node_id != node.id
        ]
        
        # Sort by recency and take top N
        recent_in_window.sort(key=lambda x: x[1], reverse=True)
        targets = recent_in_window[:self.config.max_temporal_links]
        
        for target_id, target_ts in targets:
            # Create link from newer to older (temporal sequence)
            link = Link(
                source_id=node.id,
                target_id=target_id,
                link_type=LinkType.TEMPORAL,
                weight=self._temporal_weight(current_time, target_ts)
            )
            await self._persist_link(link)
            links.append(link)
        
        return links
    
    async def _persist_link(self, link: Link) -> None:
        """Persist link to both graph and L3 storage."""
        # Add to in-memory graph
        await self.graph.add_link(link)
        
        # Persist to L3 if available
        if self._l3_available and self._l3:
            try:
                await self._l3.store_link(link)
            except Exception as e:
                # Log but don't fail - graph already has the link
                print(f"[Router] Failed to persist link to L3: {e}")
    
    def _temporal_weight(self, time_a: float, time_b: float) -> float:
        """Calculate temporal link weight based on time difference.
        
        Closer in time = higher weight.
        """
        delta = abs(time_a - time_b)
        max_delta = self.config.temporal_window
        
        # Linear decay: weight = 1 - (delta / max_delta)
        weight = 1.0 - (delta / max_delta)
        return max(0.1, weight)
    
    async def _create_semantic_links(
        self,
        node: MemoryNode,
        candidates: list[MemoryNode]
    ) -> list[Link]:
        """Create semantic links to similar nodes."""
        links = []
        
        if not node.vector:
            return links
        
        # Calculate similarities
        similarities = []
        for candidate in candidates:
            if candidate.id == node.id or not candidate.vector:
                continue
            
            sim = self._cosine_similarity(node.vector, candidate.vector)
            if sim >= self.config.semantic_threshold:
                similarities.append((candidate.id, sim))
        
        # Sort by similarity and take top N
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_candidates = similarities[:self.config.max_semantic_links]
        
        for target_id, sim in top_candidates:
            link = Link(
                source_id=node.id,
                target_id=target_id,
                link_type=LinkType.SEMANTIC,
                weight=sim
            )
            await self._persist_link(link)
            links.append(link)
        
        return links
    
    def _cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec_a) != len(vec_b):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    async def create_causal_link(
        self,
        cause_id: str,
        effect_id: str,
        confidence: float = 1.0
    ) -> Link | None:
        """Explicitly create a causal link between nodes.
        
        Args:
            cause_id: ID of the cause node
            effect_id: ID of the effect node
            confidence: Confidence in the causal relationship
        
        Returns:
            Created link or None if below threshold
        """
        if confidence < self.config.causal_confidence_threshold:
            return None
        
        link = Link(
            source_id=cause_id,
            target_id=effect_id,
            link_type=LinkType.CAUSAL,
            weight=confidence
        )
        await self._persist_link(link)
        return link
    
    async def infer_causal_links(
        self,
        node: MemoryNode,
        candidates: list[MemoryNode]
    ) -> list[Link]:
        """Attempt to infer causal relationships using LLM.
        
        Only called if causal strategy is not DISABLED and callback is set.
        """
        if (self.config.causal_strategy == LinkStrategy.DISABLED 
            or not self._infer_causal_callback):
            return []
        
        links = []
        
        for candidate in candidates:
            if candidate.id == node.id:
                continue
            
            try:
                # Check if node causes candidate
                confidence = await self._infer_causal_callback(
                    node.content,
                    candidate.content
                )
                
                if confidence >= self.config.causal_confidence_threshold:
                    link = await self.create_causal_link(
                        node.id,
                        candidate.id,
                        confidence
                    )
                    if link:
                        links.append(link)
            except Exception:
                continue
        
        return links
    
    async def strengthen_path(
        self,
        node_ids: list[str],
        boost: float = 0.1
    ) -> None:
        """Strengthen links along a path of co-activated nodes.
        
        Called when nodes are accessed together (Hebbian-like learning).
        """
        for i in range(len(node_ids) - 1):
            await self.graph.strengthen_link(
                node_ids[i],
                node_ids[i + 1],
                boost
            )
    
    async def get_associated_nodes(
        self,
        node_id: str,
        link_types: list[LinkType] | None = None,
        max_hops: int = 1
    ) -> dict[str, float]:
        """Get nodes associated with a given node.
        
        Args:
            node_id: Starting node
            link_types: Filter by link types (None = all)
            max_hops: Maximum traversal depth
        
        Returns:
            Dict of {node_id: association_score}
        """
        if max_hops == 1:
            # Direct neighbors only
            neighbors = await self.graph.get_neighbors(node_id, direction="both")
            
            result = {}
            for neighbor_id, link in neighbors:
                if link_types and link.link_type not in link_types:
                    continue
                result[neighbor_id] = link.weight
            
            return result
        else:
            # Use spreading activation for multi-hop
            return await self.graph.spread_activation(
                [node_id],
                max_hops=max_hops,
                decay_factor=0.5
            )
    
    def _update_recent_nodes(self, node_id: str, timestamp: float) -> None:
        """Update the recent nodes list."""
        self._recent_nodes.append((node_id, timestamp))
        
        # Trim if too large
        if len(self._recent_nodes) > self._max_recent:
            # Remove oldest entries
            self._recent_nodes.sort(key=lambda x: x[1], reverse=True)
            self._recent_nodes = self._recent_nodes[:self._max_recent]
    
    async def remove_node_links(self, node_id: str) -> int:
        """Remove all links for a node being deleted.
        
        Returns number of links removed.
        """
        links = await self.graph.get_links(node_id)
        count = 0
        
        for link in links:
            removed = await self.graph.remove_link(
                link.source_id,
                link.target_id,
                link.link_type.value
            )
            if removed:
                count += 1
        
        # Also remove node from recent list
        self._recent_nodes = [
            (nid, ts) for nid, ts in self._recent_nodes
            if nid != node_id
        ]
        
        return count
