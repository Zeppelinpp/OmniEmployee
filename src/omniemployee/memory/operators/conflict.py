"""ConflictChecker - Detects cognitive dissonance between memories.

Identifies when new information contradicts existing memory,
triggering confirmation or restructuring actions.
"""

from __future__ import annotations

from typing import Callable, Awaitable, Any
from dataclasses import dataclass

from src.omniemployee.memory.models import (
    MemoryNode,
    ConflictNode,
    DissonanceSignal,
)


@dataclass
class ConflictConfig:
    """Configuration for conflict detection."""
    similarity_threshold: float = 0.8   # Min similarity to check for conflict
    polarity_threshold: float = 0.5     # Min polarity difference for conflict
    confidence_threshold: float = 0.7   # Min confidence to report conflict
    
    # Actions
    auto_resolve_low_energy: bool = True  # Auto-resolve if old node has low energy
    low_energy_threshold: float = 0.3     # Energy below which auto-resolve applies


class ConflictChecker:
    """Detects and manages conflicts between memory nodes.
    
    Conflict detection strategy:
    1. Find semantically similar nodes (similarity > threshold)
    2. Check for logical polarity reversal
    3. Generate DissonanceSignal for confirmed conflicts
    """
    
    def __init__(self, config: ConflictConfig | None = None):
        self.config = config or ConflictConfig()
        
        # Optional LLM callback for conflict verification
        self._verify_conflict_callback: Callable[[str, str], Awaitable[dict]] | None = None
    
    def set_verify_conflict_callback(
        self,
        callback: Callable[[str, str], Awaitable[dict]]
    ) -> None:
        """Set callback for LLM-based conflict verification.
        
        Callback receives (content_a, content_b) and returns:
        {
            "is_conflict": bool,
            "conflict_type": str,  # "contradiction", "update", "refinement"
            "description": str,
            "confidence": float
        }
        """
        self._verify_conflict_callback = callback
    
    async def check_conflicts(
        self,
        new_node: MemoryNode,
        existing_nodes: list[MemoryNode]
    ) -> list[DissonanceSignal]:
        """Check for conflicts between new node and existing nodes.
        
        Args:
            new_node: The incoming memory node
            existing_nodes: List of potentially conflicting nodes
        
        Returns:
            List of DissonanceSignals for detected conflicts
        """
        signals = []
        
        for existing in existing_nodes:
            if existing.id == new_node.id:
                continue
            
            # Check semantic similarity
            similarity = self._compute_similarity(new_node, existing)
            
            if similarity < self.config.similarity_threshold:
                continue
            
            # Check for potential conflict
            conflict = await self._detect_conflict(new_node, existing, similarity)
            
            if conflict:
                signal = self._create_dissonance_signal(conflict, existing)
                signals.append(signal)
        
        return signals
    
    async def _detect_conflict(
        self,
        new_node: MemoryNode,
        existing_node: MemoryNode,
        similarity: float
    ) -> ConflictNode | None:
        """Detect if two nodes are in conflict."""
        # Quick heuristic check first
        heuristic_conflict = self._heuristic_conflict_check(new_node, existing_node)
        
        if not heuristic_conflict:
            return None
        
        # If LLM callback available, verify with LLM
        if self._verify_conflict_callback:
            try:
                result = await self._verify_conflict_callback(
                    new_node.content,
                    existing_node.content
                )
                
                if not result.get("is_conflict", False):
                    return None
                
                if result.get("confidence", 0) < self.config.confidence_threshold:
                    return None
                
                return ConflictNode(
                    node_a_id=existing_node.id,
                    node_b_id=new_node.id,
                    similarity=similarity,
                    conflict_type=result.get("conflict_type", "contradiction"),
                    description=result.get("description", "")
                )
            except Exception:
                pass  # Fall back to heuristic result
        
        # Return heuristic-based conflict
        return ConflictNode(
            node_a_id=existing_node.id,
            node_b_id=new_node.id,
            similarity=similarity,
            conflict_type="potential_contradiction",
            description=f"Heuristic: sentiment polarity differs significantly"
        )
    
    def _heuristic_conflict_check(
        self,
        node_a: MemoryNode,
        node_b: MemoryNode
    ) -> bool:
        """Quick heuristic to check for potential conflict."""
        # Check sentiment polarity reversal
        sentiment_a = node_a.metadata.sentiment
        sentiment_b = node_b.metadata.sentiment
        
        polarity_diff = abs(sentiment_a - sentiment_b)
        if polarity_diff >= self.config.polarity_threshold:
            # Check if they have opposite signs
            if (sentiment_a > 0 and sentiment_b < 0) or (sentiment_a < 0 and sentiment_b > 0):
                return True
        
        # Check for negation patterns in content
        negation_patterns = [
            "not ", "don't ", "doesn't ", "isn't ", "aren't ",
            "won't ", "can't ", "shouldn't ", "never ", "no longer "
        ]
        
        content_a_lower = node_a.content.lower()
        content_b_lower = node_b.content.lower()
        
        # If one has negation and other doesn't for similar content
        has_negation_a = any(p in content_a_lower for p in negation_patterns)
        has_negation_b = any(p in content_b_lower for p in negation_patterns)
        
        if has_negation_a != has_negation_b:
            return True
        
        # Check for contradicting keywords
        contradiction_pairs = [
            ("true", "false"),
            ("yes", "no"),
            ("always", "never"),
            ("all", "none"),
            ("increase", "decrease"),
            ("start", "stop"),
            ("enable", "disable"),
            ("allow", "deny"),
            ("success", "failure"),
        ]
        
        for pos, neg in contradiction_pairs:
            if (pos in content_a_lower and neg in content_b_lower) or \
               (neg in content_a_lower and pos in content_b_lower):
                return True
        
        return False
    
    def _compute_similarity(self, node_a: MemoryNode, node_b: MemoryNode) -> float:
        """Compute semantic similarity between nodes."""
        if not node_a.vector or not node_b.vector:
            return 0.0
        
        if len(node_a.vector) != len(node_b.vector):
            return 0.0
        
        # Cosine similarity
        dot = sum(a * b for a, b in zip(node_a.vector, node_b.vector))
        norm_a = sum(a * a for a in node_a.vector) ** 0.5
        norm_b = sum(b * b for b in node_b.vector) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _create_dissonance_signal(
        self,
        conflict: ConflictNode,
        existing_node: MemoryNode
    ) -> DissonanceSignal:
        """Create a dissonance signal from a detected conflict."""
        # Determine required action
        if (self.config.auto_resolve_low_energy 
            and existing_node.energy < self.config.low_energy_threshold):
            action = "restructure"  # Auto-update old memory
            priority = 0.3
        elif conflict.conflict_type == "update":
            action = "confirm"  # Ask user to confirm update
            priority = 0.5
        else:
            action = "confirm"  # Require explicit confirmation
            priority = 0.7
        
        return DissonanceSignal(
            conflict=conflict,
            action_required=action,
            priority=priority,
            context=f"Existing memory energy: {existing_node.energy:.2f}"
        )
    
    async def resolve_conflict(
        self,
        conflict: ConflictNode,
        resolution: str,
        keep_node_id: str | None = None
    ) -> None:
        """Mark a conflict as resolved.
        
        Args:
            conflict: The conflict to resolve
            resolution: How it was resolved (e.g., "kept_new", "kept_old", "merged")
            keep_node_id: ID of the node to keep (if applicable)
        """
        conflict.resolved = True
        conflict.resolution = resolution
    
    def get_conflict_summary(self, conflicts: list[ConflictNode]) -> str:
        """Generate a human-readable summary of conflicts."""
        if not conflicts:
            return "No conflicts detected."
        
        lines = [f"Detected {len(conflicts)} potential conflict(s):"]
        
        for i, c in enumerate(conflicts, 1):
            status = "✓ Resolved" if c.resolved else "⚠ Pending"
            lines.append(
                f"{i}. [{status}] {c.conflict_type}: {c.description[:100]}"
            )
        
        return "\n".join(lines)
