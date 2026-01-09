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


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt not found: {prompt_path}")


def _setup_memory_llm_callbacks(memory: MemoryManager, llm: LLMProvider) -> None:
    """Set up LLM callbacks for memory system operations."""
    
    # Load prompt template
    try:
        consolidation_prompt = _load_prompt("memory_consolidation")
    except FileNotFoundError:
        print("⚠ Memory consolidation prompt not found, using fallback")
        consolidation_prompt = "Consolidate these memories into one fact:\n{memories}"
    
    async def consolidate_memories(contents: list[str]) -> str:
        """Use LLM to consolidate multiple memory contents into a unified fact."""
        # Format memories for prompt
        memories_text = "\n".join(f"- {c}" for c in contents)
        prompt = consolidation_prompt.format(memories=memories_text)
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            response = await llm.complete(messages)
            return response.content.strip()
        except Exception as e:
            # Fallback to simple concatenation
            print(f"[Memory] LLM consolidation failed: {e}")
            return f"[Consolidated from {len(contents)} memories]\n" + contents[0]
    
    # Set the consolidation callback
    memory.set_consolidation_callback(consolidate_memories)
    print("✓ Memory LLM callbacks configured")


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
                # Set initial user_id from env or default
                initial_user_id = get_current_user_id()
                _memory.set_user_id(initial_user_id)
                print(f"✓ Memory system connected (user: {initial_user_id})")
            else:
                print("⚠ Memory plugin initialized but memory manager not available")
                _memory = None
        except Exception as e:
            print(f"⚠ Memory system not available: {e}")
            _memory = None
            _memory_plugin = None
    
    # Set up LLM callbacks for memory system after loop is initialized
    if _memory is not None and _loop is not None:
        _setup_memory_llm_callbacks(_memory, _loop.llm)
    
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
    
    # Extract knowledge from both user message and agent response
    if _knowledge_plugin and _knowledge_plugin.is_available():
        # Extract from user message
        await _knowledge_plugin.process_message(request.message, role="user")
        # Extract from agent response (search results, summaries, explanations)
        await _knowledge_plugin.process_message(result.response, role="assistant")
    
    return ChatResponse(
        response=result.response,
        tool_calls=tool_calls,
        session_id=session_id,
    )


@app.get("/api/chat/stream")
async def chat_stream(message: str, session_id: str = ""):
    """Stream chat response for real-time updates (SSE format).
    
    Events:
    - type: "context" - Memory and knowledge context used for this query (sent first)
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
        
        # Build context and track what was used
        context_parts = []
        used_memories = []
        used_knowledge = []
        
        if _memory_plugin:
            try:
                # Get actual memory nodes used
                memories = await _memory_plugin.get_relevant_memories(message)
                for node in memories:
                    used_memories.append({
                        "id": node.id,
                        "content": node.content[:200] + "..." if len(node.content) > 200 else node.content,
                        "energy": node.energy,
                        "tier": node.tier.value if hasattr(node.tier, 'value') else str(node.tier),
                    })
                memory_context = await _memory_plugin.prepare_context(message)
                if memory_context:
                    context_parts.append(memory_context)
            except Exception:
                pass
        
        if _knowledge_plugin and _knowledge_plugin.is_available():
            try:
                # Get actual knowledge triples used
                triples = await _knowledge_plugin.get_relevant_triples(message)
                for triple in triples:
                    used_knowledge.append({
                        "id": str(triple.id) if triple.id else "",
                        "subject": triple.subject,
                        "predicate": triple.predicate,
                        "object": triple.object,
                        "confidence": triple.confidence,
                        "source": triple.source.value if hasattr(triple.source, 'value') else str(triple.source),
                    })
                knowledge_context = await _knowledge_plugin.get_context_for_query(message)
                if knowledge_context:
                    context_parts.append(knowledge_context)
            except Exception:
                pass
        
        # Send context event first (what memory/knowledge was used for this query)
        yield f"data: {json.dumps({'type': 'context', 'memories': used_memories, 'knowledge': used_knowledge})}\n\n"
        
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
        
        # Process knowledge extraction from both user and agent
        if _knowledge_plugin and _knowledge_plugin.is_available():
            try:
                # Extract from user message
                await _knowledge_plugin.process_message(message, role="user")
                # Extract from agent response (search results, summaries)
                await _knowledge_plugin.process_message(response_text, role="assistant")
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
async def get_stats(user_id: str = ""):
    """Get memory system statistics for a specific user."""
    if not _memory:
        return {"status": "unavailable", "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    
    stats = await _memory.get_stats()
    # Add user-specific L1 stats
    stats["l1_user_stats"] = _memory._l1.get_stats(effective_user_id)
    return stats


@app.get("/api/memory/context")
async def get_memory_context(query: str = "", limit: int = 10, user_id: str = ""):
    """Get relevant memory items for a query (filtered by user)."""
    if not _memory:
        return {"items": [], "message": "Memory not available"}
    
    effective_user_id = user_id or get_current_user_id()
    
    try:
        # Use recall() for query-based search, or get_working_memory() for empty query
        if query:
            nodes = await _memory.recall(query, top_k=limit, user_id=effective_user_id)
        else:
            nodes = await _memory.get_working_memory(limit=limit, user_id=effective_user_id)
        return {
            "items": [
                {
                    "id": n.id,
                    "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                    "energy": round(n.energy, 3),
                    "tier": n.tier,
                    "user_id": n.user_id,
                }
                for n in nodes
            ]
        }
    except Exception as e:
        return {"items": [], "error": str(e)}


@app.get("/api/l1")
async def get_l1_nodes(user_id: str = ""):
    """Get all L1 working memory nodes for a specific user."""
    if not _memory:
        return {"nodes": [], "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    nodes = await _memory.get_working_memory(limit=100, user_id=effective_user_id)
    return {
        "nodes": [
            {
                "id": n.id,
                "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                "energy": round(n.energy, 3),
                "tier": n.tier,
                "user_id": n.user_id,
                "created_at": n.metadata.timestamp,
                "source": n.metadata.source,
                "entities": n.metadata.entities[:5],
                "sentiment": round(n.metadata.sentiment, 2),
            }
            for n in nodes
        ]
    }


@app.get("/api/l2/graph")
async def get_l2_graph(user_id: str = ""):
    """Get L2 graph data for D3.js visualization (filtered by user)."""
    if not _memory:
        return {"nodes": [], "links": [], "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    
    # Get graph storage directly
    graph = _memory._l2_graph
    vector = _memory._l2_vector
    
    # Get nodes belonging to this user
    user_nodes = graph._get_user_nodes(effective_user_id)
    
    # Get all nodes and edges from NetworkX (filtered by user)
    nodes_data = []
    edges_data = []
    
    for node_id in user_nodes:
        # Fetch content from Milvus vector storage
        node = await vector.get(node_id)
        if node:
            nodes_data.append({
                "id": node_id,
                "content": node.content[:100] + "..." if len(node.content) > 100 else node.content,
                "energy": node.energy,
                "tier": node.tier,
                "user_id": node.user_id,
            })
        else:
            # Fallback if not found in Milvus
            node_attrs = graph._graph.nodes[node_id]
            nodes_data.append({
                "id": node_id,
                "content": f"[Node {node_id[:8]}]",
                "energy": node_attrs.get("energy", 0.5),
                "tier": "L2",
                "user_id": node_attrs.get("user_id", ""),
            })
    
    for source, target, attrs in graph._graph.edges(data=True):
        # Only include edges between user's nodes
        if source in user_nodes and target in user_nodes:
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
async def get_l2_vector_nodes(user_id: str = ""):
    """Get L2 vector storage nodes (filtered by user)."""
    if not _memory:
        return {"nodes": [], "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    
    # Query nodes from Milvus (filtered by user)
    vector_storage = _memory._l2_vector
    
    if not vector_storage._connected:
        return {"nodes": [], "message": "Vector storage not connected"}
    
    try:
        # Query nodes for this user
        filter_expr = f'user_id == "{effective_user_id}"' if effective_user_id else ""
        results = vector_storage._client.query(
            collection_name=vector_storage.config.collection_name,
            filter=filter_expr,
            output_fields=["id", "content", "energy", "tier", "source", "timestamp", "entities", "user_id"],
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
                    "user_id": r.get("user_id", ""),
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"nodes": [], "error": str(e)}


@app.get("/api/l3/facts")
async def get_l3_facts(user_id: str = ""):
    """Get L3 crystal facts (filtered by user)."""
    if not _memory:
        return {"facts": [], "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"facts": [], "message": "L3 storage not available"}
    
    try:
        facts = await _memory._l3.get_all_facts(limit=100, user_id=effective_user_id)
        return {
            "facts": [
                {
                    "id": str(f.id),
                    "content": f.content[:300],
                    "confidence": round(f.confidence, 3),
                    "created_at": f.created_at,
                    "source_count": len(f.source_node_ids),
                    "user_id": f.user_id,
                }
                for f in facts
            ]
        }
    except Exception as e:
        return {"facts": [], "error": str(e)}


@app.get("/api/l3/links")
async def get_l3_links(user_id: str = ""):
    """Get L3 persistent links with content snippets (filtered by user)."""
    if not _memory:
        return {"links": [], "message": "Memory not initialized"}
    
    effective_user_id = user_id or get_current_user_id()
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"links": [], "message": "L3 storage not available"}
    
    try:
        links = await _memory._l3.get_all_links(limit=100, user_id=effective_user_id)
        
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


@app.post("/api/memory/consolidate")
async def trigger_consolidation():
    """Manually trigger memory consolidation (for testing).
    
    This will scan L2 for similar nodes and create L3 facts.
    """
    if not _memory:
        raise HTTPException(status_code=503, detail="Memory not initialized")
    
    tier = _memory._tier
    if not tier._l3_available:
        return {"success": False, "message": "L3 storage not available"}
    
    try:
        # Run consolidation
        await tier._run_consolidation()
        
        # Get updated stats
        stats = await tier.get_stats()
        
        return {
            "success": True,
            "message": "Consolidation completed",
            "l3_facts_count": stats.get("l3", {}).get("facts_count", 0),
            "l3_links_count": stats.get("l3", {}).get("links_count", 0),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    """Switch to a different user_id.
    
    Memory data is filtered by user_id (per-user isolation).
    Knowledge data is global (shared across all users).
    """
    global _current_user_id, _knowledge_plugin, _memory
    
    _current_user_id = user_id
    
    # Update memory manager user context
    if _memory:
        _memory.set_user_id(user_id)
    
    # Update knowledge plugin config (for attribution, not isolation)
    if _knowledge_plugin:
        _knowledge_plugin.config.user_id = user_id
    
    return {"success": True, "user_id": user_id}


@app.post("/api/user/create")
async def create_user(user_id: str):
    """Create a new user (just sets it as current, data will be created on first message)."""
    global _current_user_id, _knowledge_plugin, _memory
    
    if not user_id or not user_id.strip():
        return {"success": False, "error": "Invalid user_id"}
    
    _current_user_id = user_id.strip()
    
    # Update memory manager user context
    if _memory:
        _memory.set_user_id(_current_user_id)
    
    # Update knowledge plugin config (for attribution)
    if _knowledge_plugin:
        _knowledge_plugin.config.user_id = _current_user_id
    
    return {"success": True, "user_id": _current_user_id}


@app.get("/api/debug/user_ids")
async def debug_user_ids():
    """Debug endpoint to show all user_ids in the system."""
    result = {
        "current_user": get_current_user_id(),
        "memory_manager_user": _memory._current_user_id if _memory else None,
    }
    
    # Check L2 Vector (Milvus) user_ids
    if _memory and _memory._l2_vector._connected:
        try:
            all_nodes = _memory._l2_vector._client.query(
                collection_name=_memory._l2_vector.config.collection_name,
                filter="",
                output_fields=["id", "user_id"],
                limit=1000,
            )
            user_ids = set(r.get("user_id", "") for r in all_nodes)
            result["l2_vector_user_ids"] = list(user_ids)
            result["l2_vector_total"] = len(all_nodes)
        except Exception as e:
            result["l2_vector_error"] = str(e)
    
    # Check L2 Graph user_ids
    if _memory:
        try:
            graph = _memory._l2_graph._graph
            graph_user_ids = set()
            for node_id in graph.nodes():
                uid = graph.nodes[node_id].get("user_id", "")
                graph_user_ids.add(uid)
            result["l2_graph_user_ids"] = list(graph_user_ids)
            result["l2_graph_total"] = graph.number_of_nodes()
        except Exception as e:
            result["l2_graph_error"] = str(e)
    
    # Check L3 Facts user_ids
    if _memory and _memory._tier._l3_available:
        try:
            async with _memory._l3._pool.acquire() as conn:
                rows = await conn.fetch("SELECT DISTINCT user_id FROM crystal_facts")
                result["l3_facts_user_ids"] = [r["user_id"] for r in rows]
                count = await conn.fetchval("SELECT COUNT(*) FROM crystal_facts")
                result["l3_facts_total"] = count
        except Exception as e:
            result["l3_facts_error"] = str(e)
    
    return result


@app.post("/api/debug/migrate_user_id")
async def migrate_user_id(target_user_id: str):
    """Migrate all memory data with empty user_id to the target user_id."""
    if not _memory:
        return {"error": "Memory not initialized"}
    
    result = {"migrated": {}}
    
    # Migrate L2 Vector (Milvus) - use upsert to update user_id
    if _memory._l2_vector._connected:
        try:
            # Find nodes with empty user_id
            empty_nodes = _memory._l2_vector._client.query(
                collection_name=_memory._l2_vector.config.collection_name,
                filter='user_id == ""',
                output_fields=["*"],  # Get all fields for upsert
                limit=10000,
            )
            
            if empty_nodes:
                # Update user_id and upsert back
                for node_data in empty_nodes:
                    node_data["user_id"] = target_user_id
                
                _memory._l2_vector._client.upsert(
                    collection_name=_memory._l2_vector.config.collection_name,
                    data=empty_nodes
                )
                result["migrated"]["l2_vector"] = {"count": len(empty_nodes)}
            else:
                result["migrated"]["l2_vector"] = {"count": 0, "note": "No migration needed"}
        except Exception as e:
            result["migrated"]["l2_vector"] = {"error": str(e)}
    
    # Migrate L2 Graph
    try:
        graph = _memory._l2_graph._graph
        migrated_count = 0
        for node_id in graph.nodes():
            if not graph.nodes[node_id].get("user_id"):
                graph.nodes[node_id]["user_id"] = target_user_id
                migrated_count += 1
        result["migrated"]["l2_graph"] = {"count": migrated_count}
    except Exception as e:
        result["migrated"]["l2_graph"] = {"error": str(e)}
    
    # Migrate L3 Facts
    if _memory._tier._l3_available:
        try:
            async with _memory._l3._pool.acquire() as conn:
                updated = await conn.execute(
                    "UPDATE crystal_facts SET user_id = $1 WHERE user_id = '' OR user_id IS NULL",
                    target_user_id
                )
                result["migrated"]["l3_facts"] = {"count": int(updated.split()[-1])}
                
                updated_links = await conn.execute(
                    "UPDATE crystal_links SET user_id = $1 WHERE user_id = '' OR user_id IS NULL",
                    target_user_id
                )
                result["migrated"]["l3_links"] = {"count": int(updated_links.split()[-1])}
        except Exception as e:
            result["migrated"]["l3"] = {"error": str(e)}
    
    return result


# ==================== Knowledge APIs ====================
# NOTE: Knowledge is GLOBAL (shared across all users)
# Unlike Memory which is per-user isolated

@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge store statistics (GLOBAL - not per-user)."""
    if not _knowledge_store:
        return {"status": "unavailable"}
    
    try:
        # Knowledge stats are global (no user_id filter)
        stats = await _knowledge_store.get_stats()
        stats["note"] = "Knowledge is shared globally across all users"
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/knowledge/triples")
async def get_knowledge_triples(limit: int = 100):
    """Get all knowledge triples (GLOBAL - shared across all users)."""
    if not _knowledge_store:
        return {"triples": [], "message": "Knowledge store not available"}
    
    try:
        # Knowledge is global - no user_id filter
        triples = await _knowledge_store.get_all(limit=limit)
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
                    "contributed_by": t.user_id,  # Who added this knowledge
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in triples
            ],
            "note": "Knowledge is shared globally across all users"
        }
    except Exception as e:
        return {"triples": [], "error": str(e)}


@app.get("/api/knowledge/search")
async def search_knowledge(q: str, limit: int = 20):
    """Search knowledge triples (GLOBAL - shared across all users)."""
    if not _knowledge_store:
        return {"triples": [], "message": "Knowledge store not available"}
    
    try:
        # Knowledge search is global (no user_id filter)
        triples = await _knowledge_store.search(q, limit=limit)
        return {
            "triples": [
                {
                    "id": str(t.id),
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object,
                    "confidence": round(t.confidence, 3),
                    "source": t.source.value,
                    "contributed_by": t.user_id,
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
