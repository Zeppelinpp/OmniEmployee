"""Web search tool using Tavily API for comprehensive web research."""

import os
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class WebSearchTool(BaseTool):
    """Search the web using Tavily API for real-time information."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return """Search the web for real-time information using Tavily API.
Use for finding current information, news, documentation, research papers, etc.
Returns structured results with titles, URLs, and content snippets."""

    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific and include relevant keywords.",
                },
                "search_depth": {
                    "type": "string",
                    "description": "Search depth: 'basic' for quick results, 'advanced' for more comprehensive search. Default: basic.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-10). Default: 5.",
                },
                "include_answer": {
                    "type": "boolean",
                    "description": "Whether to include a direct AI-generated answer. Default: false.",
                },
                "include_raw_content": {
                    "type": "boolean",
                    "description": "Whether to include raw page content (more tokens but more detail). Default: false.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        }

    async def execute(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 5,
        include_answer: bool = False,
        include_raw_content: bool = False,
    ) -> ToolResult:
        """Execute web search using Tavily API."""
        if not self.api_key:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="TAVILY_API_KEY not set. Please set the environment variable or provide api_key.",
            )

        # Validate search_depth
        if search_depth not in ("basic", "advanced"):
            search_depth = "basic"

        max_results = max(1, min(10, max_results))

        try:
            from tavily import TavilyClient
        except ImportError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="tavily-python not installed. Run: pip install tavily-python",
            )

        try:
            client = TavilyClient(api_key=self.api_key)

            search_params = {
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": include_answer,
                "include_raw_content": include_raw_content,
            }

            response = client.search(**search_params)

            output = self._format_results(response, include_answer, include_raw_content)

            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output,
                metadata={
                    "query": query,
                    "result_count": len(response.get("results", [])),
                    "search_depth": search_depth,
                },
            )

        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR, error=f"Search failed: {str(e)}"
            )

    def _format_results(
        self, response: dict, include_answer: bool, include_raw_content: bool
    ) -> str:
        """Format search results into readable output."""
        lines = []

        if include_answer and response.get("answer"):
            lines.append("## Direct Answer")
            lines.append(response["answer"])
            lines.append("")

        results = response.get("results", [])
        if not results:
            return "No results found."

        lines.append(f"## Search Results ({len(results)} found)")
        lines.append("")

        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            content = result.get("content", "")
            score = result.get("score", 0)

            lines.append(f"### {i}. {title}")
            lines.append(f"**URL:** {url}")
            lines.append(f"**Relevance:** {score:.2f}")
            lines.append("")

            if content:
                lines.append(content[:1000] + "..." if len(content) > 1000 else content)
                lines.append("")

            if include_raw_content and result.get("raw_content"):
                raw = result["raw_content"]
                lines.append("**Raw Content (truncated):**")
                lines.append(raw[:2000] + "..." if len(raw) > 2000 else raw)
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
