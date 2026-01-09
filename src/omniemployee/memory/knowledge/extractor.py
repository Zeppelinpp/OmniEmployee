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
EXTRACTION_PROMPT = """You are a knowledge extraction system. Analyze the following message and extract structured knowledge.

## Task
1. Determine if the message contains factual information (including personal information, preferences, or objective facts)
2. If factual, extract knowledge as triples: (subject, predicate, object)
3. Identify the intent: statement, correction, question, or opinion

## Examples

Input: "我叫蒲睿" / "My name is John"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "user", "predicate": "name", "object": "蒲睿"}}
  ],
  "confidence": 1.0
}}
```

Input: "I live in Beijing and work at Google"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "user", "predicate": "location", "object": "Beijing"}},
    {{"subject": "user", "predicate": "workplace", "object": "Google"}}
  ],
  "confidence": 0.95
}}
```

Input: "I prefer dark mode and use Vim as my editor"
Output:
```json
{{
  "is_factual": true,
  "intent": "statement",
  "triples": [
    {{"subject": "user", "predicate": "ui_preference", "object": "dark mode"}},
    {{"subject": "user", "predicate": "editor", "object": "Vim"}}
  ],
  "confidence": 0.9
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
  "confidence": 0.95
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
  "confidence": 0.9
}}
```

Input: "I think Python is the best language"
Output:
```json
{{
  "is_factual": false,
  "intent": "opinion",
  "triples": [],
  "confidence": 0.8
}}
```

Input: "What's the latest version of React?"
Output:
```json
{{
  "is_factual": false,
  "intent": "question",
  "triples": [],
  "confidence": 0.9
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
  "confidence": 0.95
}}
```

## Guidelines
- subject: The main entity. Use "user" for personal information about the current user.
- predicate: The relationship or attribute (use snake_case, e.g., "name", "location", "workplace", "preference")
- object: The value or target entity
- Extract personal information the user shares about themselves (name, location, job, preferences, etc.)
- Extract technical facts and domain knowledge
- Correction intent indicates the user is correcting previous information
- Set confidence based on how clear and unambiguous the statement is (personal info = 1.0)

## Message to Analyze
{message}

## Response
Respond with ONLY valid JSON, no additional text:"""


@dataclass
class ExtractorConfig:
    """Configuration for knowledge extraction."""
    min_confidence: float = 0.5    # Minimum confidence to accept extraction
    extract_from_agent: bool = False  # Also extract from agent messages
    max_triples_per_message: int = 5  # Limit triples per message


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
    ) -> ExtractionResult:
        """Extract knowledge triples from a message.
        
        Args:
            message: The message to analyze
            session_id: Current session identifier
            user_id: Current user identifier
            
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
                triple.user_id = user_id
                
                # Set source based on intent
                if result.intent == KnowledgeIntent.CORRECTION:
                    triple.source = KnowledgeSource.USER_CORRECTION
                else:
                    triple.source = KnowledgeSource.USER_STATED
            
            return result
            
        except Exception as e:
            print(f"[Knowledge] Extraction error: {e}")
            return ExtractionResult(is_factual=False, raw_message=message)
    
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
        
        # Parse triples
        triples = []
        for t in data.get("triples", [])[:self.config.max_triples_per_message]:
            if t.get("subject") and t.get("predicate") and t.get("object"):
                triple = KnowledgeTriple(
                    subject=str(t["subject"]).strip(),
                    predicate=self._normalize_predicate(str(t["predicate"])),
                    object=str(t["object"]).strip(),
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
    ) -> list[ExtractionResult]:
        """Extract knowledge from multiple messages.
        
        Args:
            messages: List of messages to analyze
            session_id: Current session identifier
            user_id: Current user identifier
            
        Returns:
            List of ExtractionResult for each message
        """
        results = []
        for msg in messages:
            result = await self.extract(msg, session_id, user_id)
            results.append(result)
        return results
