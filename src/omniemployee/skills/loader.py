"""Skill loader with YAML frontmatter parsing and progressive disclosure."""

import re
import yaml
from pathlib import Path
from src.omniemployee.skills.models import Skill, SkillMetadata


class SkillLoader:
    """Loads skills from filesystem following Anthropic's progressive disclosure pattern.

    Three-level loading system:
    1. Metadata (name + description) - always in context (~100 words)
    2. SKILL.md body - loaded when skill triggers (<5k words)
    3. Bundled resources (references/, forms/) - loaded as needed by agent
    """

    SKILL_FILE = "SKILL.md"
    SCRIPTS_DIR = "scripts"
    RESOURCES_DIR = "resources"
    REFERENCES_DIR = "references"
    FORMS_FILE = "forms.md"  # Special file for form definitions

    def __init__(self, skills_dir: str | Path):
        self.skills_dir = Path(skills_dir)

    def discover_skills(self) -> list[SkillMetadata]:
        """Discover all skills and return their metadata only (Phase 1).

        This loads minimal information: name, description, and available references.
        Full instructions are NOT loaded until the skill is explicitly requested.
        """
        skills = []

        if not self.skills_dir.exists():
            return skills

        for skill_path in self.skills_dir.iterdir():
            if skill_path.is_dir():
                skill_file = skill_path / self.SKILL_FILE
                if skill_file.exists():
                    metadata = self._load_metadata(skill_file)
                    if metadata:
                        metadata.path = skill_path
                        # Discover available references without loading content
                        metadata.available_references = self._discover_references(skill_path)
                        skills.append(metadata)

        return skills

    def _discover_references(self, skill_path: Path) -> list[str]:
        """Discover available reference files without loading content."""
        refs = []

        # Check for forms.md
        forms_file = skill_path / self.FORMS_FILE
        if forms_file.exists():
            refs.append("forms.md")

        # Check references/ directory
        refs_dir = skill_path / self.REFERENCES_DIR
        if refs_dir.exists():
            for ref_file in refs_dir.iterdir():
                if ref_file.is_file() and ref_file.suffix in ['.md', '.txt', '.yaml', '.yml', '.json']:
                    refs.append(f"references/{ref_file.name}")

        # Check for reference.md at root level (common pattern)
        ref_file = skill_path / "reference.md"
        if ref_file.exists():
            refs.append("reference.md")

        return refs

    def load_skill(self, name: str) -> Skill | None:
        """Load full skill by name (Phase 2 - on demand).

        Loads SKILL.md instructions but NOT reference files.
        References are loaded separately via load_skill_reference().
        """
        skill_path = self.skills_dir / name

        if not skill_path.exists():
            return None

        skill_file = skill_path / self.SKILL_FILE
        if not skill_file.exists():
            return None

        # Load metadata and instructions
        metadata, instructions = self._parse_skill_file(skill_file)
        if not metadata:
            return None

        metadata.path = skill_path
        metadata.available_references = self._discover_references(skill_path)

        # Load additional docs (non-reference .md files)
        docs = self._load_docs(skill_path)

        # Load scripts
        scripts = self._load_scripts(skill_path / self.SCRIPTS_DIR)

        # Load resources (configs, not references)
        resources = self._load_resources(skill_path / self.RESOURCES_DIR)

        # Note: references and forms are NOT loaded here
        # They are loaded on-demand via load_skill_reference()

        return Skill(
            metadata=metadata,
            instructions=instructions,
            docs=docs,
            scripts=scripts,
            resources=resources
        )

    def load_skill_reference(self, skill_name: str, ref_path: str) -> str | None:
        """Load a specific reference file from a skill (Phase 3 - on demand).

        Args:
            skill_name: Name of the skill
            ref_path: Path to reference file (e.g., "forms.md", "references/api.md")

        Returns:
            Content of the reference file, or None if not found
        """
        skill_path = self.skills_dir / skill_name

        if not skill_path.exists():
            return None

        ref_file = skill_path / ref_path

        if not ref_file.exists():
            return None

        try:
            return ref_file.read_text(encoding='utf-8')
        except Exception:
            return None

    def _load_metadata(self, skill_file: Path) -> SkillMetadata | None:
        """Load only the metadata from a skill file."""
        try:
            content = skill_file.read_text(encoding='utf-8')
            frontmatter = self._extract_frontmatter(content)

            if not frontmatter:
                return None

            return SkillMetadata(
                name=frontmatter.get('name', skill_file.parent.name),
                description=frontmatter.get('description', ''),
                license=frontmatter.get('license', 'MIT'),
                version=frontmatter.get('version', '1.0.0'),
                tags=frontmatter.get('tags', []),
                when_to_use=frontmatter.get('when_to_use', ''),
                required_tools=frontmatter.get('required_tools', []),
                required_packages=frontmatter.get('required_packages', [])
            )
        except Exception:
            return None

    def _parse_skill_file(self, skill_file: Path) -> tuple[SkillMetadata | None, str]:
        """Parse skill file into metadata and instructions."""
        try:
            content = skill_file.read_text(encoding='utf-8')

            # Extract frontmatter
            frontmatter = self._extract_frontmatter(content)

            # Extract instructions (content after frontmatter)
            instructions = self._extract_instructions(content)

            if not frontmatter:
                return None, ""

            metadata = SkillMetadata(
                name=frontmatter.get('name', skill_file.parent.name),
                description=frontmatter.get('description', ''),
                license=frontmatter.get('license', 'MIT'),
                version=frontmatter.get('version', '1.0.0'),
                tags=frontmatter.get('tags', []),
                when_to_use=frontmatter.get('when_to_use', ''),
                required_tools=frontmatter.get('required_tools', []),
                required_packages=frontmatter.get('required_packages', [])
            )

            return metadata, instructions

        except Exception:
            return None, ""

    def _extract_frontmatter(self, content: str) -> dict | None:
        """Extract YAML frontmatter from markdown content."""
        # Match YAML frontmatter between --- markers
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None

        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None

    def _extract_instructions(self, content: str) -> str:
        """Extract instructions (content after frontmatter)."""
        # Remove frontmatter
        pattern = r'^---\s*\n.*?\n---\s*\n'
        instructions = re.sub(pattern, '', content, count=1, flags=re.DOTALL)
        return instructions.strip()

    def _load_docs(self, skill_path: Path) -> dict[str, str]:
        """Load additional markdown documentation files (excluding references).

        Does NOT load:
        - SKILL.md (main file)
        - forms.md (reference, loaded on demand)
        - reference.md (reference, loaded on demand)
        """
        docs = {}

        # Files to exclude from auto-loading
        exclude_files = {
            self.SKILL_FILE.lower(),
            self.FORMS_FILE.lower(),
            "reference.md"
        }

        for md_file in skill_path.glob("*.md"):
            if md_file.name.lower() not in exclude_files:
                try:
                    key = md_file.stem
                    docs[key] = md_file.read_text(encoding='utf-8')
                except Exception:
                    pass

        return docs

    def _load_scripts(self, scripts_dir: Path) -> dict[str, str]:
        """Load script files from the scripts directory."""
        scripts = {}

        if not scripts_dir.exists():
            return scripts

        for script_file in scripts_dir.iterdir():
            if script_file.is_file():
                try:
                    scripts[script_file.name] = script_file.read_text(encoding='utf-8')
                except Exception:
                    pass

        return scripts

    def _load_resources(self, resources_dir: Path) -> dict[str, any]:
        """Load resource files (YAML, JSON, etc.)."""
        resources = {}

        if not resources_dir.exists():
            return resources

        import json

        for resource_file in resources_dir.iterdir():
            if resource_file.is_file():
                try:
                    if resource_file.suffix in ['.yaml', '.yml']:
                        resources[resource_file.name] = yaml.safe_load(
                            resource_file.read_text(encoding='utf-8')
                        )
                    elif resource_file.suffix == '.json':
                        resources[resource_file.name] = json.loads(
                            resource_file.read_text(encoding='utf-8')
                        )
                    else:
                        # Store as text
                        resources[resource_file.name] = resource_file.read_text(encoding='utf-8')
                except Exception:
                    pass

        return resources
