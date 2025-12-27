#!/usr/bin/env python3
"""Generate a structured summary from research notes."""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


TEMPLATES = {
    "summary": """# Research Summary: {topic}

**Date:** {date}
**Research Question:** {question}

## Key Findings

{findings}

## Evidence Quality

| Finding | Sources | Confidence |
|---------|---------|------------|
{evidence_table}

## Limitations

{limitations}

## Next Steps

{next_steps}

## Sources

{sources}
""",
    "comparison": """# Comparison Report: {topic}

**Date:** {date}

## Executive Summary

{summary}

## Comparison Matrix

| Criterion | {options_header} |
|-----------|{options_separator}|
{comparison_rows}

## Detailed Analysis

{detailed_analysis}

## Recommendation

{recommendation}

## Sources

{sources}
""",
    "evaluation": """# Technical Evaluation: {topic}

**Date:** {date}

## Overview

- **What it is:** {description}
- **Primary use case:** {use_case}
- **Alternatives:** {alternatives}

## Technical Assessment

### Architecture
{architecture}

### Performance
{performance}

### Integration
{integration}

## Practical Validation

{validation}

## Verdict

**Recommended for:** {recommended_for}
**Not recommended for:** {not_recommended_for}

## Sources

{sources}
""",
}


def parse_notes(notes_content: str) -> dict:
    """Parse research notes into structured data."""
    data = {
        "topic": "",
        "question": "",
        "findings": [],
        "sources": [],
        "limitations": [],
        "next_steps": [],
        "options": [],
        "recommendation": "",
    }

    current_section = None
    current_content = []

    for line in notes_content.split("\n"):
        line_stripped = line.strip()

        # Detect section headers
        if line_stripped.startswith("# "):
            data["topic"] = line_stripped[2:].strip()
        elif line_stripped.lower().startswith("question:"):
            data["question"] = line_stripped.split(":", 1)[1].strip()
        elif line_stripped.lower() in ["## findings", "## key findings", "findings:"]:
            current_section = "findings"
            current_content = []
        elif line_stripped.lower() in ["## sources", "sources:", "## references"]:
            current_section = "sources"
            current_content = []
        elif line_stripped.lower() in ["## limitations", "limitations:"]:
            current_section = "limitations"
            current_content = []
        elif line_stripped.lower() in ["## next steps", "next steps:", "## todo"]:
            current_section = "next_steps"
            current_content = []
        elif line_stripped.lower() in ["## recommendation", "recommendation:"]:
            current_section = "recommendation"
            current_content = []
        elif line_stripped.startswith("- ") or line_stripped.startswith("* "):
            item = line_stripped[2:].strip()
            if current_section and item:
                if current_section == "recommendation":
                    data["recommendation"] += item + " "
                else:
                    data[current_section].append(item)
        elif line_stripped and current_section == "recommendation":
            data["recommendation"] += line_stripped + " "

    return data


def generate_summary(data: dict, template_name: str = "summary") -> str:
    """Generate a formatted summary from parsed data."""
    template = TEMPLATES.get(template_name, TEMPLATES["summary"])

    date = datetime.now().strftime("%Y-%m-%d")

    # Format findings
    findings = "\n".join(
        f"### Finding {i + 1}\n{f}\n" for i, f in enumerate(data.get("findings", []))
    )
    if not findings:
        findings = "_No findings recorded_"

    # Format evidence table
    evidence_rows = []
    for i, finding in enumerate(data.get("findings", [])[:5]):
        evidence_rows.append(f"| Finding {i + 1} | - | Medium |")
    evidence_table = "\n".join(evidence_rows) if evidence_rows else "| - | - | - |"

    # Format limitations
    limitations = "\n".join(f"- {l}" for l in data.get("limitations", []))
    if not limitations:
        limitations = "- _No limitations noted_"

    # Format next steps
    next_steps = "\n".join(f"- {s}" for s in data.get("next_steps", []))
    if not next_steps:
        next_steps = "- _No next steps defined_"

    # Format sources
    sources = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(data.get("sources", [])))
    if not sources:
        sources = "_No sources recorded_"

    return template.format(
        topic=data.get("topic", "Untitled Research"),
        date=date,
        question=data.get("question", "_Not specified_"),
        findings=findings,
        evidence_table=evidence_table,
        limitations=limitations,
        next_steps=next_steps,
        sources=sources,
        summary=data.get("recommendation", "_No summary_"),
        recommendation=data.get("recommendation", "_No recommendation_"),
        options_header="Option A | Option B",
        options_separator="----------|----------",
        comparison_rows="| - | - | - |",
        detailed_analysis="_No detailed analysis_",
        description="_Not specified_",
        use_case="_Not specified_",
        alternatives="_Not specified_",
        architecture="_Not documented_",
        performance="_Not measured_",
        integration="_Not assessed_",
        validation="_No validation performed_",
        recommended_for="_Not specified_",
        not_recommended_for="_Not specified_",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate structured summary from research notes"
    )
    parser.add_argument(
        "--notes", required=True, help="Path to notes file or raw notes text"
    )
    parser.add_argument(
        "--format",
        choices=["brief", "detailed", "executive"],
        default="detailed",
        help="Output format level",
    )
    parser.add_argument(
        "--template",
        choices=["summary", "comparison", "evaluation"],
        default="summary",
        help="Template type",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")

    args = parser.parse_args()

    # Read notes
    notes_path = Path(args.notes)
    if notes_path.exists():
        notes_content = notes_path.read_text()
    else:
        notes_content = args.notes

    # Parse and generate
    data = parse_notes(notes_content)
    summary = generate_summary(data, args.template)

    # Output
    if args.output:
        Path(args.output).write_text(summary)
        print(f"Summary written to {args.output}")
    else:
        print(summary)


if __name__ == "__main__":
    main()
