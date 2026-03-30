"""全书知识图谱 + 章级摘要：novel_knowledge.json，供注入上下文与工具调用。"""
from __future__ import annotations

import logging
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import Config
from ..story.engine import (
    load_running_summary,
    load_story_knowledge,
    project_paths,
    save_story_knowledge,
)
from ..story.models import ChapterNarrativeEntry, KnowledgeTriple, StoryKnowledge
from .vector_memory import upsert_docs

logger = logging.getLogger("aitext.web.story_knowledge_store")

_ID_SAFE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff][-a-zA-Z0-9_\u4e00-\u9fff]{0,79}$")

_locks: Dict[str, threading.Lock] = {}
_registry = threading.Lock()


def _lock(slug: str) -> threading.Lock:
    with _registry:
        if slug not in _locks:
            _locks[slug] = threading.Lock()
        return _locks[slug]


def _path(root: Path) -> Path:
    return project_paths(root)["novel_knowledge"]


def load_or_empty(root: Path) -> StoryKnowledge:
    p = _path(root)
    sk = load_story_knowledge(p)
    if sk is None:
        return StoryKnowledge()
    return sk


def save(root: Path, data: StoryKnowledge) -> None:
    save_story_knowledge(_path(root), data)


def compact_for_prompt(root: Path, manifest_premise: str) -> str:
    """注入 system：梗概锁定 + 近章摘要 + 知识三元组 + 流水线滚动摘要补全。"""
    paths = project_paths(root)
    sk = load_or_empty(root)
    rs = load_running_summary(paths["summary"])

    premise = (sk.premise_lock or "").strip() or (manifest_premise or "").strip()
    lines: List[str] = []
    lines.append("【梗概锁定·编务须对齐】\n" + (premise[:2000] if premise else "（未填写梗概，请在侧栏「叙事」中补充 premise_lock）"))

    merged: Dict[int, ChapterNarrativeEntry] = {e.chapter_id: e for e in sk.chapters}
    for e in rs.entries:
        if e.chapter_id not in merged:
            merged[e.chapter_id] = ChapterNarrativeEntry(
                chapter_id=e.chapter_id,
                summary=e.summary,
            )
        elif not (merged[e.chapter_id].summary or "").strip() and (e.summary or "").strip():
            merged[e.chapter_id].summary = e.summary

    max_ch = Config.CHAT_CHAPTER_SUMMARY_MAX
    for cid in sorted(merged.keys())[-max_ch:]:
        ce = merged[cid]
        st = (ce.sync_status or "draft").strip()
        lines.append(
            f"【第{cid}章·上下文状态:{st}】{ce.summary[:1100] if ce.summary else '（尚无摘要）'}"
        )
        for bi, bline in enumerate((ce.beat_sections or [])[:16], 1):
            b = (bline or "").strip()
            if b:
                lines.append(f"  ·子段落/节拍{bi}：{b[:450]}")
        if (ce.key_events or "").strip():
            lines.append(f"  ·人物与关键事件：{ce.key_events[:650]}")
        if (ce.open_threads or "").strip():
            lines.append(f"  ·埋线：{ce.open_threads[:500]}")
        if (ce.consistency_note or "").strip():
            lines.append(f"  ·一致性：{ce.consistency_note[:500]}")

    if sk.facts:
        lines.append("【知识三元组（事实约束 · 勿与已写矛盾）】")
        for f in sk.facts:
            s = f"{f.subject} —{f.predicate}→ {f.object}"
            if f.chapter_id:
                s += f"（第{f.chapter_id}章）"
            if (f.note or "").strip():
                s += f" 注：{f.note[:200]}"
            lines.append(s)

    cap = Config.CHAT_NOVEL_KNOWLEDGE_MAX_CHARS
    text = "\n".join(lines)
    if len(text) <= cap:
        return text
    # 超长：保留前段（梗概锁定等）+ 后段（最近章摘要窗），避免百万字项目只剩开头
    head_n = min(3200, len(text) // 3)
    sep = "\n\n…（中间已截断；可精简侧栏叙事知识或提高 AITEXT_NOVEL_KNOWLEDGE_MAX_CHARS）…\n\n"
    rest = cap - head_n - len(sep)
    if rest < 800:
        return text[:cap]
    return text[:head_n] + sep + text[-rest:]


def search_facts(sk: StoryKnowledge, query: str) -> List[KnowledgeTriple]:
    q = (query or "").strip().lower()
    if not q:
        return list(sk.facts)
    out: List[KnowledgeTriple] = []
    for f in sk.facts:
        blob = " ".join([f.subject, f.predicate, f.object, f.note, str(f.chapter_id or "")]).lower()
        if q in blob:
            out.append(f)
    return out


def execute_tool(root: Path, slug: str, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    with _lock(slug):
        sk = load_or_empty(root)
        try:
            if name == "story_get_snapshot":
                return {
                    "ok": True,
                    "premise_lock": sk.premise_lock,
                    "chapters": [c.model_dump() for c in sk.chapters],
                    "facts": [f.model_dump() for f in sk.facts],
                }

            if name == "story_set_premise_lock":
                text = str(arguments.get("premise_lock", "") or "")[:8000]
                sk.premise_lock = text
                save(root, sk)
                try:
                    upsert_docs(
                        root,
                        ids=["story:premise_lock"],
                        documents=[f"梗概锁定\n{text}"],
                        metadatas=[{"type": "premise_lock"}],
                    )
                except Exception:
                    logger.exception("vector upsert premise_lock failed")
                return {"ok": True}

            if name == "story_upsert_chapter_summary":
                cid = int(arguments.get("chapter_id", 0) or 0)
                if cid < 1:
                    return {"ok": False, "error": "chapter_id 须 ≥1"}
                summary = str(arguments.get("summary", "") or "")[:12000]
                key_events = str(arguments.get("key_events", "") or "")[:6000]
                open_threads = str(arguments.get("open_threads", "") or "")[:4000]
                consistency_note = str(arguments.get("consistency_note", "") or "")[:4000]
                existing: Optional[ChapterNarrativeEntry] = None
                for e in sk.chapters:
                    if e.chapter_id == cid:
                        existing = e
                        break
                beats_raw = arguments.get("beat_sections")
                if isinstance(beats_raw, list):
                    beat_sections = [str(x).strip()[:800] for x in beats_raw if str(x).strip()][:40]
                elif existing is not None:
                    beat_sections = list(existing.beat_sections)
                else:
                    beat_sections = []
                ss_raw = str(arguments.get("sync_status", "") or "").strip().lower()
                if ss_raw in ("draft", "synced", "stale"):
                    sync_status = ss_raw
                else:
                    sync_status = "synced"
                found = False
                new_entry = ChapterNarrativeEntry(
                    chapter_id=cid,
                    summary=summary,
                    key_events=key_events,
                    open_threads=open_threads,
                    consistency_note=consistency_note,
                    beat_sections=beat_sections,
                    sync_status=sync_status,
                )
                for i, e in enumerate(sk.chapters):
                    if e.chapter_id == cid:
                        sk.chapters[i] = new_entry
                        found = True
                        break
                if not found:
                    sk.chapters.append(new_entry)
                sk.chapters.sort(key=lambda x: x.chapter_id)
                save(root, sk)
                try:
                    blob = (
                        f"第{cid}章章摘要\n"
                        f"摘要：{summary}\n"
                        f"关键事件：{key_events}\n"
                        f"未解线索：{open_threads}\n"
                        f"一致性：{consistency_note}\n"
                        f"节拍：{' | '.join(beat_sections)}"
                    )
                    upsert_docs(
                        root,
                        ids=[f"story:chapter:{cid}"],
                        documents=[blob],
                        metadatas=[{"type": "chapter_summary", "chapter_id": cid}],
                    )
                except Exception:
                    logger.exception("vector upsert chapter summary failed")
                return {"ok": True, "chapter_id": cid}

            if name == "kg_upsert_fact":
                fid = str(arguments.get("id", "") or "").strip()
                if not fid:
                    fid = f"f_{uuid.uuid4().hex[:10]}"
                if not _ID_SAFE.match(fid):
                    return {"ok": False, "error": "id 非法"}
                subj = str(arguments.get("subject", "") or "")[:500]
                pred = str(arguments.get("predicate", "") or "")[:200]
                obj = str(arguments.get("object", "") or "")[:800]
                note = str(arguments.get("note", "") or "")[:2000]
                ch_raw = arguments.get("chapter_id")
                ch_id: Optional[int] = None
                if ch_raw is not None and str(ch_raw).strip():
                    try:
                        ch_id = int(ch_raw)
                    except (TypeError, ValueError):
                        ch_id = None
                if ch_id is not None and ch_id < 1:
                    ch_id = None
                new = KnowledgeTriple(
                    id=fid,
                    subject=subj,
                    predicate=pred,
                    object=obj,
                    chapter_id=ch_id,
                    note=note,
                )
                rep = False
                for i, f in enumerate(sk.facts):
                    if f.id == fid:
                        sk.facts[i] = new
                        rep = True
                        break
                if not rep:
                    sk.facts.append(new)
                save(root, sk)
                try:
                    blob = f"事实 {subj} - {pred} - {obj}\n注：{note}\n章号：{ch_id or ''}"
                    upsert_docs(
                        root,
                        ids=[f"kg:fact:{fid}"],
                        documents=[blob],
                        metadatas=[
                            {
                                "type": "kg_fact",
                                "id": fid,
                                "chapter_id": ch_id,
                                "subject": subj,
                                "predicate": pred,
                            }
                        ],
                    )
                except Exception:
                    logger.exception("vector upsert fact failed")
                return {"ok": True, "fact_id": fid}

            if name == "kg_remove_fact":
                fid = str(arguments.get("id", "") or "").strip()
                if not fid:
                    return {"ok": False, "error": "id 必填"}
                before = len(sk.facts)
                sk.facts = [f for f in sk.facts if f.id != fid]
                save(root, sk)
                return {"ok": True, "removed": before - len(sk.facts)}

            if name == "kg_search_facts":
                q = str(arguments.get("query", "") or "")
                hits = search_facts(sk, q)
                return {"ok": True, "facts": [f.model_dump() for f in hits[:80]]}

            return {"ok": False, "error": f"未知 story/kg 工具: {name}"}
        except Exception as e:
            logger.exception("story knowledge tool failed")
            return {"ok": False, "error": str(e)}
