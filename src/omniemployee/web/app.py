"""Memory System Web Visualizer + Chat API.

A FastAPI app providing:
- BIEM memory and knowledge visualization
- Chat API for agent interaction
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from src.omniemployee.core import Agent, AgentConfig, AgentLoop, LoopConfig, LoopState
from src.omniemployee.llm import LLMProvider
from src.omniemployee.memory import BIEMContextPlugin, MemoryConfig, MemoryManager
from src.omniemployee.memory.storage import MilvusConfig, PostgresConfig
from src.omniemployee.memory.knowledge import (
    KnowledgeLearningPlugin,
    KnowledgePluginConfig,
    KnowledgeStore,
    KnowledgeStoreConfig,
    KnowledgeVectorConfig,
)


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict]
    session_id: str


class ToolCallInfo(BaseModel):
    name: str
    arguments: dict
    result: Optional[str] = None
    success: bool = True


# Global instances
_memory: MemoryManager | None = None
_knowledge_store: KnowledgeStore | None = None
_agent: Agent | None = None
_loop: AgentLoop | None = None
_memory_plugin: BIEMContextPlugin | None = None
_knowledge_plugin: KnowledgeLearningPlugin | None = None
_sessions: dict[str, dict] = {}
_current_user_id: str = ""  # Dynamic user_id for switching


def get_current_user_id() -> str:
    """Get the current user_id (dynamic or from env)."""
    global _current_user_id
    return _current_user_id or os.getenv("USER_ID", "default")


def create_memory_config() -> MemoryConfig:
    """Create memory configuration from environment."""
    milvus_config = MilvusConfig(
        collection_name=os.getenv("MILVUS_COLLECTION", "biem_memories"),
        use_lite=os.getenv("MILVUS_USE_LITE", "false").lower() == "true",
    )
    
    postgres_config = PostgresConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "biem"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    
    return MemoryConfig(
        milvus_config=milvus_config,
        postgres_config=postgres_config,
        auto_start_tasks=False,
    )


def create_knowledge_config(session_id: str, user_id: str = "") -> KnowledgePluginConfig:
    """Create knowledge learning configuration from environment."""
    store_config = KnowledgeStoreConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "biem"),
        user=os.getenv("POSTGRES_USER", ""),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )
    
    vector_config = KnowledgeVectorConfig(
        host=os.getenv("MILVUS_HOST", "localhost"),
        port=int(os.getenv("MILVUS_PORT", "19530")),
        collection_name="biem_knowledge",
        use_lite=os.getenv("MILVUS_USE_LITE", "false").lower() == "true",
    )
    
    return KnowledgePluginConfig(
        store_config=store_config,
        vector_config=vector_config,
        enable_vector_search=os.getenv("KNOWLEDGE_VECTOR_SEARCH", "true").lower() == "true",
        user_id=user_id or os.getenv("USER_ID", "default"),
        session_id=session_id,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup all systems."""
    global _memory, _knowledge_store, _agent, _loop, _memory_plugin, _knowledge_plugin
    
    workspace = Path.cwd()
    model = os.getenv("MODEL", "gpt-4o")
    
    # Initialize agent
    agent_config = AgentConfig(
        workspace_root=str(workspace),
        skills_dir="src/skills",
        model=model,
    )
    _agent = Agent(agent_config)
    _agent.discover_skills()
    print("✓ Agent initialized")
    
    # Initialize loop
    loop_config = LoopConfig(
        model=model,
        max_iterations=int(os.getenv("MAX_ITERATIONS", "50")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
    )
    _loop = AgentLoop(_agent, loop_config)
    print("✓ Agent loop initialized")
    
    # Memory system
    if os.getenv("DISABLE_MEMORY", "").lower() != "true":
        try:
            config = create_memory_config()
            _memory_plugin = BIEMContextPlugin(config)
            await _memory_plugin.initialize()
            # Access memory manager through the plugin (attribute is 'memory', not '_memory')
            if hasattr(_memory_plugin, 'memory') and _memory_plugin.memory is not None:
                _memory = _memory_plugin.memory
                print("✓ Memory system connected")
            else:
                print("⚠ Memory plugin initialized but memory manager not available")
                _memory = None
        except Exception as e:
            print(f"⚠ Memory system not available: {e}")
            _memory = None
            _memory_plugin = None
    
    # Knowledge store
    if os.getenv("DISABLE_KNOWLEDGE", "").lower() != "true":
        try:
            session_id = str(uuid.uuid4())[:8]
            knowledge_config = create_knowledge_config(session_id)
            _knowledge_plugin = KnowledgeLearningPlugin(knowledge_config)
            
            # Safely get encoder from memory if available
            encoder = None
            if _memory is not None and hasattr(_memory, '_encoder'):
                encoder = _memory._encoder
            await _knowledge_plugin.initialize(_loop.llm, encoder)
            
            if _knowledge_plugin.is_available():
                _knowledge_store = _knowledge_plugin._store
                print("✓ Knowledge store connected")
            else:
                _knowledge_store = None
                _knowledge_plugin = None
        except Exception as e:
            print(f"⚠ Knowledge store not available: {e}")
            _knowledge_store = None
            _knowledge_plugin = None
    
    yield
    
    # Cleanup
    if _knowledge_plugin:
        await _knowledge_plugin.shutdown()
        print("✓ Knowledge store shutdown")
    
    if _memory_plugin:
        await _memory_plugin.shutdown()
        print("✓ Memory system shutdown")


app = FastAPI(
    title="OmniEmployee API",
    lifespan=lifespan
)

# Enable CORS for Rust GUI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ==================== Chat API ====================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a message to the agent and get a response."""
    if not _agent or not _loop:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    session_id = request.session_id or str(uuid.uuid4())[:8]
    
    # Get or create session
    if session_id not in _sessions:
        _sessions[session_id] = {"messages": []}
    
    # Build context from memory and knowledge
    context_parts = []
    
    if _memory_plugin:
        memory_context = await _memory_plugin.prepare_context(request.message)
        if memory_context:
            context_parts.append(memory_context)
    
    if _knowledge_plugin and _knowledge_plugin.is_available():
        knowledge_context = await _knowledge_plugin.get_context_for_query(request.message)
        if knowledge_context:
            context_parts.append(knowledge_context)
    
    if context_parts:
        _agent.context.set_memory_context("\n\n".join(context_parts))
    
    # Run agent
    result = await _loop.run(request.message)
    
    # Clear memory context
    if _memory_plugin or _knowledge_plugin:
        _agent.context.clear_memory_context()
    
    # Extract tool calls from context
    tool_calls = []
    for msg in _agent.context.messages:
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                # Handle different tool call formats
                if hasattr(tc, 'function'):
                    # OpenAI-style tool call object
                    name = tc.function.name
                    args = tc.function.arguments
                elif isinstance(tc, dict):
                    # Dict format
                    name = tc.get('name', 'unknown')
                    args = tc.get('arguments', {})
                else:
                    # Fallback - try to get attributes
                    name = getattr(tc, 'name', 'unknown')
                    args = getattr(tc, 'arguments', {})
                
                tool_calls.append({
                    "name": name,
                    "arguments": args if isinstance(args, (dict, str)) else str(args),
                    "success": True,
                })
    
    # Record to memory
    if _memory_plugin:
        await _memory_plugin.record_user_message(request.message)
        await _memory_plugin.record_assistant_message(result.response)
    
    # Extract knowledge
    if _knowledge_plugin and _knowledge_plugin.is_available():
        await _knowledge_plugin.process_message(request.message, role="user")
    
    return ChatResponse(
        response=result.response,
        tool_calls=tool_calls,
        session_id=session_id,
    )


@app.get("/api/chat/stream")
async def chat_stream(message: str, session_id: str = ""):
    """Stream chat response for real-time updates (SSE format).
    
    Events:
    - type: "chunk" - Text content chunk
    - type: "tool_start" - Tool call started (sent immediately when a tool is invoked)
    - type: "tool_result" - Tool call result (sent after tool execution)
    - type: "done" - Stream finished
    - type: "error" - Error occurred
    """
    if not _agent or not _loop:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    session_id = session_id or str(uuid.uuid4())[:8]
    
    async def generate():
        import json
        
        # Build context
        context_parts = []
        
        if _memory_plugin:
            try:
                memory_context = await _memory_plugin.prepare_context(message)
                if memory_context:
                    context_parts.append(memory_context)
            except Exception:
                pass
        
        if _knowledge_plugin and _knowledge_plugin.is_available():
            try:
                knowledge_context = await _knowledge_plugin.get_context_for_query(message)
                if knowledge_context:
                    context_parts.append(knowledge_context)
            except Exception:
                pass
        
        if context_parts:
            _agent.context.set_memory_context("\n\n".join(context_parts))
        
        full_response = []
        seen_tool_call_ids = set()
        
        # Stream response chunks
        try:
            async for chunk in _loop.run_stream(message):
                full_response.append(chunk)
                # Send chunk as JSON for easier parsing
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                # Check for new tool calls in context and send them immediately
                for msg in _agent.context.messages:
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tc in msg.tool_calls:
                            tc_id = getattr(tc, 'id', None) or id(tc)
                            if tc_id not in seen_tool_call_ids:
                                seen_tool_call_ids.add(tc_id)
                                if hasattr(tc, 'function'):
                                    name = tc.function.name
                                    args = tc.function.arguments
                                else:
                                    name = getattr(tc, 'name', 'unknown')
                                    args = getattr(tc, 'arguments', '{}')
                                # Parse args if string
                                if isinstance(args, str):
                                    try:
                                        args = json.loads(args)
                                    except:
                                        args = {"raw": args}
                                yield f"data: {json.dumps({'type': 'tool_start', 'name': name, 'arguments': args, 'id': str(tc_id)})}\n\n"
                
                # Check for tool results in context
                for msg in _agent.context.messages:
                    # Tool results are in msg.tool_result, role is MessageRole enum
                    if hasattr(msg, 'tool_result') and msg.tool_result is not None:
                        tool_id = msg.tool_result.tool_call_id
                        result_key = f"result_{tool_id}"
                        if result_key not in seen_tool_call_ids:
                            seen_tool_call_ids.add(result_key)
                            content = msg.tool_result.content
                            # Truncate long results
                            if len(content) > 500:
                                content = content[:500] + "..."
                            yield f"data: {json.dumps({'type': 'tool_result', 'id': tool_id, 'result': content})}\n\n"
                            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        
        # Final tool calls summary
        tool_calls = []
        for msg in _agent.context.messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    if hasattr(tc, 'function'):
                        name = tc.function.name
                        args = tc.function.arguments
                    elif isinstance(tc, dict):
                        name = tc.get('name', 'unknown')
                        args = tc.get('arguments', {})
                    else:
                        name = getattr(tc, 'name', 'unknown')
                        args = getattr(tc, 'arguments', {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {"raw": args}
                    tool_calls.append({"name": name, "arguments": args})
        
        # Send done signal with full tool calls
        yield f"data: {json.dumps({'type': 'done', 'tool_calls': tool_calls})}\n\n"
        
        # Cleanup and record
        if _memory_plugin or _knowledge_plugin:
            _agent.context.clear_memory_context()
        
        # Record to memory
        response_text = "".join(full_response)
        if _memory_plugin:
            try:
                await _memory_plugin.record_user_message(message)
                await _memory_plugin.record_assistant_message(response_text)
            except Exception:
                pass
        
        # Process knowledge extraction
        if _knowledge_plugin and _knowledge_plugin.is_available():
            try:
                await _knowledge_plugin.process_message(message, role="user")
            except Exception:
                pass
    
    return StreamingResponse(
        generate(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/chat/clear")
async def clear_chat(session_id: str = ""):
    """Clear the conversation context."""
    if not _agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    _agent.context.clear()
    
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    
    return {"status": "cleared"}


# ==================== Agent Info API ====================

@app.get("/api/agent/info")
async def get_agent_info():
    """Get agent information and statistics."""
    if not _agent or not _loop:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    stats = _agent.get_stats()
    provider_info = _loop.llm.get_provider_info()
    
    return {
        "provider": provider_info.get("provider", "unknown"),
        "model": provider_info.get("model", "unknown"),
        "skills": stats.get("skills", {}).get("available", []),
        "tools": stats.get("tools", []),
        "memory_enabled": _memory_plugin is not None,
        "knowledge_enabled": _knowledge_plugin is not None and _knowledge_plugin.is_available(),
    }


# ==================== Memory APIs ====================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main visualization page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return index_path.read_text()
    return "<html><body><h1>OmniEmployee API</h1><p>Use /docs for API documentation.</p></body></html>"


@app.get("/api/stats")
async def get_stats():
    """Get memory system statistics."""
    if not _memory:
        return {"status": "unavailable", "message": "Memory not initialized"}
    
    stats = await _memory.get_stats()
    return stats


@app.get("/api/memory/context")
async def get_memory_context(query: str = "", limit: int = 10):
    """Get relevant memory items for a query."""
    if not _memory:
        return {"items": [], "message": "Memory not available"}
    
    try:
        # Use recall() for query-based search, or get_working_memory() for empty query
        if query:
            nodes = await _memory.recall(query, top_k=limit)
        else:
            nodes = await _memory.get_working_memory(limit=limit)
        return {
            "items": [
                {
                    "id": n.id,
                    "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                    "energy": round(n.energy, 3),
                    "tier": n.tier,
                }
                for n in nodes
            ]
        }
    except Exception as e:
        return {"items": [], "error": str(e)}


@app.get("/api/l1")
async def get_l1_nodes():
    """Get all L1 working memory nodes."""
    if not _memory:
        return {"nodes": [], "message": "Memory not initialized"}
    
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
        return {"nodes": [], "links": [], "message": "Memory not initialized"}
    
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
        return {"nodes": [], "message": "Memory not initialized"}
    
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
        return {"facts": [], "message": "Memory not initialized"}
    
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
    """Get L3 persistent links with content snippets."""
    if not _memory:
        return {"links": [], "message": "Memory not initialized"}
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"links": [], "message": "L3 storage not available"}
    
    try:
        links = await _memory._l3.get_all_links(limit=100)
        
        # Fetch content snippets for source and target nodes
        result_links = []
        for l in links:
            source_content = "[unknown]"
            target_content = "[unknown]"
            
            # Try to get content from L2 vector storage
            source_node = await _memory._l2_vector.get(l.source_id)
            if source_node:
                content = source_node.content
                source_content = content[:50] + "..." if len(content) > 50 else content
            
            target_node = await _memory._l2_vector.get(l.target_id)
            if target_node:
                content = target_node.content
                target_content = content[:50] + "..." if len(content) > 50 else content
            
            result_links.append({
                "source_id": l.source_id,
                "target_id": l.target_id,
                "source_content": source_content,
                "target_content": target_content,
                "type": l.link_type.value,
                "weight": round(l.weight, 3),
                "created_at": l.created_at,
            })
        
        return {"links": result_links}
    except Exception as e:
        return {"links": [], "error": str(e)}


@app.delete("/api/node/{node_id}")
async def delete_node(node_id: str):
    """Delete a memory node."""
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    success = await _memory.delete_node(node_id)
    return {"success": success, "node_id": node_id}


# ==================== Config API ====================

@app.get("/api/config")
async def get_config():
    """Get current configuration including user_id."""
    return {
        "user_id": get_current_user_id(),
        "memory_enabled": _memory is not None,
        "knowledge_enabled": _knowledge_store is not None,
    }


@app.get("/api/users")
async def get_users():
    """Get list of all users with knowledge data."""
    if not _knowledge_store:
        return {"users": [get_current_user_id()], "current": get_current_user_id()}
    
    try:
        # Query distinct user_ids from knowledge store
        async with _knowledge_store._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT user_id FROM knowledge_triples ORDER BY user_id"
            )
        users = [row["user_id"] for row in rows if row["user_id"]]
        
        # Ensure current user is in list
        current = get_current_user_id()
        if current not in users:
            users.insert(0, current)
            
        return {"users": users, "current": current}
    except Exception as e:
        return {"users": [get_current_user_id()], "current": get_current_user_id(), "error": str(e)}


@app.post("/api/user/switch")
async def switch_user(user_id: str):
    """Switch to a different user_id for testing."""
    global _current_user_id, _knowledge_plugin
    
    _current_user_id = user_id
    
    # Update knowledge plugin config if available
    if _knowledge_plugin:
        _knowledge_plugin.config.user_id = user_id
    
    return {"success": True, "user_id": user_id}


@app.post("/api/user/create")
async def create_user(user_id: str):
    """Create a new user (just sets it as current, data will be created on first message)."""
    global _current_user_id, _knowledge_plugin
    
    if not user_id or not user_id.strip():
        return {"success": False, "error": "Invalid user_id"}
    
    _current_user_id = user_id.strip()
    
    # Update knowledge plugin config
    if _knowledge_plugin:
        _knowledge_plugin.config.user_id = _current_user_id
    
    return {"success": True, "user_id": _current_user_id}


# ==================== Knowledge APIs ====================

@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge store statistics."""
    if not _knowledge_store:
        return {"status": "unavailable"}
    
    try:
        stats = await _knowledge_store.get_stats(get_current_user_id())
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/knowledge/triples")
async def get_knowledge_triples(user_id: str = "", limit: int = 100):
    """Get all knowledge triples for the specified or default user."""
    if not _knowledge_store:
        return {"triples": [], "message": "Knowledge store not available"}
    
    # Use specified user_id or current user
    effective_user_id = user_id or get_current_user_id()
    
    try:
        triples = await _knowledge_store.get_all(effective_user_id, limit)
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
    """Search knowledge triples for the specified or default user."""
    if not _knowledge_store:
        return {"triples": [], "message": "Knowledge store not available"}
    
    # Use specified user_id or current user
    effective_user_id = user_id or get_current_user_id()
    
    try:
        triples = await _knowledge_store.search(q, effective_user_id, limit)
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
    if not _knowledge_store:
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
