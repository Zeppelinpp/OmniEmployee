"""L1 Working Memory - High-speed in-memory storage.

Working Canvas: Contains the most relevant, high-energy nodes for the current task.
Implementation: Python Dict (dev) / Redis (production).
"""

from __future__ import annotations

import time
import heapq
from typing import Any
from dataclasses import dataclass, field

from src.omniemployee.memory.models import MemoryNode, Link
from src.omniemployee.memory.storage.base import StorageBackend


@dataclass
class L1Config:
    """Configuration for L1 Working Memory."""
    max_nodes: int = 100        # Maximum nodes to keep in working memory
    ttl_seconds: float = 3600   # Time-to-live for inactive nodes (1 hour)
    min_energy: float = 0.1     # Minimum energy to stay in L1


class L1WorkingMemory(StorageBackend):
    """In-memory working canvas for high-speed access.
    
    Maintains Top-K high-energy nodes relevant to current task.
    Automatically evicts low-energy or stale nodes.
    Supports multi-user isolation via user_id filtering.
    """
    
    def __init__(self, config: L1Config | None = None):
        self.config = config or L1Config()
        self._nodes: dict[str, MemoryNode] = {}
        self._connected = False
    
    def _filter_by_user(self, nodes: list[MemoryNode], user_id: str = "") -> list[MemoryNode]:
        """Filter nodes by user_id. Empty user_id returns all nodes."""
        if not user_id:
            return nodes
        return [n for n in nodes if n.user_id == user_id]
    
    async def connect(self) -> None:
        """Initialize the working memory."""
        self._connected = True
    
    async def disconnect(self) -> None:
        """Clean up resources."""
        self._nodes.clear()
        self._connected = False
    
    async def put(self, node: MemoryNode) -> None:
        """Store a node in working memory.
        
        If capacity is exceeded, evicts lowest-energy nodes.
        """
        self._nodes[node.id] = node
        node.tier = "L1"
        
        # Evict if over capacity
        if len(self._nodes) > self.config.max_nodes:
            await self._evict_lowest_energy()
    
    async def get(self, node_id: str) -> MemoryNode | None:
        """Retrieve a node and update its access time."""
        node = self._nodes.get(node_id)
        if node:
            node.touch()
        return node
    
    async def delete(self, node_id: str) -> bool:
        """Remove a node from working memory."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            return True
        return False
    
    async def exists(self, node_id: str) -> bool:
        return node_id in self._nodes
    
    async def list_all(self, user_id: str = "") -> list[MemoryNode]:
        """List all nodes, sorted by energy (descending). Filter by user_id if provided."""
        nodes = self._filter_by_user(list(self._nodes.values()), user_id)
        return sorted(nodes, key=lambda n: n.energy, reverse=True)
    
    async def count(self, user_id: str = "") -> int:
        """Count nodes. Filter by user_id if provided."""
        if not user_id:
            return len(self._nodes)
        return len([n for n in self._nodes.values() if n.user_id == user_id])
    
    async def clear(self) -> None:
        self._nodes.clear()
    
    async def get_top_k(self, k: int, user_id: str = "") -> list[MemoryNode]:
        """Get top K highest-energy nodes. Filter by user_id if provided."""
        nodes = self._filter_by_user(list(self._nodes.values()), user_id)
        return heapq.nlargest(k, nodes, key=lambda n: n.energy)
    
    async def get_by_energy_threshold(self, min_energy: float, user_id: str = "") -> list[MemoryNode]:
        """Get all nodes above energy threshold. Filter by user_id if provided."""
        nodes = self._filter_by_user(list(self._nodes.values()), user_id)
        return [n for n in nodes if n.energy >= min_energy]
    
    async def get_recent(self, limit: int = 10, user_id: str = "") -> list[MemoryNode]:
        """Get most recently accessed nodes. Filter by user_id if provided."""
        nodes = self._filter_by_user(list(self._nodes.values()), user_id)
        return sorted(nodes, key=lambda n: n.last_accessed, reverse=True)[:limit]
    
    async def update_energy(self, node_id: str, new_energy: float) -> bool:
        """Update energy for a node."""
        node = self._nodes.get(node_id)
        if node:
            node.energy = max(0.0, min(1.0, new_energy))
            return True
        return False
    
    async def boost_energy(self, node_id: str, boost: float = 0.1) -> bool:
        """Boost energy for a node (e.g., when accessed)."""
        node = self._nodes.get(node_id)
        if node:
            node.energy = min(1.0, node.energy + boost)
            node.touch()
            return True
        return False
    
    async def _evict_lowest_energy(self) -> list[MemoryNode]:
        """Evict lowest-energy nodes to stay within capacity.
        
        Returns evicted nodes (for potential demotion to L2).
        """
        if len(self._nodes) <= self.config.max_nodes:
            return []
        
        # Find nodes to evict
        nodes = list(self._nodes.values())
        nodes_sorted = sorted(nodes, key=lambda n: n.energy)
        
        evict_count = len(self._nodes) - self.config.max_nodes
        to_evict = nodes_sorted[:evict_count]
        
        evicted = []
        for node in to_evict:
            del self._nodes[node.id]
            evicted.append(node)
        
        return evicted
    
    async def cleanup_stale(self) -> list[MemoryNode]:
        """Remove nodes that haven't been accessed within TTL.
        
        Returns removed nodes (for potential archival).
        """
        current_time = time.time()
        cutoff = current_time - self.config.ttl_seconds
        
        stale_ids = [
            node_id for node_id, node in self._nodes.items()
            if node.last_accessed < cutoff
        ]
        
        removed = []
        for node_id in stale_ids:
            node = self._nodes.pop(node_id)
            removed.append(node)
        
        return removed
    
    async def cleanup_low_energy(self) -> list[MemoryNode]:
        """Remove nodes below minimum energy threshold.
        
        Returns removed nodes (for potential demotion).
        """
        low_energy_ids = [
            node_id for node_id, node in self._nodes.items()
            if node.energy < self.config.min_energy
        ]
        
        removed = []
        for node_id in low_energy_ids:
            node = self._nodes.pop(node_id)
            removed.append(node)
        
        return removed
    
    def get_stats(self, user_id: str = "") -> dict[str, Any]:
        """Get statistics about working memory state. Filter by user_id if provided."""
        nodes = self._filter_by_user(list(self._nodes.values()), user_id) if user_id else list(self._nodes.values())
        
        if not nodes:
            return {
                "count": 0,
                "capacity": self.config.max_nodes,
                "usage_percent": 0.0,
                "avg_energy": 0.0,
                "min_energy": 0.0,
                "max_energy": 0.0,
            }
        
        energies = [n.energy for n in nodes]
        return {
            "count": len(nodes),
            "capacity": self.config.max_nodes,
            "usage_percent": len(nodes) / self.config.max_nodes * 100,
            "avg_energy": sum(energies) / len(energies),
            "min_energy": min(energies),
            "max_energy": max(energies),
        }
