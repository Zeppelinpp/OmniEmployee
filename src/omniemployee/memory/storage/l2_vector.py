"""L2 Vector Storage - Milvus-based semantic search.

Association Web (Vector Part): Full contextual memory with vector similarity search.
Implementation: Milvus (supports scalar filtering, persistence, distributed scaling).
"""

from __future__ import annotations

import time
from typing import Any
from dataclasses import dataclass

from src.omniemployee.memory.models import MemoryNode, MemoryMetadata
from src.omniemployee.memory.storage.base import VectorStorageBackend


@dataclass
class MilvusConfig:
    """Configuration for Milvus connection."""
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "biem_memories"
    vector_dim: int = 1024          # bge-m3 default dimension
    index_type: str = "IVF_FLAT"
    metric_type: str = "COSINE"
    nlist: int = 128                # IVF clustering parameter
    use_lite: bool = False          # Use Milvus Standalone (Docker)


class L2VectorStorage(VectorStorageBackend):
    """Milvus-based vector storage for semantic search.
    
    Stores memory nodes with their vector embeddings for similarity search.
    Supports scalar filtering on metadata fields.
    """
    
    def __init__(self, config: MilvusConfig | None = None):
        self.config = config or MilvusConfig()
        self._client = None
        self._collection = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Milvus and ensure collection exists."""
        from pymilvus import MilvusClient, DataType
        
        if self.config.use_lite:
            # Milvus Lite - embedded mode for development
            self._client = MilvusClient("./milvus_biem.db")
        else:
            # Milvus Standalone/Cluster
            uri = f"http://{self.config.host}:{self.config.port}"
            self._client = MilvusClient(uri=uri)
        
        # Create collection if not exists
        if not self._client.has_collection(self.config.collection_name):
            await self._create_collection()
        
        self._connected = True
    
    async def _create_collection(self) -> None:
        """Create the Milvus collection with schema."""
        from pymilvus import DataType
        
        schema = self._client.create_schema(
            auto_id=False,
            enable_dynamic_field=True
        )
        
        # Primary key
        schema.add_field(
            field_name="id",
            datatype=DataType.VARCHAR,
            is_primary=True,
            max_length=64
        )
        
        # Content field
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        
        # Vector embedding
        schema.add_field(
            field_name="vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=self.config.vector_dim
        )
        
        # Scalar fields for filtering
        schema.add_field(
            field_name="energy",
            datatype=DataType.FLOAT
        )
        schema.add_field(
            field_name="timestamp",
            datatype=DataType.INT64
        )
        schema.add_field(
            field_name="last_accessed",
            datatype=DataType.INT64
        )
        schema.add_field(
            field_name="tier",
            datatype=DataType.VARCHAR,
            max_length=8
        )
        schema.add_field(
            field_name="sentiment",
            datatype=DataType.FLOAT
        )
        
        # User ID for multi-user isolation
        schema.add_field(
            field_name="user_id",
            datatype=DataType.VARCHAR,
            max_length=64
        )
        
        # Index parameters
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type=self.config.index_type,
            metric_type=self.config.metric_type,
            params={"nlist": self.config.nlist}
        )
        
        self._client.create_collection(
            collection_name=self.config.collection_name,
            schema=schema,
            index_params=index_params
        )
    
    async def disconnect(self) -> None:
        """Close connection to Milvus."""
        if self._client:
            self._client.close()
        self._connected = False
    
    async def put(self, node: MemoryNode) -> None:
        """Store a memory node in Milvus."""
        if not node.vector:
            raise ValueError("Node must have a vector embedding")
        
        data = {
            "id": node.id,
            "content": node.content,
            "vector": node.vector,
            "energy": node.energy,
            "timestamp": int(node.metadata.timestamp),
            "last_accessed": int(node.last_accessed),
            "tier": node.tier,
            "sentiment": node.metadata.sentiment,
            "user_id": node.user_id,
            # Dynamic fields
            "entities": node.metadata.entities,
            "source": node.metadata.source,
            "initial_energy": node.initial_energy,
            "created_at": int(node.created_at),
        }
        
        self._client.upsert(
            collection_name=self.config.collection_name,
            data=[data]
        )
    
    async def get(self, node_id: str) -> MemoryNode | None:
        """Retrieve a node by ID."""
        results = self._client.get(
            collection_name=self.config.collection_name,
            ids=[node_id],
            output_fields=["*"]
        )
        
        if not results:
            return None
        
        return self._result_to_node(results[0])
    
    async def delete(self, node_id: str) -> bool:
        """Delete a node by ID."""
        result = self._client.delete(
            collection_name=self.config.collection_name,
            ids=[node_id]
        )
        return True
    
    async def exists(self, node_id: str) -> bool:
        """Check if a node exists."""
        results = self._client.get(
            collection_name=self.config.collection_name,
            ids=[node_id],
            output_fields=["id"]
        )
        return len(results) > 0
    
    async def list_all(self, user_id: str = "") -> list[MemoryNode]:
        """List all nodes (limited to avoid memory issues). Filter by user_id if provided."""
        filter_expr = f'user_id == "{user_id}"' if user_id else ""
        results = self._client.query(
            collection_name=self.config.collection_name,
            filter=filter_expr,
            output_fields=["*"],
            limit=1000
        )
        return [self._result_to_node(r) for r in results]
    
    async def count(self) -> int:
        """Get total node count."""
        stats = self._client.get_collection_stats(self.config.collection_name)
        return stats.get("row_count", 0)
    
    async def clear(self) -> None:
        """Clear all nodes from collection."""
        self._client.drop_collection(self.config.collection_name)
        await self._create_collection()
    
    async def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        user_id: str = ""
    ) -> list[tuple[MemoryNode, float]]:
        """Search by vector similarity with optional filters.
        
        Args:
            vector: Query vector
            top_k: Number of results
            filters: Scalar filters (e.g., {"energy": {"$gte": 0.5}})
            user_id: Filter by user ID (empty = no filter)
        
        Returns:
            List of (node, similarity_score) tuples
        """
        # Build filter expression
        filter_parts = []
        if filters:
            filter_parts.append(self._build_filter_expr(filters))
        if user_id:
            filter_parts.append(f'user_id == "{user_id}"')
        filter_expr = " and ".join(filter_parts) if filter_parts else ""
        
        results = self._client.search(
            collection_name=self.config.collection_name,
            data=[vector],
            limit=top_k,
            filter=filter_expr,
            output_fields=["*"],
            search_params={"metric_type": self.config.metric_type}
        )
        
        if not results or not results[0]:
            return []
        
        nodes_with_scores = []
        for hit in results[0]:
            node = self._result_to_node(hit["entity"])
            score = hit["distance"]  # Cosine similarity
            nodes_with_scores.append((node, score))
        
        return nodes_with_scores
    
    async def search_by_energy_range(
        self,
        min_energy: float = 0.0,
        max_energy: float = 1.0,
        limit: int = 100,
        user_id: str = ""
    ) -> list[MemoryNode]:
        """Query nodes within an energy range. Filter by user_id if provided."""
        filter_parts = [f"energy >= {min_energy}", f"energy <= {max_energy}"]
        if user_id:
            filter_parts.append(f'user_id == "{user_id}"')
        filter_expr = " and ".join(filter_parts)
        
        results = self._client.query(
            collection_name=self.config.collection_name,
            filter=filter_expr,
            output_fields=["*"],
            limit=limit
        )
        
        return [self._result_to_node(r) for r in results]
    
    async def update_vector(self, node_id: str, vector: list[float]) -> bool:
        """Update vector for an existing node."""
        node = await self.get(node_id)
        if not node:
            return False
        
        node.vector = vector
        await self.put(node)
        return True
    
    async def update_energy(self, node_id: str, energy: float) -> bool:
        """Update energy for a node."""
        node = await self.get(node_id)
        if not node:
            return False
        
        node.energy = energy
        await self.put(node)
        return True
    
    async def batch_update_energy(self, updates: dict[str, float]) -> int:
        """Batch update energy for multiple nodes.
        
        Args:
            updates: Dict of {node_id: new_energy}
        
        Returns:
            Number of successfully updated nodes
        """
        updated = 0
        for node_id, energy in updates.items():
            if await self.update_energy(node_id, energy):
                updated += 1
        return updated
    
    def _build_filter_expr(self, filters: dict[str, Any]) -> str:
        """Build Milvus filter expression from dict."""
        conditions = []
        
        for field, value in filters.items():
            if isinstance(value, dict):
                # Operators: $gte, $lte, $gt, $lt, $eq, $ne
                for op, v in value.items():
                    if op == "$gte":
                        conditions.append(f"{field} >= {v}")
                    elif op == "$lte":
                        conditions.append(f"{field} <= {v}")
                    elif op == "$gt":
                        conditions.append(f"{field} > {v}")
                    elif op == "$lt":
                        conditions.append(f"{field} < {v}")
                    elif op == "$eq":
                        if isinstance(v, str):
                            conditions.append(f'{field} == "{v}"')
                        else:
                            conditions.append(f"{field} == {v}")
                    elif op == "$ne":
                        if isinstance(v, str):
                            conditions.append(f'{field} != "{v}"')
                        else:
                            conditions.append(f"{field} != {v}")
            else:
                # Direct equality
                if isinstance(value, str):
                    conditions.append(f'{field} == "{value}"')
                else:
                    conditions.append(f"{field} == {value}")
        
        return " and ".join(conditions)
    
    def _result_to_node(self, result: dict) -> MemoryNode:
        """Convert Milvus result to MemoryNode."""
        metadata = MemoryMetadata(
            timestamp=float(result.get("timestamp", time.time())),
            entities=result.get("entities", []),
            sentiment=result.get("sentiment", 0.0),
            source=result.get("source", ""),
        )
        
        return MemoryNode(
            id=result["id"],
            content=result.get("content", ""),
            vector=result.get("vector", []),
            metadata=metadata,
            energy=result.get("energy", 1.0),
            initial_energy=result.get("initial_energy", 1.0),
            last_accessed=float(result.get("last_accessed", time.time())),
            created_at=float(result.get("created_at", time.time())),
            tier=result.get("tier", "L2"),
            user_id=result.get("user_id", ""),
        )
    
    async def list_recent(self, limit: int = 100, user_id: str = "") -> list[MemoryNode]:
        """List most recently created nodes. Filter by user_id if provided."""
        filter_expr = f'user_id == "{user_id}"' if user_id else ""
        
        results = self._client.query(
            collection_name=self.config.collection_name,
            filter=filter_expr,
            output_fields=["*"],
            limit=limit
        )
        
        # Sort by created_at descending
        nodes = [self._result_to_node(r) for r in results]
        nodes.sort(key=lambda n: n.created_at, reverse=True)
        return nodes[:limit]
    
    def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        stats = self._client.get_collection_stats(self.config.collection_name)
        return {
            "row_count": stats.get("row_count", 0),
            "collection_name": self.config.collection_name,
            "vector_dim": self.config.vector_dim,
            "index_type": self.config.index_type,
        }
