from .base import Tool, ToolResponse
from .context7 import Context7
from .deepwiki import DeepWiki
from .exa import Exa
from .exa_mcp import ExaMcp

REGISTRY: dict[str, type[Tool]] = {t.name: t for t in (Context7, DeepWiki, ExaMcp, Exa)}

__all__ = ["REGISTRY", "Context7", "DeepWiki", "Exa", "ExaMcp", "Tool", "ToolResponse"]
