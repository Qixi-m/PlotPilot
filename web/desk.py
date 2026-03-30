"""
书目扫描、章节路径解析、审稿状态读写。
审稿记录文件名 editorial.json，不向用户展示技术实现细节。
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import PROJECTS_DIR
from ..story.chapter_fs import (
    chapter_has_deliverable,
    primary_body_path,
    read_chapter_for_api,
    write_api_body,
)
from ..story.engine import load_manifest, load_outline, project_paths


_SLUG_OK = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff][-a-zA-Z0-9_\u4e00-\u9fff]{0,127}$")


def is_safe_slug(slug: str) -> bool:
    if not slug or ".." in slug or "/" in slug or "\\" in slug:
        return False
    return bool(_SLUG_OK.match(slug))


def project_root_for_slug(slug: str) -> Optional[Path]:
    if not is_safe_slug(slug):
        return None
    root = (PROJECTS_DIR / slug).resolve()
    if not str(root).startswith(str(PROJECTS_DIR.resolve())):
        return None
    if not root.is_dir():
        return None
    return root


def list_book_roots() -> List[Path]:
    if not PROJECTS_DIR.is_dir():
        return []
    out = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if p.is_dir() and (p / "manifest.json").is_file():
            out.append(p)
    return out


def delete_project_by_slug(slug: str) -> bool:
    """删除整本书目目录（须已通过 manifest 存在校验）。成功返回 True。"""
    root = project_root_for_slug(slug)
    if not root:
        return False
    shutil.rmtree(root)
    return True


def get_chapter_file(chapters_dir: Path, chapter_id: int) -> Optional[Path]:
    """主编辑文件路径（chapters/NNN/body.md 或旧版 chapter_NNN_*.md）。"""
    return primary_body_path(chapters_dir, chapter_id)


def chapter_filename_for_api(path: Path) -> str:
    return path.name


def load_editorial(root: Path) -> Dict[str, Any]:
    path = root / "editorial.json"
    if not path.is_file():
        return {"version": 1, "chapters": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"version": 1, "chapters": {}}
        data.setdefault("version", 1)
        data.setdefault("chapters", {})
        if not isinstance(data["chapters"], dict):
            data["chapters"] = {}
        return data
    except Exception:
        return {"version": 1, "chapters": {}}


def save_editorial(root: Path, data: Dict[str, Any]) -> None:
    path = root / "editorial.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def editorial_key(chapter_id: int) -> str:
    return str(chapter_id)


def get_chapter_review(root: Path, chapter_id: int) -> Dict[str, str]:
    ed = load_editorial(root)
    raw = ed["chapters"].get(editorial_key(chapter_id), {})
    if not isinstance(raw, dict):
        raw = {}
    status = raw.get("status") or "pending"
    if status not in ("pending", "ok", "revise"):
        status = "pending"
    return {
        "status": status,
        "memo": str(raw.get("memo") or "")[:8000],
    }


def set_chapter_review(root: Path, chapter_id: int, status: str, memo: str) -> None:
    if status not in ("pending", "ok", "revise"):
        status = "pending"
    ed = load_editorial(root)
    ed["chapters"][editorial_key(chapter_id)] = {
        "status": status,
        "memo": memo[:8000],
        "updated": time.strftime("%Y-%m-%d %H:%M"),
    }
    save_editorial(root, ed)


def build_chapter_rows(root: Path) -> Tuple[Optional[dict], List[dict]]:
    """返回 manifest 摘要、章节行（含审稿状态、是否有正文文件）。"""
    paths = project_paths(root)
    manifest = load_manifest(paths["manifest"])
    outline = load_outline(paths["outline"])
    if not manifest:
        return None, []

    rows = []
    if outline and outline.chapters:
        for ch in sorted(outline.chapters, key=lambda c: c.id):
            cid = ch.id
            fpath = get_chapter_file(paths["chapters_dir"], cid)
            rev = get_chapter_review(root, cid)
            rows.append(
                {
                    "id": cid,
                    "title": ch.title,
                    "one_liner": ch.one_liner,
                    "has_file": chapter_has_deliverable(paths["chapters_dir"], cid),
                    "filename": fpath.name if fpath else "",
                    "review_status": rev["status"],
                    "memo_preview": (rev["memo"][:80] + "…") if len(rev["memo"]) > 80 else rev["memo"],
                }
            )
    else:
        for fpath in sorted(paths["chapters_dir"].glob("chapter_*.md")):
            m = re.match(r"chapter_(\d{3})", fpath.name)
            if not m:
                continue
            cid = int(m.group(1))
            rev = get_chapter_review(root, cid)
            rows.append(
                {
                    "id": cid,
                    "title": fpath.stem,
                    "one_liner": "",
                    "has_file": True,
                    "filename": fpath.name,
                    "review_status": rev["status"],
                    "memo_preview": (rev["memo"][:80] + "…") if len(rev["memo"]) > 80 else rev["memo"],
                }
            )
        rows.sort(key=lambda r: r["id"])

    info = {
        "title": manifest.title,
        "slug": manifest.slug,
        "genre": manifest.genre or "—",
        "stage_label": _stage_label(manifest.current_stage),
        "has_bible": paths["bible"].is_file(),
        "has_outline": paths["outline"].is_file(),
    }
    return info, rows


def _stage_label(stage: str) -> str:
    return {
        "init": "筹备",
        "planned": "结构已定",
        "writing": "收稿中",
        "completed": "待终校",
    }.get(stage, stage)


def read_chapter_body(root: Path, chapter_id: int) -> Tuple[Optional[Path], str]:
    paths = project_paths(root)
    return read_chapter_for_api(paths["chapters_dir"], chapter_id)


def write_chapter_body(root: Path, chapter_id: int, body: str) -> bool:
    paths = project_paths(root)
    return write_api_body(paths["chapters_dir"], chapter_id, body)
