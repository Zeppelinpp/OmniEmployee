"""Abstract base classes for storage backends."""

from abc import ABC, abstractmethod
from typing import Any

from src.omniemployee.memory.models import MemoryNode, Link


class StorageBackend(ABC):
    """Abstract base class for all storage backends."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the storage."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the storage."""
        pass
    
    @abstractmethod
    async def put(self, node: MemoryNode) -> None:
        """Store a memory node."""
        pass
    
    @abstractmethod
    async def get(self, node_id: str) -> MemoryNode | None:
        """Retrieve a memory node by ID."""
        pass
    
    @abstractmethod
    async def delete(self, node_id: str) -> bool:
        """Delete a memory node by ID."""
        pass
    
    @abstractmethod
    async def exists(self, node_id: str) -> bool:
        """Check if a node exists."""
        pass
    
    @abstractmethod
    async def list_all(self) -> list[MemoryNode]:
        """List all nodes in storage."""
        pass
    
    @abstractmethod
    async def count(self) -> int:
        """Get total count of nodes."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all nodes from storage."""
        pass


class VectorStorageBackend(StorageBackend):
    """Extended interface for vector-capable storage."""
    
    @abstractmethod
    async def search_by_vector(
        self, 
        vector: list[float], 
        top_k: int = 10,
        filters: dict[str, Any] | None = None
    ) -> list[tuple[MemoryNode, float]]:
        """Search by vector similarity.
        
        Returns list of (node, similarity_score) tuples.
        """
        pass
    
    @abstractmethod
    async def update_vector(self, node_id: str, vector: list[float]) -> bool:
        """Update the vector for a node."""
        pass


class GraphStorageBackend(ABC):
    """Interface for graph-based storage of relationships."""
    
    @abstractmethod
    async def add_link(self, link: Link) -> None:
        """Add a link between nodes."""
        pass
    
    @abstractmethod
    async def remove_link(self, source_id: str, target_id: str, link_type: str) -> bool:
        """Remove a specific link."""
        pass
    
    @abstractmethod
    async def get_neighbors(
        self, 
        node_id: str, 
        link_type: str | None = None,
        direction: str = "out"  # "out", "in", "both"
    ) -> list[tuple[str, Link]]:
        """Get neighboring node IDs and their links."""
        pass
    
    @abstractmethod
    async def get_links(self, node_id: str) -> list[Link]:
        """Get all links for a node."""
        pass
    
    @abstractmethod
    async def spread_activation(
        self,
        start_ids: list[str],
        max_hops: int = 2,
        decay_factor: float = 0.5
    ) -> dict[str, float]:
        """Perform spreading activation from starting nodes.
        
        Returns dict of {node_id: activation_score}.
        """
        pass
