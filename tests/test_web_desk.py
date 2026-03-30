import json
import time
from pathlib import Path

from aitext.story.engine import save_manifest
from aitext.story.models import NovelManifest
from aitext.web import desk


def _patch_projects_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("aitext.config.PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("aitext.pipeline.runner.PROJECTS_DIR", tmp_path)
    monkeypatch.setattr("aitext.web.desk.PROJECTS_DIR", tmp_path)


def test_slug_safety():
    assert desk.is_safe_slug("ab-cd_12")
    assert desk.is_safe_slug("书名一")
    assert not desk.is_safe_slug("../x")
    assert not desk.is_safe_slug("")


def test_editorial_roundtrip(tmp_path):
    root = tmp_path / "book1"
    root.mkdir()
    desk.set_chapter_review(root, 1, "ok", "行文通顺")
    ed = desk.load_editorial(root)
    assert ed["chapters"]["1"]["status"] == "ok"
    assert "行文" in ed["chapters"]["1"]["memo"]


def test_client_home_and_save(tmp_path, monkeypatch):
    monkeypatch.setattr(desk, "PROJECTS_DIR", tmp_path)
    slug = "webtest-book"
    root = tmp_path / slug
    root.mkdir()
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    paths["chapters_dir"].mkdir(parents=True, exist_ok=True)
    m = NovelManifest(
        novel_id="x",
        slug=slug,
        title="测试书目",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)
    paths["outline"].write_text(
        json.dumps({"chapters": [{"id": 1, "title": "第一章", "one_liner": "开篇"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    chap = paths["chapters_dir"] / "chapter_001_开篇.md"
    chap.write_text("原始正文", encoding="utf-8")

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    # API-only 后端：确认书目列表接口可用
    r = c.get("/api/books")
    assert r.status_code == 200
    data = r.json()
    assert any(b.get("slug") == slug for b in data)

    r2 = c.put(
        f"/api/book/{slug}/chapter/1/body",
        json={"content": "修订后正文"},
    )
    assert r2.status_code == 200
    assert chap.read_text(encoding="utf-8") == "修订后正文"


def test_api_create_book(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    tmp_path.mkdir(parents=True, exist_ok=True)

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    r = c.post(
        "/api/jobs/create-book",
        json={
            "title": "新建测",
            "premise": "梗概内容",
            "slug": "create-api-test",
            "genre": "测",
            "chapters": 2,
            "words": 1000,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] and data["slug"] == "create-api-test"
    assert (tmp_path / "create-api-test" / "manifest.json").is_file()


def test_api_novel_knowledge(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    slug = "kg-book"
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    m = NovelManifest(
        novel_id="k1",
        slug=slug,
        title="知识测",
        premise="主线梗概",
        target_chapter_count=2,
    )
    save_manifest(paths["manifest"], m)

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    assert c.get(f"/api/book/{slug}/knowledge").json()["premise_lock"] == ""
    body = {
        "version": 1,
        "premise_lock": "不得偏离",
        "chapters": [
            {
                "chapter_id": 1,
                "summary": "开局",
                "key_events": "",
                "open_threads": "",
                "consistency_note": "",
            }
        ],
        "facts": [{"id": "f1", "subject": "甲", "predicate": "是", "object": "剑客", "chapter_id": 1, "note": ""}],
    }
    assert c.put(f"/api/book/{slug}/knowledge", json=body).status_code == 200
    j = c.get(f"/api/book/{slug}/knowledge").json()
    assert j["premise_lock"] == "不得偏离"
    assert j["chapters"][0]["summary"] == "开局"


def test_api_cast_crud(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    slug = "cast-book"
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    m = NovelManifest(
        novel_id="c1",
        slug=slug,
        title="人物测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    r = c.get(f"/api/book/{slug}/cast")
    assert r.status_code == 200
    assert r.json()["characters"] == []

    body = {
        "version": 1,
        "characters": [
            {
                "id": "p1",
                "name": "主角",
                "aliases": [],
                "role": "男主",
                "traits": "",
                "note": "",
            }
        ],
        "relationships": [],
    }
    assert c.put(f"/api/book/{slug}/cast", json=body).status_code == 200
    r2 = c.get(f"/api/book/{slug}/cast/search", params={"q": "主"})
    assert r2.status_code == 200
    assert len(r2.json()["characters"]) == 1


def test_api_cast_coverage(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    slug = "cov-book"
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    paths["chapters_dir"].mkdir(parents=True, exist_ok=True)
    m = NovelManifest(
        novel_id="cv1",
        slug=slug,
        title="覆盖测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)
    (paths["chapters_dir"] / "chapter_001.md").write_text("李明与王芳在此相遇。", encoding="utf-8")

    from aitext.story.engine import save_bible
    from aitext.story.models import Bible, BibleCharacter

    save_bible(
        paths["bible"],
        Bible(characters=[BibleCharacter(name="赵六", role="配角")]),
    )

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    cast_body = {
        "version": 1,
        "characters": [
            {
                "id": "lm",
                "name": "李明",
                "aliases": [],
                "role": "",
                "traits": "",
                "note": "",
            },
            {
                "id": "wf",
                "name": "王芳",
                "aliases": [],
                "role": "",
                "traits": "",
                "note": "",
            },
        ],
        "relationships": [],
    }
    assert c.put(f"/api/book/{slug}/cast", json=cast_body).status_code == 200

    r = c.get(f"/api/book/{slug}/cast/coverage")
    assert r.status_code == 200
    j = r.json()
    assert j["chapter_files_scanned"] == 1
    by_name = {x["name"]: x for x in j["characters"]}
    assert by_name["李明"]["mentioned"] is True
    assert 1 in by_name["李明"]["chapter_ids"]
    bible_miss = [x for x in j["bible_not_in_cast"] if x["name"] == "赵六"]
    assert len(bible_miss) == 1
    assert bible_miss[0]["in_novel_text"] is False


def test_api_delete_book(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    slug = "del-book-test"
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    m = NovelManifest(
        novel_id="d1",
        slug=slug,
        title="删测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    assert root.is_dir()
    r = c.delete(f"/api/book/{slug}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert not root.exists()

    assert c.delete(f"/api/book/{slug}").status_code == 404


def test_api_export_and_job_conflict(tmp_path, monkeypatch):
    slug = "export-test"
    _patch_projects_dir(tmp_path, monkeypatch)
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    paths["chapters_dir"].mkdir(parents=True, exist_ok=True)
    m = NovelManifest(
        novel_id="e1",
        slug=slug,
        title="导测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)
    paths["outline"].write_text(
        json.dumps({"chapters": [{"id": 1, "title": "一", "one_liner": ""}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (paths["chapters_dir"] / "chapter_001_x.md").write_text("x", encoding="utf-8")

    monkeypatch.setattr("aitext.web.jobs.run_export", lambda root: True)

    from fastapi.testclient import TestClient
    from aitext.web import jobs as jobq
    from aitext.web.app import app

    c = TestClient(app)
    r = c.post(f"/api/jobs/{slug}/export")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    assert jobq.try_acquire_book(slug) is True
    try:
        r2 = c.post(f"/api/jobs/{slug}/export")
        assert r2.status_code == 409
    finally:
        jobq.release_book(slug)


def test_api_plan_dry_run_job(tmp_path, monkeypatch):
    slug = "plan-dry"
    _patch_projects_dir(tmp_path, monkeypatch)
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    paths["beats_dir"].mkdir(parents=True, exist_ok=True)
    paths["chapters_dir"].mkdir(parents=True, exist_ok=True)
    m = NovelManifest(
        novel_id="p1",
        slug=slug,
        title="规划测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    r = c.post(f"/api/jobs/{slug}/plan", json={"dry_run": True})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    ok = False
    for _ in range(100):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j.get("done"):
            ok = j.get("ok") is True
            break
        time.sleep(0.05)
    assert ok


def test_api_job_not_found():
    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    assert c.get("/api/jobs/00000000-0000-0000-0000-000000000000").status_code == 404


def test_api_job_cancel_unknown():
    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    assert c.post("/api/jobs/00000000-0000-0000-0000-000000000000/cancel").status_code == 404


def test_api_desk_has_bible_outline_flags(tmp_path, monkeypatch):
    _patch_projects_dir(tmp_path, monkeypatch)
    slug = "desk-flags"
    root = tmp_path / slug
    root.mkdir(parents=True)
    paths = __import__("aitext.story.engine", fromlist=["project_paths"]).project_paths(root)
    m = NovelManifest(
        novel_id="df1",
        slug=slug,
        title="标志测",
        premise="p",
        target_chapter_count=1,
    )
    save_manifest(paths["manifest"], m)
    paths["bible"].write_text(
        '{"characters":[],"locations":[],"timeline_notes":[],"style_notes":""}',
        encoding="utf-8",
    )
    paths["outline"].write_text('{"chapters":[]}', encoding="utf-8")

    from fastapi.testclient import TestClient
    from aitext.web.app import app

    c = TestClient(app)
    r = c.get(f"/api/book/{slug}/desk")
    assert r.status_code == 200
    j = r.json()
    assert j["book"]["has_bible"] is True
    assert j["book"]["has_outline"] is True
