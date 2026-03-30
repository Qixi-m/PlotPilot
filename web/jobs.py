"""后台任务：结构规划 / 分章撰稿 / 一键成书；同书目互斥锁。"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..clients.llm import LLMClient
from ..pipeline.runner import (
    init_project,
    run_export,
    run_full_pipeline,
    run_plan,
    run_write,
)

logger = logging.getLogger("aitext.web.jobs")

_registry_lock = threading.Lock()
_slug_locks: Dict[str, threading.Lock] = {}
_jobs: Dict[str, Dict[str, Any]] = {}
_job_cancel_events: Dict[str, threading.Event] = {}


def _slug_lock(slug: str) -> threading.Lock:
    with _registry_lock:
        if slug not in _slug_locks:
            _slug_locks[slug] = threading.Lock()
        return _slug_locks[slug]


def try_acquire_book(slug: str) -> bool:
    return _slug_lock(slug).acquire(blocking=False)


def is_slug_busy(slug: str) -> bool:
    """书目是否有后台任务占用锁（结构规划/撰稿等）。"""
    return _slug_lock(slug).locked()


def release_book(slug: str) -> None:
    lk = _slug_lock(slug)
    try:
        if lk.locked():
            lk.release()
    except RuntimeError:
        pass


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def new_job_record(kind: str, slug: str) -> Dict[str, Any]:
    return {
        "job_id": str(uuid.uuid4()),
        "kind": kind,
        "slug": slug,
        "status": "queued",
        "phase": "queued",
        "message": "",
        "error": None,
        "started": None,
        "finished": None,
    }


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)


def _run_in_thread(job_id: str, slug: str, work: Callable[[], bool], label: str) -> None:
    rec = _jobs[job_id]
    ev = _job_cancel_events.get(job_id)
    rec["status"] = "running"
    rec["phase"] = "running"
    rec["message"] = label
    rec["started"] = _now_iso()
    ok = False
    try:
        ok = bool(work())
        if ev and ev.is_set():
            rec["status"] = "cancelled"
            rec["phase"] = "cancelled"
            rec["message"] = "已终止"
            rec["error"] = None
        elif ok:
            rec["status"] = "done"
            rec["phase"] = "done"
            rec["error"] = None
        else:
            rec["status"] = "error"
            rec["phase"] = "error"
            rec["error"] = "任务未成功完成，请检查日志、网络与接口配置"
            rec["message"] = rec["error"]
    except Exception as e:
        logger.exception("job %s failed", job_id)
        if ev and ev.is_set():
            rec["status"] = "cancelled"
            rec["phase"] = "cancelled"
            rec["message"] = "已终止"
            rec["error"] = None
        else:
            rec["status"] = "error"
            rec["phase"] = "error"
            rec["error"] = str(e)
            rec["message"] = str(e)
    finally:
        rec["finished"] = _now_iso()
        release_book(slug)
        _job_cancel_events.pop(job_id, None)


def submit_plan(root: Path, slug: str, dry_run: bool, mode: str = "initial") -> Optional[str]:
    if not try_acquire_book(slug):
        return None
    rec = new_job_record("plan", slug)
    job_id = rec["job_id"]
    _jobs[job_id] = rec
    ev = threading.Event()
    _job_cancel_events[job_id] = ev

    def work() -> bool:
        if ev.is_set():
            return False
        rec["message"] = "结构规划中…" if not dry_run else "预演结构规划（无外部调用）…"
        client = LLMClient(quiet=True)
        return run_plan(root, llm=client, dry_run=dry_run, mode=mode, cancel_event=ev)

    threading.Thread(
        target=_run_in_thread,
        args=(job_id, slug, work, "结构规划"),
        daemon=True,
    ).start()
    return job_id


def submit_write(
    root: Path,
    slug: str,
    chapter_from: int,
    chapter_to: Optional[int],
    dry_run: bool,
    continuity: bool,
) -> Optional[str]:
    if not try_acquire_book(slug):
        return None
    rec = new_job_record("write", slug)
    job_id = rec["job_id"]
    _jobs[job_id] = rec
    ev = threading.Event()
    _job_cancel_events[job_id] = ev

    def work() -> bool:
        if ev.is_set():
            return False
        rec["message"] = "分章撰稿中…" if not dry_run else "预演撰稿流程…"
        client = LLMClient(quiet=True)
        return run_write(
            root,
            chapter_from=chapter_from,
            chapter_to=chapter_to,
            llm=client,
            dry_run=dry_run,
            continuity=continuity,
            cancel_event=ev,
        )

    threading.Thread(
        target=_run_in_thread,
        args=(job_id, slug, work, "分章撰稿"),
        daemon=True,
    ).start()
    return job_id


def submit_run(root: Path, slug: str, dry_run: bool, continuity: bool) -> Optional[str]:
    if not try_acquire_book(slug):
        return None
    rec = new_job_record("run", slug)
    job_id = rec["job_id"]
    _jobs[job_id] = rec
    ev = threading.Event()
    _job_cancel_events[job_id] = ev

    def work() -> bool:
        if ev.is_set():
            return False
        rec["message"] = "一键成书执行中…" if not dry_run else "预演全书流程…"
        client = LLMClient(quiet=True)
        return run_full_pipeline(
            root,
            dry_run=dry_run,
            skip_confirm=True,
            continuity=continuity,
            llm=client,
            cancel_event=ev,
        )

    threading.Thread(
        target=_run_in_thread,
        args=(job_id, slug, work, "一键成书"),
        daemon=True,
    ).start()
    return job_id


def run_export_sync(root: Path, slug: str):
    """成功 True，合并失败 False，书目锁占用 None。"""
    if not try_acquire_book(slug):
        return None
    try:
        return run_export(root)
    finally:
        release_book(slug)


def create_book(
    title: str,
    premise: str,
    slug: Optional[str],
    genre: str,
    chapter_count: Optional[int],
    words_per_chapter: Optional[int],
    style_hint: str,
) -> str:
    root = init_project(
        title=title,
        premise=premise,
        slug=slug,
        genre=genre or "",
        chapter_count=chapter_count,
        words_per_chapter=words_per_chapter,
        style_hint=style_hint or "",
    )
    return root.name


def cancel_job(job_id: str) -> bool:
    """请求终止后台任务（在下一检查点生效）。成功返回 True。"""
    rec = _jobs.get(job_id)
    if not rec:
        return False
    if rec["status"] not in ("queued", "running"):
        return False
    ev = _job_cancel_events.get(job_id)
    if ev:
        ev.set()
    return True


def job_to_response(rec: Dict[str, Any]) -> Dict[str, Any]:
    terminal = rec["status"] in ("done", "error", "cancelled")
    return {
        "job_id": rec["job_id"],
        "kind": rec["kind"],
        "slug": rec["slug"],
        "status": rec["status"],
        "phase": rec["phase"],
        "message": rec.get("message") or "",
        "error": rec.get("error"),
        "started": rec.get("started"),
        "finished": rec.get("finished"),
        "done": terminal,
        "ok": rec["status"] == "done",
    }
