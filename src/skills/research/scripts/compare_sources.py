#!/usr/bin/env python3
"""Compare information from multiple sources on a topic."""

import argparse
import json
import os
import sys
from dataclasses import dataclass


@dataclass
class SourceInfo:
    """Information from a single source."""
    title: str
    url: str
    domain: str
    content: str
    score: float
    authority_tier: int = 3


AUTHORITY_TIERS = {
    # Tier 1: Highest authority
    1: [
        "arxiv.org", "nature.com", "science.org", "acm.org", "ieee.org",
        "gov", "edu", "who.int", "cdc.gov"
    ],
    # Tier 2: High authority
    2: [
        "github.com", "stackoverflow.com", "developer.mozilla.org",
        "docs.python.org", "react.dev", "kubernetes.io",
        "gartner.com", "mckinsey.com", "hbr.org"
    ],
    # Tier 3: Medium authority
    3: [
        "medium.com", "dev.to", "techcrunch.com", "wired.com",
        "arstechnica.com", "theverge.com"
    ],
    # Tier 4: Lower authority (requires verification)
    4: [
        "reddit.com", "quora.com", "twitter.com", "linkedin.com"
    ]
}


def get_authority_tier(url: str) -> int:
    """Determine authority tier based on domain."""
    domain = url.lower()
    
    for tier, domains in AUTHORITY_TIERS.items():
        for d in domains:
            if d in domain:
                return tier
    
    return 3


def compare_sources(
    topic: str,
    specific_sources: list[str] | None = None,
    evaluate_authority: bool = False,
    max_results: int = 10
) -> dict:
    """Compare information from multiple sources on a topic."""
    try:
        from tavily import TavilyClient
    except ImportError:
        return {"error": "tavily-python not installed. Run: pip install tavily-python"}
    
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not set"}
    
    client = TavilyClient(api_key=api_key)
    
    search_params = {
        "query": topic,
        "search_depth": "advanced",
        "max_results": max_results,
    }
    
    if specific_sources:
        search_params["include_domains"] = specific_sources
    
    try:
        response = client.search(**search_params)
    except Exception as e:
        return {"error": str(e)}
    
    results = response.get("results", [])
    
    sources = []
    for result in results:
        url = result.get("url", "")
        source = SourceInfo(
            title=result.get("title", ""),
            url=url,
            domain=extract_domain(url),
            content=result.get("content", ""),
            score=result.get("score", 0),
            authority_tier=get_authority_tier(url) if evaluate_authority else 3
        )
        sources.append(source)
    
    # Group by domain
    by_domain = {}
    for source in sources:
        if source.domain not in by_domain:
            by_domain[source.domain] = []
        by_domain[source.domain].append(source)
    
    # Extract key points from each source
    key_points = extract_key_points(sources)
    
    # Find consensus and disagreements
    analysis = analyze_consensus(sources)
    
    comparison_result = {
        "topic": topic,
        "total_sources": len(sources),
        "unique_domains": len(by_domain),
        "sources": [
            {
                "title": s.title,
                "url": s.url,
                "domain": s.domain,
                "authority_tier": s.authority_tier if evaluate_authority else None,
                "relevance_score": s.score,
                "excerpt": s.content[:500] if s.content else ""
            }
            for s in sorted(sources, key=lambda x: (-x.authority_tier if evaluate_authority else 0, -x.score))
        ],
        "key_points": key_points,
        "analysis": analysis
    }
    
    if evaluate_authority:
        comparison_result["authority_summary"] = {
            "tier_1_count": sum(1 for s in sources if s.authority_tier == 1),
            "tier_2_count": sum(1 for s in sources if s.authority_tier == 2),
            "tier_3_count": sum(1 for s in sources if s.authority_tier == 3),
            "tier_4_count": sum(1 for s in sources if s.authority_tier == 4),
            "recommendation": get_authority_recommendation(sources)
        }
    
    return comparison_result


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def extract_key_points(sources: list[SourceInfo]) -> list[str]:
    """Extract key points from sources (simplified version)."""
    points = []
    
    for source in sources[:5]:
        if source.content:
            # Take first meaningful sentence
            sentences = source.content.split(". ")
            if sentences:
                point = sentences[0].strip()
                if len(point) > 20:
                    points.append(f"[{source.domain}] {point}")
    
    return points[:5]


def analyze_consensus(sources: list[SourceInfo]) -> dict:
    """Analyze consensus among sources."""
    if not sources:
        return {"status": "no_data", "message": "No sources found"}
    
    if len(sources) == 1:
        return {"status": "single_source", "message": "Only one source found. Verify with additional sources."}
    
    # Simplified consensus analysis
    high_authority = [s for s in sources if s.authority_tier <= 2]
    
    if len(high_authority) >= 2:
        return {
            "status": "good_coverage",
            "message": f"Found {len(high_authority)} high-authority sources. Good basis for research."
        }
    elif len(sources) >= 3:
        return {
            "status": "moderate_coverage",
            "message": "Multiple sources found but authority varies. Cross-reference key claims."
        }
    else:
        return {
            "status": "limited_coverage",
            "message": "Limited sources. Consider expanding search or using different queries."
        }


def get_authority_recommendation(sources: list[SourceInfo]) -> str:
    """Generate recommendation based on authority analysis."""
    tier_1 = sum(1 for s in sources if s.authority_tier == 1)
    tier_2 = sum(1 for s in sources if s.authority_tier == 2)
    
    if tier_1 >= 2:
        return "Excellent source quality. Primary sources available."
    elif tier_1 + tier_2 >= 3:
        return "Good source quality. Mix of primary and authoritative secondary sources."
    elif tier_2 >= 2:
        return "Moderate source quality. Consider seeking primary sources."
    else:
        return "Source quality could be improved. Seek more authoritative sources."


def format_output(result: dict, output_format: str) -> str:
    """Format the comparison result."""
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    lines = [
        "=" * 70,
        f"SOURCE COMPARISON: {result['topic']}",
        "=" * 70,
        f"Total Sources: {result['total_sources']} from {result['unique_domains']} domains",
        "",
    ]
    
    if result.get("authority_summary"):
        auth = result["authority_summary"]
        lines.extend([
            "AUTHORITY BREAKDOWN:",
            f"  Tier 1 (Highest): {auth['tier_1_count']}",
            f"  Tier 2 (High): {auth['tier_2_count']}",
            f"  Tier 3 (Medium): {auth['tier_3_count']}",
            f"  Tier 4 (Lower): {auth['tier_4_count']}",
            f"  Recommendation: {auth['recommendation']}",
            "",
        ])
    
    lines.append("SOURCES:")
    for i, source in enumerate(result["sources"][:5], 1):
        tier_str = f" [Tier {source['authority_tier']}]" if source.get("authority_tier") else ""
        lines.extend([
            f"\n{i}. {source['title']}{tier_str}",
            f"   URL: {source['url']}",
            f"   Relevance: {source['relevance_score']:.2f}",
        ])
        if source["excerpt"]:
            lines.append(f"   Excerpt: {source['excerpt'][:200]}...")
    
    if result.get("key_points"):
        lines.extend([
            "",
            "KEY POINTS:",
        ])
        for point in result["key_points"]:
            lines.append(f"  • {point[:100]}...")
    
    lines.extend([
        "",
        "ANALYSIS:",
        f"  Status: {result['analysis']['status']}",
        f"  {result['analysis']['message']}",
        "=" * 70,
    ])
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare information from multiple sources")
    parser.add_argument("--topic", required=True, help="Topic to research")
    parser.add_argument("--sources", help="Specific sources/domains (comma-separated)")
    parser.add_argument("--evaluate_authority", action="store_true", help="Include authority assessment")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    
    args = parser.parse_args()
    
    sources = args.sources.split(",") if args.sources else None
    
    result = compare_sources(
        topic=args.topic,
        specific_sources=sources,
        evaluate_authority=args.evaluate_authority
    )
    
    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    
    output = format_output(result, args.format)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output written to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()

