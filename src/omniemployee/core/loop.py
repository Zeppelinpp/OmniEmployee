"""Agent execution loop with complete flow control."""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable, Any
from enum import Enum

from src.omniemployee.core.agent import Agent
from src.omniemployee.llm import LLMProvider, LLMConfig, LLMResponse
from src.omniemployee.context.message import ToolCall, MessageRole
from src.omniemployee.tools.base import ToolResult, ToolResultStatus


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
    ):
        self.agent = agent
        self.config = config or LoopConfig()
        
        # Callbacks
        self.on_tool_start = on_tool_start
        self.on_tool_end = on_tool_end
        self.on_thinking = on_thinking
        
        # Initialize LLM provider
        llm_config = LLMConfig(
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            api_key=self.config.api_key,
            api_base=self.config.api_base,
        )
        self.llm = LLMProvider(llm_config)
        
        # State tracking
        self.state = LoopState.IDLE
        self._iteration = 0
        self._tool_calls_count = 0
        self._total_tokens = 0
    
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
                        yield f"\n\n🔧 **{tc['name']}**\n"
                        
                        result = await self._execute_single_tool(tc["name"], tc["arguments"])
                        
                        self.agent.context.add_tool_result(
                            tool_call_id=tc["id"],
                            content=result.to_message(),
                            is_error=not result.success
                        )
                        
                        # Yield truncated result
                        result_preview = result.to_message()
                        if len(result_preview) > 200:
                            result_preview = result_preview[:200] + "..."
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
                    "description": "Load a skill to get detailed instructions. Use when you need specialized knowledge.",
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
                    "description": "List all available skills with their descriptions. Call with empty object {}.",
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
            
            self.agent.context.add_tool_result(
                tool_call_id=tc.id,
                content=result.to_message(),
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
            skill = self.agent.skills.load_skill(skill_name)
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=f"Skill '{skill_name}' loaded successfully. Instructions are now available in context."
            )
        else:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Failed to load skill '{skill_name}'. It may not exist or exceed token budget."
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
