"""BIEM - Bio-Inspired Evolving Memory System.

A memory system with energy decay, associative recall, and conflict detection.

Architecture:
- L1 (Working Canvas): High-speed in-memory storage for active context
- L2 (Association Web): Milvus vector storage + NetworkX graph
- L3 (Crystal): PostgreSQL persistent knowledge base

Usage:
    from src.omniemployee.memory import MemoryManager, MemoryConfig
    
    # Initialize
    config = MemoryConfig()
    memory = MemoryManager(config)
    await memory.initialize()
    
    # Ingest memories
    node, conflicts = await memory.ingest("User prefers dark mode")
    
    # Recall relevant memories
    memories = await memory.recall("What are the user's preferences?")
    
    # Get context for LLM
    context = await memory.get_context("current task description")
"""

from src.omniemployee.memory.models import (
    MemoryNode,
    MemoryMetadata,
    Link,
    LinkType,
    ConflictNode,
    DissonanceSignal,
    CrystalFact,
)
from src.omniemployee.memory.memory_manager import MemoryManager, MemoryConfig
from src.omniemployee.memory.integration import BIEMContextPlugin, PluginConfig

__all__ = [
    # Models
    "MemoryNode",
    "MemoryMetadata",
    "Link",
    "LinkType",
    "ConflictNode",
    "DissonanceSignal",
    "CrystalFact",
    # Main API
    "MemoryManager",
    "MemoryConfig",
    # Integration
    "BIEMContextPlugin",
    "PluginConfig",
]
