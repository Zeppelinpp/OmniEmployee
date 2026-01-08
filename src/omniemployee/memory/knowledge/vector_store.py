"""Knowledge Vector Store - Milvus-based semantic search for knowledge triples.

Provides semantic similarity search for knowledge triples using vector embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.omniemployee.memory.knowledge.models import KnowledgeTriple


@dataclass
class KnowledgeVectorConfig:
    """Configuration for knowledge vector storage."""
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "biem_knowledge"
    vector_dim: int = 1024  # bge-m3 default
    index_type: str = "IVF_FLAT"
    metric_type: str = "COSINE"
    nlist: int = 128
    use_lite: bool = False


class KnowledgeVectorStore:
    """Milvus-based vector store for knowledge triples.
    
    Stores vector embeddings of knowledge triples for semantic search.
    Works alongside the PostgreSQL store for structured data.
    """
    
    def __init__(self, config: KnowledgeVectorConfig | None = None):
        self.config = config or KnowledgeVectorConfig()
        self._client = None
        self._connected = False
        self._encoder = None
    
    async def connect(self) -> None:
        """Connect to Milvus and ensure collection exists."""
        from pymilvus import MilvusClient, DataType
        
        if self.config.use_lite:
            self._client = MilvusClient("./milvus_knowledge.db")
        else:
            uri = f"http://{self.config.host}:{self.config.port}"
            self._client = MilvusClient(uri=uri)
        
        # Create collection if not exists
        if not self._client.has_collection(self.config.collection_name):
            await self._create_collection()
        
        self._connected = True
    
    async def _create_collection(self) -> None:
        """Create the knowledge vectors collection."""
        from pymilvus import DataType
        
        schema = self._client.create_schema(auto_id=False, enable_dynamic_field=True)
        
        schema.add_field("triple_id", DataType.VARCHAR, max_length=64, is_primary=True)
        schema.add_field("user_id", DataType.VARCHAR, max_length=64)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=self.config.vector_dim)
        schema.add_field("subject", DataType.VARCHAR, max_length=255)
        schema.add_field("predicate", DataType.VARCHAR, max_length=255)
        
        self._client.create_collection(
            collection_name=self.config.collection_name,
            schema=schema,
        )
        
        # Create vector index
        index_params = self._client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            index_type=self.config.index_type,
            metric_type=self.config.metric_type,
            params={"nlist": self.config.nlist}
        )
        
        self._client.create_index(
            collection_name=self.config.collection_name,
            index_params=index_params
        )
    
    async def disconnect(self) -> None:
        """Disconnect from Milvus."""
        if self._client:
            self._client.close()
        self._connected = False
    
    def is_available(self) -> bool:
        """Check if store is connected."""
        return self._connected and self._client is not None
    
    async def set_encoder(self, encoder) -> None:
        """Set the encoder for generating embeddings.
        
        Args:
            encoder: Encoder instance from memory.operators.encoder
        """
        self._encoder = encoder
    
    async def store(self, triple: KnowledgeTriple) -> bool:
        """Store a knowledge triple with its vector embedding.
        
        Args:
            triple: The knowledge triple to store
            
        Returns:
            True if stored successfully
        """
        if not self.is_available():
            return False
        
        # Generate embedding if not present
        if not triple.vector and self._encoder:
            text = triple.to_text()
            embedding = await self._encoder.encode(text)
            if embedding:
                triple.vector = embedding
        
        if not triple.vector:
            return False
        
        # Prepare data
        data = {
            "triple_id": triple.id,
            "user_id": triple.user_id,
            "vector": triple.vector,
            "subject": triple.subject,
            "predicate": triple.predicate,
        }
        
        # Upsert to collection
        self._client.upsert(
            collection_name=self.config.collection_name,
            data=[data]
        )
        
        return True
    
    async def search(
        self,
        query: str,
        user_id: str = "",
        top_k: int = 10,
        min_score: float = 0.5,
    ) -> list[tuple[str, float]]:
        """Search for similar knowledge triples.
        
        Args:
            query: Search query text
            user_id: Filter by user ID
            top_k: Maximum results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of (triple_id, score) tuples
        """
        if not self.is_available() or not self._encoder:
            return []
        
        # Generate query embedding
        query_vector = await self._encoder.encode(query)
        if not query_vector:
            return []
        
        # Build filter
        filter_expr = ""
        if user_id:
            filter_expr = f'user_id == "{user_id}"'
        
        # Search
        results = self._client.search(
            collection_name=self.config.collection_name,
            data=[query_vector],
            filter=filter_expr if filter_expr else None,
            limit=top_k,
            output_fields=["triple_id", "subject", "predicate"],
        )
        
        # Parse results
        matches = []
        for hits in results:
            for hit in hits:
                # Cosine distance: 0 = identical, 2 = opposite
                # Convert to similarity: 1 - (distance / 2)
                score = 1.0 - (hit["distance"] / 2.0)
                if score >= min_score:
                    matches.append((hit["entity"]["triple_id"], score))
        
        return matches
    
    async def delete(self, triple_id: str) -> bool:
        """Delete a knowledge triple's vector.
        
        Args:
            triple_id: The triple ID to delete
            
        Returns:
            True if deleted successfully
        """
        if not self.is_available():
            return False
        
        self._client.delete(
            collection_name=self.config.collection_name,
            filter=f'triple_id == "{triple_id}"'
        )
        return True
    
    async def get_stats(self) -> dict[str, Any]:
        """Get collection statistics."""
        if not self.is_available():
            return {"status": "unavailable"}
        
        stats = self._client.get_collection_stats(self.config.collection_name)
        return {
            "row_count": stats.get("row_count", 0),
            "collection": self.config.collection_name,
        }
