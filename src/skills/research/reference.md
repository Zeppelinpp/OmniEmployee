# Research Reference

This document contains supplementary information for the research skill, including advanced search techniques, source evaluation criteria, synthesis templates, and experimentation frameworks.

## Advanced Search Techniques

### Query Optimization

#### Boolean Operators

Use these operators to refine search queries:

| Operator | Usage | Example |
|----------|-------|---------|
| `AND` | Both terms must appear | `machine learning AND healthcare` |
| `OR` | Either term can appear | `GPT-4 OR Claude` |
| `NOT` / `-` | Exclude term | `python framework -django` |
| `"..."` | Exact phrase | `"attention is all you need"` |
| `site:` | Specific domain | `site:arxiv.org transformer` |

#### Effective Query Patterns

```bash
# Find comparisons
web_search(query="X vs Y comparison 2024")

# Find tutorials/guides
web_search(query="how to implement X step by step")

# Find recent developments
web_search(query="X latest updates 2024")

# Find expert opinions
web_search(query="X expert analysis review")

# Find problems/issues
web_search(query="X common problems issues limitations")
```

### Domain-Specific Search Strategies

#### Academic Research

```python
# Find papers on a topic (use site: operator in query)
web_search(query="attention mechanism neural networks survey site:arxiv.org")

# Find citations and related work
web_search(query="papers citing 'Attention Is All You Need'", search_depth="advanced")

# Find code implementations
web_search(query="transformer implementation github stars:>1000 site:github.com")

# Extract full paper content
web_extract(url="https://arxiv.org/abs/1706.03762")
```

#### Technical Documentation

```python
# Official documentation
web_search(query="React useEffect cleanup function site:react.dev")

# Stack Overflow solutions
web_search(query="Python async await best practices site:stackoverflow.com")

# GitHub discussions
web_search(query="Next.js app router migration issues site:github.com")

# Read specific documentation page
web_extract(url="https://react.dev/reference/react/useEffect")
```

#### Market Research

```python
# Industry reports
web_search(query="AI market size forecast 2025 gartner mckinsey", search_depth="advanced")

# Company information
web_search(query="OpenAI funding valuation 2024")

# Competitive analysis
web_search(query="cloud providers comparison AWS Azure GCP 2024", search_depth="advanced")

# Extract detailed report
web_extract(url="https://example.com/industry-report", extract_depth="advanced")
```

---

## Source Evaluation

### Source Hierarchy by Domain

#### Technical/Engineering

| Tier | Source Type | Examples | Trust Level |
|------|-------------|----------|-------------|
| 1 | Official Documentation | React docs, Python docs | Very High |
| 2 | Authoritative Blogs | Official engineering blogs | High |
| 3 | Community Resources | Stack Overflow (high votes) | Medium-High |
| 4 | Tutorial Sites | Medium, Dev.to | Medium |
| 5 | Personal Blogs | Individual developers | Verify |

#### Academic/Scientific

| Tier | Source Type | Examples | Trust Level |
|------|-------------|----------|-------------|
| 1 | Peer-Reviewed Journals | Nature, Science, ACL | Very High |
| 2 | Conference Proceedings | NeurIPS, ICML, ACL | High |
| 3 | Preprints | arXiv, bioRxiv | Medium-High (verify) |
| 4 | Technical Reports | Company research blogs | Medium |
| 5 | News Coverage | Tech news sites | Low (verify claims) |

#### Business/Market

| Tier | Source Type | Examples | Trust Level |
|------|-------------|----------|-------------|
| 1 | Official Filings | SEC filings, annual reports | Very High |
| 2 | Research Firms | Gartner, Forrester | High |
| 3 | Industry Publications | TechCrunch, Wired | Medium |
| 4 | Analyst Opinions | Blog posts, podcasts | Low (opinion) |
| 5 | Social Media | Twitter, LinkedIn | Very Low |

### Detailed CRAAP Evaluation

#### Currency Checklist

- [ ] When was the information published or last updated?
- [ ] Is this topic time-sensitive? (Tech: very; History: less so)
- [ ] Are the links functional?
- [ ] Is newer information available that supersedes this?

**Red Flags:**
- No publication date
- References to outdated versions/tools
- Broken links to sources

#### Relevance Checklist

- [ ] Does this directly answer your research question?
- [ ] Is the depth appropriate (too basic/too advanced)?
- [ ] Is this the primary source or secondary commentary?
- [ ] Who is the intended audience?

#### Authority Checklist

- [ ] Who is the author/organization?
- [ ] What are their credentials?
- [ ] Are they recognized experts in this field?
- [ ] Is contact information provided?
- [ ] What is the domain? (.edu, .gov, .com)

**Verification Steps:**
```bash
# Check author credentials
web_search(query="[Author Name] credentials expertise")

# Verify organization
web_search(query="[Organization] about reputation")
```

#### Accuracy Checklist

- [ ] Is the information supported by evidence?
- [ ] Can you verify the facts elsewhere?
- [ ] Are sources cited?
- [ ] Is the methodology explained?
- [ ] Has it been peer-reviewed or edited?

#### Purpose Checklist

- [ ] Why was this created? (Inform, sell, persuade, entertain)
- [ ] Is there obvious bias?
- [ ] Is it sponsored content?
- [ ] Does the author have financial interests?

---

## Handling Conflicting Information

### Conflict Resolution Framework

When sources disagree, follow this process:

**Step 1: Identify the Nature of Conflict**

| Conflict Type | Description | Resolution Approach |
|---------------|-------------|---------------------|
| Factual | Different numbers/dates | Find primary source |
| Interpretive | Same facts, different conclusions | Present both views |
| Temporal | Outdated vs current | Use most recent |
| Methodological | Different measurement approaches | Explain differences |

**Step 2: Evaluate Source Quality**

```bash
# Compare source authority
uv run scripts/compare_sources.py --topic "conflict topic" --evaluate_authority
```

**Step 3: Document the Conflict**

```markdown
## Conflicting Information

**Claim**: [The disputed claim]

**Source A** ([URL], [Date]):
- States: [Position A]
- Evidence: [Supporting evidence]
- Authority: [Credentials]

**Source B** ([URL], [Date]):
- States: [Position B]
- Evidence: [Supporting evidence]
- Authority: [Credentials]

**Resolution**: [Your analysis of which is more reliable and why]
```

---

## Synthesis Templates

### Comparison Report Template

```markdown
# [Topic] Comparison Report

## Executive Summary
[2-3 sentence overview of findings and recommendation]

## Comparison Matrix

| Criterion | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| [Criterion 1] | ✓/✗/~ | ✓/✗/~ | ✓/✗/~ |
| [Criterion 2] | ... | ... | ... |
| [Criterion 3] | ... | ... | ... |

## Detailed Analysis

### [Option A]
**Strengths:**
- ...

**Weaknesses:**
- ...

**Best For:** [Use case]

### [Option B]
...

## Recommendation

Based on [criteria], we recommend **[Option]** because:
1. [Reason 1]
2. [Reason 2]
3. [Reason 3]

## Sources
- [Source 1]
- [Source 2]
```

### Technical Evaluation Template

```markdown
# [Technology/Tool] Evaluation

## Overview
- **What it is**: [Brief description]
- **Primary use case**: [Main purpose]
- **Alternatives**: [Competing solutions]

## Technical Assessment

### Architecture
[How it works]

### Performance
| Metric | Value | Benchmark |
|--------|-------|-----------|
| [Metric 1] | [Value] | [vs alternatives] |

### Integration
- **Ease of setup**: [Rating]
- **Documentation quality**: [Rating]
- **Community support**: [Rating]

## Practical Validation

### Test Setup
```python
# Code used for validation
```

### Results
[Findings from hands-on testing]

## Verdict
**Recommended for**: [Use cases]
**Not recommended for**: [Anti-patterns]
```

### Research Summary Template

```markdown
# Research Summary: [Topic]

## Research Question
[The specific question being answered]

## Key Findings

### Finding 1: [Title]
[Description with supporting evidence]

### Finding 2: [Title]
[Description with supporting evidence]

## Evidence Quality
| Finding | Source Count | Confidence |
|---------|--------------|------------|
| Finding 1 | [N] sources | High/Medium/Low |
| Finding 2 | [N] sources | High/Medium/Low |

## Limitations
- [What this research doesn't cover]
- [Potential biases or gaps]

## Next Steps
- [Recommended follow-up research]
- [Actions to take based on findings]

## Sources
[Numbered list of all sources used]
```

---

## Experimentation Guide

### When to Experiment

Conduct practical validation when:
- Claims are easily testable
- Stakes are high (production decisions)
- Information is outdated or conflicting
- You need specific metrics for your use case

### Experiment Design Framework

**Step 1: Define Hypothesis**
```bash
uv run scripts/create_experiment.py \
    --hypothesis "FastAPI handles more requests per second than Flask" \
    --metric "requests_per_second" \
    --output benchmark_test.py
```

**Step 2: Control Variables**
- Same hardware/environment
- Same test data
- Same measurement methodology
- Multiple runs for statistical significance

**Step 3: Document Setup**
```markdown
## Experiment Setup
- **Date**: [Date]
- **Environment**: [OS, Python version, etc.]
- **Hardware**: [CPU, RAM, etc.]
- **Methodology**: [How measurements were taken]
```

**Step 4: Run and Record**
```bash
# Run multiple iterations
for i in {1..5}; do
    uv run benchmark_test.py >> results.txt
done
```

**Step 5: Analyze Results**
```bash
uv run scripts/analyze_results.py --input results.txt --output analysis.md
```

### Common Experiment Types

#### Performance Benchmark
```python
# Template for performance testing
import time
import statistics

def benchmark(func, iterations=100):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times),
        "min": min(times),
        "max": max(times)
    }
```

#### A/B Comparison
```python
# Template for comparing two approaches
def compare_approaches(approach_a, approach_b, test_cases):
    results = {"a": [], "b": []}
    
    for case in test_cases:
        results["a"].append(approach_a(case))
        results["b"].append(approach_b(case))
    
    return analyze_results(results)
```

---

## Common Pitfalls

### Search Pitfalls

| Pitfall | Problem | Solution |
|---------|---------|----------|
| Too broad | Irrelevant results | Add specific terms, use filters |
| Too narrow | Missing important info | Start broader, then narrow |
| Single source | Bias, incompleteness | Always use multiple sources |
| Recency bias | Missing foundational info | Include seminal works |
| Confirmation bias | Only finding supporting evidence | Actively search for counterarguments |

### Evaluation Pitfalls

| Pitfall | Problem | Solution |
|---------|---------|----------|
| Authority fallacy | Trusting based on reputation alone | Verify claims independently |
| Outdated info | Using obsolete information | Check publication dates |
| Sponsored content | Hidden bias | Check for disclosures |
| Anecdotal evidence | Overgeneralizing | Look for systematic studies |

### Synthesis Pitfalls

| Pitfall | Problem | Solution |
|---------|---------|----------|
| Cherry-picking | Selective evidence | Present full picture |
| False equivalence | Treating unequal sources equally | Weight by quality |
| Missing context | Misrepresenting findings | Include caveats |
| Overconfidence | Certainty without evidence | Express uncertainty levels |

---

## Script Reference

### validate_claim.py

**Purpose:** Verify a claim across multiple sources.

**Usage:**
```bash
uv run scripts/validate_claim.py --claim "CLAIM" [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--claim` | The claim to validate | Required |
| `--min_sources` | Minimum sources needed | 3 |
| `--domains` | Preferred domains (comma-separated) | None |
| `--output` | Output format (text/json/markdown) | text |

### compare_sources.py

**Purpose:** Compare information from multiple sources on a topic.

**Usage:**
```bash
uv run scripts/compare_sources.py --topic "TOPIC" [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--topic` | Topic to compare | Required |
| `--sources` | Specific sources (comma-separated) | Auto |
| `--evaluate_authority` | Include authority assessment | False |
| `--output` | Output file path | stdout |

### create_experiment.py

**Purpose:** Generate experiment code to validate a hypothesis.

**Usage:**
```bash
uv run scripts/create_experiment.py --hypothesis "HYPOTHESIS" [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--hypothesis` | The hypothesis to test | Required |
| `--metric` | What to measure | time |
| `--iterations` | Number of test runs | 10 |
| `--output` | Output script path | experiment.py |

### summarize_research.py

**Purpose:** Generate a structured summary from research notes.

**Usage:**
```bash
uv run scripts/summarize_research.py --notes "NOTES_FILE" [OPTIONS]
```

**Options:**
| Option | Description | Default |
|--------|-------------|---------|
| `--notes` | Path to notes file | Required |
| `--format` | Output format (brief/detailed/executive) | detailed |
| `--template` | Template type (comparison/evaluation/summary) | summary |
| `--output` | Output file path | stdout |

