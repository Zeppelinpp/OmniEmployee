"""Memory System Web Visualizer.

A FastAPI app to visualize BIEM memory and knowledge contents with D3.js graph.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse

from src.omniemployee.memory import MemoryManager, MemoryConfig
from src.omniemployee.memory.storage import MilvusConfig, PostgresConfig
from src.omniemployee.memory.knowledge import (
    KnowledgeStore,
    KnowledgeStoreConfig,
)


# Global instances
_memory: MemoryManager | None = None
_knowledge_store: KnowledgeStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup memory and knowledge systems."""
    global _memory, _knowledge_store
    
    # Memory system
    config = MemoryConfig(
        milvus_config=MilvusConfig(use_lite=False),  # Use Milvus Standalone
        postgres_config=PostgresConfig(),
        auto_start_tasks=False,
    )
    _memory = MemoryManager(config)
    await _memory.initialize()
    print("✓ Memory system connected")
    
    # Knowledge store
    try:
        _knowledge_store = KnowledgeStore(KnowledgeStoreConfig())
        await _knowledge_store.connect()
        print("✓ Knowledge store connected")
    except Exception as e:
        print(f"⚠ Knowledge store not available: {e}")
        _knowledge_store = None
    
    yield
    
    if _knowledge_store:
        await _knowledge_store.disconnect()
        print("✓ Knowledge store shutdown")
    
    await _memory.shutdown()
    print("✓ Memory system shutdown")


app = FastAPI(
    title="BIEM Memory Visualizer",
    lifespan=lifespan
)

# Serve static files
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main visualization page."""
    index_path = static_dir / "index.html"
    return index_path.read_text()


@app.get("/api/stats")
async def get_stats():
    """Get memory system statistics."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    stats = await _memory.get_stats()
    return stats


@app.get("/api/l1")
async def get_l1_nodes():
    """Get all L1 working memory nodes."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    nodes = await _memory.get_working_memory(limit=100)
    return {
        "nodes": [
            {
                "id": n.id,
                "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                "energy": round(n.energy, 3),
                "tier": n.tier,
                "created_at": n.metadata.timestamp,
                "source": n.metadata.source,
                "entities": n.metadata.entities[:5],
                "sentiment": round(n.metadata.sentiment, 2),
            }
            for n in nodes
        ]
    }


@app.get("/api/l2/graph")
async def get_l2_graph():
    """Get L2 graph data for D3.js visualization."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    # Get graph storage directly
    graph = _memory._l2_graph
    vector = _memory._l2_vector
    
    # Get all nodes and edges from NetworkX
    nodes_data = []
    edges_data = []
    
    for node_id in graph._graph.nodes():
        # Fetch content from Milvus vector storage
        node = await vector.get(node_id)
        if node:
            nodes_data.append({
                "id": node_id,
                "content": node.content[:100] + "..." if len(node.content) > 100 else node.content,
                "energy": node.energy,
                "tier": node.tier,
            })
        else:
            # Fallback if not found in Milvus
            node_attrs = graph._graph.nodes[node_id]
            nodes_data.append({
                "id": node_id,
                "content": f"[Node {node_id[:8]}]",
                "energy": node_attrs.get("energy", 0.5),
                "tier": "L2",
            })
    
    for source, target, attrs in graph._graph.edges(data=True):
        edges_data.append({
            "source": source,
            "target": target,
            "weight": attrs.get("weight", 1.0),
            "type": attrs.get("link_type", "semantic"),
        })
    
    return {
        "nodes": nodes_data,
        "links": edges_data,
    }


@app.get("/api/l2/vector")
async def get_l2_vector_nodes():
    """Get L2 vector storage nodes."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    # Query all nodes from Milvus (limited)
    vector_storage = _memory._l2_vector
    
    if not vector_storage._connected:
        return {"nodes": [], "message": "Vector storage not connected"}
    
    try:
        # Query recent nodes
        results = vector_storage._client.query(
            collection_name=vector_storage.config.collection_name,
            filter="",
            output_fields=["id", "content", "energy", "tier", "source", "timestamp", "entities"],
            limit=100,
        )
        
        return {
            "nodes": [
                {
                    "id": r.get("id", ""),
                    "content": r.get("content", "")[:200],
                    "energy": round(r.get("energy", 0), 3),
                    "tier": r.get("tier", "L2"),
                    "source": r.get("source", ""),
                    "created_at": r.get("timestamp", 0),
                    "entities": r.get("entities", [])[:5],
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"nodes": [], "error": str(e)}


@app.get("/api/l3/facts")
async def get_l3_facts():
    """Get L3 crystal facts."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"facts": [], "message": "L3 storage not available"}
    
    try:
        facts = await _memory._l3.get_all_facts(limit=100)
        return {
            "facts": [
                {
                    "id": str(f.id),
                    "content": f.content[:300],
                    "confidence": round(f.confidence, 3),
                    "created_at": f.created_at,
                    "source_count": len(f.source_node_ids),
                }
                for f in facts
            ]
        }
    except Exception as e:
        return {"facts": [], "error": str(e)}


@app.get("/api/l3/links")
async def get_l3_links():
    """Get L3 persistent links."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"links": [], "message": "L3 storage not available"}
    
    try:
        links = await _memory._l3.get_all_links(limit=100)
        return {
            "links": [
                {
                    "source_id": l.source_id,
                    "target_id": l.target_id,
                    "type": l.link_type.value,
                    "weight": round(l.weight, 3),
                    "created_at": l.created_at,
                }
                for l in links
            ]
        }
    except Exception as e:
        return {"links": [], "error": str(e)}


@app.delete("/api/node/{node_id}")
async def delete_node(node_id: str):
    """Delete a memory node."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    success = await _memory.delete_node(node_id)
    return {"success": success, "node_id": node_id}


# ==================== Knowledge APIs ====================

@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge store statistics."""
    if not _knowledge_store or not _knowledge_store.is_available():
        return {"status": "unavailable"}
    
    try:
        stats = await _knowledge_store.get_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/knowledge/triples")
async def get_knowledge_triples(user_id: str = "", limit: int = 100):
    """Get all knowledge triples."""
    if not _knowledge_store or not _knowledge_store.is_available():
        return {"triples": [], "message": "Knowledge store not available"}
    
    try:
        triples = await _knowledge_store.get_all(user_id, limit)
        return {
            "triples": [
                {
                    "id": str(t.id),
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": round(t.confidence, 3),
                    "source": t.source.value,
                    "version": t.version,
                    "previous_values": t.previous_values,
                    "user_id": t.user_id,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in triples
            ]
        }
    except Exception as e:
        return {"triples": [], "error": str(e)}


@app.get("/api/knowledge/search")
async def search_knowledge(q: str, user_id: str = "", limit: int = 20):
    """Search knowledge triples."""
    if not _knowledge_store or not _knowledge_store.is_available():
        return {"triples": [], "message": "Knowledge store not available"}
    
    try:
        triples = await _knowledge_store.search(q, user_id, limit)
        return {
            "triples": [
                {
                    "id": str(t.id),
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": round(t.confidence, 3),
                    "source": t.source.value,
                }
                for t in triples
            ]
        }
    except Exception as e:
        return {"triples": [], "error": str(e)}


@app.get("/api/knowledge/history/{triple_id}")
async def get_knowledge_history(triple_id: str, limit: int = 10):
    """Get update history for a knowledge triple."""
    if not _knowledge_store or not _knowledge_store.is_available():
        return {"history": [], "message": "Knowledge store not available"}
    
    try:
        history = await _knowledge_store.get_history(triple_id, limit)
        return {
            "history": [
                {
                    "id": str(h.id),
                    "old_value": h.old_value,
                    "new_value": h.new_value,
                    "reason": h.reason,
                    "confirmed": h.confirmed,
                    "timestamp": h.timestamp,
                }
                for h in history
            ]
        }
    except Exception as e:
        return {"history": [], "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
