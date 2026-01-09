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
        else:
            # Load existing collection for searching
            self._client.load_collection(self.config.collection_name)
        
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
        
        # Load collection for searching
        self._client.load_collection(self.config.collection_name)
    
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
            # Use generate_embedding directly (encode returns MemoryNode)
            embedding = await self._encoder.generate_embedding(text)
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
        query_vector = await self._encoder.generate_embedding(query)
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
    
    async def search_with_cluster_expansion(
        self,
        query: str,
        top_k: int = 5,
        expansion_k: int = 3,
        min_score: float = 0.5,
    ) -> list[tuple[str, float]]:
        """Search for knowledge with cluster expansion.
        
        1. First retrieve top_k most relevant triples
        2. For each retrieved triple, find expansion_k related triples
        3. Return the combined, deduplicated results
        
        This mimics how human knowledge recall works - activating a concept
        also activates related concepts.
        
        Args:
            query: Search query text
            top_k: Initial retrieval count
            expansion_k: How many related items to expand per initial result
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of (triple_id, score) tuples (deduplicated, sorted by score)
        """
        if not self.is_available() or not self._encoder:
            return []
        
        # Step 1: Initial search
        initial_results = await self.search(query, top_k=top_k, min_score=min_score)
        
        if not initial_results:
            return []
        
        # Collect results with their scores (use dict for dedup)
        all_results: dict[str, float] = {}
        for triple_id, score in initial_results:
            all_results[triple_id] = score
        
        # Step 2: Cluster expansion - for each result, find related triples
        for triple_id, initial_score in initial_results:
            related = await self._find_related_triples(
                triple_id, 
                k=expansion_k, 
                min_score=min_score * 0.8  # Slightly lower threshold for expansion
            )
            
            for related_id, related_score in related:
                if related_id not in all_results:
                    # Decay the score for expanded results
                    # Score = initial_score * related_score * decay_factor
                    expanded_score = initial_score * related_score * 0.7
                    if expanded_score >= min_score * 0.5:  # Lower threshold for expanded
                        all_results[related_id] = expanded_score
                elif all_results[related_id] < related_score:
                    # Update if found a higher score path
                    all_results[related_id] = related_score
        
        # Sort by score (descending)
        sorted_results = sorted(
            all_results.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return sorted_results
    
    async def _find_related_triples(
        self,
        triple_id: str,
        k: int = 3,
        min_score: float = 0.4,
    ) -> list[tuple[str, float]]:
        """Find triples related to a given triple by vector similarity.
        
        Args:
            triple_id: The seed triple to find related items for
            k: Number of related triples to find
            min_score: Minimum similarity score
            
        Returns:
            List of (triple_id, score) tuples
        """
        if not self.is_available():
            return []
        
        # Get the vector for this triple
        try:
            results = self._client.get(
                collection_name=self.config.collection_name,
                ids=[triple_id],
                output_fields=["vector"]
            )
            
            if not results or not results[0].get("vector"):
                return []
            
            seed_vector = results[0]["vector"]
            
            # Search for similar vectors (k+1 to exclude self)
            search_results = self._client.search(
                collection_name=self.config.collection_name,
                data=[seed_vector],
                limit=k + 1,
                output_fields=["triple_id"],
            )
            
            # Parse results, excluding the seed itself
            related = []
            for hits in search_results:
                for hit in hits:
                    found_id = hit["entity"]["triple_id"]
                    if found_id != triple_id:
                        score = 1.0 - (hit["distance"] / 2.0)
                        if score >= min_score:
                            related.append((found_id, score))
            
            return related[:k]  # Ensure we return at most k results
            
        except Exception:
            return []
    
    async def get_subject_cluster(
        self,
        subject: str,
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """Get all knowledge triples related to a subject.
        
        This retrieves all triples that mention the subject (directly or semantically)
        forming a knowledge cluster around that entity.
        
        Args:
            subject: The subject/entity to find knowledge about
            limit: Maximum results
            
        Returns:
            List of (triple_id, score) tuples
        """
        return await self.search(subject, top_k=limit, min_score=0.3)