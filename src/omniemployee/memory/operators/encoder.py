"""Encoder - Extracts entities, sentiment, and generates embeddings.

Responsible for processing raw input into structured memory metadata
and vector representations using Ollama embedding.
"""

from __future__ import annotations

import re
import ollama
from typing import Callable, Awaitable
from dataclasses import dataclass

from src.omniemployee.memory.models import MemoryNode, MemoryMetadata


@dataclass
class EncoderConfig:
    """Configuration for the Encoder module."""
    # Ollama embedding settings
    embedding_model: str = "bge-m3:latest"
    embedding_dim: int = 1024
    ollama_host: str | None = None  # None = default localhost:11434
    ollama_timeout: float = 60.0
    
    # NLP settings
    use_spacy: bool = False
    spacy_model: str = "en_core_web_sm"
    max_content_length: int = 8000


class Encoder:
    """Encodes content into memory nodes with metadata and embeddings.
    
    Uses Ollama Python library for vector embedding generation.
    Supports batch embedding for better performance.
    """
    
    def __init__(self, config: EncoderConfig | None = None):
        self.config = config or EncoderConfig()
        self._nlp = None
        self._client: ollama.AsyncClient | None = None
        self._initialized = False
        
        # Optional external embedding callback
        self._embed_callback: Callable[[str], Awaitable[list[float]]] | None = None
    
    async def initialize(self) -> None:
        """Initialize Ollama client and verify connection."""
        if self._initialized:
            return
        
        # Initialize Ollama async client
        self._client = ollama.AsyncClient(
            host=self.config.ollama_host,
            timeout=self.config.ollama_timeout
        )
        
        # Verify connection and detect embedding dimension
        await self._verify_ollama()
        
        # Initialize spaCy if enabled
        if self.config.use_spacy:
            try:
                import spacy
                self._nlp = spacy.load(self.config.spacy_model)
            except (ImportError, OSError):
                pass
        
        self._initialized = True
    
    async def _verify_ollama(self) -> None:
        """Verify Ollama connection and detect embedding dimension."""
        try:
            response = await self._client.embed(
                model=self.config.embedding_model,
                input="test"
            )
            
            if response and "embeddings" in response:
                actual_dim = len(response["embeddings"][0])
                if actual_dim != self.config.embedding_dim:
                    print(f"Updating embedding_dim: {self.config.embedding_dim} -> {actual_dim}")
                    self.config.embedding_dim = actual_dim
        except Exception as e:
            print(f"Warning: Could not verify Ollama: {e}")
            print(f"Ensure Ollama is running: ollama serve")
            print(f"Ensure model available: ollama pull {self.config.embedding_model}")
    
    async def close(self) -> None:
        """Release resources."""
        self._client = None
        self._initialized = False
    
    def set_embed_callback(self, callback: Callable[[str], Awaitable[list[float]]]) -> None:
        """Set external embedding callback (overrides Ollama)."""
        self._embed_callback = callback
    
    async def encode(
        self,
        content: str,
        source: str = "",
        location: str = "",
        tags: list[str] | None = None
    ) -> MemoryNode:
        """Encode content into a MemoryNode with embedding and metadata."""
        await self.initialize()
        
        entities = await self.extract_entities(content)
        sentiment = await self.analyze_sentiment(content)
        vector = await self.generate_embedding(content)
        
        metadata = MemoryMetadata(
            location=location,
            entities=entities,
            sentiment=sentiment,
            source=source,
            tags=tags or []
        )
        
        return MemoryNode(
            content=content,
            vector=vector,
            metadata=metadata,
            energy=1.0,
            tier="L1"
        )
    
    async def generate_embedding(self, content: str) -> list[float]:
        """Generate vector embedding using Ollama."""
        truncated = content[:self.config.max_content_length]
        
        # Use callback if set
        if self._embed_callback:
            try:
                return await self._embed_callback(truncated)
            except Exception as e:
                print(f"Embedding callback failed: {e}")
        
        # Use Ollama
        return await self._ollama_embed(truncated)
    
    async def generate_embeddings_batch(self, contents: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple contents in one call."""
        if not contents:
            return []
        
        truncated = [c[:self.config.max_content_length] for c in contents]
        return await self._ollama_embed_batch(truncated)
    
    async def _ollama_embed(self, content: str) -> list[float]:
        """Single embedding via Ollama."""
        if not self._client:
            await self.initialize()
        
        try:
            response = await self._client.embed(
                model=self.config.embedding_model,
                input=content
            )
            
            if response and "embeddings" in response:
                return response["embeddings"][0]
            
            return [0.0] * self.config.embedding_dim
            
        except Exception as e:
            print(f"Ollama embedding error: {e}")
            return [0.0] * self.config.embedding_dim
    
    async def _ollama_embed_batch(self, contents: list[str]) -> list[list[float]]:
        """Batch embedding via Ollama."""
        if not self._client:
            await self.initialize()
        
        try:
            response = await self._client.embed(
                model=self.config.embedding_model,
                input=contents
            )
            
            if response and "embeddings" in response:
                return response["embeddings"]
            
            return [[0.0] * self.config.embedding_dim for _ in contents]
            
        except Exception as e:
            print(f"Ollama batch embedding error: {e}")
            return [[0.0] * self.config.embedding_dim for _ in contents]
    
    async def batch_encode(
        self,
        contents: list[str],
        source: str = ""
    ) -> list[MemoryNode]:
        """Encode multiple contents with batch embedding."""
        await self.initialize()
        
        if not contents:
            return []
        
        embeddings = await self.generate_embeddings_batch(contents)
        
        nodes = []
        for i, content in enumerate(contents):
            entities = await self.extract_entities(content)
            sentiment = await self.analyze_sentiment(content)
            
            metadata = MemoryMetadata(
                entities=entities,
                sentiment=sentiment,
                source=source
            )
            
            vector = embeddings[i] if i < len(embeddings) else [0.0] * self.config.embedding_dim
            
            nodes.append(MemoryNode(
                content=content,
                vector=vector,
                metadata=metadata,
                energy=1.0,
                tier="L1"
            ))
        
        return nodes
    
    # ==================== Entity Extraction ====================
    
    async def extract_entities(self, content: str) -> list[str]:
        """Extract named entities from content."""
        if self._nlp:
            return self._extract_entities_spacy(content)
        return self._extract_entities_regex(content)
    
    def _extract_entities_spacy(self, content: str) -> list[str]:
        """Extract entities using spaCy NER."""
        doc = self._nlp(content[:self.config.max_content_length])
        
        entities = []
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG", "GPE", "LOC", "PRODUCT", "EVENT", "DATE", "TIME", "MONEY"):
                entities.append(ent.text)
        
        seen = set()
        return [e for e in entities if not (e.lower() in seen or seen.add(e.lower()))][:20]
    
    def _extract_entities_regex(self, content: str) -> list[str]:
        """Fallback entity extraction using regex."""
        entities = []
        
        # Capitalized phrases
        entities.extend(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)[:10])
        
        # Emails
        entities.extend(re.findall(r'\b[\w.-]+@[\w.-]+\.\w+\b', content)[:3])
        
        # URLs
        entities.extend(re.findall(r'https?://\S+', content)[:3])
        
        # Dates
        entities.extend(re.findall(
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4}\b',
            content, re.IGNORECASE
        )[:5])
        
        seen = set()
        return [e for e in entities if not (e.lower() in seen or seen.add(e.lower()))][:20]
    
    # ==================== Sentiment Analysis ====================
    
    async def analyze_sentiment(self, content: str) -> float:
        """Analyze sentiment (-1 to 1) using lexicon-based approach."""
        positive_words = {
            "good", "great", "excellent", "amazing", "wonderful", "fantastic",
            "happy", "love", "best", "perfect", "success", "win", "positive",
            "helpful", "useful", "effective", "efficient", "improve", "solved"
        }
        negative_words = {
            "bad", "terrible", "awful", "horrible", "worst", "fail", "error",
            "problem", "issue", "bug", "crash", "broken", "wrong", "negative",
            "difficult", "hard", "confusing", "slow", "frustrated", "angry"
        }
        
        words = content.lower().split()
        if not words:
            return 0.0
        
        pos = sum(1 for w in words if w in positive_words)
        neg = sum(1 for w in words if w in negative_words)
        
        total = pos + neg
        return max(-1.0, min(1.0, (pos - neg) / total)) if total else 0.0
    
    # ==================== Utilities ====================
    
    def get_embedding_dim(self) -> int:
        return self.config.embedding_dim
    
    def get_provider_info(self) -> dict:
        return {
            "provider": "ollama",
            "model": self.config.embedding_model,
            "dimension": self.config.embedding_dim,
            "host": self.config.ollama_host or "localhost:11434"
        }
