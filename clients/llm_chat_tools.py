"""
编务对话：带人物关系网 tool 的多轮调用（Anthropic Messages / OpenAI chat.completions）。
返回 { reply, tools } 供前端展示工具交互感。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import httpx

from ..config import Config
from ..web.cast_store import tool_result_json
from ..web.graph_tools import execute_tool
from ..web.graph_tool_defs import ANTHROPIC_GRAPH_TOOLS, openai_graph_tools

logger = logging.getLogger("aitext.clients.llm_chat_tools")


def _split_messages(msgs: List[Dict[str, str]]) -> tuple[str, List[Dict[str, Any]]]:
    system_parts: List[str] = []
    rest: List[Dict[str, Any]] = []
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system_parts.append(str(content))
        else:
            rest.append({"role": role, "content": str(content)})
    return "\n\n".join(system_parts).strip(), rest


def _anthropic_extract_text(content: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for block in content:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts).strip()


def _tool_event(name: str, inp: Dict[str, Any], res: Dict[str, Any]) -> Dict[str, Any]:
    ok = bool(res.get("ok", True))
    detail = ""
    if not ok:
        detail = str(res.get("error", "失败"))[:220]
    elif name == "story_upsert_chapter_summary":
        cid = res.get("chapter_id") or inp.get("chapter_id", "?")
        detail = f"第{cid}章叙事已同步"
    elif name == "story_set_premise_lock":
        detail = "梗概锁定已写入"
    elif name == "story_get_snapshot":
        detail = "已读取叙事/章摘要快照"
    elif name == "kg_upsert_fact":
        fid = res.get("fact_id") or inp.get("id") or ""
        detail = f"三元组已写入 {fid}" if fid else "三元组已写入"
    elif name == "kg_remove_fact":
        detail = "三元组已删除"
    elif name == "kg_search_facts":
        facts = res.get("facts") or []
        detail = f"检索到 {len(facts)} 条事实"
    elif name == "cast_search":
        cnt = res.get("counts") or {}
        detail = (
            f"人物 {cnt.get('characters', '?')} · 边 {cnt.get('relationships', '?')} · "
            f"人物事件 {cnt.get('character_events', '?')} · 边事件 {cnt.get('relationship_events', '?')}"
        )
    elif name == "cast_get_snapshot":
        st = res.get("stats") or {}
        detail = (
            f"快照 {st.get('characters', '?')}人 · {st.get('relationships', '?')}边 · "
            f"人物事件{st.get('character_events', '?')} · 边事件{st.get('relationship_events', '?')}"
        )
    elif name == "cast_upsert_story_event":
        scope = res.get("scope") or inp.get("scope", "")
        pv = str(res.get("preview") or "")[:100]
        eid = res.get("event_id") or ""
        detail = f"{scope} {eid} {pv}".strip()[:220]
    elif name == "cast_remove_story_event":
        detail = f"删事件 {res.get('removed_event_id', '')}"[:220]
    elif name == "cast_upsert_character":
        detail = f"人物 {res.get('character_id') or inp.get('id', '?')} 已写入"
    elif name == "cast_remove_character":
        detail = f"已删人物 {res.get('id', '')}"
    elif name == "cast_upsert_relationship":
        lab = str(inp.get("label") or "")[:40]
        rid = res.get("relationship_id") or inp.get("id") or "?"
        detail = (f"关系 {rid} " + (f"「{lab}」" if lab else "") + " 已写入").strip()[:220]
    elif name == "cast_remove_relationship":
        detail = f"已删关系 {res.get('id', '')}"
    elif name.startswith("cast_"):
        detail = "关系图已更新"
    else:
        detail = "完成"
    return {"name": name, "ok": ok, "detail": detail}


def run_chat_with_cast_tools(
    root: Path, slug: str, base_messages: List[Dict[str, str]]
) -> Optional[Dict[str, Any]]:
    """多轮 tool + 最终回复；返回 { reply: str, tools: list }。"""
    for ev in iter_chat_tool_events(root, slug, base_messages):
        k = ev.get("kind")
        if k == "final":
            return {"reply": ev.get("reply") or "", "tools": list(ev.get("tools") or [])}
        if k == "error":
            return None
    return None


def iter_chat_tool_events(
    root: Path, slug: str, base_messages: List[Dict[str, str]]
) -> Iterator[Dict[str, Any]]:
    """供 SSE 流式输出：先多次 yield 工具事件（类 thinking），最后 yield final。"""
    provider = (Config.LLM_PROVIDER or "anthropic").strip().lower()
    if provider == "ark":
        yield from _iter_openai_tool_events(root, slug, base_messages)
    else:
        yield from _iter_anthropic_tool_events(root, slug, base_messages)


def _iter_anthropic_tool_events(
    root: Path, slug: str, base_messages: List[Dict[str, str]]
) -> Iterator[Dict[str, Any]]:
    api_key = Config.ANTHROPIC_API_KEY
    base = Config.ANTHROPIC_BASE_URL.rstrip("/")
    if base.endswith("/v1/messages"):
        url = base
    else:
        url = base + "/v1/messages"
    model = Config.ANTHROPIC_MODEL
    if not api_key or not model:
        yield {"kind": "error", "message": "Anthropic 未配置"}
        return

    system_text, api_messages = _split_messages(base_messages)
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    tool_events: List[Dict[str, Any]] = []
    max_rounds = 8
    for _ in range(max_rounds):
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": 8192,
            "messages": api_messages,
            "tools": ANTHROPIC_GRAPH_TOOLS,
        }
        if system_text:
            payload["system"] = system_text

        try:
            with httpx.Client(timeout=Config.ARK_TIMEOUT) as client:
                r = client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.exception("anthropic tool request failed: %s", e)
            yield {"kind": "error", "message": str(e)[:500]}
            return

        stop = data.get("stop_reason")
        content = data.get("content") or []

        if stop == "end_turn":
            text = _anthropic_extract_text(content)
            yield {"kind": "final", "reply": text or "", "tools": tool_events}
            return

        if stop == "tool_use" or any(b.get("type") == "tool_use" for b in content):
            api_messages.append({"role": "assistant", "content": content})
            tool_blocks: List[Dict[str, Any]] = []
            for block in content:
                if block.get("type") != "tool_use":
                    continue
                tid = block.get("id")
                name = block.get("name")
                inp = block.get("input") or {}
                if not tid or not name:
                    continue
                args = inp if isinstance(inp, dict) else {}
                res = execute_tool(root, slug, str(name), args)
                ev = _tool_event(str(name), args, res)
                tool_events.append(ev)
                yield {"kind": "tool", **ev}
                tool_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": tool_result_json(str(name), res),
                    }
                )
            if not tool_blocks:
                text = _anthropic_extract_text(content)
                yield {"kind": "final", "reply": text or "", "tools": tool_events}
                return
            api_messages.append({"role": "user", "content": tool_blocks})
            continue

        text = _anthropic_extract_text(content)
        yield {"kind": "final", "reply": text or "", "tools": tool_events}
        return

    logger.warning("anthropic tool loop max rounds")
    yield {"kind": "error", "message": "工具轮次过多，已中止"}


def _iter_openai_tool_events(
    root: Path, slug: str, base_messages: List[Dict[str, str]]
) -> Iterator[Dict[str, Any]]:
    api_key = Config.ARK_API_KEY
    url = Config.ARK_BASE_URL.strip()
    model = Config.ARK_MODEL
    if not api_key or not model:
        yield {"kind": "error", "message": "ARK/OpenAI 兼容未配置"}
        return

    oa_messages: List[Dict[str, Any]] = []
    for m in base_messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            oa_messages.append({"role": "system", "content": str(content)})
        else:
            oa_messages.append({"role": role, "content": str(content)})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    tools = openai_graph_tools()
    tool_events: List[Dict[str, Any]] = []
    max_rounds = 8

    for _ in range(max_rounds):
        payload: Dict[str, Any] = {
            "model": model,
            "messages": oa_messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        try:
            with httpx.Client(timeout=Config.ARK_TIMEOUT) as client:
                r = client.post(url, headers=headers, json=payload)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.exception("openai-style tool request failed: %s", e)
            yield {"kind": "error", "message": str(e)[:500]}
            return

        choices = data.get("choices") or []
        if not choices:
            yield {"kind": "error", "message": "模型无有效 choices"}
            return
        msg = choices[0].get("message") or {}
        tool_calls = msg.get("tool_calls")
        text = msg.get("content") or ""

        if tool_calls:
            oa_messages.append(
                {
                    "role": "assistant",
                    "content": text if text else None,
                    "tool_calls": tool_calls,
                }
            )
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                raw_args = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                res = execute_tool(root, slug, str(name), args)
                ev = _tool_event(str(name), args, res)
                tool_events.append(ev)
                yield {"kind": "tool", **ev}
                oa_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": tool_result_json(str(name), res),
                    }
                )
            continue

        if isinstance(text, str) and text.strip():
            yield {"kind": "final", "reply": text.strip(), "tools": tool_events}
            return
        yield {"kind": "final", "reply": "", "tools": tool_events}
        return

    yield {"kind": "error", "message": "工具轮次过多，已中止"}
