"""Knowledge Store - PostgreSQL-based knowledge triple storage.

Provides persistent storage for knowledge triples with version history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.omniemployee.memory.knowledge.models import (
    KnowledgeTriple,
    KnowledgeSource,
    KnowledgeUpdateEvent,
)


# SQL for creating knowledge tables
CREATE_KNOWLEDGE_TABLES_SQL = """
-- Knowledge triples table
CREATE TABLE IF NOT EXISTS knowledge_triples (
    id UUID PRIMARY KEY,
    subject VARCHAR(255) NOT NULL,
    predicate VARCHAR(255) NOT NULL,
    object TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.8,
    source VARCHAR(32) DEFAULT 'conversation',
    version INT DEFAULT 1,
    previous_values JSONB DEFAULT '[]',
    session_id VARCHAR(64) DEFAULT '',
    user_id VARCHAR(64) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint on (subject, predicate) per user
    UNIQUE(user_id, subject, predicate)
);

-- Knowledge update history
CREATE TABLE IF NOT EXISTS knowledge_history (
    id UUID PRIMARY KEY,
    triple_id UUID REFERENCES knowledge_triples(id) ON DELETE CASCADE,
    old_value TEXT,
    new_value TEXT,
    reason VARCHAR(64),
    confirmed BOOLEAN DEFAULT false,
    session_id VARCHAR(64) DEFAULT '',
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_triples_subject ON knowledge_triples(subject);
CREATE INDEX IF NOT EXISTS idx_triples_predicate ON knowledge_triples(predicate);
CREATE INDEX IF NOT EXISTS idx_triples_user ON knowledge_triples(user_id);
CREATE INDEX IF NOT EXISTS idx_triples_updated ON knowledge_triples(updated_at);
CREATE INDEX IF NOT EXISTS idx_history_triple ON knowledge_history(triple_id);

-- Full-text search on subject and object
CREATE INDEX IF NOT EXISTS idx_triples_fts 
ON knowledge_triples USING gin(
    to_tsvector('english', subject || ' ' || object)
);
"""


@dataclass
class KnowledgeStoreConfig:
    """Configuration for KnowledgeStore."""
    host: str = "localhost"
    port: int = 5432
    database: str = "biem"
    user: str = ""
    password: str = ""
    min_connections: int = 2
    max_connections: int = 10


class KnowledgeStore:
    """PostgreSQL-based knowledge triple storage.
    
    Stores knowledge triples with support for:
    - CRUD operations
    - Version history tracking
    - Conflict detection queries
    - Full-text and semantic search
    """
    
    def __init__(self, config: KnowledgeStoreConfig | None = None):
        self.config = config or KnowledgeStoreConfig()
        self._pool = None
        self._connected = False
    
    async def connect(self) -> None:
        """Establish connection pool and ensure tables exist."""
        import asyncpg
        
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
        
        # Create tables
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_KNOWLEDGE_TABLES_SQL)
        
        self._connected = True
    
    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
        self._connected = False
    
    def is_available(self) -> bool:
        """Check if store is connected."""
        return self._connected and self._pool is not None
    
    # ==================== CRUD Operations ====================
    
    async def store(self, triple: KnowledgeTriple) -> str:
        """Store a new knowledge triple.
        
        If triple with same (user_id, subject, predicate) exists, updates it.
        
        Returns:
            The triple ID
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO knowledge_triples (
                    id, subject, predicate, object, confidence, source,
                    version, previous_values, session_id, user_id
                )
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
                ON CONFLICT (user_id, subject, predicate) 
                DO UPDATE SET
                    object = EXCLUDED.object,
                    confidence = EXCLUDED.confidence,
                    source = EXCLUDED.source,
                    version = knowledge_triples.version + 1,
                    previous_values = knowledge_triples.previous_values || 
                        jsonb_build_array(knowledge_triples.object),
                    updated_at = NOW()
                RETURNING id, version
                """,
                triple.id,
                triple.subject,
                triple.predicate,
                triple.object,
                triple.confidence,
                triple.source.value,
                triple.version,
                json.dumps(triple.previous_values),
                triple.session_id,
                triple.user_id,
            )
            return str(row["id"])
    
    async def get(self, triple_id: str) -> KnowledgeTriple | None:
        """Get a triple by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM knowledge_triples WHERE id = $1::uuid",
                triple_id
            )
            if row:
                return self._row_to_triple(row)
            return None
    
    async def get_by_subject_predicate(
        self,
        subject: str,
        predicate: str,
        user_id: str = "",
    ) -> KnowledgeTriple | None:
        """Get triple by subject and predicate (exact match)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM knowledge_triples
                WHERE LOWER(subject) = LOWER($1)
                  AND LOWER(predicate) = LOWER($2)
                  AND user_id = $3
                """,
                subject, predicate, user_id
            )
            if row:
                return self._row_to_triple(row)
            return None
    
    async def update(
        self,
        triple_id: str,
        new_object: str,
        source: KnowledgeSource = KnowledgeSource.USER_VERIFIED,
        confidence: float = 1.0,
        session_id: str = "",
    ) -> bool:
        """Update a triple's object value with history tracking.
        
        Args:
            triple_id: The triple to update
            new_object: New value for the object field
            source: Source of the update
            confidence: New confidence level
            session_id: Session that triggered the update
            
        Returns:
            True if update succeeded
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Get current value
                current = await conn.fetchrow(
                    "SELECT object FROM knowledge_triples WHERE id = $1::uuid",
                    triple_id
                )
                if not current:
                    return False
                
                old_value = current["object"]
                
                # Update triple
                result = await conn.execute(
                    """
                    UPDATE knowledge_triples
                    SET object = $2,
                        confidence = $3,
                        source = $4,
                        version = version + 1,
                        previous_values = previous_values || jsonb_build_array($5),
                        updated_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    triple_id, new_object, confidence, source.value, old_value
                )
                
                # Record history
                import uuid
                await conn.execute(
                    """
                    INSERT INTO knowledge_history (id, triple_id, old_value, new_value, reason, confirmed, session_id)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
                    """,
                    str(uuid.uuid4()), triple_id, old_value, new_object,
                    source.value, True, session_id
                )
                
                return result == "UPDATE 1"
    
    async def delete(self, triple_id: str) -> bool:
        """Delete a triple."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM knowledge_triples WHERE id = $1::uuid",
                triple_id
            )
            return result == "DELETE 1"
    
    # ==================== Query Methods ====================
    
    async def query_by_subject(
        self,
        subject: str,
        user_id: str = "",
        limit: int = 20,
    ) -> list[KnowledgeTriple]:
        """Get all triples for a subject."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_triples
                WHERE LOWER(subject) = LOWER($1) AND user_id = $2
                ORDER BY updated_at DESC
                LIMIT $3
                """,
                subject, user_id, limit
            )
            return [self._row_to_triple(row) for row in rows]
    
    async def query_by_predicate(
        self,
        predicate: str,
        user_id: str = "",
        limit: int = 20,
    ) -> list[KnowledgeTriple]:
        """Get all triples with a specific predicate."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_triples
                WHERE LOWER(predicate) = LOWER($1) AND user_id = $2
                ORDER BY updated_at DESC
                LIMIT $3
                """,
                predicate, user_id, limit
            )
            return [self._row_to_triple(row) for row in rows]
    
    async def search(
        self,
        query: str,
        user_id: str = "",
        limit: int = 10,
    ) -> list[KnowledgeTriple]:
        """Full-text search on subject and object."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *, 
                       ts_rank(to_tsvector('english', subject || ' ' || object),
                               plainto_tsquery('english', $1)) as rank
                FROM knowledge_triples
                WHERE to_tsvector('english', subject || ' ' || object) 
                      @@ plainto_tsquery('english', $1)
                  AND user_id = $2
                ORDER BY rank DESC
                LIMIT $3
                """,
                query, user_id, limit
            )
            return [self._row_to_triple(row) for row in rows]
    
    async def get_recent(
        self,
        user_id: str = "",
        limit: int = 20,
    ) -> list[KnowledgeTriple]:
        """Get recently updated triples."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_triples
                WHERE user_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
                """,
                user_id, limit
            )
            return [self._row_to_triple(row) for row in rows]
    
    async def get_all(
        self,
        user_id: str = "",
        limit: int = 100,
    ) -> list[KnowledgeTriple]:
        """Get all triples for a user."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_triples
                WHERE user_id = $1
                ORDER BY subject, predicate
                LIMIT $2
                """,
                user_id, limit
            )
            return [self._row_to_triple(row) for row in rows]
    
    # ==================== Conflict Detection ====================
    
    async def find_potential_conflicts(
        self,
        triple: KnowledgeTriple,
    ) -> list[KnowledgeTriple]:
        """Find existing triples that might conflict with a new triple.
        
        Looks for triples with same subject and similar predicates.
        """
        async with self._pool.acquire() as conn:
            # Exact match on subject and predicate
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_triples
                WHERE LOWER(subject) = LOWER($1)
                  AND LOWER(predicate) = LOWER($2)
                  AND user_id = $3
                  AND LOWER(object) != LOWER($4)
                """,
                triple.subject, triple.predicate, triple.user_id, triple.object
            )
            return [self._row_to_triple(row) for row in rows]
    
    # ==================== History ====================
    
    async def get_history(
        self,
        triple_id: str,
        limit: int = 10,
    ) -> list[KnowledgeUpdateEvent]:
        """Get update history for a triple."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_history
                WHERE triple_id = $1::uuid
                ORDER BY timestamp DESC
                LIMIT $2
                """,
                triple_id, limit
            )
            return [
                KnowledgeUpdateEvent(
                    id=str(row["id"]),
                    triple_id=str(row["triple_id"]),
                    old_value=row["old_value"],
                    new_value=row["new_value"],
                    reason=row["reason"],
                    confirmed=row["confirmed"],
                    session_id=row["session_id"],
                    timestamp=row["timestamp"].timestamp(),
                )
                for row in rows
            ]
    
    # ==================== Stats ====================
    
    async def get_stats(self, user_id: str = "") -> dict[str, Any]:
        """Get knowledge store statistics."""
        async with self._pool.acquire() as conn:
            if user_id:
                total = await conn.fetchval(
                    "SELECT COUNT(*) FROM knowledge_triples WHERE user_id = $1",
                    user_id
                )
                subjects = await conn.fetchval(
                    "SELECT COUNT(DISTINCT subject) FROM knowledge_triples WHERE user_id = $1",
                    user_id
                )
                predicates = await conn.fetchval(
                    "SELECT COUNT(DISTINCT predicate) FROM knowledge_triples WHERE user_id = $1",
                    user_id
                )
            else:
                total = await conn.fetchval("SELECT COUNT(*) FROM knowledge_triples")
                subjects = await conn.fetchval("SELECT COUNT(DISTINCT subject) FROM knowledge_triples")
                predicates = await conn.fetchval("SELECT COUNT(DISTINCT predicate) FROM knowledge_triples")
            
            history_count = await conn.fetchval("SELECT COUNT(*) FROM knowledge_history")
            
            return {
                "total_triples": total,
                "unique_subjects": subjects,
                "unique_predicates": predicates,
                "total_updates": history_count,
            }
    
    # ==================== Utility ====================
    
    def _row_to_triple(self, row) -> KnowledgeTriple:
        """Convert database row to KnowledgeTriple."""
        previous = row["previous_values"]
        if isinstance(previous, str):
            previous = json.loads(previous)
        
        return KnowledgeTriple(
            id=str(row["id"]),
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            confidence=row["confidence"],
            source=KnowledgeSource(row["source"]),
            version=row["version"],
            previous_values=previous or [],
            session_id=row["session_id"],
            user_id=row["user_id"],
            created_at=row["created_at"].timestamp(),
            updated_at=row["updated_at"].timestamp(),
        )
    
    async def clear_all(self, user_id: str = "") -> None:
        """Clear all knowledge (for testing)."""
        async with self._pool.acquire() as conn:
            if user_id:
                await conn.execute(
                    "DELETE FROM knowledge_triples WHERE user_id = $1",
                    user_id
                )
            else:
                await conn.execute("TRUNCATE knowledge_triples, knowledge_history CASCADE")
