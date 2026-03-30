"""章节能力聚合：供流水线、HTTP、编务对话引用（避免在路由里散落路径逻辑）。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .chapter_fs import (
    read_composite_body,
    read_chapter_for_api,
    tail_of_previous_chapter,
    write_pipeline_chapter,
    write_api_body,
    chapter_has_deliverable,
    primary_body_path,
)
from .engine import project_paths


def project_chapters_dir(root: Path) -> Path:
    return project_paths(root)["chapters_dir"]


def get_chapter_text(root: Path, chapter_id: int) -> str:
    """合并正文（含 parts），供摘要、工具、对话注入。"""
    return read_composite_body(project_chapters_dir(root), chapter_id)


def get_chapter_display(root: Path, chapter_id: int) -> Tuple[Optional[Path], str]:
    return read_chapter_for_api(project_chapters_dir(root), chapter_id)


def save_chapter_body(root: Path, chapter_id: int, body: str) -> bool:
    return write_api_body(project_chapters_dir(root), chapter_id, body)


def previous_chapter_tail(root: Path, prev_chapter_id: int, max_chars: int = 2500) -> str:
    return tail_of_previous_chapter(project_chapters_dir(root), prev_chapter_id, max_chars)


def write_generated_chapter(root: Path, chapter_id: int, body: str, title: str) -> Path:
    return write_pipeline_chapter(project_chapters_dir(root), chapter_id, body, title)


def is_chapter_delivered(root: Path, chapter_id: int) -> bool:
    return chapter_has_deliverable(project_chapters_dir(root), chapter_id)


def editor_target_path(root: Path, chapter_id: int) -> Optional[Path]:
    return primary_body_path(project_chapters_dir(root), chapter_id)
