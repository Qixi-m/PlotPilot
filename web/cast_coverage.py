"""正文与人物关系图对照：章节内是否出现、设定人物是否入库、书名号引用等。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from ..story.engine import load_bible, project_paths
from .cast_store import load_or_empty as cast_load_or_empty
from ..story.models import Bible, CastCharacter, CastGraph

_MD_FENCE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_MD_INLINE_CODE = re.compile(r"`([^`]+)`")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_HEADING = re.compile(r"^#+\s*", re.MULTILINE)

# 中文书名号内常见非人名片段（减少误报）
_QUOTE_STOP: Set[str] = {
    "说道",
    "问道",
    "笑道",
    "叹道",
    "喝道",
    "骂道",
    "心想",
    "一声",
    "一句",
    "半晌",
    "良久",
}


def _strip_markdown_light(s: str) -> str:
    s = _MD_FENCE.sub(" ", s)
    s = _MD_INLINE_CODE.sub(r"\1", s)
    s = _MD_IMAGE.sub(" ", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _MD_HEADING.sub(" ", s)
    return s


def _label_appears_in_text(label: str, text: str) -> bool:
    if not label:
        return False
    if len(label) >= 2:
        return label in text
    if len(label) == 1 and "\u4e00" <= label <= "\u9fff":
        return label in text
    return False


def _labels_for_character(c: CastCharacter) -> List[str]:
    raw: List[str] = []
    for lab in [c.name] + list(c.aliases):
        s = (lab or "").strip()
        if s:
            raw.append(s)
    seen: Set[str] = set()
    out: List[str] = []
    for s in sorted(raw, key=len, reverse=True):
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _all_cast_labels_flat(graph: CastGraph) -> Set[str]:
    s: Set[str] = set()
    for c in graph.characters:
        for lab in _labels_for_character(c):
            s.add(lab)
    return s


def _iter_chapter_texts(root: Path) -> List[Tuple[int, str]]:
    paths = project_paths(root)
    d = paths["chapters_dir"]
    if not d.is_dir():
        return []
    from ..story.chapter_fs import iter_chapter_ids_on_disk, read_composite_body

    out: List[Tuple[int, str]] = []
    for cid in iter_chapter_ids_on_disk(d):
        raw = read_composite_body(d, cid)
        if not raw.strip():
            continue
        out.append((cid, raw))
    return out


def _fallback_novel_text(root: Path) -> str:
    paths = project_paths(root)
    p = paths["novel"]
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
    return ""


_QUOTED_CN = re.compile(r"「([^」]{2,12})」")


def _quoted_per_chapter(
    chapter_texts: List[Tuple[int, str]], cast_labels: Set[str]
) -> List[Dict[str, Any]]:
    agg: Dict[str, Dict[str, Any]] = {}

    for cid, raw in chapter_texts:
        plain = _strip_markdown_light(raw)
        for m in _QUOTED_CN.finditer(plain):
            q = (m.group(1) or "").strip()
            if not q or q in _QUOTE_STOP:
                continue
            if q in cast_labels:
                continue
            if q not in agg:
                agg[q] = {"text": q, "count": 0, "chapter_ids": set()}
            agg[q]["count"] += 1
            agg[q]["chapter_ids"].add(cid)

    out = []
    for v in agg.values():
        chs = sorted(v["chapter_ids"])
        out.append({"text": v["text"], "count": v["count"], "chapter_ids": chs})
    out.sort(key=lambda x: (-x["count"], x["text"]))
    return out


def build_cast_coverage(root: Path) -> Dict[str, Any]:
    graph = cast_load_or_empty(root)
    chapter_rows = _iter_chapter_texts(root)
    bible: Bible | None = load_bible(project_paths(root)["bible"])

    cast_flat = _all_cast_labels_flat(graph)

    characters_out: List[Dict[str, Any]] = []
    for c in graph.characters:
        labels = _labels_for_character(c)
        chapter_ids: List[int] = []
        for cid, raw in chapter_rows:
            plain = _strip_markdown_light(raw)
            hit = any(_label_appears_in_text(lab, plain) for lab in labels)
            if hit:
                chapter_ids.append(cid)
        if not chapter_rows:
            plain_fb = _strip_markdown_light(_fallback_novel_text(root))
            if plain_fb.strip() and any(_label_appears_in_text(lab, plain_fb) for lab in labels):
                chapter_ids.append(0)
        chapter_ids.sort()
        characters_out.append(
            {
                "id": c.id,
                "name": c.name,
                "mentioned": bool(chapter_ids),
                "chapter_ids": chapter_ids,
            }
        )

    cast_name_set: Set[str] = set()
    for c in graph.characters:
        cast_name_set.add((c.name or "").strip())
        for a in c.aliases:
            cast_name_set.add((a or "").strip())
    cast_name_set.discard("")

    bible_not_in_cast: List[Dict[str, Any]] = []
    for bc in bible.characters if bible else []:
        n = (bc.name or "").strip()
        if not n:
            continue
        if n in cast_name_set:
            continue
        chapter_ids: List[int] = []
        for cid, raw in chapter_rows:
            plain = _strip_markdown_light(raw)
            if _label_appears_in_text(n, plain):
                chapter_ids.append(cid)
        if not chapter_rows:
            novel = _fallback_novel_text(root)
            plain = _strip_markdown_light(novel)
            if n in plain:
                chapter_ids.append(0)
        in_novel = bool(chapter_ids)
        bible_not_in_cast.append(
            {
                "name": n,
                "role": (bc.role or "").strip(),
                "in_novel_text": in_novel,
                "chapter_ids": sorted(set(chapter_ids)),
            }
        )

    combined_plain = ""
    for _cid, raw in chapter_rows:
        combined_plain += "\n" + _strip_markdown_light(raw)
    if not combined_plain.strip():
        combined_plain = _strip_markdown_light(_fallback_novel_text(root))

    quoted_not_in_cast = _quoted_per_chapter(chapter_rows, cast_flat) if chapter_rows else []
    if not chapter_rows and combined_plain:
        # 无分章文件时，仍用全文书名号做提示
        tmp = _quoted_per_chapter([(1, combined_plain)], cast_flat)
        quoted_not_in_cast = tmp

    return {
        "chapter_files_scanned": len(chapter_rows),
        "characters": characters_out,
        "bible_not_in_cast": bible_not_in_cast,
        "quoted_not_in_cast": quoted_not_in_cast[:80],
    }
