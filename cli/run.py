"""
aitext CLI：init | plan | write | run | export
加载包根目录 .env（与 aivideo 一致）。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from ..load_env import load_env

load_env()

from ..clients.llm import LLMClient
from ..config import Config
from ..pipeline.runner import (
    init_project,
    resolve_project_dir,
    run_export,
    run_full_pipeline,
    run_plan,
    run_write,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aitext.cli")


def cmd_init(args):
    try:
        root = init_project(
            title=args.title,
            premise=args.premise,
            slug=args.slug,
            genre=args.genre or "",
            chapter_count=args.chapters,
            words_per_chapter=args.words,
            style_hint=args.style or "",
        )
    except FileExistsError as e:
        print(e)
        return 1
    print(f"项目已创建: {root}")
    print("下一步: python -m aitext plan " + root.name)
    return 0


def cmd_plan(args):
    try:
        root = resolve_project_dir(args.project)
    except FileNotFoundError as e:
        print(e)
        return 1
    llm = LLMClient(quiet=not args.verbose)
    ok = run_plan(root, llm=llm, dry_run=args.dry_run)
    return 0 if ok else 1


def cmd_write(args):
    try:
        root = resolve_project_dir(args.project)
    except FileNotFoundError as e:
        print(e)
        return 1
    llm = LLMClient(quiet=not args.verbose)
    ok = run_write(
        root,
        chapter_from=args.from_chapter,
        chapter_to=args.to_chapter,
        llm=llm,
        dry_run=args.dry_run,
        continuity=args.continuity,
    )
    return 0 if ok else 1


def cmd_run(args):
    try:
        root = resolve_project_dir(args.project)
    except FileNotFoundError as e:
        print(e)
        return 1
    llm = LLMClient(quiet=not args.verbose)
    ok = run_full_pipeline(
        root,
        dry_run=args.dry_run,
        skip_confirm=args.yes,
        continuity=args.continuity,
        llm=llm,
    )
    return 0 if ok else 1


def cmd_export(args):
    try:
        root = resolve_project_dir(args.project)
    except FileNotFoundError as e:
        print(e)
        return 1
    ok = run_export(root)
    return 0 if ok else 1


def cmd_serve(args):
    import uvicorn
    import sys

    # 禁用Python输出缓冲
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # 强制配置日志到标准输出
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除现有handlers
    root_logger.handlers.clear()

    # 添加控制台handler，强制刷新
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 设置各模块日志级别
    logging.getLogger("aitext").setLevel(logging.DEBUG)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    print("=" * 60, flush=True)
    print("日志系统已配置 - DEBUG 级别", flush=True)
    print("=" * 60, flush=True)

    uvicorn.run(
        "aitext.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,  # 禁用uvicorn的日志配置
        access_log=True,
    )
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="aitext", description="长篇书稿流水线与校阅（对齐 aivideo 分层）")
    p.add_argument("-v", "--verbose", action="store_true", help="LLM 流式输出显示在终端")
    sub = p.add_subparsers(dest="command", required=True, metavar="{init,plan,write,run,export,serve}")

    s_init = sub.add_parser("init", help="创建项目目录与 manifest.json")
    s_init.add_argument("--title", required=True, help="书名")
    s_init.add_argument("--premise", required=True, help="梗概")
    s_init.add_argument("--slug", default=None, help="目录名（默认由书名生成）")
    s_init.add_argument("--genre", default="", help="类型")
    s_init.add_argument("--chapters", type=int, default=None, help=f"章数（默认 {Config.DEFAULT_CHAPTER_COUNT}）")
    s_init.add_argument("--words", type=int, default=None, help=f"每章目标字数（默认 {Config.DEFAULT_WORDS_PER_CHAPTER}）")
    s_init.add_argument("--style", default="", help="风格提示")
    s_init.set_defaults(func=cmd_init)

    s_plan = sub.add_parser("plan", help="S1：生成 bible.json + outline.json")
    s_plan.add_argument("project", help="项目目录名（在 output/novels/ 下）或绝对路径")
    s_plan.add_argument("--dry-run", action="store_true", help="不调用模型")
    s_plan.set_defaults(func=cmd_plan)

    s_write = sub.add_parser("write", help="S2–S3：按章生成 beats、正文、滚动摘要")
    s_write.add_argument("project", help="项目名或路径")
    s_write.add_argument("--from", dest="from_chapter", type=int, default=1, help="起始章号")
    s_write.add_argument("--to", dest="to_chapter", type=int, default=None, help="结束章号（默认可选：写到最后一章）")
    s_write.add_argument("--dry-run", action="store_true", help="只打印将执行的章节")
    s_write.add_argument("--continuity", action="store_true", help="每章后做轻量一致性修订")
    s_write.set_defaults(func=cmd_write)

    s_run = sub.add_parser("run", help="一键：plan（若需）+ 全书 write + export")
    s_run.add_argument("project", help="项目名或路径")
    s_run.add_argument("--dry-run", action="store_true", help="不调用模型、不写文件")
    s_run.add_argument("-y", "--yes", action="store_true", help="跳过耗时前的确认")
    s_run.add_argument("--continuity", action="store_true", help="轻量一致性修订")
    s_run.set_defaults(func=cmd_run)

    s_exp = sub.add_parser("export", help="S5：按 outline 合并 chapters → novel.md")
    s_exp.add_argument("project", help="项目名或路径")
    s_exp.set_defaults(func=cmd_export)

    s_serve = sub.add_parser("serve", help="启动书稿校阅 Web（浏览器打开，默认仅本机）")
    s_serve.add_argument("--host", default="127.0.0.1", help="监听地址")
    s_serve.add_argument("--port", type=int, default=8005, help="端口（与 web-app Vite 代理默认一致）")
    s_serve.add_argument("--reload", action="store_true", help="开发时热重载")
    s_serve.set_defaults(func=cmd_serve)

    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
