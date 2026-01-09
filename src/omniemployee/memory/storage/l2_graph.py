"""L2 Graph Storage - NetworkX-based relationship management.

Association Web (Graph Part): Manages relationships between memory nodes.
Implementation: NetworkX (pure Python, easy debugging and serialization).
"""

from __future__ import annotations

import json
import time
from typing import Any
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

import networkx as nx

from src.omniemployee.memory.models import Link, LinkType
from src.omniemployee.memory.storage.base import GraphStorageBackend


@dataclass
class GraphConfig:
    """Configuration for graph storage."""
    persist_path: str | None = None  # Path for JSON persistence
    auto_save: bool = True           # Auto-save on modifications
    max_edges_per_node: int = 50     # Limit edges to prevent explosion


class L2GraphStorage(GraphStorageBackend):
    """NetworkX-based graph storage for memory relationships.
    
    Manages temporal, semantic, and causal links between memory nodes.
    Supports spreading activation for associative recall.
    Supports multi-user isolation via user_id on nodes.
    """
    
    def __init__(self, config: GraphConfig | None = None):
        self.config = config or GraphConfig()
        self._graph: nx.DiGraph = nx.DiGraph()
        self._connected = False
    
    def _get_user_nodes(self, user_id: str = "") -> set[str]:
        """Get node IDs belonging to a specific user. Empty user_id returns all."""
        if not user_id:
            return set(self._graph.nodes())
        return {n for n in self._graph.nodes() if self._graph.nodes[n].get("user_id", "") == user_id}
    
    async def connect(self) -> None:
        """Initialize graph, loading from persistence if available."""
        if self.config.persist_path:
            path = Path(self.config.persist_path)
            if path.exists():
                await self._load_from_file(path)
        self._connected = True
    
    async def disconnect(self) -> None:
        """Save graph to persistence if configured."""
        if self.config.persist_path and self.config.auto_save:
            await self._save_to_file(Path(self.config.persist_path))
        self._connected = False
    
    async def add_node(self, node_id: str, user_id: str = "") -> None:
        """Add a node to the graph (without edges)."""
        if not self._graph.has_node(node_id):
            self._graph.add_node(node_id, created_at=time.time(), user_id=user_id)
        elif user_id and not self._graph.nodes[node_id].get("user_id"):
            # Update user_id if not set
            self._graph.nodes[node_id]["user_id"] = user_id
    
    async def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        if self._graph.has_node(node_id):
            self._graph.remove_node(node_id)
            await self._auto_save()
            return True
        return False
    
    async def add_link(self, link: Link, user_id: str = "") -> None:
        """Add a directed link between nodes."""
        # Ensure nodes exist with user_id
        await self.add_node(link.source_id, user_id)
        await self.add_node(link.target_id, user_id)
        
        # Check edge limit
        out_degree = self._graph.out_degree(link.source_id)
        if out_degree >= self.config.max_edges_per_node:
            # Remove weakest edge
            await self._prune_weakest_edge(link.source_id)
        
        # Add or update edge
        self._graph.add_edge(
            link.source_id,
            link.target_id,
            link_type=link.link_type.value,
            weight=link.weight,
            created_at=link.created_at
        )
        
        await self._auto_save()
    
    async def remove_link(self, source_id: str, target_id: str, link_type: str) -> bool:
        """Remove a specific link."""
        if self._graph.has_edge(source_id, target_id):
            edge_data = self._graph.get_edge_data(source_id, target_id)
            if edge_data and edge_data.get("link_type") == link_type:
                self._graph.remove_edge(source_id, target_id)
                await self._auto_save()
                return True
        return False
    
    async def get_neighbors(
        self,
        node_id: str,
        link_type: str | None = None,
        direction: str = "out"
    ) -> list[tuple[str, Link]]:
        """Get neighboring nodes and their links.
        
        Args:
            node_id: Source node ID
            link_type: Filter by link type (None = all)
            direction: "out" (successors), "in" (predecessors), "both"
        """
        if not self._graph.has_node(node_id):
            return []
        
        neighbors = []
        
        if direction in ("out", "both"):
            for target_id in self._graph.successors(node_id):
                edge = self._graph.get_edge_data(node_id, target_id)
                if link_type and edge.get("link_type") != link_type:
                    continue
                link = Link(
                    source_id=node_id,
                    target_id=target_id,
                    link_type=LinkType(edge["link_type"]),
                    weight=edge.get("weight", 1.0),
                    created_at=edge.get("created_at", 0)
                )
                neighbors.append((target_id, link))
        
        if direction in ("in", "both"):
            for source_id in self._graph.predecessors(node_id):
                edge = self._graph.get_edge_data(source_id, node_id)
                if link_type and edge.get("link_type") != link_type:
                    continue
                link = Link(
                    source_id=source_id,
                    target_id=node_id,
                    link_type=LinkType(edge["link_type"]),
                    weight=edge.get("weight", 1.0),
                    created_at=edge.get("created_at", 0)
                )
                neighbors.append((source_id, link))
        
        return neighbors
    
    async def get_links(self, node_id: str) -> list[Link]:
        """Get all links (outgoing) for a node."""
        links = []
        if self._graph.has_node(node_id):
            for target_id in self._graph.successors(node_id):
                edge = self._graph.get_edge_data(node_id, target_id)
                link = Link(
                    source_id=node_id,
                    target_id=target_id,
                    link_type=LinkType(edge["link_type"]),
                    weight=edge.get("weight", 1.0),
                    created_at=edge.get("created_at", 0)
                )
                links.append(link)
        return links
    
    async def spread_activation(
        self,
        start_ids: list[str],
        max_hops: int = 2,
        decay_factor: float = 0.5,
        user_id: str = ""
    ) -> dict[str, float]:
        """Perform spreading activation from starting nodes.
        
        Simulates activation spreading through the network.
        Each hop, activation decays by decay_factor.
        Only spreads within nodes belonging to the same user_id.
        
        Returns:
            Dict of {node_id: activation_score}
        """
        activation: dict[str, float] = defaultdict(float)
        
        # Get valid nodes for this user
        valid_nodes = self._get_user_nodes(user_id)
        
        # Initialize starting nodes with activation 1.0
        current_wave = {node_id: 1.0 for node_id in start_ids if node_id in valid_nodes}
        
        for node_id, score in current_wave.items():
            activation[node_id] = max(activation[node_id], score)
        
        for hop in range(max_hops):
            next_wave: dict[str, float] = {}
            
            for node_id, score in current_wave.items():
                # Spread to neighbors (only within same user's nodes)
                for neighbor_id in self._graph.successors(node_id):
                    if neighbor_id not in valid_nodes:
                        continue
                    edge = self._graph.get_edge_data(node_id, neighbor_id)
                    weight = edge.get("weight", 1.0)
                    
                    # Activation = previous_score * decay * edge_weight
                    new_activation = score * decay_factor * weight
                    
                    if new_activation > 0.01:  # Threshold to stop weak signals
                        current_activation = next_wave.get(neighbor_id, 0)
                        next_wave[neighbor_id] = max(current_activation, new_activation)
            
            # Update activation scores
            for node_id, score in next_wave.items():
                activation[node_id] = max(activation[node_id], score)
            
            current_wave = next_wave
            
            if not current_wave:
                break
        
        return dict(activation)
    
    async def find_path(
        self,
        source_id: str,
        target_id: str,
        max_length: int = 5
    ) -> list[str] | None:
        """Find shortest path between two nodes."""
        if not self._graph.has_node(source_id) or not self._graph.has_node(target_id):
            return None
        
        try:
            path = nx.shortest_path(
                self._graph,
                source=source_id,
                target=target_id
            )
            if len(path) <= max_length:
                return path
        except nx.NetworkXNoPath:
            pass
        
        return None
    
    async def get_connected_component(self, node_id: str) -> set[str]:
        """Get all nodes in the same weakly connected component."""
        if not self._graph.has_node(node_id):
            return set()
        
        # Convert to undirected for component analysis
        undirected = self._graph.to_undirected()
        for component in nx.connected_components(undirected):
            if node_id in component:
                return component
        
        return {node_id}
    
    async def get_strongly_connected(self, node_id: str) -> set[str]:
        """Get nodes in the same strongly connected component."""
        if not self._graph.has_node(node_id):
            return set()
        
        for component in nx.strongly_connected_components(self._graph):
            if node_id in component:
                return component
        
        return {node_id}
    
    async def update_link_weight(
        self,
        source_id: str,
        target_id: str,
        new_weight: float
    ) -> bool:
        """Update weight of an existing link."""
        if self._graph.has_edge(source_id, target_id):
            self._graph[source_id][target_id]["weight"] = new_weight
            await self._auto_save()
            return True
        return False
    
    async def strengthen_link(
        self,
        source_id: str,
        target_id: str,
        boost: float = 0.1
    ) -> bool:
        """Strengthen a link (e.g., when co-activated)."""
        if self._graph.has_edge(source_id, target_id):
            current = self._graph[source_id][target_id].get("weight", 1.0)
            self._graph[source_id][target_id]["weight"] = min(2.0, current + boost)
            await self._auto_save()
            return True
        return False
    
    async def _prune_weakest_edge(self, node_id: str) -> None:
        """Remove the weakest outgoing edge from a node."""
        edges = [
            (node_id, target, self._graph[node_id][target].get("weight", 1.0))
            for target in self._graph.successors(node_id)
        ]
        
        if edges:
            # Find weakest edge
            weakest = min(edges, key=lambda x: x[2])
            self._graph.remove_edge(weakest[0], weakest[1])
    
    async def _auto_save(self) -> None:
        """Save if auto_save is enabled."""
        if self.config.auto_save and self.config.persist_path:
            await self._save_to_file(Path(self.config.persist_path))
    
    async def _save_to_file(self, path: Path) -> None:
        """Serialize graph to JSON file."""
        data = {
            "nodes": list(self._graph.nodes()),
            "edges": [
                {
                    "source": u,
                    "target": v,
                    **d
                }
                for u, v, d in self._graph.edges(data=True)
            ]
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    
    async def _load_from_file(self, path: Path) -> None:
        """Load graph from JSON file."""
        data = json.loads(path.read_text())
        
        self._graph = nx.DiGraph()
        self._graph.add_nodes_from(data.get("nodes", []))
        
        for edge in data.get("edges", []):
            source = edge.pop("source")
            target = edge.pop("target")
            self._graph.add_edge(source, target, **edge)
    
    async def clear(self) -> None:
        """Clear all nodes and edges."""
        self._graph.clear()
        await self._auto_save()
    
    def get_stats(self) -> dict[str, Any]:
        """Get graph statistics."""
        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
            "density": nx.density(self._graph) if self._graph.number_of_nodes() > 0 else 0,
            "is_connected": nx.is_weakly_connected(self._graph) if self._graph.number_of_nodes() > 0 else True,
        }
