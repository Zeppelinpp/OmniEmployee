#!/usr/bin/env python3
"""Reset and migrate database schemas for Memory and Knowledge systems.

This script:
1. Clears and recreates Milvus collections with updated schema (including user_id)
2. Clears and recreates PostgreSQL tables with updated schema
"""

import asyncio
import os
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def reset_milvus():
    """Reset Milvus collections."""
    print("\n=== Resetting Milvus ===")
    
    try:
        from pymilvus import MilvusClient
        
        # Connect to Milvus
        milvus_host = os.getenv("MILVUS_HOST", "localhost")
        milvus_port = int(os.getenv("MILVUS_PORT", "19530"))
        uri = f"http://{milvus_host}:{milvus_port}"
        
        print(f"Connecting to Milvus at {uri}...")
        client = MilvusClient(uri=uri)
        
        # Collections to reset
        collections = [
            os.getenv("MILVUS_COLLECTION", "biem_memories"),
            "biem_knowledge",
        ]
        
        for collection_name in collections:
            if client.has_collection(collection_name):
                print(f"  Dropping collection: {collection_name}")
                client.drop_collection(collection_name)
                print(f"  ✓ Dropped {collection_name}")
            else:
                print(f"  Collection {collection_name} does not exist, skipping")
        
        client.close()
        print("✓ Milvus reset complete")
        return True
        
    except Exception as e:
        print(f"✗ Milvus reset failed: {e}")
        return False


async def reset_postgres():
    """Reset PostgreSQL tables."""
    print("\n=== Resetting PostgreSQL ===")
    
    try:
        import asyncpg
        
        # Connect to PostgreSQL
        pg_host = os.getenv("POSTGRES_HOST", "localhost")
        pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
        pg_db = os.getenv("POSTGRES_DB", "biem")
        pg_user = os.getenv("POSTGRES_USER", "")
        pg_password = os.getenv("POSTGRES_PASSWORD", "")
        
        conn_kwargs = {
            "host": pg_host,
            "port": pg_port,
            "database": pg_db,
        }
        if pg_user:
            conn_kwargs["user"] = pg_user
        if pg_password:
            conn_kwargs["password"] = pg_password
        
        print(f"Connecting to PostgreSQL at {pg_host}:{pg_port}/{pg_db}...")
        conn = await asyncpg.connect(**conn_kwargs)
        
        # Drop existing tables
        print("  Dropping existing tables...")
        await conn.execute("""
            DROP TABLE IF EXISTS knowledge_history CASCADE;
            DROP TABLE IF EXISTS knowledge_triples CASCADE;
            DROP TABLE IF EXISTS crystal_links CASCADE;
            DROP TABLE IF EXISTS crystal_facts CASCADE;
        """)
        print("  ✓ Tables dropped")
        
        # Create new tables with updated schema
        print("  Creating crystal_facts table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS crystal_facts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                source_node_ids UUID[] NOT NULL DEFAULT '{}',
                confidence FLOAT DEFAULT 1.0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                metadata JSONB DEFAULT '{}',
                user_id VARCHAR(64) DEFAULT ''
            );
            
            CREATE INDEX IF NOT EXISTS idx_facts_created ON crystal_facts(created_at);
            CREATE INDEX IF NOT EXISTS idx_facts_confidence ON crystal_facts(confidence);
            CREATE INDEX IF NOT EXISTS idx_facts_user ON crystal_facts(user_id);
            CREATE INDEX IF NOT EXISTS idx_facts_content_fts 
                ON crystal_facts USING gin(to_tsvector('english', content));
        """)
        
        print("  Creating crystal_links table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS crystal_links (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_id UUID NOT NULL,
                target_id UUID NOT NULL,
                link_type VARCHAR(16) NOT NULL,
                weight FLOAT DEFAULT 1.0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                user_id VARCHAR(64) DEFAULT '',
                UNIQUE(source_id, target_id, link_type)
            );
            
            CREATE INDEX IF NOT EXISTS idx_links_source ON crystal_links(source_id);
            CREATE INDEX IF NOT EXISTS idx_links_target ON crystal_links(target_id);
            CREATE INDEX IF NOT EXISTS idx_links_type ON crystal_links(link_type);
            CREATE INDEX IF NOT EXISTS idx_links_user ON crystal_links(user_id);
        """)
        
        print("  Creating knowledge_triples table (GLOBAL)...")
        await conn.execute("""
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
                
                -- GLOBAL unique constraint (not per-user)
                UNIQUE(subject, predicate)
            );
            
            CREATE INDEX IF NOT EXISTS idx_triples_subject ON knowledge_triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_predicate ON knowledge_triples(predicate);
            CREATE INDEX IF NOT EXISTS idx_triples_updated ON knowledge_triples(updated_at);
            CREATE INDEX IF NOT EXISTS idx_triples_fts 
                ON knowledge_triples USING gin(to_tsvector('english', subject || ' ' || object));
        """)
        
        print("  Creating knowledge_history table...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_history (
                id UUID PRIMARY KEY,
                triple_id UUID REFERENCES knowledge_triples(id) ON DELETE CASCADE,
                old_value TEXT,
                new_value TEXT,
                reason VARCHAR(64),
                confirmed BOOLEAN DEFAULT false,
                session_id VARCHAR(64) DEFAULT '',
                contributor_id VARCHAR(64) DEFAULT '',
                timestamp TIMESTAMPTZ DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_history_triple ON knowledge_history(triple_id);
        """)
        
        await conn.close()
        print("✓ PostgreSQL reset complete")
        return True
        
    except Exception as e:
        print(f"✗ PostgreSQL reset failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("=" * 60)
    print("Database Reset Script")
    print("=" * 60)
    print("\nThis will DELETE ALL DATA in Milvus and PostgreSQL!")
    print("Press Ctrl+C within 3 seconds to cancel...")
    
    try:
        await asyncio.sleep(3)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return
    
    print("\nProceeding with reset...")
    
    milvus_ok = await reset_milvus()
    postgres_ok = await reset_postgres()
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Milvus:     {'✓ OK' if milvus_ok else '✗ FAILED'}")
    print(f"  PostgreSQL: {'✓ OK' if postgres_ok else '✗ FAILED'}")
    print("=" * 60)
    
    if milvus_ok and postgres_ok:
        print("\n✓ All databases reset successfully!")
        print("  Collections will be recreated on first use with new schemas.")
    else:
        print("\n⚠ Some operations failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
