"""章节目录布局：子目录 body.md、parts 拼接、旧版兼容。"""
from pathlib import Path

from aitext.story.chapter_fs import (
    read_composite_body,
    write_api_body,
    write_pipeline_chapter,
    chapter_has_deliverable,
    primary_body_path,
    tail_of_previous_chapter,
)
from aitext.story.models import ChapterFolderMeta


def test_legacy_flat_file(tmp_path):
    d = tmp_path / "chapters"
    d.mkdir()
    (d / "chapter_001_开篇.md").write_text("legacy body", encoding="utf-8")
    assert read_composite_body(d, 1) == "legacy body"
    assert chapter_has_deliverable(d, 1)
    p = primary_body_path(d, 1)
    assert p and p.name.startswith("chapter_001")


def test_folder_body_md(tmp_path):
    d = tmp_path / "chapters"
    root = d / "002"
    root.mkdir(parents=True)
    (root / "body.md").write_text("folder main", encoding="utf-8")
    assert read_composite_body(d, 2) == "folder main"
    assert primary_body_path(d, 2).name == "body.md"


def test_parts_order(tmp_path):
    d = tmp_path / "chapters"
    root = d / "003"
    (root / "parts").mkdir(parents=True)
    (root / "parts" / "a.md").write_text("A", encoding="utf-8")
    (root / "parts" / "b.md").write_text("B", encoding="utf-8")
    meta = ChapterFolderMeta(
        version=1,
        chapter_id=3,
        use_parts=True,
        parts_order=["parts/a.md", "parts/b.md"],
    )
    (root / "chapter.json").write_text(meta.model_dump_json(indent=2), encoding="utf-8")
    assert read_composite_body(d, 3) == "A\n\nB"


def test_write_api_creates_folder(tmp_path):
    d = tmp_path / "chapters"
    d.mkdir()
    assert write_api_body(d, 5, "new chapter")
    assert (d / "005" / "body.md").read_text(encoding="utf-8") == "new chapter"
    assert chapter_has_deliverable(d, 5)


def test_pipeline_write(tmp_path):
    d = tmp_path / "chapters"
    d.mkdir()
    p = write_pipeline_chapter(d, 1, "gen", "标题一")
    assert p.name == "body.md"
    assert "gen" in p.read_text(encoding="utf-8")


def test_tail_previous(tmp_path):
    d = tmp_path / "chapters"
    d.mkdir()
    write_api_body(d, 1, "x" * 100)
    t = tail_of_previous_chapter(d, 1, max_chars=30)
    assert len(t) <= 30
