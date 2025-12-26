"""Main Agent class."""

from dataclasses import dataclass
from pathlib import Path
from src.omniemployee.context import ContextManager, ContextConfig
from src.omniemployee.tools import ToolRegistry
from src.omniemployee.skills import SkillRegistry

# Default path to system prompt template
DEFAULT_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "system_prompt.md"


@dataclass
class AgentConfig:
    """Agent configuration."""
    workspace_root: str
    skills_dir: str = "skills"
    model: str = "gpt-4o"
    max_iterations: int = 50
    
    # Context settings
    max_tokens: int = 128000
    reserved_for_output: int = 4096
    
    # System prompt (path to md file or custom content)
    system_prompt_path: Path | str | None = None
    system_prompt: str = ""  # Override with custom prompt if provided


class Agent:
    """The main Agent class that orchestrates everything."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.workspace_root = Path(config.workspace_root)
        
        # Initialize context manager
        context_config = ContextConfig(
            max_tokens=config.max_tokens,
            reserved_for_output=config.reserved_for_output
        )
        self.context = ContextManager(context_config)
        
        # Initialize tool registry
        self.tools = ToolRegistry()
        
        # Initialize skill registry
        skills_path = self.workspace_root / config.skills_dir
        self.skills = SkillRegistry(skills_path)
        
        # Set up system prompt
        self._setup_system_prompt()
        
        # Register default tools
        self._register_default_tools()
    
    def _setup_system_prompt(self) -> None:
        """Set up the system prompt from template or custom content."""
        if self.config.system_prompt:
            # Use custom prompt if provided
            prompt = self.config.system_prompt
        else:
            # Load from template file
            prompt = self._load_system_prompt_template()
        
        self.context.set_system_prompt(prompt)
    
    def _load_system_prompt_template(self) -> str:
        """Load and render the system prompt template."""
        prompt_path = self.config.system_prompt_path or DEFAULT_PROMPT_PATH
        prompt_path = Path(prompt_path)
        
        if not prompt_path.exists():
            return self._fallback_system_prompt()
        
        template = prompt_path.read_text(encoding='utf-8')
        
        # Render template with placeholders
        return template.format(
            workspace_root=self.workspace_root,
            tools_summary=self.tools.get_tools_summary(),
            skills_summary=self.skills.get_skills_summary(),
            loaded_skill_instructions=""  # Will be populated dynamically
        )
    
    def _fallback_system_prompt(self) -> str:
        """Fallback system prompt if template not found."""
        return f"""You are OmniEmployee, an AI assistant.

Working directory: {self.workspace_root}

## Available Tools
{self.tools.get_tools_summary()}
"""
    
    def _register_default_tools(self) -> None:
        """Register default tools."""
        from src.omniemployee.tools.grep import GrepTool
        from src.omniemployee.tools.list_dir import ListDirTool
        from src.omniemployee.tools.read_file import ReadFileTool
        from src.omniemployee.tools.write_file import WriteFileTool
        from src.omniemployee.tools.run_command import RunCommandTool
        from src.omniemployee.tools.web_search import WebSearchTool
        from src.omniemployee.tools.web_extract import WebExtractTool
        
        workspace = str(self.workspace_root)
        
        self.tools.register(GrepTool(workspace))
        self.tools.register(ListDirTool(workspace))
        self.tools.register(ReadFileTool(workspace))
        self.tools.register(WriteFileTool(workspace))
        self.tools.register(RunCommandTool(workspace))
        self.tools.register(WebSearchTool())
        self.tools.register(WebExtractTool())
    
    def discover_skills(self) -> None:
        """Discover available skills and register metadata."""
        metadata_list = self.skills.discover()
        
        for meta in metadata_list:
            self.context.register_skill_metadata(meta.name, meta.to_dict())
    
    def load_skill(self, name: str) -> bool:
        """Load a skill into context (Phase 2).
        
        Loads the main SKILL.md instructions. Reference files are NOT loaded
        automatically - use load_skill_reference() for on-demand loading.
        """
        skill = self.skills.load_skill(name)
        if not skill:
            return False
        
        instructions = skill.get_full_instructions()
        return self.context.load_skill(name, instructions)
    
    def load_skill_reference(self, skill_name: str, ref_path: str) -> str | None:
        """Load a specific reference file from a skill (Phase 3).
        
        Use this to load additional reference files mentioned in SKILL.md:
        - forms.md: Form definitions and templates
        - references/*.md: Domain-specific documentation
        - reference.md: General reference material
        
        Args:
            skill_name: Name of the skill
            ref_path: Path to reference (e.g., "forms.md", "references/api.md")
        
        Returns:
            Content of the reference, or None if not found
        """
        content = self.skills.load_skill_reference(skill_name, ref_path)
        
        if content:
            # Add reference content to context
            ref_key = f"{skill_name}:{ref_path}"
            self.context.add_skill_reference(ref_key, content)
        
        return content
    
    def get_skill_references(self, skill_name: str) -> list[str]:
        """Get list of available references for a skill."""
        return self.skills.get_skill_available_references(skill_name)
    
    def unload_skill(self, name: str) -> None:
        """Unload a skill from context."""
        self.context.unload_skill(name)
        self.skills.unload_skill(name)
    
    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for LLM."""
        return self.tools.get_definitions()
    
    def get_messages(self) -> list[dict]:
        """Get messages for LLM."""
        return self.context.build_messages()
    
    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "context": self.context.get_context_stats(),
            "tools": self.tools.list_tools(),
            "skills": {
                "available": self.skills.list_skills(),
                "loaded": self.skills.list_loaded_skills()
            }
        }

