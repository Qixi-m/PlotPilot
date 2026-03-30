"""合并：人物关系工具 + 全书知识/章摘要/三元组工具。"""
from __future__ import annotations

from typing import Any, Dict, List

from .cast_tool_defs import ANTHROPIC_CAST_TOOLS, openai_cast_tools

ANTHROPIC_STORY_KG_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "story_get_snapshot",
        "description": "读取全书梗概锁定、各章章摘要与知识三元组。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "story_set_premise_lock",
        "description": "设置或更新「梗概锁定」文本，用于防止剧情跑篇、偏离主线。",
        "input_schema": {
            "type": "object",
            "properties": {
                "premise_lock": {"type": "string", "description": "全书核心梗概与不可违背的设定要点"},
            },
            "required": ["premise_lock"],
        },
    },
    {
        "name": "story_upsert_chapter_summary",
        "description": "按章号写入或更新章级剧情摘要、大纲下子段落/节拍、关键事件、埋线、一致性；人物关系仍以 cast_* 为准。",
        "input_schema": {
            "type": "object",
            "properties": {
                "chapter_id": {"type": "integer", "description": "章号，从 1 起"},
                "summary": {"type": "string", "description": "本章剧情摘要（章末总结）"},
                "beat_sections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可选，本章内子段落/节拍标题与要点，每元素一条，对齐大纲细目",
                },
                "key_events": {"type": "string", "description": "关键情节点（可与人物图谱姓名对齐）"},
                "open_threads": {"type": "string", "description": "未解/埋线"},
                "consistency_note": {"type": "string", "description": "与大纲/前章的一致性说明"},
                "sync_status": {
                    "type": "string",
                    "description": "可选：draft / synced / stale；工具写入可省略，默认 synced",
                },
            },
            "required": ["chapter_id", "summary"],
        },
    },
    {
        "name": "kg_upsert_fact",
        "description": "新增或更新一条知识三元组（主语—谓词—宾语），可标注所属章。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "可选，稳定 id"},
                "subject": {"type": "string"},
                "predicate": {"type": "string", "description": "关系，如 持有、位于、敌对"},
                "object": {"type": "string", "description": "客体或对象"},
                "chapter_id": {"type": "integer", "description": "可选，出处章号"},
                "note": {"type": "string"},
            },
            "required": ["subject", "predicate", "object"],
        },
    },
    {
        "name": "kg_remove_fact",
        "description": "按 id 删除一条知识三元组。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "kg_search_facts",
        "description": "按关键词检索知识三元组。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        },
    },
]

ANTHROPIC_GRAPH_TOOLS = ANTHROPIC_CAST_TOOLS + ANTHROPIC_STORY_KG_TOOLS


def _openai_from_anthropic(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in specs:
        name = t["name"]
        desc = t["description"]
        params = t.get("input_schema") or {"type": "object", "properties": {}}
        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            }
        )
    return out


def openai_graph_tools() -> List[Dict[str, Any]]:
    return openai_cast_tools() + _openai_from_anthropic(ANTHROPIC_STORY_KG_TOOLS)
