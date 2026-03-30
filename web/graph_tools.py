"""人物关系 + 全书知识图谱 tool 统一入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from . import cast_store
from . import story_knowledge_store


def execute_tool(root: Path, slug: str, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name.startswith("cast_"):
        return cast_store.execute_tool(root, slug, name, arguments)
    return story_knowledge_store.execute_tool(root, slug, name, arguments)
