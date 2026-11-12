from .base import Tool, ToolResponse
from .context7 import Context7
from .deepwiki import DeepWiki
from .exa import Exa

REGISTRY: dict[str, type[Tool]] = {t.name: t for t in (Context7, DeepWiki, Exa)}

__all__ = ["REGISTRY", "Tool", "ToolResponse"]
