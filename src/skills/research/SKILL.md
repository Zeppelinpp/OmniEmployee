---
name: research
description: Research methodology skill that guides systematic investigation, information gathering, validation, and synthesis for any topic. Provides frameworks for academic research, market analysis, technical exploration, and evidence-based decision making.
---

# Research Methodology Guide

## Overview

This skill provides a systematic approach to conducting research. It covers information gathering strategies, source validation, synthesis techniques, and practical experimentation methods.

## Standard Operating Procedure

### Step 1: Define Research Scope

Before starting any research, clearly define:

| Element | Questions to Answer |
|---------|---------------------|
| **Objective** | What specific question are you trying to answer? |
| **Scope** | What's in/out of scope? Time period? Geographic focus? |
| **Output** | What deliverable is expected? Report? Decision? Code? |
| **Constraints** | Time limit? Budget? Access restrictions? |

**Important**: Always confirm the research objective with the user before proceeding. Vague requests like "research AI" should be clarified.

### Step 2: Plan Information Channels

Different research questions require different information sources:

| Research Type | Primary Channels | Secondary Channels |
|---------------|------------------|-------------------|
| **Technical/Engineering** | Official docs, GitHub, Stack Overflow | Blogs, tutorials, benchmarks |
| **Academic/Scientific** | arXiv, Google Scholar, journals | Conference proceedings, preprints |
| **Market/Business** | Industry reports, company filings | News, analyst opinions |
| **Current Events** | News aggregators, official sources | Social media, expert commentary |
| **Product/Tool Evaluation** | Official sites, user reviews | Comparison sites, forums |

Use the web search tool:

```python
# Academic research
web_search(query="transformer attention mechanism arxiv")

# Technical documentation  
web_search(query="React Server Components site:react.dev")

# Market research (more comprehensive)
web_search(query="AI market size 2024", search_depth="advanced")

# Get detailed content from a specific URL
web_extract(url="https://arxiv.org/abs/2502.08346")
```

### Step 3: Execute Search Strategy

Follow the **Breadth-First, Depth-Second** approach:

**Phase 1: Breadth (Discovery)**
- Cast a wide net with general queries
- Identify key themes, terminology, and authoritative sources
- Note recurring names, organizations, and references

```python
# Start broad
web_search(query="large language model training techniques 2024", max_results=10)
```

**Phase 2: Depth (Deep Dive)**
- Focus on specific subtopics identified in Phase 1
- Use domain-specific queries
- Cross-reference multiple sources

```python
# Go deep on specific topics
web_search(query="RLHF vs DPO training comparison arxiv", search_depth="advanced")

# Extract full content from promising URLs
web_extract(url="https://arxiv.org/abs/2310.xxxxx")
```

### Step 4: Validate Information

Apply the **CRAAP Test** to evaluate sources:

| Criterion | Questions |
|-----------|-----------|
| **Currency** | When was it published? Is it up-to-date for your topic? |
| **Relevance** | Does it directly address your research question? |
| **Authority** | Who is the author? What are their credentials? |
| **Accuracy** | Is it supported by evidence? Can you verify claims? |
| **Purpose** | Why was it created? Is there bias? |

**Validation Scripts:**

```bash
# Check if a claim appears in multiple authoritative sources
uv run scripts/validate_claim.py --claim "GPT-4 has 1.8 trillion parameters" --min_sources 3

# Compare information across sources
uv run scripts/compare_sources.py --topic "quantum computing timeline" --sources "ibm,google,nature"
```

### Step 5: Synthesize Findings

Organize research findings using these frameworks:

**For Comparisons:**
```markdown
| Aspect | Option A | Option B | Winner |
|--------|----------|----------|--------|
| Performance | ... | ... | ... |
| Cost | ... | ... | ... |
| Ease of use | ... | ... | ... |
```

**For Trend Analysis:**
```markdown
## Timeline
- 2022: [Event/Development]
- 2023: [Event/Development]
- 2024: [Event/Development]

## Key Insights
1. ...
2. ...
```

**For Technical Evaluation:**
```markdown
## Pros
- ...

## Cons
- ...

## Recommendation
Based on [criteria], recommend [choice] because [reasons].
```

### Step 6: Practical Validation (When Applicable)

For technical research, validate findings through experimentation:

```bash
# Create a test script to verify claims
uv run scripts/create_experiment.py --hypothesis "FastAPI is faster than Flask" --output test_benchmark.py

# Run the experiment
uv run test_benchmark.py
```

## Quick Reference

| Task | Tool/Script | Usage |
|------|-------------|-------|
| Web search | `web_search` | `web_search(query="...", search_depth="advanced")` |
| Validate claim | `validate_claim.py` | `uv run scripts/validate_claim.py --claim "..."` |
| Compare sources | `compare_sources.py` | `uv run scripts/compare_sources.py --topic "..."` |
| Create experiment | `create_experiment.py` | `uv run scripts/create_experiment.py --hypothesis "..."` |
| Summarize findings | `summarize_research.py` | `uv run scripts/summarize_research.py --notes "..."` |

## Research Best Practices

1. **Start with known authoritative sources** - Don't rely solely on general web search
2. **Document as you go** - Keep track of sources and key findings
3. **Triangulate information** - Verify claims across multiple independent sources
4. **Be aware of recency** - Tech information can become outdated quickly
5. **Distinguish fact from opinion** - Clearly separate verified facts from interpretations

## Error Handling

**IMPORTANT**: When you encounter issues (e.g., "No results found", "Conflicting information", "Outdated sources"), load the reference document for detailed solutions:

```
load_skill_reference("research", "reference.md")
```

The reference document contains:
- **Search Query Optimization** - How to refine queries for better results
- **Source Evaluation Checklist** - Detailed criteria for assessing reliability
- **Conflict Resolution** - How to handle contradictory information
- **Domain-Specific Strategies** - Tailored approaches for different research types

## Additional Resources

For detailed information on advanced search techniques, source evaluation, synthesis methods, and experimentation frameworks, load [reference.md](./reference.md) using `load_skill_reference`.

Contents include:
- **Advanced Search Techniques** - Boolean operators, site-specific searches, date filtering
- **Source Hierarchy** - Ranking sources by reliability for different domains
- **Synthesis Templates** - Ready-to-use formats for different research outputs
- **Experimentation Guide** - How to design and execute validation experiments
- **Common Pitfalls** - Mistakes to avoid in research

