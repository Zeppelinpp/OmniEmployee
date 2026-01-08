"""Knowledge Learning System - Extract, store, and update structured knowledge.

This module provides LLM-driven knowledge extraction from conversations,
conflict detection, and knowledge base management.
"""

from src.omniemployee.memory.knowledge.models import (
    KnowledgeTriple,
    KnowledgeIntent,
    KnowledgeSource,
    ExtractionResult,
    ConflictResult,
    KnowledgeUpdateEvent,
    PendingUpdate,
)
from src.omniemployee.memory.knowledge.extractor import KnowledgeExtractor, ExtractorConfig
from src.omniemployee.memory.knowledge.store import KnowledgeStore, KnowledgeStoreConfig
from src.omniemployee.memory.knowledge.conflict import (
    KnowledgeConflictDetector,
    ConfirmationManager,
    ConflictConfig,
)
from src.omniemployee.memory.knowledge.integration import (
    KnowledgeLearningPlugin,
    KnowledgePluginConfig,
    ProcessResult,
    create_knowledge_plugin,
)
from src.omniemployee.memory.knowledge.vector_store import (
    KnowledgeVectorStore,
    KnowledgeVectorConfig,
)

__all__ = [
    # Models
    "KnowledgeTriple",
    "KnowledgeIntent",
    "KnowledgeSource",
    "ExtractionResult",
    "ConflictResult",
    "KnowledgeUpdateEvent",
    "PendingUpdate",
    # Components
    "KnowledgeExtractor",
    "ExtractorConfig",
    "KnowledgeStore",
    "KnowledgeStoreConfig",
    "KnowledgeConflictDetector",
    "ConfirmationManager",
    "ConflictConfig",
    # Vector Store
    "KnowledgeVectorStore",
    "KnowledgeVectorConfig",
    # Integration
    "KnowledgeLearningPlugin",
    "KnowledgePluginConfig",
    "ProcessResult",
    "create_knowledge_plugin",
]
