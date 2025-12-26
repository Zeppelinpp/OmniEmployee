"""Agent execution loop with complete flow control."""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Any
from enum import Enum
from pathlib import Path

from rich.console import Console
from rich.text import Text
from rich.style import Style

from src.omniemployee.core.agent import Agent
from src.omniemployee.llm import LLMProvider, LLMConfig, LLMResponse
from src.omniemployee.context.message import ToolCall, MessageRole
from src.omniemployee.tools.base import ToolResult, ToolResultStatus

# Prompts directory
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# Rich console for output (force_terminal for color support in various environments)
console = Console(force_terminal=True)


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt template not found: {prompt_path}")


class LoopState(Enum):
    """State of the agent loop."""
    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    ERROR = "error"
    MAX_ITERATIONS = "max_iterations"


@dataclass
class LoopConfig:
    """Configuration for the agent loop."""
    # Model settings
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # Loop control
    max_iterations: int = 50
    max_tool_calls_per_turn: int = 10
    
    # API settings
    api_key: str | None = None
    api_base: str | None = None
    
    # Behavior
    auto_load_skills: bool = True  # Auto-load skills when mentioned
    stream_output: bool = True
    
    # Context compression settings
    compress_threshold: float = 0.7  # Trigger compression at 70% of context window
    llm_compress_enabled: bool = True  # Use LLM for summarization
    
    # Web search summarization settings
    summarize_web_results: bool = True  # Summarize web_search/web_extract results
    summarize_model: str = "qwen-turbo"  # Model for summarization


@dataclass
class LoopResult:
    """Result from a loop execution."""
    response: str
    state: LoopState
    iterations: int
    tool_calls_made: int
    tokens_used: int = 0
    error: str | None = None


@dataclass
class ToolExecution:
    """Record of a tool execution."""
    name: str
    arguments: dict
    result: ToolResult
    duration_ms: float = 0


class AgentLoop:
    """Executes the agent loop with full control flow.
    
    The loop follows this pattern:
    1. Receive user input
    2. Call LLM with context and tools
    3. If LLM returns tool calls:
       a. Execute each tool
       b. Add results to context
       c. Go to step 2
    4. If LLM returns final response:
       a. Return response to user
    """
    
    def __init__(
        self,
        agent: Agent,
        config: LoopConfig | None = None,
        on_tool_start: Callable[[str, dict], None] | None = None,
        on_tool_end: Callable[[str, ToolResult], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        on_compression: Callable[[str], None] | None = None,
    ):
        self.agent = agent
        self.config = config or LoopConfig()
        
        # Callbacks
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.on_thinking = on_thinking
        self.on_compression = on_compression
        
        # Initialize LLM provider
        llm_config = LLMConfig(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=self.config.api_key,
            api_base=self.config.api_base,
        )
        self.llm = LLMProvider(llm_config)
        
        # Auto-detect context window from model
        self._setup_context_window()
        
        # Set up LLM compression callback
        if self.config.llm_compress_enabled:
            self.agent.context.set_llm_summarize_callback(self._summarize_conversation)
        
        # Initialize summarization LLM (qwen-turbo for web results)
        self._summarize_llm: LLMProvider | None = None
        if self.config.summarize_web_results:
            self._init_summarize_llm()
        
        # State tracking
        self.state = LoopState.IDLE
        self._iteration = 0
        self._tool_calls_count = 0
        self._total_tokens = 0
    
    def _init_summarize_llm(self) -> None:
        """Initialize the LLM for web search summarization."""
        summarize_config = LLMConfig(
            model=self.config.summarize_model,
            temperature=0.3,
            max_tokens=1024,
        )
        self._summarize_llm = LLMProvider(summarize_config)
    
    def _print_context_status(self) -> str:
        """Print context usage status to terminal."""
        stats = self.agent.context.get_context_stats()
        usage_percent = stats.get("usage_percent", 0)
        current_tokens = stats.get("current_tokens", 0)
        max_tokens = stats.get("max_tokens", 0)
        
        text = Text()
        text.append("Context: ", style="dim")
        text.append(f"({current_tokens:,}/{max_tokens:,})", style="white")
        text.append(f" {usage_percent:.1f}%", style="bold cyan")
        
        console.print(text)
        return f"Context: ({current_tokens:,}/{max_tokens:,}) {usage_percent:.1f}%"
    
    async def _summarize_web_result(self, content: str, search_intent: str) -> str:
        """Summarize web search/extract result based on search intent."""
        if not self._summarize_llm or not content:
            return content
        
        # Skip if content is short enough
        if len(content) < 1000:
            return content
        
        try:
            prompt_template = load_prompt("web_search_summary")
            prompt = prompt_template.format(
                search_intent=search_intent,
                content=content[:15000]
            )
        except FileNotFoundError:
            console.print("[yellow]⚠️ Prompt template not found, using fallback[/yellow]")
            prompt = f"Summarize the following content based on search intent '{search_intent}':\n\n{content[:15000]}"
        
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._summarize_llm.complete(messages)
            summary = response.content or content
            return f"[Summarized from {len(content)} chars]\n\n{summary}"
        except Exception as e:
            console.print(f"[yellow]⚠️ Summarization failed: {e}[/yellow]")
            return content
    
    def _setup_context_window(self) -> None:
        """Auto-detect and configure context window from model."""
        context_window = self.llm.get_model_context_window()
        
        # Update context manager config
        self.agent.context.config.max_tokens = context_window
        self.agent.context.config.compress_threshold = self.config.compress_threshold
        self.agent.context.config.llm_compress_enabled = self.config.llm_compress_enabled
    
    async def _summarize_conversation(self, conversation_text: str) -> str:
        """Summarize conversation using LLM."""
        try:
            prompt_template = load_prompt("conversation_summary")
            summary_prompt = prompt_template.format(conversation_text=conversation_text)
        except FileNotFoundError:
            console.print("[yellow]⚠️ Prompt template not found, using fallback[/yellow]")
            summary_prompt = f"Summarize the following conversation:\n\n{conversation_text}"
        
        messages = [{"role": "user", "content": summary_prompt}]
        
        # Use a smaller max_tokens for summary
        original_max = self.llm.config.max_tokens
        self.llm.config.max_tokens = 1024
        
        try:
            response = await self.llm.complete(messages)
            return response.content or ""
        finally:
            self.llm.config.max_tokens = original_max
    
    async def run(self, user_input: str) -> LoopResult:
        """Run the agent loop until completion."""
        self.state = LoopState.THINKING
        self._iteration = 0
        self._tool_calls_count = 0
        self._total_tokens = 0
        
        # Add user message to context
        self.agent.context.add_user_message(user_input)
        
        final_response = ""
        
        while self._iteration < self.config.max_iterations:
            self._iteration += 1
            
            # Print context status before LLM call
            self._print_context_status()
            
            # Check if context compression is needed
            if self.agent.context.needs_compression():
                summary = await self.agent.context.compress_context_async()
                if summary and self.on_compression:
                    self.on_compression(summary)
            
            try:
                # Get LLM response
                response = await self._call_llm()
                self._total_tokens += response.total_tokens
                
                # Check for tool calls
                if response.has_tool_calls:
                    self.state = LoopState.TOOL_CALLING
                    
                    # Add assistant message with tool calls
                    tool_calls = [
                        ToolCall(
                            id=tc.id,
                            name=tc.name,
                            arguments=tc.arguments
                        )
                        for tc in response.tool_calls
                    ]
                    self.agent.context.add_assistant_message(
                        content=response.content,
                        tool_calls=tool_calls
                    )
                    
                    # Execute tools
                    await self._execute_tools(response.tool_calls)
                    
                    # Continue loop
                    self.state = LoopState.THINKING
                    continue
                
                # No tool calls - we have a final response
                final_response = response.content or ""
                self.agent.context.add_assistant_message(content=final_response)
                self.state = LoopState.COMPLETED
                break
                
            except Exception as e:
                self.state = LoopState.ERROR
                return LoopResult(
                    response="",
                    state=self.state,
                    iterations=self._iteration,
                    tool_calls_made=self._tool_calls_count,
                    tokens_used=self._total_tokens,
                    error=str(e)
                )
        
        # Check if we hit max iterations
        if self._iteration >= self.config.max_iterations:
            self.state = LoopState.MAX_ITERATIONS
        
        return LoopResult(
            response=final_response,
            state=self.state,
            iterations=self._iteration,
            tool_calls_made=self._tool_calls_count,
            tokens_used=self._total_tokens
        )
    
    async def run_stream(self, user_input: str) -> AsyncIterator[str]:
        """Run the agent loop with streaming output."""
        self.state = LoopState.THINKING
        self._iteration = 0
        self._tool_calls_count = 0
        
        # Add user message
        self.agent.context.add_user_message(user_input)
        
        while self._iteration < self.config.max_iterations:
            self._iteration += 1
            
            # Print context status before LLM call
            self._print_context_status()
            
            # Check if context compression is needed
            if self.agent.context.needs_compression():
                yield "\n\n📦 **Compressing context...**\n"
                summary = await self.agent.context.compress_context_async()
                if summary:
                    yield f"_Context compressed. Summary: {summary[:200]}..._\n\n"
            
            content_buffer = ""
            tool_calls_buffer: list[dict] = []
            
            try:
                # Stream LLM response
                async for chunk in self._stream_llm():
                    if chunk.type == "content" and chunk.content:
                        content_buffer += chunk.content
                        yield chunk.content
                    elif chunk.type == "tool_call" and chunk.tool_call:
                        tool_calls_buffer.append(chunk.tool_call)
                
                # Check for tool calls
                if tool_calls_buffer:
                    self.state = LoopState.TOOL_CALLING
                    
                    # Add assistant message
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"]
                        )
                        for tc in tool_calls_buffer
                    ]
                    self.agent.context.add_assistant_message(
                        content=content_buffer,
                        tool_calls=tool_calls
                    )
                    
                    # Execute tools and yield status
                    for tc in tool_calls_buffer:
                        tool_name = tc["name"]
                        tool_args = tc["arguments"]
                        
                        # Show tool name and arguments
                        yield f"\n\n🔧 **{tool_name}**\n"
                        
                        # For run_command, show the command being executed
                        if tool_name == "run_command" and "command" in tool_args:
                            command = tool_args["command"]
                            working_dir = tool_args.get("working_dir")
                            cmd_display = f"$ {command}"
                            if working_dir:
                                cmd_display += f" (in {working_dir})"
                            yield f"```\n{cmd_display}\n```\n"
                        
                        result = await self._execute_single_tool(tool_name, tool_args)
                        
                        # Get result content
                        result_content = result.to_message()
                        
                        # Summarize web search/extract results
                        if tool_name in ("web_search", "web_extract") and result.success and self.config.summarize_web_results:
                            search_intent = tool_args.get("query", "") or tool_args.get("url", "")
                            yield f"_Summarizing results for: {search_intent[:100]}..._\n"
                            result_content = await self._summarize_web_result(result_content, search_intent)
                        
                        self.agent.context.add_tool_result(
                            tool_call_id=tc["id"],
                            content=result_content,
                            is_error=not result.success
                        )
                        
                        # Yield result preview
                        result_preview = result_content
                        
                        # For run_command, the output already includes the command at the top
                        max_preview = 500 if tool_name != "run_command" else 800
                        if tool_name in ("web_search", "web_extract"):
                            max_preview = 1500  # Show more for summarized web results
                        
                        if len(result_preview) > max_preview:
                            result_preview = result_preview[:max_preview] + "..."
                        
                        yield f"```\n{result_preview}\n```\n"
                    
                    self.state = LoopState.THINKING
                    yield "\n"
                    continue
                
                # No tool calls - done
                self.agent.context.add_assistant_message(content=content_buffer)
                self.state = LoopState.COMPLETED
                break
                
            except Exception as e:
                self.state = LoopState.ERROR
                yield f"\n\n❌ Error: {e}"
                break
        
        if self._iteration >= self.config.max_iterations:
            self.state = LoopState.MAX_ITERATIONS
            yield f"\n\n⚠️ Reached maximum iterations ({self.config.max_iterations})"
    
    async def _call_llm(self) -> LLMResponse:
        """Call the LLM with current context."""
        messages = self.agent.get_messages()
        tools = self.agent.get_tool_definitions()
        
        # Add skill loading tool if auto_load is enabled
        if self.config.auto_load_skills:
            tools = self._add_skill_tools(tools)
        
        return await self.llm.complete(messages, tools if tools else None)
    
    async def _stream_llm(self) -> AsyncIterator:
        """Stream LLM response."""
        messages = self.agent.get_messages()
        tools = self.agent.get_tool_definitions()
        
        if self.config.auto_load_skills:
            tools = self._add_skill_tools(tools)
        
        async for chunk in self.llm.stream(messages, tools if tools else None):
            yield chunk
    
    def _add_skill_tools(self, tools: list[dict]) -> list[dict]:
        """Add skill management tools."""
        skill_tools = [
            {
                "type": "function",
                "function": {
                    "name": "load_skill",
                    "description": "Load a skill to get detailed instructions. Use when you need specialized knowledge. You can load multiple skills simultaneously for complex tasks.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the skill to load"
                            }
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "unload_skill",
                    "description": "Unload a skill to free up context space. Use when switching topics or when a skill is no longer needed. This also unloads all references associated with the skill.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the skill to unload"
                            }
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "load_skill_reference",
                    "description": "Load a reference file from a loaded skill. Use when you need additional information like error handling, examples, or detailed documentation mentioned in the skill instructions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "Name of the skill (must be already loaded)"
                            },
                            "ref_path": {
                                "type": "string",
                                "description": "Path to the reference file (e.g., 'reference.md', 'forms.md')"
                            }
                        },
                        "required": ["skill_name", "ref_path"],
                        "additionalProperties": False
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_skills",
                    "description": "List all available skills with their descriptions and loading status. Shows which skills are currently loaded (✓) and which are available (○).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "verbose": {
                                "type": "boolean",
                                "description": "Whether to show detailed info. Default: false"
                            }
                        },
                        "required": [],
                        "additionalProperties": False
                    }
                }
            }
        ]
        return tools + skill_tools
    
    async def _execute_tools(self, tool_calls: list) -> None:
        """Execute multiple tool calls."""
        for tc in tool_calls:
            if self._tool_calls_count >= self.config.max_tool_calls_per_turn * self._iteration:
                # Safety limit on tool calls
                break
            
            result = await self._execute_single_tool(tc.name, tc.arguments)
            
            # Get result content
            result_content = result.to_message()
            
            # Summarize web search/extract results
            if tc.name in ("web_search", "web_extract") and result.success and self.config.summarize_web_results:
                search_intent = tc.arguments.get("query", "") or tc.arguments.get("url", "")
                print(f"📝 Summarizing web results for: {search_intent[:100]}...")
                result_content = await self._summarize_web_result(result_content, search_intent)
            
            self.agent.context.add_tool_result(
                tool_call_id=tc.id,
                content=result_content,
                is_error=not result.success
            )
    
    async def _execute_single_tool(self, name: str, arguments: dict) -> ToolResult:
        """Execute a single tool."""
        self._tool_calls_count += 1
        
        # Callback
        if self.on_tool_start:
            self.on_tool_start(name, arguments)
        
        # Handle skill management tools
        if name == "load_skill":
            result = self._handle_load_skill(arguments.get("name", ""))
        elif name == "unload_skill":
            result = self._handle_unload_skill(arguments.get("name", ""))
        elif name == "load_skill_reference":
            result = self._handle_load_skill_reference(
                arguments.get("skill_name", ""),
                arguments.get("ref_path", "")
            )
        elif name == "list_skills":
            result = self._handle_list_skills(arguments.get("verbose", False))
        else:
            # Execute regular tool
            result = await self.agent.tools.execute(name, **arguments)
        
        # Callback
        if self.on_tool_end:
            self.on_tool_end(name, result)
        
        return result
    
    def _handle_load_skill(self, skill_name: str) -> ToolResult:
        """Handle skill loading."""
        if not skill_name:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Skill name is required"
            )
        
        success = self.agent.load_skill(skill_name)
        
        if success:
            loaded_skills = self.agent.skills.list_loaded_skills()
            available_refs = self.agent.get_skill_references(skill_name)
            refs_info = f" Available references: {available_refs}" if available_refs else ""
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Skill '{skill_name}' loaded successfully.{refs_info}\nCurrently loaded skills: {loaded_skills}"
            )
        else:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to load skill '{skill_name}'. It may not exist or exceed token budget."
            )
    
    def _handle_unload_skill(self, skill_name: str) -> ToolResult:
        """Handle skill unloading."""
        if not skill_name:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Skill name is required"
            )
        
        if not self.agent.skills.is_loaded(skill_name):
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Skill '{skill_name}' is not currently loaded."
            )
        
        self.agent.unload_skill(skill_name)
        
        loaded_skills = self.agent.skills.list_loaded_skills()
        context_stats = self.agent.context.get_context_stats()
        
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=f"Skill '{skill_name}' unloaded successfully.\nCurrently loaded skills: {loaded_skills}\nContext usage: {context_stats['usage_percent']}%"
        )
    
    def _handle_load_skill_reference(self, skill_name: str, ref_path: str) -> ToolResult:
        """Handle loading a skill reference file."""
        if not skill_name:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Skill name is required"
            )
        
        if not ref_path:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="Reference path is required"
            )
        
        # Check if skill is loaded
        if not self.agent.skills.is_loaded(skill_name):
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Skill '{skill_name}' is not loaded. Load the skill first using load_skill."
            )
        
        # Get available references
        available_refs = self.agent.get_skill_references(skill_name)
        if ref_path not in available_refs:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Reference '{ref_path}' not found. Available references: {available_refs}"
            )
        
        # Load the reference
        content = self.agent.load_skill_reference(skill_name, ref_path)
        
        if content:
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Reference '{ref_path}' loaded:\n\n{content}"
            )
        else:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to load reference '{ref_path}' from skill '{skill_name}'"
            )
    
    def _handle_list_skills(self, verbose: bool = False) -> ToolResult:
        """Handle listing available skills."""
        summary = self.agent.skills.get_skills_summary()
        
        return ToolResult(
            status=ToolResultStatus.SUCCESS,
            output=summary if summary else "No skills available."
        )
    
    def reset(self) -> None:
        """Reset the loop state."""
        self.state = LoopState.IDLE
        self._iteration = 0
        self._tool_calls_count = 0
        self._total_tokens = 0
