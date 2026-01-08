"""Storage layer for BIEM memory system."""

from src.omniemployee.memory.storage.base import (
    StorageBackend,
    VectorStorageBackend,
    GraphStorageBackend,
)
from src.omniemployee.memory.storage.l1_working import L1WorkingMemory, L1Config
from src.omniemployee.memory.storage.l2_vector import L2VectorStorage, MilvusConfig
from src.omniemployee.memory.storage.l2_graph import L2GraphStorage, GraphConfig
from src.omniemployee.memory.storage.l3_crystal import L3CrystalStorage, PostgresConfig

__all__ = [
    # Base interfaces
    "StorageBackend",
    "VectorStorageBackend",
    "GraphStorageBackend",
    # L1 Working Memory
    "L1WorkingMemory",
    "L1Config",
    # L2 Vector Storage
    "L2VectorStorage",
    "MilvusConfig",
    # L2 Graph Storage
    "L2GraphStorage",
    "GraphConfig",
    # L3 Crystal Storage
    "L3CrystalStorage",
    "PostgresConfig",
]
