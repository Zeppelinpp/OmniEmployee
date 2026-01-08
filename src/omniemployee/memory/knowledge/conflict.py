"""Knowledge Conflict Detector.

Detects conflicts between new and existing knowledge triples.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.omniemployee.memory.knowledge.models import (
    KnowledgeTriple,
    ConflictResult,
)
from src.omniemployee.memory.knowledge.store import KnowledgeStore


@dataclass
class ConflictConfig:
    """Configuration for conflict detection."""
    # Semantic similarity threshold for considering triples as "about the same thing"
    similarity_threshold: float = 0.7
    # Whether to use LLM for advanced conflict reasoning
    use_llm_reasoning: bool = False


class KnowledgeConflictDetector:
    """Detects conflicts between knowledge triples.
    
    Conflict scenarios:
    1. Same subject + predicate, different object (value change)
    2. Semantically equivalent but lexically different predicates
    3. Logical contradictions (requires LLM reasoning)
    """
    
    def __init__(
        self,
        store: KnowledgeStore,
        config: ConflictConfig | None = None,
    ):
        self._store = store
        self.config = config or ConflictConfig()
    
    async def check(self, new_triple: KnowledgeTriple) -> ConflictResult:
        """Check if a new triple conflicts with existing knowledge.
        
        Args:
            new_triple: The new knowledge triple to check
            
        Returns:
            ConflictResult with details if conflict found
        """
        if not self._store.is_available():
            return ConflictResult(has_conflict=False)
        
        # Find potential conflicts
        conflicts = await self._store.find_potential_conflicts(new_triple)
        
        if not conflicts:
            return ConflictResult(has_conflict=False)
        
        # Check for direct value conflicts
        for existing in conflicts:
            if self._is_direct_conflict(new_triple, existing):
                return ConflictResult(
                    has_conflict=True,
                    existing_triple=existing,
                    new_triple=new_triple,
                    conflict_type="value_change",
                    suggestion=self._generate_suggestion(existing, new_triple),
                )
        
        return ConflictResult(has_conflict=False)
    
    def _is_direct_conflict(
        self,
        new: KnowledgeTriple,
        existing: KnowledgeTriple,
    ) -> bool:
        """Check if two triples have a direct value conflict.
        
        Same subject + predicate but different object values.
        """
        return (
            new.subject.lower() == existing.subject.lower()
            and new.predicate.lower() == existing.predicate.lower()
            and new.object.lower() != existing.object.lower()
        )
    
    def _generate_suggestion(
        self,
        existing: KnowledgeTriple,
        new: KnowledgeTriple,
    ) -> str:
        """Generate a human-readable suggestion for the conflict."""
        # Format predicate for display
        display_predicate = existing.predicate.replace("_", " ")
        
        return (
            f"我记得 **{existing.subject}** 的 {display_predicate} 是 "
            f"**{existing.object}**，您确认更新为 **{new.object}** 吗？"
        )
    
    async def check_batch(
        self,
        triples: list[KnowledgeTriple],
    ) -> list[ConflictResult]:
        """Check multiple triples for conflicts.
        
        Args:
            triples: List of new knowledge triples
            
        Returns:
            List of ConflictResults for each triple
        """
        results = []
        for triple in triples:
            result = await self.check(triple)
            results.append(result)
        return results


class ConfirmationManager:
    """Manages pending knowledge updates awaiting user confirmation.
    
    Handles the conversation flow when a conflict is detected:
    1. Store pending update
    2. Generate confirmation prompt
    3. Process user response
    4. Execute or cancel update
    """
    
    def __init__(self, store: KnowledgeStore):
        self._store = store
        self._pending: dict[str, tuple[KnowledgeTriple, KnowledgeTriple | None]] = {}
    
    def add_pending(
        self,
        new_triple: KnowledgeTriple,
        existing_triple: KnowledgeTriple | None = None,
    ) -> str:
        """Add a pending update.
        
        Args:
            new_triple: The new knowledge to potentially store
            existing_triple: The existing conflicting triple (if any)
            
        Returns:
            A key to reference this pending update
        """
        key = f"pending_{new_triple.id}"
        self._pending[key] = (new_triple, existing_triple)
        return key
    
    def get_pending(self, key: str) -> tuple[KnowledgeTriple, KnowledgeTriple | None] | None:
        """Get a pending update by key."""
        return self._pending.get(key)
    
    def remove_pending(self, key: str) -> None:
        """Remove a pending update."""
        self._pending.pop(key, None)
    
    def has_pending(self) -> bool:
        """Check if there are pending updates."""
        return len(self._pending) > 0
    
    def get_all_pending_keys(self) -> list[str]:
        """Get all pending update keys."""
        return list(self._pending.keys())
    
    async def confirm(self, key: str, session_id: str = "") -> bool:
        """Confirm and execute a pending update.
        
        Args:
            key: The pending update key
            session_id: Current session ID
            
        Returns:
            True if update was executed
        """
        pending = self._pending.pop(key, None)
        if not pending:
            return False
        
        new_triple, existing = pending
        
        if existing:
            # Update existing triple
            from src.omniemployee.memory.knowledge.models import KnowledgeSource
            await self._store.update(
                existing.id,
                new_triple.object,
                source=KnowledgeSource.USER_VERIFIED,
                confidence=1.0,
                session_id=session_id,
            )
        else:
            # Store new triple
            new_triple.source = KnowledgeSource.USER_VERIFIED
            new_triple.confidence = 1.0
            await self._store.store(new_triple)
        
        return True
    
    async def reject(self, key: str) -> bool:
        """Reject a pending update.
        
        Args:
            key: The pending update key
            
        Returns:
            True if pending was removed
        """
        return self._pending.pop(key, None) is not None
    
    def clear_all(self) -> None:
        """Clear all pending updates."""
        self._pending.clear()
    
    def generate_confirmation_prompt(
        self,
        conflict: ConflictResult,
        language: str = "zh",
    ) -> str:
        """Generate a confirmation prompt for the user.
        
        Args:
            conflict: The conflict result
            language: "zh" for Chinese, "en" for English
            
        Returns:
            Human-readable confirmation prompt
        """
        if not conflict.existing_triple or not conflict.new_triple:
            return ""
        
        existing = conflict.existing_triple
        new = conflict.new_triple
        display_pred = existing.predicate.replace("_", " ")
        
        if language == "zh":
            return (
                f"我记得 **{existing.subject}** 的 {display_pred} 是 "
                f"**{existing.object}**。\n\n"
                f"您说的是 **{new.object}**，请问是信息有更新吗？"
            )
        else:
            return (
                f"I have recorded that **{existing.subject}**'s {display_pred} is "
                f"**{existing.object}**.\n\n"
                f"You mentioned **{new.object}**. Has this information been updated?"
            )
