"""章节目录与正文解析：支持 chapters/001/body.md + 可选 parts/ 多文件拼接，兼容旧版扁平 chapter_001_*.md。"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .models import ChapterFolderMeta

logger = logging.getLogger("aitext.story.chapter_fs")

META_NAME = "chapter.json"
BODY_NAME = "body.md"
PARTS_DIR = "parts"


def chapter_content_dir(chapters_dir: Path, chapter_id: int) -> Path:
    return Path(chapters_dir) / f"{chapter_id:03d}"


def _legacy_globs(chapters_dir: Path, chapter_id: int) -> List[Path]:
    d = Path(chapters_dir)
    g = sorted(d.glob(f"chapter_{chapter_id:03d}_*.md"))
    if g:
        return g
    p = d / f"chapter_{chapter_id:03d}.md"
    return [p] if p.is_file() else []


def load_meta(chapter_dir: Path) -> Optional[ChapterFolderMeta]:
    p = chapter_dir / META_NAME
    if not p.is_file():
        return None
    try:
        return ChapterFolderMeta.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_meta failed %s", p)
        return None


def save_meta(chapter_dir: Path, meta: ChapterFolderMeta) -> None:
    chapter_dir.mkdir(parents=True, exist_ok=True)
    (chapter_dir / META_NAME).write_text(
        meta.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_from_chapter_dir(d: Path) -> str:
    meta = load_meta(d)
    if meta and meta.use_parts and meta.parts_order:
        chunks: List[str] = []
        for rel in meta.parts_order:
            rel = (rel or "").strip().lstrip("/").replace("\\", "/")
            if not rel or ".." in rel:
                continue
            fp = (d / rel).resolve()
            if not str(fp).startswith(str(d.resolve())):
                continue
            if fp.is_file():
                chunks.append(fp.read_text(encoding="utf-8").strip())
        return "\n\n".join(chunks).strip()
    body_p = d / BODY_NAME
    if body_p.is_file():
        return body_p.read_text(encoding="utf-8").strip()
    parts_dir = d / PARTS_DIR
    if parts_dir.is_dir():
        files = sorted(parts_dir.glob("*.md"))
        if files:
            return "\n\n".join(f.read_text(encoding="utf-8").strip() for f in files).strip()
    return ""


def read_composite_body(chapters_dir: Path, chapter_id: int) -> str:
    """合并后的章节正文：供导出、上一章尾、摘要、审稿、对话引用。"""
    d = chapter_content_dir(chapters_dir, chapter_id)
    if d.is_dir():
        block = _read_from_chapter_dir(d)
        if block.strip():
            return block.strip()
    legacy = _legacy_globs(chapters_dir, chapter_id)
    if legacy:
        return legacy[0].read_text(encoding="utf-8").strip()
    return ""


def chapter_has_deliverable(chapters_dir: Path, chapter_id: int) -> bool:
    return bool(read_composite_body(chapters_dir, chapter_id).strip())


def primary_body_path(chapters_dir: Path, chapter_id: int) -> Optional[Path]:
    """单文件编辑入口：优先 body.md，否则旧版扁平 md。"""
    d = chapter_content_dir(chapters_dir, chapter_id)
    body_p = d / BODY_NAME
    if body_p.is_file():
        return body_p
    legacy = _legacy_globs(chapters_dir, chapter_id)
    if legacy:
        return legacy[0]
    if d.is_dir():
        return body_p
    return None


def ensure_body_path(chapters_dir: Path, chapter_id: int) -> Path:
    """创建章节目录并返回 body.md 路径（尚无文件时）。"""
    d = chapter_content_dir(chapters_dir, chapter_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / BODY_NAME


def write_api_body(chapters_dir: Path, chapter_id: int, body: str) -> bool:
    """工作台保存：优先写 chapters/NNN/body.md；仅当尚无该文件且仅有旧版 md 时写旧路径。"""
    d = chapter_content_dir(chapters_dir, chapter_id)
    body_p = d / BODY_NAME
    legacy = _legacy_globs(chapters_dir, chapter_id)

    if body_p.is_file():
        d.mkdir(parents=True, exist_ok=True)
        meta = load_meta(d) or ChapterFolderMeta(version=1, chapter_id=chapter_id)
        meta.chapter_id = chapter_id
        meta.use_parts = False
        meta.parts_order = []
        body_p.write_text(body, encoding="utf-8")
        save_meta(d, meta)
        return True

    if not d.is_dir() and legacy:
        name = legacy[0].name
        if not re.match(r"^chapter_\d{3}(?:_[^/\\]+)?\.md$", name):
            return False
        legacy[0].write_text(body, encoding="utf-8")
        return True

    d.mkdir(parents=True, exist_ok=True)
    meta = load_meta(d) or ChapterFolderMeta(version=1, chapter_id=chapter_id)
    meta.chapter_id = chapter_id
    meta.use_parts = False
    meta.parts_order = []
    body_p.write_text(body, encoding="utf-8")
    save_meta(d, meta)
    return True


def write_pipeline_chapter(
    chapters_dir: Path, chapter_id: int, body: str, chapter_title: str
) -> Path:
    """撰稿流水线：落盘到子目录 body.md，写入 meta.title。"""
    d = chapter_content_dir(chapters_dir, chapter_id)
    d.mkdir(parents=True, exist_ok=True)
    meta = load_meta(d) or ChapterFolderMeta(version=1, chapter_id=chapter_id)
    meta.chapter_id = chapter_id
    meta.title = (chapter_title or "").strip()
    meta.use_parts = False
    (d / BODY_NAME).write_text(body, encoding="utf-8")
    save_meta(d, meta)
    return d / BODY_NAME


def tail_of_previous_chapter(chapters_dir: Path, prev_chapter_id: int, max_chars: int = 2500) -> str:
    text = read_composite_body(chapters_dir, prev_chapter_id)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def iter_chapter_ids_on_disk(chapters_dir: Path) -> List[int]:
    ids = set()
    d = Path(chapters_dir)
    if not d.is_dir():
        return []
    for p in d.iterdir():
        if p.is_dir() and p.name.isdigit() and len(p.name) == 3:
            ids.add(int(p.name))
    for p in d.glob("chapter_*.md"):
        m = re.match(r"chapter_(\d{3})", p.name)
        if m:
            ids.add(int(m.group(1)))
    return sorted(ids)


def read_chapter_for_api(chapters_dir: Path, chapter_id: int) -> Tuple[Optional[Path], str]:
    """GET 章节正文：返回主编辑路径（若有）与合并后的展示正文。"""
    text = read_composite_body(chapters_dir, chapter_id)
    path = primary_body_path(chapters_dir, chapter_id)
    return path, text
