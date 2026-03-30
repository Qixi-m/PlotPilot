"""人物关系网：供 LLM 使用的 tool 定义（Anthropic / OpenAI 兼容）。"""

from __future__ import annotations

from typing import Any, Dict, List

# Anthropic Messages API: name + description + input_schema
ANTHROPIC_CAST_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "cast_search",
        "description": "按关键词检索人物与关系（名称、别名、角色、关系标签等）。query 为空则返回全部摘要。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，可为空表示列出全部",
                }
            },
            "required": [],
        },
    },
    {
        "name": "cast_get_snapshot",
        "description": "读取完整人物表与关系边列表（数据量大时慎用，优先用 cast_search）。",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "cast_upsert_character",
        "description": "新增或更新一个人物节点。id 可省略则自动生成。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "稳定 id，英文/数字/中文，不含空格"},
                "name": {"type": "string", "description": "姓名"},
                "aliases": {"type": "array", "items": {"type": "string"}, "description": "别名"},
                "role": {"type": "string", "description": "故事角色定位"},
                "traits": {"type": "string", "description": "性格特点"},
                "note": {"type": "string", "description": "备注"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "cast_remove_character",
        "description": "按 id 删除人物及其关联的所有关系边。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "cast_upsert_relationship",
        "description": "新增或更新一条人物关系（有向边：source → target）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "关系 id，可省略则自动生成"},
                "source_id": {"type": "string", "description": "起点人物 id"},
                "target_id": {"type": "string", "description": "终点人物 id"},
                "label": {"type": "string", "description": "关系类型，如 师徒、夫妻、敌对"},
                "note": {"type": "string"},
                "directed": {"type": "boolean", "description": "默认 true"},
            },
            "required": ["source_id", "target_id"],
        },
    },
    {
        "name": "cast_remove_relationship",
        "description": "按 id 删除一条关系。",
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "name": "cast_upsert_story_event",
        "description": "在人物节点或一条关系边上追加/更新「具体剧情事件」（里程碑、共同经历）。ReAct：先 cast_search 或 cast_get_snapshot 取得 host_id（人物 id 或关系 id），再写入；importance=key 表示关键转折。",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "description": "character=挂在人物上；relationship=挂在某条关系边上",
                    "enum": ["character", "relationship"],
                },
                "host_id": {"type": "string", "description": "人物 id，或关系边的 id"},
                "event_id": {"type": "string", "description": "可选，更新已有事件时填；省略则新建并自动生成 id"},
                "summary": {"type": "string", "description": "事件一句话描述"},
                "chapter_id": {"type": "integer", "description": "可选，发生章节"},
                "importance": {
                    "type": "string",
                    "description": "normal 或 key",
                    "enum": ["normal", "key"],
                },
            },
            "required": ["scope", "host_id", "summary"],
        },
    },
    {
        "name": "cast_remove_story_event",
        "description": "删除人物或关系上的一条事件（按 event_id）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["character", "relationship"]},
                "host_id": {"type": "string"},
                "event_id": {"type": "string"},
            },
            "required": ["scope", "host_id", "event_id"],
        },
    },
]


def openai_cast_tools() -> List[Dict[str, Any]]:
    """OpenAI / 火山方舟 chat.completions 的 tools 列表。"""
    out: List[Dict[str, Any]] = []
    for t in ANTHROPIC_CAST_TOOLS:
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
