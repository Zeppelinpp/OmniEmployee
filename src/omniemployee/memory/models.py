"""Core data models for BIEM memory system."""

from __future__ import annotations

import uuid
import time
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class LinkType(str, Enum):
    """Type of relationship between memory nodes."""
    TEMPORAL = "temporal"   # Sequential/time-based relationship
    SEMANTIC = "semantic"   # Meaning-based similarity
    CAUSAL = "causal"       # Cause-effect relationship


@dataclass
class Link:
    """Association edge between memory nodes.
    
    Represents a directed relationship from source to target node.
    """
    source_id: str
    target_id: str
    link_type: LinkType
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "link_type": self.link_type.value,
            "weight": self.weight,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Link:
        """Deserialize from dictionary."""
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            link_type=LinkType(data["link_type"]),
            weight=data.get("weight", 1.0),
            created_at=data.get("created_at", time.time()),
        )
    
    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.link_type))
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Link):
            return False
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.link_type == other.link_type
        )


@dataclass
class MemoryMetadata:
    """Metadata associated with a memory node."""
    timestamp: float = field(default_factory=time.time)
    location: str = ""          # Environment context
    entities: list[str] = field(default_factory=list)  # Extracted entity anchors
    sentiment: float = 0.0      # Emotional polarity (-1 to 1)
    source: str = ""            # Origin of the memory (user, tool, agent, etc.)
    tags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryMetadata:
        return cls(**data)


@dataclass
class MemoryNode:
    """A single memory unit in the BIEM system.
    
    Contains content, vector embedding, metadata, and energy state.
    Energy decays over time based on the formula: E = E0 * e^(-λΔt)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    vector: list[float] = field(default_factory=list)  # Semantic embedding
    metadata: MemoryMetadata = field(default_factory=MemoryMetadata)
    energy: float = 1.0         # Current energy level (0-1)
    initial_energy: float = 1.0 # Energy at creation (for reference)
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    tier: str = "L1"            # Current storage tier: L1/L2/L3
    links: list[Link] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "vector": self.vector,
            "metadata": self.metadata.to_dict(),
            "energy": self.energy,
            "initial_energy": self.initial_energy,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
            "tier": self.tier,
            "links": [link.to_dict() for link in self.links],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryNode:
        """Deserialize from dictionary."""
        metadata = MemoryMetadata.from_dict(data.get("metadata", {}))
        links = [Link.from_dict(l) for l in data.get("links", [])]
        return cls(
            id=data["id"],
            content=data.get("content", ""),
            vector=data.get("vector", []),
            metadata=metadata,
            energy=data.get("energy", 1.0),
            initial_energy=data.get("initial_energy", 1.0),
            last_accessed=data.get("last_accessed", time.time()),
            created_at=data.get("created_at", time.time()),
            tier=data.get("tier", "L1"),
            links=links,
        )
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> MemoryNode:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def touch(self) -> None:
        """Update last_accessed timestamp (activates the memory)."""
        self.last_accessed = time.time()
    
    def add_link(self, link: Link) -> None:
        """Add a link to this node."""
        if link not in self.links:
            self.links.append(link)
    
    def get_links_by_type(self, link_type: LinkType) -> list[Link]:
        """Get all links of a specific type."""
        return [l for l in self.links if l.link_type == link_type]
    
    def summarize(self, max_length: int = 100) -> str:
        """Get a summary of this memory for display."""
        content_preview = self.content[:max_length]
        if len(self.content) > max_length:
            content_preview += "..."
        return f"[E={self.energy:.2f}] {content_preview}"


@dataclass
class ConflictNode:
    """Represents a detected conflict between memory nodes.
    
    Created when new information contradicts existing memory.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    node_a_id: str = ""         # Existing memory
    node_b_id: str = ""         # New conflicting memory
    similarity: float = 0.0     # Semantic similarity score
    conflict_type: str = ""     # Type of conflict detected
    description: str = ""       # Human-readable conflict description
    resolved: bool = False
    resolution: str = ""        # How the conflict was resolved
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConflictNode:
        return cls(**data)


@dataclass
class DissonanceSignal:
    """Signal emitted when cognitive dissonance is detected.
    
    Used to trigger confirmation or restructuring actions.
    """
    conflict: ConflictNode
    action_required: str        # "confirm" | "restructure" | "ignore"
    priority: float = 0.5       # 0-1, higher = more urgent
    context: str = ""           # Additional context for resolution
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict": self.conflict.to_dict(),
            "action_required": self.action_required,
            "priority": self.priority,
            "context": self.context,
        }


@dataclass
class CrystalFact:
    """A consolidated semantic fact stored in L3 (The Crystal).
    
    Created by merging frequently activated, highly related memory nodes.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    source_node_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrystalFact:
        return cls(**data)
