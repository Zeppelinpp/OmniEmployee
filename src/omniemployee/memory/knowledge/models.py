"""Data models for the Knowledge Learning System."""

from __future__ import annotations

import uuid
import time
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class KnowledgeIntent(str, Enum):
    """Intent behind a knowledge statement."""
    STATEMENT = "statement"       # Normal factual statement
    CORRECTION = "correction"     # Correcting previous information
    QUESTION = "question"         # Asking about knowledge
    OPINION = "opinion"           # Subjective opinion (not stored as fact)


class KnowledgeSource(str, Enum):
    """Source/confidence level of knowledge."""
    CONVERSATION = "conversation"     # Extracted from normal chat
    USER_STATED = "user_stated"       # User explicitly stated
    USER_CORRECTION = "user_correction"  # User corrected agent's info
    USER_VERIFIED = "user_verified"   # User confirmed an update
    AGENT_INFERRED = "agent_inferred" # Agent inferred from context
    AGENT_SEARCH = "agent_search"     # From agent's web search results
    AGENT_SUMMARY = "agent_summary"   # Agent's summary of external info


@dataclass
class KnowledgeTriple:
    """A knowledge triple (subject, predicate, object).
    
    Represents a single fact like:
    - (GPT-4, context_window, 128k tokens)
    - (Python, created_by, Guido van Rossum)
    - (Claude 3.5, output_limit, 8k tokens)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""              # Entity: "GPT-4", "Python"
    predicate: str = ""            # Relation: "context_window", "created_by"
    object: str = ""               # Value: "128k tokens", "Guido van Rossum"
    
    confidence: float = 0.8        # 0.0-1.0, higher = more confident
    source: KnowledgeSource = KnowledgeSource.CONVERSATION
    
    version: int = 1               # Incremented on updates
    previous_values: list[str] = field(default_factory=list)  # History
    
    # Metadata
    session_id: str = ""           # Which session created this
    user_id: str = ""              # Which user owns this knowledge
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Vector for semantic search (optional)
    vector: list[float] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "source": self.source.value,
            "version": self.version,
            "previous_values": self.previous_values,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "vector": self.vector,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeTriple:
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            subject=data.get("subject", ""),
            predicate=data.get("predicate", ""),
            object=data.get("object", ""),
            confidence=data.get("confidence", 0.8),
            source=KnowledgeSource(data.get("source", "conversation")),
            version=data.get("version", 1),
            previous_values=data.get("previous_values", []),
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            vector=data.get("vector", []),
        )
    
    def to_text(self) -> str:
        """Convert triple to readable text for embedding."""
        return f"{self.subject} {self.predicate} {self.object}"
    
    def display(self) -> str:
        """Human-readable display format."""
        return f"({self.subject}, {self.predicate}, {self.object})"
    
    def __hash__(self) -> int:
        return hash((self.subject.lower(), self.predicate.lower()))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, KnowledgeTriple):
            return False
        return (
            self.subject.lower() == other.subject.lower()
            and self.predicate.lower() == other.predicate.lower()
        )


@dataclass
class ExtractionResult:
    """Result of knowledge extraction from a message."""
    is_factual: bool = False       # Does message contain factual content?
    intent: KnowledgeIntent = KnowledgeIntent.STATEMENT
    triples: list[KnowledgeTriple] = field(default_factory=list)
    confidence: float = 0.0        # Overall extraction confidence
    raw_message: str = ""          # Original message
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "is_factual": self.is_factual,
            "intent": self.intent.value,
            "triples": [t.to_dict() for t in self.triples],
            "confidence": self.confidence,
            "raw_message": self.raw_message,
        }


@dataclass
class ConflictResult:
    """Result of conflict detection between knowledge triples."""
    has_conflict: bool = False
    existing_triple: KnowledgeTriple | None = None
    new_triple: KnowledgeTriple | None = None
    conflict_type: str = ""        # "value_change", "contradiction"
    suggestion: str = ""           # Human-readable suggestion
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "has_conflict": self.has_conflict,
            "existing_triple": self.existing_triple.to_dict() if self.existing_triple else None,
            "new_triple": self.new_triple.to_dict() if self.new_triple else None,
            "conflict_type": self.conflict_type,
            "suggestion": self.suggestion,
        }


@dataclass
class KnowledgeUpdateEvent:
    """Event recording a knowledge update."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    triple_id: str = ""
    old_value: str = ""
    new_value: str = ""
    reason: str = ""               # "user_correction", "new_information"
    confirmed: bool = False        # Was update confirmed by user?
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeUpdateEvent:
        return cls(**data)


@dataclass
class PendingUpdate:
    """A pending knowledge update awaiting user confirmation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    new_triple: KnowledgeTriple = field(default_factory=KnowledgeTriple)
    existing_triple: KnowledgeTriple | None = None
    confirmation_message: str = ""  # Message shown to user
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300)  # 5 min timeout
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "new_triple": self.new_triple.to_dict(),
            "existing_triple": self.existing_triple.to_dict() if self.existing_triple else None,
            "confirmation_message": self.confirmation_message,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
