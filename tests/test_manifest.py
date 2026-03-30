from pathlib import Path

from aitext.story.engine import load_manifest, save_manifest, project_paths
from aitext.story.models import NovelManifest


def test_manifest_stage_and_chapters(tmp_path: Path):
    m = NovelManifest(
        novel_id="u1",
        slug="t",
        title="T",
        premise="p",
        target_chapter_count=3,
        target_words_per_chapter=2000,
    )
    assert m.current_stage == "init"
    m.mark_planned()
    assert m.current_stage == "planned"
    m.register_chapter_done(2)
    m.register_chapter_done(1)
    assert m.completed_chapters == [1, 2]
    m.mark_writing()
    m.mark_completed()
    assert m.current_stage == "completed"


def test_load_save_roundtrip(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    paths = project_paths(root)
    m = NovelManifest(
        novel_id="id",
        slug="proj",
        title="书名",
        premise="梗概",
        target_chapter_count=5,
    )
    save_manifest(paths["manifest"], m)
    m2 = load_manifest(paths["manifest"])
    assert m2 is not None
    assert m2.title == "书名"
    assert m2.premise == "梗概"
