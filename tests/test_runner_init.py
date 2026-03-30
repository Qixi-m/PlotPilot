"""init / dry-run plan 无需真实 LLM。"""
from aitext.pipeline.runner import init_project, run_plan, project_paths
from aitext.story.engine import load_manifest


def test_init_and_dry_run_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("aitext.pipeline.runner.PROJECTS_DIR", tmp_path)
    root = init_project(title="测", premise="梗", chapter_count=2, words_per_chapter=1000)
    assert root.is_dir()
    m = load_manifest(project_paths(root)["manifest"])
    assert m.target_chapter_count == 2
    assert run_plan(root, dry_run=True) is True
