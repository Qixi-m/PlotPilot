"""各阶段生成：圣经+大纲、章纲、正文、滚动摘要。"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from ..config import Config
from .jsonutil import parse_model, parse_json_loose
from .models import (
    Bible,
    BibleOutlineBundle,
    CastGraph,
    ChapterBeats,
    NovelManifest,
    Outline,
    RunningSummary,
    StoryKnowledge,
)
from .prompts import (
    SYSTEM_JSON_ONLY,
    build_beats_user_prompt,
    build_draft_user_prompt,
    build_plan_revise_user_prompt,
    build_plan_user_prompt,
    build_update_summary_user_prompt,
)

if TYPE_CHECKING:
    from ..clients.llm import LLMClient

logger = logging.getLogger("aitext.story.engine")


def project_paths(root: Path) -> dict:
    root = Path(root)
    chat_dir = root / "chat"
    return {
        "root": root,
        "manifest": root / "manifest.json",
        "bible": root / "bible.json",
        "outline": root / "outline.json",
        "beats_dir": root / "beats",
        "chapters_dir": root / "chapters",
        "summary": root / "running_summary.json",
        "novel": root / "novel.md",
        "chat_dir": chat_dir,
        "chat_thread": chat_dir / "thread.json",
        "chat_digest": chat_dir / "context_digest.md",
        "cast_graph": root / "cast_graph.json",
        "novel_knowledge": root / "novel_knowledge.json",
    }


def load_manifest(path: Path) -> Optional[NovelManifest]:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return NovelManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_manifest failed")
        return None


def save_manifest(path: Path, manifest: NovelManifest) -> None:
    path.write_text(manifest.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def load_bible(path: Path) -> Optional[Bible]:
    if not path.is_file():
        return None
    try:
        return Bible.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_bible(path: Path, bible: Bible) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bible.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def load_cast_graph(path: Path) -> Optional[CastGraph]:
    if not path.is_file():
        return None
    try:
        return CastGraph.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_cast_graph failed")
        return None


def save_cast_graph(path: Path, graph: CastGraph) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def load_story_knowledge(path: Path) -> Optional[StoryKnowledge]:
    if not path.is_file():
        return None
    try:
        return StoryKnowledge.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_story_knowledge failed")
        return None


def save_story_knowledge(path: Path, data: StoryKnowledge) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def load_outline(path: Path) -> Optional[Outline]:
    if not path.is_file():
        return None
    try:
        return Outline.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_running_summary(path: Path) -> RunningSummary:
    if not path.is_file():
        return RunningSummary()
    try:
        return RunningSummary.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return RunningSummary()


def save_running_summary(path: Path, rs: RunningSummary) -> None:
    path.write_text(rs.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")


def compact_bible(bible: Bible, max_chars: Optional[int] = None) -> str:
    """供 LLM system 注入：按真实创作流程分块（文风→人物→地点→时间线），避免整坨 JSON。"""
    cap = max_chars if max_chars is not None else Config.CHAT_BIBLE_COMPACT_CHARS
    lines: List[str] = []
    lines.append("【文风 / 叙事约束 / 禁忌】")
    lines.append((bible.style_notes or "").strip() or "（未填写：可在工作台「设定」中补充）")
    lines.append("\n【人物（设定表 · 与关系图 ID 可独立维护）】")
    if not bible.characters:
        lines.append("（尚无人物条目）")
    else:
        for i, c in enumerate(bible.characters, 1):
            lines.append(
                f"{i}. {c.name} | 定位：{c.role or '—'} | 特质：{c.traits or '—'} | 弧光/成长：{c.arc_note or '—'}"
            )
    lines.append("\n【地点 / 势力 / 场景】")
    if not bible.locations:
        lines.append("（尚无地点条目）")
    else:
        for loc in bible.locations:
            lines.append(f"- {loc.name}：{loc.description or '—'}")
    if bible.timeline_notes:
        lines.append("\n【时间线 / 关键节点】")
        for t in bible.timeline_notes:
            if (t or "").strip():
                lines.append(f"- {(t or '').strip()}")
    text = "\n".join(lines)
    if len(text) <= cap:
        return text
    return text[: cap - 24] + "\n…（设定过长已截断，请精简或依赖工具检索）"


def compact_outline(outline: Outline, max_chars: Optional[int] = None) -> str:
    """分章大纲：按章号排序，便于模型对齐「写到哪一章」。"""
    cap = max_chars if max_chars is not None else Config.CHAT_OUTLINE_COMPACT_CHARS
    if not outline.chapters:
        return "（尚无分章大纲，请先执行「结构规划」。）"
    lines: List[str] = []
    for ch in sorted(outline.chapters, key=lambda c: c.id):
        lines.append(
            f"第{ch.id}章 《{ch.title}》\n   一行纲：{ch.one_liner or '（未填）'}"
        )
    text = "\n".join(lines)
    if len(text) <= cap:
        return text
    return text[: cap - 24] + "\n…（大纲过长已截断）"


def outline_chapter(outline: Outline, chapter_id: int) -> Optional[Tuple[int, str, str]]:
    for ch in outline.chapters:
        if ch.id == chapter_id:
            return ch.id, ch.title, ch.one_liner
    return None


def read_tail_of_file(path: Path, max_chars: int = 2500) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    return text[-max_chars:] if len(text) > max_chars else text


def format_running_summaries(rs: RunningSummary, max_entries: int) -> str:
    entries = sorted(rs.entries, key=lambda e: e.chapter_id)[-max_entries:]
    if not entries:
        return ""
    lines = [f"- 第{e.chapter_id}章：{e.summary}" for e in entries]
    return "\n".join(lines)


def _clip_text_block(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 12] + "\n…（已截断）"


def _cancelled(ev: Optional[Any]) -> bool:
    return ev is not None and bool(getattr(ev, "is_set", lambda: False)())


def generate_bible_and_outline(
    llm: LLMClient,
    manifest: NovelManifest,
    dry_run: bool = False,
    cancel_event: Optional[Any] = None,
) -> Optional[BibleOutlineBundle]:
    if dry_run:
        logger.info("dry_run: skip bible/outline LLM")
        return None
    if not llm.enabled:
        logger.error("LLM 不可用: %s", llm.last_error)
        return None
    user = build_plan_user_prompt(
        manifest.title,
        manifest.premise,
        manifest.genre,
        manifest.target_chapter_count,
        manifest.target_words_per_chapter,
        manifest.style_hint,
    )
    messages = [
        {"role": "system", "content": SYSTEM_JSON_ONLY},
        {"role": "user", "content": user},
    ]
    if _cancelled(cancel_event):
        return None
    text = llm.request(messages)
    if not text:
        return None
    bundle = parse_model(text, BibleOutlineBundle)
    if bundle is None:
        logger.error("无法解析 bible/outline JSON")
        return None
    if len(bundle.outline.chapters) != manifest.target_chapter_count:
        logger.warning(
            "大纲章数=%d 与目标=%d 不一致，以模型输出为准",
            len(bundle.outline.chapters),
            manifest.target_chapter_count,
        )
    return bundle


def generate_bible_and_outline_revise(
    llm: LLMClient,
    manifest: NovelManifest,
    bible: Bible,
    outline: Outline,
    running_summary: RunningSummary,
    story_knowledge: Optional[StoryKnowledge],
    digest_tail: str,
    dry_run: bool = False,
    cancel_event: Optional[Any] = None,
) -> Optional[BibleOutlineBundle]:
    if dry_run:
        logger.info("dry_run: skip bible/outline revise LLM")
        return None
    if not llm.enabled:
        logger.error("LLM 不可用: %s", llm.last_error)
        return None
    bible_ex = _clip_text_block(bible.model_dump_json(indent=2, ensure_ascii=False), 12000)
    outline_ex = _clip_text_block(outline.model_dump_json(indent=2, ensure_ascii=False), 12000)
    rs_n = max(5, Config.RUNNING_SUMMARY_MAX_CHAPTERS)
    rs_text = _clip_text_block(format_running_summaries(running_summary, rs_n), 8000)
    pl = ""
    if story_knowledge and (story_knowledge.premise_lock or "").strip():
        pl = _clip_text_block(story_knowledge.premise_lock.strip(), 4000)
    digest_ex = _clip_text_block(digest_tail, 4000)
    done = sorted(manifest.completed_chapters or [])
    completed_hint = (
        f"manifest 已标记完成章节号：{done}" if done else "尚无 manifest 标记的完成章；请以滚动摘要与正文为准。"
    )
    user = build_plan_revise_user_prompt(
        manifest.title,
        manifest.premise,
        manifest.genre,
        manifest.target_chapter_count,
        manifest.target_words_per_chapter,
        manifest.style_hint,
        bible_ex,
        outline_ex,
        rs_text,
        pl or "（未填写）",
        digest_ex or "（无）",
        completed_hint,
    )
    messages = [
        {"role": "system", "content": SYSTEM_JSON_ONLY},
        {"role": "user", "content": user},
    ]
    if _cancelled(cancel_event):
        return None
    text = llm.request(messages)
    if not text:
        return None
    bundle = parse_model(text, BibleOutlineBundle)
    if bundle is None:
        logger.error("无法解析修订版 bible/outline JSON")
        return None
    if len(bundle.outline.chapters) != manifest.target_chapter_count:
        logger.warning(
            "修订大纲章数=%d 与目标=%d 不一致，以模型输出为准",
            len(bundle.outline.chapters),
            manifest.target_chapter_count,
        )
    return bundle


def generate_chapter_beats(
    llm: LLMClient,
    manifest: NovelManifest,
    bible: Bible,
    outline: Outline,
    chapter_id: int,
    running_summary: RunningSummary,
    previous_chapter_tail: str = "",
    dry_run: bool = False,
) -> Optional[ChapterBeats]:
    if dry_run:
        return None
    if not llm.enabled:
        return None
    oc = outline_chapter(outline, chapter_id)
    if not oc:
        logger.error("outline 中无第 %d 章", chapter_id)
        return None
    _, title, one_liner = oc
    prev_tail = (previous_chapter_tail or "").strip()
    rs_text = format_running_summaries(running_summary, Config.RUNNING_SUMMARY_MAX_CHAPTERS)
    user = build_beats_user_prompt(
        chapter_id,
        title,
        one_liner,
        compact_bible(bible),
        compact_outline(outline),
        prev_tail,
        rs_text,
        manifest.target_words_per_chapter,
    )
    text = llm.request(
        [
            {"role": "system", "content": SYSTEM_JSON_ONLY},
            {"role": "user", "content": user},
        ]
    )
    if not text:
        return None
    beats = parse_model(text, ChapterBeats)
    if beats is None:
        return None
    beats.chapter_id = chapter_id
    beats.chapter_title = beats.chapter_title or title
    return beats


def generate_chapter_draft(
    llm: LLMClient,
    manifest: NovelManifest,
    bible: Bible,
    outline: Outline,
    beats: ChapterBeats,
    running_summary: RunningSummary,
    previous_chapter_tail: str = "",
    dry_run: bool = False,
) -> Optional[str]:
    if dry_run:
        return "（dry-run 占位正文）\n\n本章未调用模型。"
    if not llm.enabled:
        return None
    prev_tail = (previous_chapter_tail or "").strip()
    rs_text = format_running_summaries(running_summary, Config.RUNNING_SUMMARY_MAX_CHAPTERS)
    beats_compact = beats.model_dump_json(ensure_ascii=False)
    style = (bible.style_notes or "") + "\n" + (manifest.style_hint or "")
    user = build_draft_user_prompt(
        beats_compact,
        compact_bible(bible),
        compact_outline(outline),
        prev_tail,
        rs_text,
        manifest.target_words_per_chapter,
        style,
    )
    text = llm.request(
        [
            {
                "role": "system",
                "content": "你是资深中文小说作者。只输出小说正文，不要 JSON。",
            },
            {"role": "user", "content": user},
        ]
    )
    return text.strip() if text else None


def update_running_summary(
    llm: LLMClient,
    manifest: NovelManifest,
    chapter_id: int,
    chapter_title: str,
    chapter_body: str,
    current: RunningSummary,
    dry_run: bool = False,
) -> RunningSummary:
    if dry_run:
        return current
    tail = chapter_body[-3500:] if len(chapter_body) > 3500 else chapter_body
    existing = json.dumps(
        [e.model_dump() for e in sorted(current.entries, key=lambda x: x.chapter_id)],
        ensure_ascii=False,
    )
    user = build_update_summary_user_prompt(
        chapter_id,
        chapter_title,
        tail,
        existing,
        Config.RUNNING_SUMMARY_MAX_CHAPTERS,
    )
    text = llm.request(
        [
            {"role": "system", "content": SYSTEM_JSON_ONLY},
            {"role": "user", "content": user},
        ]
    )
    if not text:
        return current
    data = parse_json_loose(text)
    if not isinstance(data, dict):
        return current
    try:
        new_rs = RunningSummary.model_validate(data)
    except Exception:
        return current
    # enforce max_keep by chapter_id
    max_keep = Config.RUNNING_SUMMARY_MAX_CHAPTERS
    entries = sorted(new_rs.entries, key=lambda e: e.chapter_id)
    if len(entries) > max_keep:
        entries = entries[-max_keep:]
    return RunningSummary(entries=entries)


def continuity_light_revision(
    llm: LLMClient,
    bible: Bible,
    chapter_body: str,
    chapter_title: str,
    dry_run: bool = False,
) -> Optional[str]:
    """可选：轻量一致性修订。失败则返回 None，由调用方保留原文。"""
    if dry_run or not llm.enabled:
        return None
    user = f"""根据【人物/设定摘要】检查下列章节正文：是否有明显人名错误、称谓矛盾或与设定冲突。
若有，输出修订后的完整正文；若无问题，原样输出正文（可微调语病）。

【设定 JSON 摘要】
{compact_bible(bible, max_chars=3500)}

【章节】{chapter_title}

【正文】
{chapter_body[:12000]}
"""
    text = llm.request(
        [
            {
                "role": "system",
                "content": "你是专业小说编辑。只输出修订后的完整正文，不要解释。",
            },
            {"role": "user", "content": user},
        ]
    )
    return text.strip() if text else None


def assemble_novel(chapters_dir: Path, outline: Outline, out_path: Path) -> None:
    from .chapter_fs import read_composite_body

    parts = []
    by_id = {c.id: c for c in outline.chapters}
    for cid in sorted(by_id.keys()):
        body = read_composite_body(chapters_dir, cid).strip()
        if body:
            parts.append(body)
    out_path.write_text("\n\n---\n\n".join(parts), encoding="utf-8")
