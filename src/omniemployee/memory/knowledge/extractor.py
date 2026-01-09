"""LLM-driven Knowledge Extractor.

Extracts structured knowledge triples from conversations using LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.omniemployee.memory.knowledge.models import (
    KnowledgeTriple,
    KnowledgeIntent,
    KnowledgeSource,
    ExtractionResult,
)


# Extraction prompt template
# Note: Use double braces {{}} to escape JSON in f-string/format
EXTRACTION_PROMPT = """You are a knowledge extraction system. Your task is to extract **ONLY objective, generalizable knowledge** from conversations - knowledge that would be useful for anyone, not specific to any individual user.

## Task
1. First, classify the content:
   - **User-specific information**: Name, age, birthday, location, job, personal preferences, opinions → DO NOT EXTRACT
   - **Objective knowledge**: Facts about entities, technical information, processes, workflows, domain knowledge → EXTRACT
2. If it contains objective knowledge, extract as triples: (subject, predicate, object)
3. Each triple should represent reusable knowledge that could benefit any conversation

## What to EXTRACT (Objective Knowledge)
- Technical facts about tools, languages, frameworks (e.g., "Python was created by Guido van Rossum")
- Process/workflow knowledge (e.g., "CI/CD pipelines typically include testing and deployment stages")
- Domain facts (e.g., "Machine learning models require training data")
- API/tool capabilities (e.g., "GPT-4 has 128k context window")
- Best practices and patterns (e.g., "RESTful APIs use HTTP methods for CRUD operations")
- Causal relationships (e.g., "Memory leaks can cause application crashes")

## What NOT to EXTRACT (User-Specific)
- Personal identifiers: name, age, birthday, phone, email, address
- Personal preferences: "I prefer...", "My favorite..."
- Current state: "I'm working on...", "I live in..."
- Opinions: "I think...", "I believe..."
- Questions: "What is...?", "How do I...?"

## Examples

Input: "My name is John and I'm 25 years old"
Output:
```json
{{
  "is_factual": false,
  "intent": "statement",
  "triples": [],
  "reasoning": "Personal user information - not generalizable knowledge"
}}
```

Input: "I prefer using Vim as my editor"
Output:
```json
{{
  "is_factual": false,
  "intent": "statement",
  "triples": [],
  "reasoning": "Personal preference - belongs in user memory, not knowledge base"
}}
```

Input: "Claude 3.5 Sonnet has a context window of 200k tokens"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "Claude 3.5 Sonnet", "predicate": "context_window", "object": "200k tokens"}}
  ],
  "confidence": 0.95,
  "reasoning": "Technical fact about an AI model - useful for anyone"
}}
```

Input: "Actually, GPT-4 now supports 128k context, not 32k"
Output:
```json
{{
  "is_factual": true,
  "intent": "correction",
  "triples": [
    {{"subject": "GPT-4", "predicate": "context_window", "object": "128k"}}
  ],
  "confidence": 0.9,
  "reasoning": "Correction of technical fact"
}}
```

Input: "Python was created by Guido van Rossum and released in 1991"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "Python", "predicate": "created_by", "object": "Guido van Rossum"}},
    {{"subject": "Python", "predicate": "release_year", "object": "1991"}}
  ],
  "confidence": 0.95,
  "reasoning": "Historical facts about a programming language"
}}
```

Input: "To deploy a Docker container, you first build the image with docker build, then run it with docker run"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "Docker container deployment", "predicate": "step_1", "object": "build image with docker build"}},
    {{"subject": "Docker container deployment", "predicate": "step_2", "object": "run with docker run"}}
  ],
  "confidence": 0.9,
  "reasoning": "Process knowledge about Docker workflow"
}}
```

Input: "Memory leaks in Python often occur when circular references prevent garbage collection"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "Python memory leak", "predicate": "common_cause", "object": "circular references"}},
    {{"subject": "circular references", "predicate": "effect", "object": "prevent garbage collection"}}
  ],
  "confidence": 0.85,
  "reasoning": "Technical knowledge about Python memory management"
}}
```

Input: "I think Python is the best language"
Output:
```json
{{
  "is_factual": false,
  "intent": "opinion",
  "triples": [],
  "reasoning": "Subjective opinion, not objective knowledge"
}}
```

## Guidelines
- **Subject**: The main entity, concept, or process (NEVER use "user")
- **Predicate**: The relationship in snake_case (e.g., "created_by", "has_feature", "requires", "step_n")
- **Object**: The value, related entity, or outcome
- **Confidence**: 0.9+ for well-known facts, 0.7-0.9 for domain knowledge, < 0.7 for uncertain claims
- Knowledge should be **abstractions or summaries** that could form a knowledge graph
- Think: "Would this triple be useful to anyone asking about this topic?"

## Message to Analyze
{message}

## Response
Respond with ONLY valid JSON, no additional text:"""


@dataclass
class ExtractorConfig:
    """Configuration for knowledge extraction."""
    min_confidence: float = 0.7    # Minimum confidence to accept extraction (higher for stricter)
    extract_from_agent: bool = True  # Extract from agent messages (search results, explanations)
    max_triples_per_message: int = 5  # Limit triples per message
    strict_mode: bool = True  # Filter out user-specific info


# Predicates that indicate user-specific information (should NOT be stored in global knowledge)
USER_SPECIFIC_PREDICATES = frozenset({
    "name", "age", "birthday", "birth_date", "location", "address", "city", "country",
    "email", "phone", "phone_number", "job", "workplace", "employer", "occupation",
    "preference", "ui_preference", "editor", "favorite", "likes", "dislikes",
    "hobby", "hobbies", "interest", "interests", "goal", "goals",
    "project", "current_project", "working_on",
})


class KnowledgeExtractor:
    """LLM-driven knowledge triple extractor.
    
    Uses LLM to identify factual statements in conversations and extract
    structured (subject, predicate, object) triples.
    """
    
    def __init__(
        self,
        llm_provider: Any = None,  # LLMProvider instance
        config: ExtractorConfig | None = None,
    ):
        self._llm = llm_provider
        self.config = config or ExtractorConfig()
        self._initialized = False
    
    async def initialize(self, llm_provider: Any = None) -> None:
        """Initialize with LLM provider."""
        if llm_provider:
            self._llm = llm_provider
        self._initialized = self._llm is not None
    
    def is_available(self) -> bool:
        """Check if extractor is available."""
        return self._initialized and self._llm is not None
    
    async def extract(
        self,
        message: str,
        session_id: str = "",
        user_id: str = "",
        role: str = "user",
    ) -> ExtractionResult:
        """Extract knowledge triples from a message.
        
        Args:
            message: The message to analyze
            session_id: Current session identifier
            user_id: Current user identifier (for attribution)
            role: "user" or "assistant" - determines knowledge source
            
        Returns:
            ExtractionResult with extracted triples
        """
        if not self.is_available():
            return ExtractionResult(
                is_factual=False,
                raw_message=message,
            )
        
        # Skip very short messages
        if len(message.strip()) < 10:
            return ExtractionResult(
                is_factual=False,
                raw_message=message,
            )
        
        # Skip agent messages if not configured
        if role == "assistant" and not self.config.extract_from_agent:
            return ExtractionResult(is_factual=False, raw_message=message)
        
        # Call LLM for extraction
        prompt = EXTRACTION_PROMPT.format(message=message)
        
        try:
            response = await self._llm.complete(
                messages=[{"role": "user", "content": prompt}]
            )
            
            if not response.content:
                return ExtractionResult(is_factual=False, raw_message=message)
            
            # Parse JSON response
            result = self._parse_llm_response(response.content, message)
            
            # Add metadata to triples
            for triple in result.triples:
                triple.session_id = session_id
                triple.user_id = user_id  # Who contributed (for attribution)
                
                # Set source based on role and intent
                if role == "assistant":
                    # Agent-provided knowledge
                    if self._is_search_result(message):
                        triple.source = KnowledgeSource.AGENT_SEARCH
                    else:
                        triple.source = KnowledgeSource.AGENT_SUMMARY
                elif result.intent == KnowledgeIntent.CORRECTION:
                    triple.source = KnowledgeSource.USER_CORRECTION
                else:
                    triple.source = KnowledgeSource.USER_STATED
            
            return result
            
        except Exception as e:
            print(f"[Knowledge] Extraction error: {e}")
            return ExtractionResult(is_factual=False, raw_message=message)
    
    def _is_search_result(self, message: str) -> bool:
        """Detect if message contains search/external data results."""
        search_indicators = [
            "根据搜索", "搜索结果", "查询结果", "search result",
            "according to", "based on my search", "I found that",
            "官方文档", "documentation", "wikipedia", "官网",
            "来源:", "source:", "参考:", "reference:",
        ]
        msg_lower = message.lower()
        return any(ind.lower() in msg_lower for ind in search_indicators)
    
    def _parse_llm_response(self, response: str, original_message: str) -> ExtractionResult:
        """Parse LLM JSON response into ExtractionResult."""
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_str = response.strip()
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return ExtractionResult(is_factual=False, raw_message=original_message)
        
        # Parse intent
        intent_str = data.get("intent", "statement").lower()
        try:
            intent = KnowledgeIntent(intent_str)
        except ValueError:
            intent = KnowledgeIntent.STATEMENT
        
        # Parse triples with strict filtering
        triples = []
        for t in data.get("triples", [])[:self.config.max_triples_per_message]:
            if t.get("subject") and t.get("predicate") and t.get("object"):
                subject = str(t["subject"]).strip()
                predicate = self._normalize_predicate(str(t["predicate"]))
                obj = str(t["object"]).strip()
                
                # Strict mode: filter out user-specific info
                if self.config.strict_mode:
                    # Skip if subject is "user" (personal info)
                    if subject.lower() == "user":
                        continue
                    # Skip if predicate indicates personal info
                    if predicate in USER_SPECIFIC_PREDICATES:
                        continue
                
                triple = KnowledgeTriple(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    confidence=data.get("confidence", 0.8),
                )
                triples.append(triple)
        
        confidence = data.get("confidence", 0.0)
        
        # Filter by minimum confidence
        if confidence < self.config.min_confidence:
            return ExtractionResult(
                is_factual=False,
                raw_message=original_message,
            )
        
        # If no valid triples after filtering, mark as not factual
        if not triples:
            return ExtractionResult(
                is_factual=False,
                raw_message=original_message,
            )
        
        return ExtractionResult(
            is_factual=data.get("is_factual", False),
            intent=intent,
            triples=triples,
            confidence=confidence,
            raw_message=original_message,
        )
    
    def _normalize_predicate(self, predicate: str) -> str:
        """Normalize predicate to snake_case."""
        # Convert to lowercase
        pred = predicate.lower().strip()
        # Replace spaces and hyphens with underscores
        pred = re.sub(r'[\s\-]+', '_', pred)
        # Remove non-alphanumeric except underscores
        pred = re.sub(r'[^a-z0-9_]', '', pred)
        return pred
    
    async def batch_extract(
        self,
        messages: list[str],
        session_id: str = "",
        user_id: str = "",
        role: str = "user",
    ) -> list[ExtractionResult]:
        """Extract knowledge from multiple messages.
        
        Args:
            messages: List of messages to analyze
            session_id: Current session identifier
            user_id: Current user identifier
            role: "user" or "assistant"
            
        Returns:
            List of ExtractionResult for each message
        """
        results = []
        for msg in messages:
            result = await self.extract(msg, session_id, user_id, role)
            results.append(result)
        return results
