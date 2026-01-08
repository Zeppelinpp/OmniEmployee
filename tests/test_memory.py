"""Tests for the BIEM memory system.

These tests validate the core functionality without requiring
external services (Milvus, PostgreSQL).
"""

import pytest
import asyncio
import time

from src.omniemployee.memory.models import (
    MemoryNode,
    MemoryMetadata,
    Link,
    LinkType,
    ConflictNode,
    CrystalFact,
)
from src.omniemployee.memory.storage.l1_working import L1WorkingMemory, L1Config
from src.omniemployee.memory.storage.l2_graph import L2GraphStorage, GraphConfig
from src.omniemployee.memory.operators.energy import EnergyController, EnergyConfig
from src.omniemployee.memory.operators.encoder import Encoder, EncoderConfig
from src.omniemployee.memory.operators.conflict import ConflictChecker, ConflictConfig


class TestMemoryNode:
    """Tests for MemoryNode model."""
    
    def test_create_node(self):
        """Test basic node creation."""
        node = MemoryNode(
            content="Test content",
            energy=0.8
        )
        
        assert node.content == "Test content"
        assert node.energy == 0.8
        assert node.tier == "L1"
        assert node.id is not None
    
    def test_node_serialization(self):
        """Test node serialization/deserialization."""
        node = MemoryNode(
            content="Test content",
            vector=[0.1, 0.2, 0.3],
            energy=0.75,
            metadata=MemoryMetadata(
                entities=["Entity1", "Entity2"],
                sentiment=0.5
            )
        )
        
        # Serialize
        data = node.to_dict()
        assert data["content"] == "Test content"
        assert data["energy"] == 0.75
        
        # Deserialize
        restored = MemoryNode.from_dict(data)
        assert restored.content == node.content
        assert restored.vector == node.vector
        assert restored.metadata.entities == node.metadata.entities
    
    def test_node_json(self):
        """Test JSON serialization."""
        node = MemoryNode(content="JSON test")
        
        json_str = node.to_json()
        restored = MemoryNode.from_json(json_str)
        
        assert restored.content == node.content
        assert restored.id == node.id
    
    def test_node_touch(self):
        """Test touch updates last_accessed."""
        node = MemoryNode(content="Touch test")
        original_time = node.last_accessed
        
        time.sleep(0.01)
        node.touch()
        
        assert node.last_accessed > original_time


class TestLink:
    """Tests for Link model."""
    
    def test_create_link(self):
        """Test basic link creation."""
        link = Link(
            source_id="node1",
            target_id="node2",
            link_type=LinkType.TEMPORAL,
            weight=0.9
        )
        
        assert link.source_id == "node1"
        assert link.target_id == "node2"
        assert link.link_type == LinkType.TEMPORAL
        assert link.weight == 0.9
    
    def test_link_serialization(self):
        """Test link serialization."""
        link = Link(
            source_id="a",
            target_id="b",
            link_type=LinkType.SEMANTIC,
            weight=0.5
        )
        
        data = link.to_dict()
        restored = Link.from_dict(data)
        
        assert restored.source_id == link.source_id
        assert restored.link_type == link.link_type
    
    def test_link_equality(self):
        """Test link equality based on source, target, type."""
        link1 = Link("a", "b", LinkType.TEMPORAL)
        link2 = Link("a", "b", LinkType.TEMPORAL)
        link3 = Link("a", "b", LinkType.SEMANTIC)
        
        assert link1 == link2
        assert link1 != link3


class TestL1WorkingMemory:
    """Tests for L1 working memory."""
    
    @pytest.fixture
    def l1(self):
        config = L1Config(max_nodes=5, min_energy=0.1)
        return L1WorkingMemory(config)
    
    @pytest.mark.asyncio
    async def test_put_and_get(self, l1):
        """Test basic put/get operations."""
        await l1.connect()
        
        node = MemoryNode(content="Test", energy=0.8)
        await l1.put(node)
        
        retrieved = await l1.get(node.id)
        assert retrieved is not None
        assert retrieved.content == "Test"
        
        await l1.disconnect()
    
    @pytest.mark.asyncio
    async def test_capacity_eviction(self, l1):
        """Test eviction when capacity exceeded."""
        await l1.connect()
        
        # Add more nodes than capacity
        for i in range(7):
            node = MemoryNode(content=f"Node {i}", energy=0.1 * (i + 1))
            await l1.put(node)
        
        # Should have evicted lowest energy nodes
        count = await l1.count()
        assert count <= 5
        
        await l1.disconnect()
    
    @pytest.mark.asyncio
    async def test_top_k(self, l1):
        """Test getting top K highest energy nodes."""
        await l1.connect()
        
        for i in range(5):
            node = MemoryNode(content=f"Node {i}", energy=0.2 * (i + 1))
            await l1.put(node)
        
        top = await l1.get_top_k(3)
        assert len(top) == 3
        
        # Should be sorted by energy descending
        energies = [n.energy for n in top]
        assert energies == sorted(energies, reverse=True)
        
        await l1.disconnect()
    
    @pytest.mark.asyncio
    async def test_energy_update(self, l1):
        """Test energy update."""
        await l1.connect()
        
        node = MemoryNode(content="Test", energy=0.5)
        await l1.put(node)
        
        await l1.update_energy(node.id, 0.9)
        retrieved = await l1.get(node.id)
        
        assert retrieved.energy == 0.9
        
        await l1.disconnect()


class TestL2GraphStorage:
    """Tests for L2 graph storage."""
    
    @pytest.fixture
    def graph(self):
        config = GraphConfig(persist_path=None, auto_save=False)
        return L2GraphStorage(config)
    
    @pytest.mark.asyncio
    async def test_add_link(self, graph):
        """Test adding links."""
        await graph.connect()
        
        link = Link("node1", "node2", LinkType.TEMPORAL, weight=0.8)
        await graph.add_link(link)
        
        neighbors = await graph.get_neighbors("node1", direction="out")
        assert len(neighbors) == 1
        assert neighbors[0][0] == "node2"
        
        await graph.disconnect()
    
    @pytest.mark.asyncio
    async def test_spreading_activation(self, graph):
        """Test spreading activation."""
        await graph.connect()
        
        # Create a chain: A -> B -> C
        await graph.add_link(Link("A", "B", LinkType.SEMANTIC, weight=1.0))
        await graph.add_link(Link("B", "C", LinkType.SEMANTIC, weight=1.0))
        
        # Activate from A
        activation = await graph.spread_activation(["A"], max_hops=2, decay_factor=0.5)
        
        assert "A" in activation
        assert "B" in activation
        assert "C" in activation
        
        # B should have higher activation than C (closer to source)
        assert activation["B"] > activation["C"]
        
        await graph.disconnect()
    
    @pytest.mark.asyncio
    async def test_strengthen_link(self, graph):
        """Test link strengthening."""
        await graph.connect()
        
        link = Link("A", "B", LinkType.SEMANTIC, weight=0.5)
        await graph.add_link(link)
        
        await graph.strengthen_link("A", "B", boost=0.2)
        
        links = await graph.get_links("A")
        assert links[0].weight == 0.7
        
        await graph.disconnect()


class TestEnergyController:
    """Tests for energy controller."""
    
    @pytest.fixture
    def controller(self):
        config = EnergyConfig(
            decay_lambda=0.01,
            min_energy=0.01,
            activation_boost=0.1
        )
        return EnergyController(config)
    
    def test_decay_calculation(self, controller):
        """Test energy decay calculation."""
        node = MemoryNode(content="Test", energy=1.0)
        node.last_accessed = time.time() - 100  # 100 seconds ago
        
        decayed = controller.calculate_decay(node)
        
        # Should have decayed
        assert decayed < 1.0
        assert decayed > 0.0
    
    def test_boost_energy(self, controller):
        """Test energy boost."""
        node = MemoryNode(content="Test", energy=0.5)
        
        new_energy = controller.boost_energy(node)
        
        assert new_energy == 0.6  # 0.5 + 0.1 boost
        assert node.energy == 0.6
    
    def test_boost_capped_at_max(self, controller):
        """Test energy boost is capped at 1.0."""
        node = MemoryNode(content="Test", energy=0.95)
        
        new_energy = controller.boost_energy(node)
        
        assert new_energy == 1.0
    
    def test_is_alive(self, controller):
        """Test alive check."""
        alive_node = MemoryNode(content="Alive", energy=0.5)
        dead_node = MemoryNode(content="Dead", energy=0.001)
        
        assert controller.is_alive(alive_node) is True
        assert controller.is_alive(dead_node) is False
    
    @pytest.mark.asyncio
    async def test_heuristic_importance(self, controller):
        """Test heuristic importance estimation."""
        # High importance content
        high = await controller.estimate_initial_energy(
            "Important: Remember that John Smith is the CEO of Acme Corp",
        )
        
        # Low importance content
        low = await controller.estimate_initial_energy(
            "ok",
        )
        
        assert high > low


class TestEncoder:
    """Tests for the encoder module."""
    
    @pytest.fixture
    def encoder(self):
        # Use config that doesn't require spaCy or sentence-transformers
        config = EncoderConfig(use_spacy=False)
        return Encoder(config)
    
    @pytest.mark.asyncio
    async def test_entity_extraction_regex(self, encoder):
        """Test regex-based entity extraction."""
        entities = await encoder.extract_entities(
            "John Smith works at Google in San Francisco. Contact: john@example.com"
        )
        
        # Should find capitalized phrases and email
        assert "John Smith" in entities or "John" in entities
        assert "Google" in entities
        assert "john@example.com" in entities
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis(self, encoder):
        """Test sentiment analysis."""
        positive = await encoder.analyze_sentiment(
            "This is great! I love the excellent results."
        )
        negative = await encoder.analyze_sentiment(
            "This is terrible. The worst failure ever."
        )
        neutral = await encoder.analyze_sentiment(
            "The meeting is scheduled for tomorrow."
        )
        
        assert positive > 0
        assert negative < 0
        assert abs(neutral) < abs(positive)


class TestConflictChecker:
    """Tests for conflict detection."""
    
    @pytest.fixture
    def checker(self):
        config = ConflictConfig(
            similarity_threshold=0.7,
            polarity_threshold=0.5
        )
        return ConflictChecker(config)
    
    @pytest.mark.asyncio
    async def test_heuristic_conflict_detection(self, checker):
        """Test heuristic-based conflict detection."""
        node_a = MemoryNode(
            content="The feature is enabled by default",
            vector=[0.1] * 10,
            metadata=MemoryMetadata(sentiment=0.3)
        )
        node_b = MemoryNode(
            content="The feature is disabled by default",
            vector=[0.1] * 10,
            metadata=MemoryMetadata(sentiment=-0.3)
        )
        
        # Should detect conflict based on negation pattern
        result = checker._heuristic_conflict_check(node_a, node_b)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_no_conflict_similar_content(self, checker):
        """Test no conflict for similar non-contradicting content."""
        node_a = MemoryNode(
            content="The user prefers dark mode",
            vector=[0.1] * 10,
            metadata=MemoryMetadata(sentiment=0.2)
        )
        node_b = MemoryNode(
            content="Dark mode is the user's preference",
            vector=[0.1] * 10,
            metadata=MemoryMetadata(sentiment=0.2)
        )
        
        result = checker._heuristic_conflict_check(node_a, node_b)
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
