"""Memory System Web Visualizer.

A FastAPI app to visualize BIEM memory contents with D3.js graph.
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


# Global memory manager instance
_memory: MemoryManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup memory system."""
    global _memory
    
    config = MemoryConfig(
        milvus_config=MilvusConfig(use_lite=False),  # Use Milvus Standalone
        postgres_config=PostgresConfig(),
        auto_start_tasks=False,
    )
    _memory = MemoryManager(config)
    await _memory.initialize()
    print("✓ Memory system connected")
    
    yield
    
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
    
    # Get all nodes and edges from NetworkX
    nodes_data = []
    edges_data = []
    
    for node_id in graph._graph.nodes():
        node_attrs = graph._graph.nodes[node_id]
        nodes_data.append({
            "id": node_id,
            "content": node_attrs.get("content", "")[:100],
            "energy": node_attrs.get("energy", 0.5),
            "tier": node_attrs.get("tier", "L2"),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
