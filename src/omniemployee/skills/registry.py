"""Skill registry with progressive disclosure support."""

from pathlib import Path
from src.omniemployee.skills.loader import SkillLoader
from src.omniemployee.skills.models import Skill, SkillMetadata


class SkillRegistry:
    """Registry for managing skills with progressive disclosure."""

    def __init__(self, skills_dir: str | Path):
        self.loader = SkillLoader(skills_dir)
        self._metadata_cache: dict[str, SkillMetadata] = {}
        self._skill_cache: dict[str, Skill] = {}
        self._discovered = False

    def discover(self) -> list[SkillMetadata]:
        """Discover all available skills (loads metadata only)."""
        if self._discovered:
            return list(self._metadata_cache.values())

        metadata_list = self.loader.discover_skills()

        for meta in metadata_list:
            self._metadata_cache[meta.name] = meta

        self._discovered = True
        return metadata_list

    def get_metadata(self, name: str) -> SkillMetadata | None:
        """Get skill metadata by name."""
        if not self._discovered:
            self.discover()
        return self._metadata_cache.get(name)

    def get_all_metadata(self) -> dict[str, SkillMetadata]:
        """Get all skill metadata."""
        if not self._discovered:
            self.discover()
        return self._metadata_cache.copy()

    def load_skill(self, name: str) -> Skill | None:
        """Load full skill (on demand)."""
        # Check cache first
        if name in self._skill_cache:
            return self._skill_cache[name]

        # Load from filesystem
        skill = self.loader.load_skill(name)

        if skill:
            self._skill_cache[name] = skill
            # Update metadata cache
            self._metadata_cache[name] = skill.metadata

        return skill

    def unload_skill(self, name: str) -> None:
        """Unload a skill from cache."""
        if name in self._skill_cache:
            del self._skill_cache[name]

    def is_loaded(self, name: str) -> bool:
        """Check if a skill is fully loaded."""
        return name in self._skill_cache

    def load_skill_reference(self, skill_name: str, ref_path: str) -> str | None:
        """Load a specific reference file from a skill (Phase 3).

        Args:
            skill_name: Name of the skill
            ref_path: Path to reference file (e.g., "forms.md", "references/api.md")

        Returns:
            Content of the reference file, or None if not found
        """
        # Ensure skill is loaded first
        skill = self.load_skill(skill_name)
        if not skill:
            return None

        # Check if already loaded
        if ref_path in skill.references:
            return skill.references[ref_path]
        if ref_path in skill.forms:
            return skill.forms[ref_path]

        # Load from filesystem
        content = self.loader.load_skill_reference(skill_name, ref_path)

        if content:
            # Cache the loaded reference
            if ref_path.lower() == "forms.md" or "form" in ref_path.lower():
                skill.forms[ref_path] = content
            else:
                skill.references[ref_path] = content

        return content

    def get_skill_available_references(self, skill_name: str) -> list[str]:
        """Get list of available references for a skill."""
        meta = self.get_metadata(skill_name)
        if meta:
            return meta.available_references
        return []

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        if not self._discovered:
            self.discover()
        return list(self._metadata_cache.keys())

    def list_loaded_skills(self) -> list[str]:
        """List currently loaded skills."""
        return list(self._skill_cache.keys())

    def get_skills_summary(self) -> str:
        """Get a summary of all skills for display."""
        if not self._discovered:
            self.discover()

        if not self._metadata_cache:
            return "No skills available."

        lines = []
        for name, meta in self._metadata_cache.items():
            loaded = "✓" if name in self._skill_cache else "○"
            lines.append(f"[{loaded}] {meta.to_summary()}")

        return "\n".join(lines)

    def find_skills_by_tag(self, tag: str) -> list[SkillMetadata]:
        """Find skills by tag."""
        if not self._discovered:
            self.discover()

        return [
            meta for meta in self._metadata_cache.values()
            if tag.lower() in [t.lower() for t in meta.tags]
        ]

    def search_skills(self, query: str) -> list[SkillMetadata]:
        """Search skills by name or description."""
        if not self._discovered:
            self.discover()

        query_lower = query.lower()
        results = []

        for meta in self._metadata_cache.values():
            if (query_lower in meta.name.lower() or
                query_lower in meta.description.lower() or
                query_lower in meta.when_to_use.lower()):
                results.append(meta)

        return results
