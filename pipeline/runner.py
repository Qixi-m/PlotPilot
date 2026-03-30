"""小说流水线：init → plan → write（beats+draft+summary）→ 可选 continuity → export。"""
from __future__ import annotations

import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Optional

from ..clients.llm import LLMClient
from ..config import PROJECTS_DIR, Config
from ..story.chapter_fs import write_pipeline_chapter, tail_of_previous_chapter
from ..story.engine import (
    assemble_novel,
    continuity_light_revision,
    generate_bible_and_outline,
    generate_bible_and_outline_revise,
    generate_chapter_beats,
    generate_chapter_draft,
    load_bible,
    load_manifest,
    load_outline,
    load_running_summary,
    load_story_knowledge,
    project_paths,
    save_manifest,
    save_running_summary,
    update_running_summary,
)
from ..story.models import NovelManifest
from .confirm import confirm_stage, estimate_chapter_llm_calls

logger = logging.getLogger("aitext.pipeline.runner")


def slugify(text: str) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "novel"


def safe_filename_part(title: str, max_len: int = 40) -> str:
    t = re.sub(r'[<>:"/\\|?*]', "", title).strip()
    t = re.sub(r"\s+", "_", t)
    return (t[:max_len] or "untitled").rstrip("_.")


def resolve_project_dir(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.is_dir():
        return p.resolve()
    cand = PROJECTS_DIR / name_or_path
    if cand.is_dir():
        return cand.resolve()
    raise FileNotFoundError(f"找不到项目目录: {name_or_path}")


def init_project(
    title: str,
    premise: str,
    slug: Optional[str] = None,
    genre: str = "",
    chapter_count: Optional[int] = None,
    words_per_chapter: Optional[int] = None,
    style_hint: str = "",
) -> Path:
    sl = slugify(slug or title)
    root = PROJECTS_DIR / sl
    if root.exists():
        raise FileExistsError(f"项目已存在: {root}")
    root.mkdir(parents=True)
    paths = project_paths(root)
    paths["beats_dir"].mkdir(parents=True, exist_ok=True)
    paths["chapters_dir"].mkdir(parents=True, exist_ok=True)
    manifest = NovelManifest(
        novel_id=str(uuid.uuid4()),
        slug=sl,
        title=title.strip(),
        premise=premise.strip(),
        genre=genre.strip(),
        target_chapter_count=chapter_count or Config.DEFAULT_CHAPTER_COUNT,
        target_words_per_chapter=words_per_chapter or Config.DEFAULT_WORDS_PER_CHAPTER,
        current_stage="init",
        completed_chapters=[],
        style_hint=style_hint.strip(),
    )
    save_manifest(paths["manifest"], manifest)
    logger.info("init project %s", root)
    return root


def run_plan(
    project_root: Path,
    llm: Optional[LLMClient] = None,
    dry_run: bool = False,
    mode: str = "initial",
    cancel_event: Optional[Any] = None,
) -> bool:
    paths = project_paths(project_root)
    manifest = load_manifest(paths["manifest"])
    if not manifest:
        logger.error("manifest 缺失")
        return False
    if cancel_event is not None and cancel_event.is_set():
        return False
    client = llm or LLMClient()
    if dry_run:
        print("[dry-run] 已跳过 S1 模型调用")
        return True

    use_revise = mode == "revise"
    if use_revise:
        bible = load_bible(paths["bible"])
        outline = load_outline(paths["outline"])
        if not bible or not outline:
            logger.warning("再规划需要已有 bible/outline，改为首次生成")
            use_revise = False

    if use_revise:
        sk = load_story_knowledge(paths["novel_knowledge"])
        rs = load_running_summary(paths["summary"])
        digest_tail = ""
        cd = paths.get("chat_digest")
        if cd and cd.is_file():
            digest_tail = read_tail_of_file(cd, 4000)
        bundle = generate_bible_and_outline_revise(
            client,
            manifest,
            bible,
            outline,
            rs,
            sk,
            digest_tail,
            dry_run=False,
            cancel_event=cancel_event,
        )
    else:
        bundle = generate_bible_and_outline(
            client, manifest, dry_run=False, cancel_event=cancel_event
        )

    if cancel_event is not None and cancel_event.is_set():
        print("结构规划已终止")
        return False
    if not bundle:
        print("S1 失败: 无法生成 bible/outline（检查 ARK_API_KEY 与网络）")
        return False
    paths["bible"].write_text(bundle.bible.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    paths["outline"].write_text(bundle.outline.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    manifest.mark_planned()
    # 同步章数若大纲与 manifest 不一致
    n = len(bundle.outline.chapters)
    if n > 0:
        manifest.target_chapter_count = n
    save_manifest(paths["manifest"], manifest)
    print(f"S1 完成: bible → {paths['bible']}, outline → {paths['outline']}")
    return True


def run_write(
    project_root: Path,
    chapter_from: int = 1,
    chapter_to: Optional[int] = None,
    llm: Optional[LLMClient] = None,
    dry_run: bool = False,
    continuity: bool = False,
    cancel_event: Optional[Any] = None,
) -> bool:
    paths = project_paths(project_root)
    manifest = load_manifest(paths["manifest"])
    if not manifest:
        return False
    if cancel_event is not None and cancel_event.is_set():
        print("撰稿已终止")
        return False
    bible = load_bible(paths["bible"])
    outline = load_outline(paths["outline"])
    if not bible or not outline:
        if dry_run:
            print("[dry-run] 尚无 bible/outline，跳过 write（可先执行 plan 再试）")
            return True
        print("请先执行 plan 生成 bible.json / outline.json")
        return False
    client = llm or LLMClient()
    manifest.mark_writing()
    save_manifest(paths["manifest"], manifest)

    ids = [c.id for c in sorted(outline.chapters, key=lambda x: x.id)]
    if not ids:
        print("大纲无章节")
        return False
    hi = max(ids)
    lo = min(ids)
    start = max(chapter_from, lo)
    end = min(chapter_to if chapter_to is not None else hi, hi)

    rs = load_running_summary(paths["summary"])

    for cid in range(start, end + 1):
        if cancel_event is not None and cancel_event.is_set():
            print("撰稿已终止")
            return False
        if cid not in ids:
            logger.warning("跳过不存在的章节 id=%d", cid)
            continue
        if manifest.is_chapter_done(cid) and not dry_run:
            print(f"第 {cid} 章已完成，跳过（若需重写请手动删 beats/chapters 并编辑 manifest）")
            continue

        prev_tail = ""
        if cid > lo:
            prev_tail = tail_of_previous_chapter(paths["chapters_dir"], cid - 1)

        beats = generate_chapter_beats(
            client, manifest, bible, outline, cid, rs, previous_chapter_tail=prev_tail, dry_run=dry_run
        )
        if dry_run:
            print(f"[dry-run] 将生成第 {cid} 章 beats + 正文 + 摘要")
            continue
        if not beats:
            print(f"第 {cid} 章 beats 生成失败")
            return False
        beats_path = paths["beats_dir"] / f"chapter_{cid:03d}.json"
        beats_path.write_text(beats.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")

        body = generate_chapter_draft(
            client, manifest, bible, outline, beats, rs, previous_chapter_tail=prev_tail, dry_run=dry_run
        )
        if not body:
            print(f"第 {cid} 章正文生成失败")
            return False

        if continuity:
            revised = continuity_light_revision(client, bible, body, beats.chapter_title, dry_run=dry_run)
            if revised:
                body = revised

        chap_path = write_pipeline_chapter(
            paths["chapters_dir"], cid, body, beats.chapter_title
        )

        rs = update_running_summary(
            client, manifest, cid, beats.chapter_title, body, rs, dry_run=dry_run
        )
        save_running_summary(paths["summary"], rs)

        manifest.register_chapter_done(cid)
        save_manifest(paths["manifest"], manifest)
        print(f"第 {cid} 章完成 → {chap_path}")

    return True


def run_export(project_root: Path) -> bool:
    paths = project_paths(project_root)
    outline = load_outline(paths["outline"])
    if not outline:
        print("缺少 outline.json")
        return False
    assemble_novel(paths["chapters_dir"], outline, paths["novel"])
    print(f"已合并 → {paths['novel']}")
    return True


def run_full_pipeline(
    project_root: Path,
    dry_run: bool = False,
    skip_confirm: bool = False,
    continuity: bool = False,
    llm: Optional[LLMClient] = None,
    cancel_event: Optional[Any] = None,
) -> bool:
    paths = project_paths(project_root)
    manifest = load_manifest(paths["manifest"])
    if not manifest:
        return False
    if cancel_event is not None and cancel_event.is_set():
        return False

    if manifest.current_stage == "init" or not paths["outline"].is_file():
        if not skip_confirm and not dry_run:
            n = manifest.target_chapter_count
            calls = estimate_chapter_llm_calls(n) + 1
            if not confirm_stage(
                f"将执行全书流水线：S1 规划 + 约 {n} 章 ×（章纲+正文+摘要）≈ {calls} 次 LLM 调用，是否继续？",
                default_yes=False,
            ):
                print("已取消")
                return False
        if not run_plan(
            project_root,
            llm=llm,
            dry_run=dry_run,
            mode="initial",
            cancel_event=cancel_event,
        ):
            return False

    if cancel_event is not None and cancel_event.is_set():
        return False

    manifest = load_manifest(paths["manifest"])
    if not manifest:
        return False
    chapter_hi = manifest.target_chapter_count
    if paths["outline"].is_file():
        try:
            ol = json.loads(paths["outline"].read_text(encoding="utf-8"))
            chs = ol.get("chapters") or []
            if chs:
                chapter_hi = max(c.get("id", 0) for c in chs if isinstance(c, dict))
        except Exception:
            pass

    if not dry_run and not skip_confirm:
        remaining = sum(1 for i in range(1, chapter_hi + 1) if not manifest.is_chapter_done(i))
        if remaining > 0:
            calls = estimate_chapter_llm_calls(remaining)
            if not confirm_stage(
                f"将撰写剩余约 {remaining} 章（约 {calls} 次调用），是否继续？",
                default_yes=False,
            ):
                print("已取消")
                return False

    if cancel_event is not None and cancel_event.is_set():
        return False

    if not run_write(
        project_root,
        chapter_from=1,
        chapter_to=chapter_hi,
        llm=llm,
        dry_run=dry_run,
        continuity=continuity,
        cancel_event=cancel_event,
    ):
        return False

    if dry_run:
        print("[dry-run] 跳过合并与完成标记")
        return True

    if cancel_event is not None and cancel_event.is_set():
        return False

    if not run_export(project_root):
        return False

    manifest = load_manifest(paths["manifest"])
    if manifest:
        manifest.mark_completed()
        save_manifest(paths["manifest"], manifest)
    print("全书流水线完成")
    return True
