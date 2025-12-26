"""Web content extraction tool using Tavily Extract API."""

import os
from src.omniemployee.tools.base import BaseTool, ToolResult, ToolResultStatus


class WebExtractTool(BaseTool):
    """Extract content from URLs using Tavily Extract API."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
    
    @property
    def name(self) -> str:
        return "web_extract"
    
    @property
    def description(self) -> str:
        return """Extract full content from one or more URLs using Tavily Extract API.
Use this to read the actual content of web pages found via web_search.
Supports extracting text, markdown, and images from URLs."""
    
    @property
    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to extract content from. For multiple URLs, call this tool multiple times."
                },
                "extract_depth": {
                    "type": "string",
                    "description": "Extraction depth: 'basic' for quick extraction, 'advanced' for more thorough. Default: basic."
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to include image URLs. Default: false."
                }
            },
            "required": ["url"],
            "additionalProperties": False
        }
    
    async def execute(
        self,
        url: str,
        extract_depth: str = "basic",
        include_images: bool = False
    ) -> ToolResult:
        """Extract content from URL using Tavily Extract API."""
        if not self.api_key:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="TAVILY_API_KEY not set. Please set the environment variable or provide api_key."
            )
        
        if not url:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="No URL provided."
            )
        
        # Validate extract_depth
        if extract_depth not in ("basic", "advanced"):
            extract_depth = "basic"
        
        try:
            from tavily import TavilyClient
        except ImportError:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error="tavily-python not installed. Run: pip install tavily-python"
            )
        
        try:
            client = TavilyClient(api_key=self.api_key)
            
            response = client.extract(
                urls=[url],
                include_images=include_images,
                extract_depth=extract_depth,
                format="markdown"
            )
            
            output = self._format_results(response, include_images)
            
            successful = len(response.get("results", []))
            failed = len(response.get("failed_results", []))
            
            return ToolResult(
                status=ToolResultStatus.SUCCESS,
                output=output,
                metadata={
                    "url": url,
                    "successful": successful > 0,
                    "failed": failed > 0
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ToolResultStatus.ERROR,
                error=f"Extraction failed: {str(e)}"
            )
    
    def _format_results(self, response: dict, include_images: bool) -> str:
        """Format extraction results into readable output."""
        lines = []
        
        results = response.get("results", [])
        failed = response.get("failed_results", [])
        
        if not results and not failed:
            return "No content extracted."
        
        lines.append(f"## Extracted Content ({len(results)} successful, {len(failed)} failed)")
        lines.append("")
        
        for i, result in enumerate(results, 1):
            url = result.get("url", "Unknown URL")
            content = result.get("raw_content", "")
            
            lines.append(f"### {i}. {url}")
            lines.append("")
            
            if content:
                # Truncate very long content
                max_len = 8000
                if len(content) > max_len:
                    lines.append(content[:max_len])
                    lines.append(f"\n... [Content truncated, total {len(content)} characters]")
                else:
                    lines.append(content)
            else:
                lines.append("_No content extracted_")
            
            lines.append("")
            
            if include_images and result.get("images"):
                lines.append("**Images:**")
                for img in result["images"][:10]:
                    lines.append(f"- {img}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        if failed:
            lines.append("## Failed Extractions")
            lines.append("")
            for fail in failed:
                url = fail.get("url", "Unknown")
                error = fail.get("error", "Unknown error")
                lines.append(f"- {url}: {error}")
            lines.append("")
        
        return "\n".join(lines)

