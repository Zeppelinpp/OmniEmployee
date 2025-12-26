"""Skill data models with progressive disclosure support."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillMetadata:
    """Skill metadata for progressive disclosure (Phase 1: always in context)."""
    name: str
    description: str
    license: str = "MIT"
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    
    # When to use this skill
    when_to_use: str = ""
    
    # Dependencies
    required_tools: list[str] = field(default_factory=list)
    required_packages: list[str] = field(default_factory=list)
    
    # Path to skill directory
    path: Path | None = None
    
    # Available references (discovered but not loaded)
    available_references: list[str] = field(default_factory=list)
    
    def to_summary(self) -> str:
        """Get a brief summary for skill discovery."""
        return f"**{self.name}**: {self.description}"
    
    def to_detailed_summary(self) -> str:
        """Get detailed summary including when_to_use."""
        parts = [f"**{self.name}**: {self.description}"]
        if self.when_to_use:
            parts.append(f"  - When to use: {self.when_to_use}")
        if self.available_references:
            parts.append(f"  - References: {', '.join(self.available_references)}")
        return "\n".join(parts)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "version": self.version,
            "tags": self.tags,
            "when_to_use": self.when_to_use,
            "required_tools": self.required_tools,
            "required_packages": self.required_packages,
            "available_references": self.available_references
        }


@dataclass
class Skill:
    """Full skill with instructions and resources (Phase 2: loaded on demand)."""
    metadata: SkillMetadata
    
    # Main instructions (from SKILL.md after frontmatter)
    instructions: str = ""
    
    # Additional documentation files (non-reference .md files)
    docs: dict[str, str] = field(default_factory=dict)  # filename -> content
    
    # Scripts in the skill
    scripts: dict[str, str] = field(default_factory=dict)  # filename -> content
    
    # Resources (YAML, JSON configs)
    resources: dict[str, Any] = field(default_factory=dict)
    
    # Reference files (Phase 3: loaded on demand, not auto-loaded)
    # These are discovered but content is loaded only when needed
    references: dict[str, str] = field(default_factory=dict)  # ref_name -> content (when loaded)
    
    # Forms (special reference type for structured data)
    forms: dict[str, str] = field(default_factory=dict)  # form_name -> content (when loaded)
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    def get_full_instructions(self) -> str:
        """Get complete instructions for loading into context (Phase 2)."""
        parts = [f"# Skill: {self.name}"]
        parts.append(f"\n{self.metadata.description}")
        
        if self.metadata.when_to_use:
            parts.append(f"\n**When to use**: {self.metadata.when_to_use}")
        
        # Add skill directory context for script execution
        if self.metadata.path:
            parts.append(f"\n## Skill Context")
            parts.append(f"- **Skill Directory**: `{self.metadata.path}`")
            
            # List available scripts with full paths
            if self.scripts:
                parts.append(f"- **Available Scripts**:")
                for script_name in self.scripts.keys():
                    script_path = self.metadata.path / "scripts" / script_name
                    parts.append(f"  - `{script_path}` (run with: `uv run {script_path}`)")
        
        parts.append(f"\n## Instructions\n{self.instructions}")
        
        # Add additional docs (but NOT references - those are loaded on demand)
        for doc_name, doc_content in self.docs.items():
            parts.append(f"\n## {doc_name}\n{doc_content}")
        
        # Indicate available references without loading them
        if self.metadata.available_references:
            parts.append("\n## Available References (Load on Demand)")
            parts.append("The following reference files contain additional information. Load them using `load_skill_reference` when needed:")
            for ref in self.metadata.available_references:
                parts.append(f"- `{ref}`")
            parts.append("\n**When to load references:**")
            parts.append("- Encountering errors (e.g., unknown city, invalid date)")
            parts.append("- Need detailed examples or conversation flows")
            parts.append("- Need script usage documentation")
            parts.append("- User asks for more options or alternatives")
        
        return "\n".join(parts)
    
    def get_reference(self, name: str) -> str | None:
        """Get a loaded reference by name."""
        return self.references.get(name) or self.forms.get(name)
    
    def list_available_references(self) -> list[str]:
        """List available reference files."""
        return self.metadata.available_references
    
    def list_loaded_references(self) -> list[str]:
        """List currently loaded references."""
        return list(self.references.keys()) + list(self.forms.keys())
    
    def get_script(self, name: str) -> str | None:
        """Get a script by name."""
        return self.scripts.get(name)
    
    def list_scripts(self) -> list[str]:
        """List available scripts."""
        return list(self.scripts.keys())

