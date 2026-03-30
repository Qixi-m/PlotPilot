"""人物关系网：cast_graph.json 读写、检索、供工具调用执行。"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..story.engine import load_cast_graph, project_paths, save_cast_graph
from ..story.models import CastCharacter, CastGraph, CastRelationship, CastStoryEvent

logger = logging.getLogger("aitext.web.cast_store")
from .vector_memory import upsert_docs

_ID_SAFE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff][-a-zA-Z0-9_\u4e00-\u9fff]{0,79}$")

_locks: Dict[str, threading.Lock] = {}
_registry = threading.Lock()


def _cast_lock(slug: str) -> threading.Lock:
    with _registry:
        if slug not in _locks:
            _locks[slug] = threading.Lock()
        return _locks[slug]


def _graph_path(root: Path) -> Path:
    return project_paths(root)["cast_graph"]


def load_or_empty(root: Path) -> CastGraph:
    p = _graph_path(root)
    g = load_cast_graph(p)
    if g is None:
        return CastGraph()
    return g


def save(root: Path, graph: CastGraph) -> None:
    save_cast_graph(_graph_path(root), graph)


def compact_for_prompt(graph: CastGraph, max_chars: int = 12000) -> str:
    """注入 system 的简短文本。"""
    lines: List[str] = []
    ev_c = sum(len(c.story_events) for c in graph.characters)
    ev_r = sum(len(r.story_events) for r in graph.relationships)
    lines.append(
        f"【人物关系网】共 {len(graph.characters)} 人，{len(graph.relationships)} 条关系；"
        f"人物侧事件 {ev_c} 条，关系侧事件 {ev_r} 条。"
        "可用 cast_get_snapshot / cast_search 读取；用 cast_upsert_story_event 写入具体事件（ReAct 时工具结果会摘要展示）。"
    )
    for c in graph.characters[:80]:
        als = " / ".join(c.aliases) if c.aliases else ""
        lines.append(f"- [{c.id}] {c.name}" + (f"（别名:{als}）" if als else "") + f" 角色:{c.role or '—'}")
        key_ev = [e for e in c.story_events if (e.importance or "").lower() == "key"][:3]
        rest_ev = [e for e in c.story_events if (e.importance or "").lower() != "key"][:2]
        for e in key_ev + rest_ev:
            ch = f"第{e.chapter_id}章" if e.chapter_id else "未标章"
            t = (e.summary or "").replace("\n", " ").strip()
            if t:
                lines.append(f"    · 事件[{e.id}] {ch} {t[:120]}{'…' if len(t) > 120 else ''}")
    for r in graph.relationships[:120]:
        lines.append(f"- 关系 {r.source_id} —[{r.label or '关系'}]→ {r.target_id}")
        for e in (r.story_events[:4] if r.story_events else []):
            ch = f"第{e.chapter_id}章" if e.chapter_id else "未标章"
            t = (e.summary or "").replace("\n", " ").strip()
            if t:
                lines.append(f"    · 共同经历[{e.id}] {ch} {t[:120]}{'…' if len(t) > 120 else ''}")
    s = "\n".join(lines)
    return s[:max_chars]


def search(graph: CastGraph, query: str) -> Tuple[List[CastCharacter], List[CastRelationship]]:
    q = (query or "").strip().lower()
    if not q:
        return list(graph.characters), list(graph.relationships)
    ch: List[CastCharacter] = []
    for c in graph.characters:
        ev_blob = " ".join(
            [f"{e.id} {(e.summary or '')}" for e in c.story_events]
            + ([str(e.chapter_id)] if any(e.chapter_id for e in c.story_events) else [])
        )
        blob = " ".join([c.name, c.role, c.traits, c.note, ev_blob] + c.aliases).lower()
        if q in blob:
            ch.append(c)
    rel: List[CastRelationship] = []
    for r in graph.relationships:
        ev_blob = " ".join([f"{e.id} {(e.summary or '')}" for e in r.story_events])
        blob = " ".join([r.label, r.note, r.source_id, r.target_id, ev_blob]).lower()
        if q in blob:
            rel.append(r)
    return ch, rel


def _ensure_id(s: str) -> bool:
    return bool(s and _ID_SAFE.match(s))


def execute_tool(root: Path, slug: str, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行单条 tool，返回可 JSON 序列化的结果。"""
    with _cast_lock(slug):
        g = load_or_empty(root)
        try:
            if name == "cast_search":
                q = str(arguments.get("query", "") or "")
                ch, rel = search(g, q)
                ce = sum(len(c.story_events) for c in ch)
                re = sum(len(r.story_events) for r in rel)
                return {
                    "ok": True,
                    "query": q,
                    "characters": [c.model_dump() for c in ch[:50]],
                    "relationships": [r.model_dump() for r in rel[:80]],
                    "counts": {
                        "characters": len(ch),
                        "relationships": len(rel),
                        "character_events": ce,
                        "relationship_events": re,
                    },
                }

            if name == "cast_get_snapshot":
                ce = sum(len(c.story_events) for c in g.characters)
                re = sum(len(r.story_events) for r in g.relationships)
                return {
                    "ok": True,
                    "characters": [c.model_dump() for c in g.characters],
                    "relationships": [r.model_dump() for r in g.relationships],
                    "stats": {
                        "characters": len(g.characters),
                        "relationships": len(g.relationships),
                        "character_events": ce,
                        "relationship_events": re,
                    },
                }

            if name == "cast_upsert_character":
                cid = str(arguments.get("id", "") or "").strip()
                name_ = str(arguments.get("name", "") or "").strip()
                if not name_:
                    return {"ok": False, "error": "name 必填"}
                if not cid:
                    cid = f"c_{uuid.uuid4().hex[:10]}"
                if not _ensure_id(cid):
                    return {"ok": False, "error": "id 含非法字符"}
                aliases = arguments.get("aliases")
                if not isinstance(aliases, list):
                    aliases = []
                aliases = [str(a).strip() for a in aliases if str(a).strip()][:20]
                role = str(arguments.get("role", "") or "")[:500]
                traits = str(arguments.get("traits", "") or "")[:2000]
                note = str(arguments.get("note", "") or "")[:4000]
                found = False
                prev_events: List[CastStoryEvent] = []
                for i, c in enumerate(g.characters):
                    if c.id == cid:
                        prev_events = list(c.story_events)
                        g.characters[i] = CastCharacter(
                            id=cid,
                            name=name_,
                            aliases=aliases,
                            role=role,
                            traits=traits,
                            note=note,
                            story_events=prev_events,
                        )
                        found = True
                        break
                if not found:
                    g.characters.append(
                        CastCharacter(
                            id=cid,
                            name=name_,
                            aliases=aliases,
                            role=role,
                            traits=traits,
                            note=note,
                            story_events=[],
                        )
                    )
                save(root, g)
                try:
                    blob = (
                        f"人物 {name_}\n"
                        f"ID：{cid}\n"
                        f"角色：{role}\n"
                        f"特征：{traits}\n"
                        f"备注：{note}\n"
                        f"别名：{', '.join(aliases)}"
                    )
                    upsert_docs(
                        root,
                        ids=[f"cast:character:{cid}"],
                        documents=[blob],
                        metadatas=[{"type": "cast_character", "id": cid, "name": name_}],
                    )
                except Exception:
                    logger.exception("vector upsert character failed")
                return {"ok": True, "character_id": cid, "action": "upserted"}

            if name == "cast_remove_character":
                cid = str(arguments.get("id", "") or "").strip()
                if not cid:
                    return {"ok": False, "error": "id 必填"}
                before = len(g.characters)
                g.characters = [c for c in g.characters if c.id != cid]
                g.relationships = [
                    r for r in g.relationships if r.source_id != cid and r.target_id != cid
                ]
                save(root, g)
                return {"ok": True, "removed": before - len(g.characters), "id": cid}

            if name == "cast_upsert_relationship":
                rid = str(arguments.get("id", "") or "").strip()
                sid = str(arguments.get("source_id", "") or "").strip()
                tid = str(arguments.get("target_id", "") or "").strip()
                if not sid or not tid:
                    return {"ok": False, "error": "source_id 与 target_id 必填"}
                if not rid:
                    rid = f"r_{uuid.uuid4().hex[:10]}"
                if not _ensure_id(rid) or not _ensure_id(sid) or not _ensure_id(tid):
                    return {"ok": False, "error": "id 含非法字符"}
                label = str(arguments.get("label", "") or "")[:200]
                note = str(arguments.get("note", "") or "")[:2000]
                directed = bool(arguments.get("directed", True))
                found = False
                prev_ev: List[CastStoryEvent] = []
                for i, r in enumerate(g.relationships):
                    if r.id == rid:
                        prev_ev = list(r.story_events)
                        g.relationships[i] = CastRelationship(
                            id=rid,
                            source_id=sid,
                            target_id=tid,
                            label=label,
                            note=note,
                            directed=directed,
                            story_events=prev_ev,
                        )
                        found = True
                        break
                if not found:
                    g.relationships.append(
                        CastRelationship(
                            id=rid,
                            source_id=sid,
                            target_id=tid,
                            label=label,
                            note=note,
                            directed=directed,
                            story_events=[],
                        )
                    )
                save(root, g)
                try:
                    blob = (
                        f"关系 {label}\n"
                        f"ID：{rid}\n"
                        f"来源：{sid}\n"
                        f"目标：{tid}\n"
                        f"备注：{note}\n"
                        f"有向：{directed}"
                    )
                    upsert_docs(
                        root,
                        ids=[f"cast:rel:{rid}"],
                        documents=[blob],
                        metadatas=[{"type": "cast_relationship", "id": rid, "label": label}],
                    )
                except Exception:
                    logger.exception("vector upsert relationship failed")
                return {"ok": True, "relationship_id": rid, "action": "upserted"}

            if name == "cast_remove_relationship":
                rid = str(arguments.get("id", "") or "").strip()
                if not rid:
                    return {"ok": False, "error": "id 必填"}
                before = len(g.relationships)
                g.relationships = [r for r in g.relationships if r.id != rid]
                save(root, g)
                return {"ok": True, "removed": before - len(g.relationships), "id": rid}

            if name == "cast_upsert_story_event":
                scope = str(arguments.get("scope", "") or "").strip().lower()
                host_id = str(arguments.get("host_id", "") or "").strip()
                summary = str(arguments.get("summary", "") or "").strip()
                if not summary:
                    return {"ok": False, "error": "summary 必填"}
                if scope not in ("character", "relationship"):
                    return {"ok": False, "error": "scope 须为 character 或 relationship"}
                if not host_id:
                    return {"ok": False, "error": "host_id 必填"}
                eid = str(arguments.get("event_id", "") or "").strip()
                if not eid:
                    eid = f"ev_{uuid.uuid4().hex[:10]}"
                if not _ensure_id(eid):
                    return {"ok": False, "error": "event_id 含非法字符"}
                ch_raw = arguments.get("chapter_id")
                chapter_id: Optional[int] = None
                if ch_raw is not None and str(ch_raw).strip() != "":
                    try:
                        chapter_id = int(ch_raw)
                        if chapter_id < 1:
                            chapter_id = None
                    except (TypeError, ValueError):
                        chapter_id = None
                importance = str(arguments.get("importance", "normal") or "normal").strip().lower()
                if importance not in ("normal", "key"):
                    importance = "normal"
                ev = CastStoryEvent(
                    id=eid,
                    summary=summary[:4000],
                    chapter_id=chapter_id,
                    importance=importance,
                )
                if scope == "character":
                    found = False
                    for i, c in enumerate(g.characters):
                        if c.id == host_id:
                            events = list(c.story_events)
                            replaced = False
                            for j, ex in enumerate(events):
                                if ex.id == eid:
                                    events[j] = ev
                                    replaced = True
                                    break
                            if not replaced:
                                events.append(ev)
                            g.characters[i] = CastCharacter(
                                id=c.id,
                                name=c.name,
                                aliases=c.aliases,
                                role=c.role,
                                traits=c.traits,
                                note=c.note,
                                story_events=events,
                            )
                            found = True
                            break
                    if not found:
                        return {"ok": False, "error": f"未找到人物 {host_id}"}
                else:
                    found = False
                    for i, r in enumerate(g.relationships):
                        if r.id == host_id:
                            events = list(r.story_events)
                            replaced = False
                            for j, ex in enumerate(events):
                                if ex.id == eid:
                                    events[j] = ev
                                    replaced = True
                                    break
                            if not replaced:
                                events.append(ev)
                            g.relationships[i] = CastRelationship(
                                id=r.id,
                                source_id=r.source_id,
                                target_id=r.target_id,
                                label=r.label,
                                note=r.note,
                                directed=r.directed,
                                story_events=events,
                            )
                            found = True
                            break
                    if not found:
                        return {"ok": False, "error": f"未找到关系 {host_id}"}
                save(root, g)
                try:
                    blob = f"事件 第{chapter_id or '—'}章\n范围：{scope}\n宿主：{host_id}\n摘要：{summary}"
                    upsert_docs(
                        root,
                        ids=[f"cast:event:{eid}"],
                        documents=[blob],
                        metadatas=[
                            {
                                "type": "cast_event",
                                "id": eid,
                                "scope": scope,
                                "host_id": host_id,
                                "chapter_id": chapter_id,
                            }
                        ],
                    )
                except Exception:
                    logger.exception("vector upsert story event failed")
                return {
                    "ok": True,
                    "event_id": eid,
                    "scope": scope,
                    "host_id": host_id,
                    "preview": summary[:220],
                }

            if name == "cast_remove_story_event":
                scope = str(arguments.get("scope", "") or "").strip().lower()
                host_id = str(arguments.get("host_id", "") or "").strip()
                eid = str(arguments.get("event_id", "") or "").strip()
                if scope not in ("character", "relationship"):
                    return {"ok": False, "error": "scope 须为 character 或 relationship"}
                if not host_id or not eid:
                    return {"ok": False, "error": "host_id 与 event_id 必填"}
                removed = False
                if scope == "character":
                    for i, c in enumerate(g.characters):
                        if c.id == host_id:
                            events = [e for e in c.story_events if e.id != eid]
                            if len(events) < len(c.story_events):
                                g.characters[i] = CastCharacter(
                                    id=c.id,
                                    name=c.name,
                                    aliases=c.aliases,
                                    role=c.role,
                                    traits=c.traits,
                                    note=c.note,
                                    story_events=events,
                                )
                                removed = True
                            break
                else:
                    for i, r in enumerate(g.relationships):
                        if r.id == host_id:
                            events = [e for e in r.story_events if e.id != eid]
                            if len(events) < len(r.story_events):
                                g.relationships[i] = CastRelationship(
                                    id=r.id,
                                    source_id=r.source_id,
                                    target_id=r.target_id,
                                    label=r.label,
                                    note=r.note,
                                    directed=r.directed,
                                    story_events=events,
                                )
                                removed = True
                            break
                if not removed:
                    return {"ok": False, "error": "未找到对应事件或 host"}
                save(root, g)
                return {"ok": True, "removed_event_id": eid}

            return {"ok": False, "error": f"未知工具: {name}"}
        except Exception as e:
            logger.exception("cast tool failed")
            return {"ok": False, "error": str(e)}


def tool_result_json(name: str, result: Dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)
