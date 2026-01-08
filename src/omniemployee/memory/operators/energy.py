"""EnergyController - Manages energy decay and activation for memory nodes.

Implements the biological-inspired energy decay formula: E = E0 * e^(-λΔt)
where λ is the decay coefficient and Δt is time since last access.
"""

from __future__ import annotations

import math
import time
import asyncio
from typing import Callable, Awaitable
from dataclasses import dataclass

from src.omniemployee.memory.models import MemoryNode


@dataclass
class EnergyConfig:
    """Configuration for energy decay behavior."""
    decay_lambda: float = 0.001     # Decay coefficient (higher = faster decay)
    min_energy: float = 0.01        # Minimum energy before node is considered dead
    activation_boost: float = 0.1   # Energy boost when node is accessed
    max_energy: float = 1.0         # Maximum energy cap
    decay_interval: float = 60.0    # Seconds between decay cycles
    
    # Importance thresholds
    high_importance_threshold: float = 0.7  # Trigger LLM evaluation above this
    low_importance_threshold: float = 0.3   # Consider for demotion below this


class EnergyController:
    """Controls energy dynamics for memory nodes.
    
    Handles:
    - Time-based exponential decay
    - Activation boosts on access
    - Initial energy estimation
    - Batch energy updates
    """
    
    def __init__(self, config: EnergyConfig | None = None):
        self.config = config or EnergyConfig()
        self._running = False
        self._decay_task: asyncio.Task | None = None
        
        # Optional callback for LLM-based importance evaluation
        self._llm_evaluate_callback: Callable[[str], Awaitable[float]] | None = None
    
    def set_llm_evaluate_callback(self, callback: Callable[[str], Awaitable[float]]) -> None:
        """Set callback for LLM-based importance evaluation.
        
        Callback receives content string, returns importance score (0-1).
        """
        self._llm_evaluate_callback = callback
    
    def calculate_decay(self, node: MemoryNode, current_time: float | None = None) -> float:
        """Calculate current energy after decay.
        
        Formula: E = E_last * e^(-λ * Δt)
        
        Args:
            node: Memory node to calculate decay for
            current_time: Current timestamp (defaults to time.time())
        
        Returns:
            New energy value after decay
        """
        if current_time is None:
            current_time = time.time()
        
        delta_t = current_time - node.last_accessed
        
        if delta_t <= 0:
            return node.energy
        
        # Exponential decay
        decayed_energy = node.energy * math.exp(-self.config.decay_lambda * delta_t)
        
        return max(self.config.min_energy, decayed_energy)
    
    def apply_decay(self, node: MemoryNode) -> float:
        """Apply decay to a node and update its energy.
        
        Returns:
            The new energy value
        """
        new_energy = self.calculate_decay(node)
        node.energy = new_energy
        return new_energy
    
    def apply_decay_batch(self, nodes: list[MemoryNode]) -> dict[str, float]:
        """Apply decay to multiple nodes.
        
        Returns:
            Dict of {node_id: new_energy}
        """
        current_time = time.time()
        results = {}
        
        for node in nodes:
            new_energy = self.calculate_decay(node, current_time)
            node.energy = new_energy
            results[node.id] = new_energy
        
        return results
    
    def boost_energy(self, node: MemoryNode, boost: float | None = None) -> float:
        """Boost node energy (e.g., when accessed or reinforced).
        
        Args:
            node: Node to boost
            boost: Custom boost amount (defaults to config.activation_boost)
        
        Returns:
            New energy value
        """
        boost_amount = boost if boost is not None else self.config.activation_boost
        node.energy = min(self.config.max_energy, node.energy + boost_amount)
        node.touch()
        return node.energy
    
    async def estimate_initial_energy(
        self,
        content: str,
        context: str = "",
        explicit_importance: float | None = None
    ) -> float:
        """Estimate initial energy for new content.
        
        Uses hybrid evaluation strategy:
        1. Explicit importance (if provided by user)
        2. Content-based heuristics
        3. LLM evaluation (for high-value content only)
        
        Args:
            content: The content to evaluate
            context: Current task/conversation context
            explicit_importance: User-provided importance (0-1)
        
        Returns:
            Initial energy value (0-1)
        """
        # If explicit importance provided, weight it heavily
        if explicit_importance is not None:
            return max(0.1, min(1.0, explicit_importance))
        
        # Heuristic evaluation
        heuristic_score = self._heuristic_importance(content)
        
        # If score is high enough and LLM callback available, refine with LLM
        if (heuristic_score > self.config.high_importance_threshold 
            and self._llm_evaluate_callback is not None):
            try:
                llm_score = await self._llm_evaluate_callback(content)
                # Blend heuristic and LLM scores
                return 0.4 * heuristic_score + 0.6 * llm_score
            except Exception:
                pass  # Fall back to heuristic
        
        return heuristic_score
    
    def _heuristic_importance(self, content: str) -> float:
        """Calculate importance using simple heuristics.
        
        Factors:
        - Content length (moderate length preferred)
        - Contains entities/proper nouns (capitalized words)
        - Contains numbers/dates
        - Contains action words
        """
        score = 0.5  # Base score
        
        # Length factor (prefer 50-500 chars)
        length = len(content)
        if 50 <= length <= 500:
            score += 0.1
        elif length < 20:
            score -= 0.2
        elif length > 2000:
            score -= 0.1
        
        # Entity density (capitalized words as proxy)
        words = content.split()
        if words:
            capitalized = sum(1 for w in words if w and w[0].isupper())
            entity_ratio = capitalized / len(words)
            if entity_ratio > 0.1:
                score += min(0.2, entity_ratio)
        
        # Contains numbers (often important facts)
        if any(c.isdigit() for c in content):
            score += 0.1
        
        # Contains explicit importance markers
        importance_markers = ["important", "remember", "key", "critical", "must", "always", "never"]
        if any(marker in content.lower() for marker in importance_markers):
            score += 0.15
        
        return max(0.1, min(1.0, score))
    
    def is_alive(self, node: MemoryNode) -> bool:
        """Check if a node has enough energy to be considered active."""
        return node.energy >= self.config.min_energy
    
    def needs_demotion(self, node: MemoryNode) -> bool:
        """Check if a node should be demoted to a lower tier."""
        return node.energy < self.config.low_importance_threshold
    
    def get_decay_info(self, node: MemoryNode) -> dict:
        """Get detailed decay information for a node."""
        current_time = time.time()
        time_since_access = current_time - node.last_accessed
        projected_energy = self.calculate_decay(node, current_time)
        
        # Calculate time until node reaches min_energy
        if node.energy > self.config.min_energy:
            time_to_min = -math.log(self.config.min_energy / node.energy) / self.config.decay_lambda
        else:
            time_to_min = 0
        
        return {
            "current_energy": node.energy,
            "projected_energy": projected_energy,
            "time_since_access": time_since_access,
            "time_to_minimum": time_to_min,
            "is_alive": self.is_alive(node),
            "needs_demotion": self.needs_demotion(node),
        }
    
    async def start_decay_loop(
        self,
        get_nodes_callback: Callable[[], Awaitable[list[MemoryNode]]],
        update_callback: Callable[[dict[str, float]], Awaitable[None]]
    ) -> None:
        """Start background decay loop.
        
        Args:
            get_nodes_callback: Async function that returns nodes to decay
            update_callback: Async function to persist energy updates
        """
        self._running = True
        
        async def decay_loop():
            while self._running:
                try:
                    nodes = await get_nodes_callback()
                    if nodes:
                        updates = self.apply_decay_batch(nodes)
                        await update_callback(updates)
                except Exception as e:
                    # Log but continue
                    print(f"Decay loop error: {e}")
                
                await asyncio.sleep(self.config.decay_interval)
        
        self._decay_task = asyncio.create_task(decay_loop())
    
    async def stop_decay_loop(self) -> None:
        """Stop the background decay loop."""
        self._running = False
        if self._decay_task:
            self._decay_task.cancel()
            try:
                await self._decay_task
            except asyncio.CancelledError:
                pass
            self._decay_task = None
