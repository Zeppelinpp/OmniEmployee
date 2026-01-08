"""L3 Crystal Storage - PostgreSQL-based persistent knowledge base.

The Crystal: Long-term structured storage for consolidated facts and rules.
Implementation: PostgreSQL with asyncpg for async operations.
"""

from __future__ import annotations

import time
import json
from typing import Any
from dataclasses import dataclass

from src.omniemployee.memory.models import CrystalFact, Link, LinkType


@dataclass
class PostgresConfig:
    """Configuration for PostgreSQL connection."""
    host: str = "localhost"
    port: int = 5432
    database: str = "biem"
    user: str = ""       # Empty = use current system user
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10


# SQL for creating tables
CREATE_TABLES_SQL = """
-- Crystal facts table (consolidated semantic facts)
CREATE TABLE IF NOT EXISTS crystal_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    source_node_ids UUID[] NOT NULL DEFAULT '{}',
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Crystal links table (persisted relationships)
CREATE TABLE IF NOT EXISTS crystal_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL,
    target_id UUID NOT NULL,
    link_type VARCHAR(16) NOT NULL,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_id, target_id, link_type)
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_facts_created ON crystal_facts(created_at);
CREATE INDEX IF NOT EXISTS idx_facts_confidence ON crystal_facts(confidence);
CREATE INDEX IF NOT EXISTS idx_links_source ON crystal_links(source_id);
CREATE INDEX IF NOT EXISTS idx_links_target ON crystal_links(target_id);
CREATE INDEX IF NOT EXISTS idx_links_type ON crystal_links(link_type);

-- Full-text search index on content
CREATE INDEX IF NOT EXISTS idx_facts_content_fts 
ON crystal_facts USING gin(to_tsvector('english', content));
"""


class L3CrystalStorage:
    """PostgreSQL-based long-term knowledge storage.
    
    Stores consolidated facts derived from frequently activated memory clusters.
    Supports full-text search and structured queries.
    """
    
    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or PostgresConfig()
        self._pool = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection pool and ensure tables exist."""
        import asyncpg
        
        # Build connection kwargs (empty user = use system user)
        conn_kwargs = {
            "host": self.config.host,
            "port": self.config.port,
            "database": self.config.database,
            "min_size": self.config.min_connections,
            "max_size": self.config.max_connections,
        }
        if self.config.user:
            conn_kwargs["user"] = self.config.user
        if self.config.password:
            conn_kwargs["password"] = self.config.password
        
        self._pool = await asyncpg.create_pool(**conn_kwargs)
        
        # Create tables if not exist
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_TABLES_SQL)
        
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
        self._connected = False
    
    # ==================== Crystal Facts Operations ====================
    
    async def store_fact(self, fact: CrystalFact) -> str:
        """Store a new crystal fact."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO crystal_facts (id, content, source_node_ids, confidence, metadata)
                VALUES ($1::uuid, $2, $3::uuid[], $4, $5::jsonb)
                RETURNING id
                """,
                fact.id,
                fact.content,
                fact.source_node_ids,
                fact.confidence,
                json.dumps(fact.metadata)
            )
            return str(row["id"])
    
    async def get_fact(self, fact_id: str) -> CrystalFact | None:
        """Retrieve a fact by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM crystal_facts WHERE id = $1::uuid",
                fact_id
            )
            
            if not row:
                return None
            
            return self._row_to_fact(row)
    
    async def update_fact(self, fact_id: str, content: str, confidence: float | None = None) -> bool:
        """Update a fact's content and optionally confidence."""
        async with self._pool.acquire() as conn:
            if confidence is not None:
                result = await conn.execute(
                    """
                    UPDATE crystal_facts 
                    SET content = $2, confidence = $3, updated_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    fact_id, content, confidence
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE crystal_facts 
                    SET content = $2, updated_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    fact_id, content
                )
            return result == "UPDATE 1"
    
    async def delete_fact(self, fact_id: str) -> bool:
        """Delete a fact."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM crystal_facts WHERE id = $1::uuid",
                fact_id
            )
            return result == "DELETE 1"
    
    async def search_facts_by_content(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float = 0.0
    ) -> list[CrystalFact]:
        """Full-text search on fact content."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *, ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) as rank
                FROM crystal_facts
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                  AND confidence >= $3
                ORDER BY rank DESC
                LIMIT $2
                """,
                query, limit, min_confidence
            )
            return [self._row_to_fact(row) for row in rows]
    
    async def get_facts_by_source(self, source_node_id: str) -> list[CrystalFact]:
        """Get all facts derived from a specific source node."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM crystal_facts
                WHERE $1::uuid = ANY(source_node_ids)
                ORDER BY created_at DESC
                """,
                source_node_id
            )
            return [self._row_to_fact(row) for row in rows]
    
    async def get_recent_facts(self, limit: int = 50) -> list[CrystalFact]:
        """Get most recently created facts."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM crystal_facts
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit
            )
            return [self._row_to_fact(row) for row in rows]
    
    async def get_high_confidence_facts(
        self,
        min_confidence: float = 0.8,
        limit: int = 100
    ) -> list[CrystalFact]:
        """Get facts with high confidence scores."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM crystal_facts
                WHERE confidence >= $1
                ORDER BY confidence DESC, created_at DESC
                LIMIT $2
                """,
                min_confidence, limit
            )
            return [self._row_to_fact(row) for row in rows]
    
    # ==================== Crystal Links Operations ====================
    
    async def store_link(self, link: Link) -> str:
        """Store a persistent link."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO crystal_links (source_id, target_id, link_type, weight)
                VALUES ($1::uuid, $2::uuid, $3, $4)
                ON CONFLICT (source_id, target_id, link_type) 
                DO UPDATE SET weight = EXCLUDED.weight
                RETURNING id
                """,
                link.source_id,
                link.target_id,
                link.link_type.value,
                link.weight
            )
            return str(row["id"])
    
    async def get_links_for_node(self, node_id: str) -> list[Link]:
        """Get all links where node is source or target."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM crystal_links
                WHERE source_id = $1::uuid OR target_id = $1::uuid
                """,
                node_id
            )
            return [self._row_to_link(row) for row in rows]
    
    async def get_outgoing_links(self, source_id: str, link_type: str | None = None) -> list[Link]:
        """Get outgoing links from a node."""
        async with self._pool.acquire() as conn:
            if link_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM crystal_links
                    WHERE source_id = $1::uuid AND link_type = $2
                    """,
                    source_id, link_type
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM crystal_links
                    WHERE source_id = $1::uuid
                    """,
                    source_id
                )
            return [self._row_to_link(row) for row in rows]
    
    async def delete_link(self, source_id: str, target_id: str, link_type: str) -> bool:
        """Delete a specific link."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM crystal_links
                WHERE source_id = $1::uuid AND target_id = $2::uuid AND link_type = $3
                """,
                source_id, target_id, link_type
            )
            return result == "DELETE 1"
    
    async def update_link_weight(self, source_id: str, target_id: str, link_type: str, weight: float) -> bool:
        """Update link weight."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE crystal_links
                SET weight = $4
                WHERE source_id = $1::uuid AND target_id = $2::uuid AND link_type = $3
                """,
                source_id, target_id, link_type, weight
            )
            return result == "UPDATE 1"
    
    # ==================== Utility Methods ====================
    
    async def clear_all(self) -> None:
        """Clear all data (for testing)."""
        async with self._pool.acquire() as conn:
            await conn.execute("TRUNCATE crystal_facts, crystal_links")
    
    async def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        async with self._pool.acquire() as conn:
            facts_count = await conn.fetchval("SELECT COUNT(*) FROM crystal_facts")
            links_count = await conn.fetchval("SELECT COUNT(*) FROM crystal_links")
            avg_confidence = await conn.fetchval(
                "SELECT AVG(confidence) FROM crystal_facts"
            ) or 0.0
            
            return {
                "facts_count": facts_count,
                "links_count": links_count,
                "avg_confidence": float(avg_confidence),
            }
    
    def _row_to_fact(self, row) -> CrystalFact:
        """Convert database row to CrystalFact."""
        return CrystalFact(
            id=str(row["id"]),
            content=row["content"],
            source_node_ids=[str(uid) for uid in row["source_node_ids"]],
            confidence=row["confidence"],
            created_at=row["created_at"].timestamp(),
            updated_at=row["updated_at"].timestamp(),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        )
    
    def _row_to_link(self, row) -> Link:
        """Convert database row to Link."""
        return Link(
            source_id=str(row["source_id"]),
            target_id=str(row["target_id"]),
            link_type=LinkType(row["link_type"]),
            weight=row["weight"],
            created_at=row["created_at"].timestamp()
        )
