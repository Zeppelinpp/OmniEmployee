#!/usr/bin/env python3
"""Validate a claim by searching multiple sources."""

import argparse
import json
import os
import sys


def validate_claim(
    claim: str,
    min_sources: int = 3,
    domains: list[str] | None = None,
    output_format: str = "text",
) -> dict:
    """Validate a claim by searching for supporting/contradicting evidence."""
    try:
        from tavily import TavilyClient
    except ImportError:
        return {
            "error": "tavily-python not installed. Run: pip install tavily-python",
            "valid": False,
        }

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not set", "valid": False}

    client = TavilyClient(api_key=api_key)

    search_params = {
        "query": f'"{claim}" evidence fact check',
        "search_depth": "advanced",
        "max_results": min_sources * 2,
    }

    if domains:
        search_params["include_domains"] = domains

    try:
        response = client.search(**search_params)
    except Exception as e:
        return {"error": str(e), "valid": False}

    results = response.get("results", [])

    supporting = []
    contradicting = []
    neutral = []

    claim_lower = claim.lower()

    for result in results:
        content = (result.get("content", "") or "").lower()
        title = (result.get("title", "") or "").lower()

        source_info = {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "snippet": result.get("content", "")[:300] if result.get("content") else "",
            "score": result.get("score", 0),
        }

        # Simple heuristic for classification
        if any(
            word in content
            for word in ["confirms", "verified", "true", "correct", "accurate"]
        ):
            supporting.append(source_info)
        elif any(
            word in content
            for word in ["false", "incorrect", "debunked", "myth", "wrong"]
        ):
            contradicting.append(source_info)
        else:
            neutral.append(source_info)

    total_sources = len(results)
    confidence = "low"
    if len(supporting) >= min_sources:
        confidence = "high"
    elif len(supporting) >= min_sources // 2:
        confidence = "medium"

    validation_result = {
        "claim": claim,
        "total_sources_found": total_sources,
        "supporting_sources": len(supporting),
        "contradicting_sources": len(contradicting),
        "neutral_sources": len(neutral),
        "confidence": confidence,
        "valid": len(supporting) > len(contradicting),
        "sources": {
            "supporting": supporting[:3],
            "contradicting": contradicting[:3],
            "neutral": neutral[:2],
        },
        "recommendation": get_recommendation(
            len(supporting), len(contradicting), total_sources
        ),
    }

    return validation_result


def get_recommendation(supporting: int, contradicting: int, total: int) -> str:
    """Generate a recommendation based on validation results."""
    if total == 0:
        return "Unable to find sources. Try rephrasing the claim or using different search terms."

    if contradicting > supporting:
        return "This claim appears to be disputed or incorrect. Verify with primary sources."
    elif supporting >= 3 and contradicting == 0:
        return "This claim is well-supported by multiple sources."
    elif supporting > contradicting:
        return "This claim has some support but should be verified with authoritative sources."
    else:
        return "Insufficient evidence to validate. Conduct deeper research with specific sources."


def format_output(result: dict, output_format: str) -> str:
    """Format the validation result."""
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)

    if output_format == "markdown":
        lines = [
            f"# Claim Validation Report",
            "",
            f"**Claim:** {result['claim']}",
            "",
            "## Summary",
            f"- **Confidence:** {result['confidence'].upper()}",
            f"- **Valid:** {'Yes' if result['valid'] else 'No/Uncertain'}",
            f"- **Sources Found:** {result['total_sources_found']}",
            f"  - Supporting: {result['supporting_sources']}",
            f"  - Contradicting: {result['contradicting_sources']}",
            f"  - Neutral: {result['neutral_sources']}",
            "",
            f"## Recommendation",
            result["recommendation"],
            "",
        ]

        if result["sources"]["supporting"]:
            lines.append("## Supporting Sources")
            for s in result["sources"]["supporting"]:
                lines.append(f"- [{s['title']}]({s['url']})")
                if s["snippet"]:
                    lines.append(f"  > {s['snippet'][:200]}...")
            lines.append("")

        if result["sources"]["contradicting"]:
            lines.append("## Contradicting Sources")
            for s in result["sources"]["contradicting"]:
                lines.append(f"- [{s['title']}]({s['url']})")
            lines.append("")

        return "\n".join(lines)

    # Text format
    lines = [
        "=" * 60,
        "CLAIM VALIDATION REPORT",
        "=" * 60,
        f"Claim: {result['claim']}",
        "",
        f"Confidence: {result['confidence'].upper()}",
        f"Valid: {'Yes' if result['valid'] else 'No/Uncertain'}",
        "",
        f"Sources Found: {result['total_sources_found']}",
        f"  - Supporting: {result['supporting_sources']}",
        f"  - Contradicting: {result['contradicting_sources']}",
        f"  - Neutral: {result['neutral_sources']}",
        "",
        "Recommendation:",
        result["recommendation"],
        "=" * 60,
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate a claim across multiple sources"
    )
    parser.add_argument("--claim", required=True, help="The claim to validate")
    parser.add_argument(
        "--min_sources",
        type=int,
        default=3,
        help="Minimum sources needed for validation",
    )
    parser.add_argument("--domains", help="Preferred domains (comma-separated)")
    parser.add_argument(
        "--output",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    domains = args.domains.split(",") if args.domains else None

    result = validate_claim(
        claim=args.claim,
        min_sources=args.min_sources,
        domains=domains,
        output_format=args.output,
    )

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(format_output(result, args.output))


if __name__ == "__main__":
    main()
