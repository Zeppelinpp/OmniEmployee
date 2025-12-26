"""LLM provider using LiteLLM for unified multi-model access."""

import os
import json
from dataclasses import dataclass, field
from typing import AsyncIterator
from dotenv import load_dotenv
import litellm
from litellm import acompletion

# Load environment variables from .env file
load_dotenv()


@dataclass
class ProviderConfig:
    """Configuration for a specific provider."""
    api_key: str | None = None
    api_base: str | None = None
    
    @classmethod
    def from_env(cls, prefix: str) -> "ProviderConfig":
        """Load provider config from environment variables.
        
        Example: prefix="OPENAI" loads OPENAI_API_KEY and OPENAI_BASE_URL
        """
        return cls(
            api_key=os.getenv(f"{prefix}_API_KEY"),
            api_base=os.getenv(f"{prefix}_BASE_URL") or os.getenv(f"{prefix}_API_BASE")
        )


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # API configuration (optional, auto-detected from env if not set)
    api_key: str | None = None
    api_base: str | None = None
    
    # Model-specific options
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    
    # Retry configuration
    num_retries: int = 3
    timeout: float = 120.0


@dataclass
class ToolCall:
    """Represents a tool call from the model."""
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    """Response from LLM."""
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    
    # Usage stats
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class StreamChunk:
    """A chunk from streaming response."""
    type: str  # "content" or "tool_call"
    content: str | None = None
    tool_call: dict | None = None


class LLMProvider:
    """Unified LLM provider using LiteLLM.
    
    Supports multiple providers with auto-detection from environment:
    - OpenAI: gpt-4o, gpt-4-turbo (OPENAI_API_KEY, OPENAI_BASE_URL)
    - Anthropic: claude-3-opus, claude-3-sonnet (ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL)
    - Google: gemini-pro, gemini-1.5-pro (GOOGLE_API_KEY)
    - DashScope/Qwen: qwen-turbo, qwen-plus, qwen-max (DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL)
    - DeepSeek: deepseek-chat, deepseek-coder (DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL)
    - Ollama: ollama/llama3, ollama/qwen2.5-coder (OLLAMA_BASE_URL)
    - Azure OpenAI: azure/deployment-name (AZURE_API_KEY, AZURE_API_BASE)
    """
    
    # Provider detection patterns and their env var prefixes
    PROVIDER_CONFIG = {
        "openai": {
            "prefixes": ["gpt-", "o1-", "o3-"],
            "env_prefix": "OPENAI",
        },
        "anthropic": {
            "prefixes": ["claude-"],
            "env_prefix": "ANTHROPIC",
        },
        "google": {
            "prefixes": ["gemini-"],
            "env_prefix": "GOOGLE",
        },
        "dashscope": {
            # Support qwen, qwen2, qwen2.5, qwen3 series
            "prefixes": ["qwen-", "qwen/", "qwen2", "qwen3"],
            "env_prefix": "DASHSCOPE",
            # DashScope uses OpenAI-compatible API, need openai/ prefix for LiteLLM
            "litellm_prefix": "openai/",
        },
        "deepseek": {
            "prefixes": ["deepseek-", "deepseek/"],
            "env_prefix": "DEEPSEEK",
        },
        "ollama": {
            "prefixes": ["ollama/"],
            "env_prefix": "OLLAMA",
        },
        "azure": {
            "prefixes": ["azure/"],
            "env_prefix": "AZURE",
        },
        "groq": {
            "prefixes": ["groq/"],
            "env_prefix": "GROQ",
        },
        "together": {
            "prefixes": ["together/"],
            "env_prefix": "TOGETHER",
        },
    }
    
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        
        # Configure LiteLLM
        litellm.drop_params = True  # Drop unsupported params for each provider
        
        # Detect provider and load config from env
        self.provider = self._detect_provider()
        self._load_provider_config()
    
    def _detect_provider(self) -> str:
        """Detect provider from model name."""
        model = self.config.model.lower()
        
        for provider, cfg in self.PROVIDER_CONFIG.items():
            if any(model.startswith(p) for p in cfg["prefixes"]):
                return provider
        
        # Default to openai for unknown models
        return "openai"
    
    def _load_provider_config(self) -> None:
        """Load provider-specific configuration from environment."""
        provider_cfg = self.PROVIDER_CONFIG.get(self.provider, {})
        env_prefix = provider_cfg.get("env_prefix", "OPENAI")
        
        # Load from env if not explicitly set
        if not self.config.api_key:
            self.config.api_key = os.getenv(f"{env_prefix}_API_KEY")
        
        if not self.config.api_base:
            self.config.api_base = (
                os.getenv(f"{env_prefix}_BASE_URL") or 
                os.getenv(f"{env_prefix}_API_BASE")
            )
        
        # Set LiteLLM API keys based on provider
        if self.config.api_key:
            if self.provider == "anthropic":
                litellm.anthropic_key = self.config.api_key
            elif self.provider == "google":
                litellm.vertex_key = self.config.api_key
            else:
                # OpenAI-compatible providers (including DashScope)
                litellm.openai_key = self.config.api_key
    
    def _get_model_name(self) -> str:
        """Get the model name for LiteLLM, with provider prefix if needed."""
        model = self.config.model
        provider_cfg = self.PROVIDER_CONFIG.get(self.provider, {})
        
        # Some providers need a litellm prefix for OpenAI-compatible API
        litellm_prefix = provider_cfg.get("litellm_prefix", "")
        
        if litellm_prefix and not model.startswith(litellm_prefix):
            # For DashScope, we use openai/ prefix with custom base URL
            return f"{litellm_prefix}{model}"
        
        return model
    
    def _build_params(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Build parameters for LiteLLM call."""
        params = {
            "model": self._get_model_name(),
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "num_retries": self.config.num_retries,
        }
        
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"
        
        # Set API base for custom endpoints
        if self.config.api_base:
            params["api_base"] = self.config.api_base
        
        # Set API key if available
        if self.config.api_key:
            params["api_key"] = self.config.api_key
        
        if self.config.top_p is not None:
            params["top_p"] = self.config.top_p
        
        if self.config.frequency_penalty is not None:
            params["frequency_penalty"] = self.config.frequency_penalty
        
        if self.config.presence_penalty is not None:
            params["presence_penalty"] = self.config.presence_penalty
        
        return params
    
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None
    ) -> LLMResponse:
        """Get a completion from the model."""
        params = self._build_params(messages, tools)
        
        response = await acompletion(**params)
        
        return self._parse_response(response)
    
    async def stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream a completion from the model."""
        params = self._build_params(messages, tools)
        params["stream"] = True
        
        response = await acompletion(**params)
        
        tool_calls: dict[int, dict] = {}
        
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            
            if not delta:
                continue
            
            # Handle content
            if delta.content:
                yield StreamChunk(type="content", content=delta.content)
            
            # Handle tool calls
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function else "",
                            "arguments": ""
                        }
                    
                    if tc.id:
                        tool_calls[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments
        
        # Yield completed tool calls
        for tc in tool_calls.values():
            try:
                tc["arguments"] = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                tc["arguments"] = {}
            
            yield StreamChunk(type="tool_call", tool_call=tc)
    
    def _parse_response(self, response) -> LLMResponse:
        """Parse LiteLLM response into LLMResponse."""
        choice = response.choices[0]
        message = choice.message
        
        # Parse tool calls
        tool_calls = []
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args
                ))
        
        # Get usage stats
        usage = response.usage if hasattr(response, 'usage') else None
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0
        )
    
    def get_provider_info(self) -> dict:
        """Get current provider configuration info."""
        return {
            "provider": self.provider,
            "model": self.config.model,
            "api_base": self.config.api_base or "(default)",
            "api_key_set": bool(self.config.api_key),
        }
    
    @staticmethod
    def list_models() -> dict[str, list[str]]:
        """List commonly used models by provider."""
        return {
            "OpenAI": [
                "gpt-4o",
                "gpt-4o-mini", 
                "gpt-4-turbo",
                "o1-preview",
                "o1-mini",
            ],
            "Anthropic": [
                "claude-sonnet-4-20250514",
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307",
            ],
            "DashScope (Qwen)": [
                "qwen-turbo",
                "qwen-plus", 
                "qwen-max",
                "qwen-max-longcontext",
                "qwen-coder-plus",
                "qwen2.5-72b-instruct",
                "qwen2.5-coder-32b-instruct",
                "qwen3-max",
                "qwen3-235b-a22b",
            ],
            "Google": [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-pro",
            ],
            "DeepSeek": [
                "deepseek-chat",
                "deepseek-coder",
            ],
            "Ollama (local)": [
                "ollama/llama3",
                "ollama/mistral",
                "ollama/codellama",
                "ollama/qwen2.5-coder",
            ],
        }
    
    @staticmethod
    def get_env_template() -> str:
        """Get a template for .env file configuration."""
        return """# OmniEmployee LLM Configuration
# Uncomment and configure the providers you want to use

# === OpenAI ===
# OPENAI_API_KEY=sk-xxx
# OPENAI_BASE_URL=https://api.openai.com/v1

# === Anthropic ===
# ANTHROPIC_API_KEY=sk-ant-xxx
# ANTHROPIC_BASE_URL=https://api.anthropic.com

# === DashScope (Qwen) ===
# DASHSCOPE_API_KEY=sk-xxx
# DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# === DeepSeek ===
# DEEPSEEK_API_KEY=sk-xxx
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# === Google (Gemini) ===
# GOOGLE_API_KEY=xxx

# === Ollama (local) ===
# OLLAMA_BASE_URL=http://localhost:11434

# === Azure OpenAI ===
# AZURE_API_KEY=xxx
# AZURE_API_BASE=https://your-resource.openai.azure.com

# === Groq ===
# GROQ_API_KEY=xxx

# === Together AI ===
# TOGETHER_API_KEY=xxx

# === Default Model ===
# MODEL=qwen-plus
# TEMPERATURE=0.7
# MAX_ITERATIONS=50
"""
