# Memory Conflict Verification Prompt

Analyze whether these two memory statements contain conflicting information.

Statement A (existing):
{content_a}

Statement B (new):
{content_b}

Determine if they:
1. Contradict each other (opposing facts)
2. One updates/supersedes the other
3. One refines/adds detail to the other
4. No conflict (compatible information)

Respond in JSON format:
```json
{
    "is_conflict": true/false,
    "conflict_type": "contradiction" | "update" | "refinement" | "none",
    "description": "Brief explanation of the conflict or compatibility",
    "confidence": 0.0-1.0
}
```
