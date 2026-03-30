"""
书稿 Web：校阅 + 与 CLI 对等的创作流水线（后台任务 + 轮询）。
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Literal, Optional

from ..load_env import load_env

load_env()

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ..clients.llm import LLMClient
from ..config import Config
from ..pipeline.confirm import estimate_chapter_llm_calls
from ..story.chapter_fs import (
    chapter_content_dir,
    chapter_has_deliverable,
    load_meta,
    read_composite_body,
)
from ..story.engine import load_manifest as load_manifest_engine
from ..story.engine import load_bible, load_outline, project_paths, save_bible
from ..story.models import Bible, CastGraph, StoryKnowledge
from .desk import (
    build_chapter_rows,
    delete_project_by_slug,
    get_chapter_review,
    list_book_roots,
    project_root_for_slug,
    read_chapter_body,
    set_chapter_review,
    write_chapter_body,
)
from . import jobs as jobq
from . import chat_store
from . import log_stream
from .vector_memory import query as vector_query
from .cast_coverage import build_cast_coverage
from .chapter_review_ai import run_ai_review
from .cast_store import load_or_empty as cast_load_or_empty
from .cast_store import save as cast_save
from .cast_store import search as cast_search_graph
from .story_knowledge_store import load_or_empty as knowledge_load_or_empty
from .story_knowledge_store import save as knowledge_save

logger = logging.getLogger("aitext.web.app")

_BASE = Path(__file__).resolve().parent

# 安装日志流处理器
log_stream.install_handler()

app = FastAPI(
    title="书稿工作台API",
    description="前后端分离架构，为前端提供书目/章节/设定/关系与任务编排接口",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f">>> {request.method} {request.url.path}", flush=True)
    logger.info(f">>> {request.method} {request.url.path}")
    if request.query_params:
        logger.debug(f"    Query: {dict(request.query_params)}")
    response = await call_next(request)
    print(f"<<< {request.method} {request.url.path} - {response.status_code}", flush=True)
    logger.info(f"<<< {request.method} {request.url.path} - {response.status_code}")
    return response

# CORS配置 - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveBodyPayload(BaseModel):
    content: str = Field(default="")


class ReviewPayload(BaseModel):
    status: str = Field(default="pending")
    memo: str = Field(default="")


class ChapterReviewAiPayload(BaseModel):
    save: bool = Field(default=False, description="为 true 时将审读结果写入 editorial.json")


class CreateBookPayload(BaseModel):
    title: str = Field(..., min_length=1)
    premise: str = Field(..., min_length=1)
    slug: Optional[str] = None
    genre: str = ""
    chapters: Optional[int] = None
    words: Optional[int] = None
    style: str = ""


class PlanJobPayload(BaseModel):
    dry_run: bool = False
    mode: Literal["initial", "revise"] = "initial"


class WriteJobPayload(BaseModel):
    from_chapter: int = Field(default=1, ge=1)
    to_chapter: Optional[int] = Field(default=None, ge=1)
    dry_run: bool = False
    continuity: bool = False


class RunJobPayload(BaseModel):
    dry_run: bool = False
    continuity: bool = False


class ChatPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=32000)
    regenerate_digest: bool = False
    use_cast_tools: bool = Field(
        default=True,
        description="为 true 时启用 graph tools（cast/story/kg，仅非流式 /chat 生效）",
    )
    history_mode: Literal["full", "fresh"] = Field(
        default="full",
        description="full=带多轮对话历史；fresh=仅本轮用户句+全书 system（仍含设定/梗概等）",
    )
    clear_thread: bool = Field(
        default=False,
        description="在写入本条用户消息前清空 thread.json（不删侧栏文件）",
    )


class ChatClearPayload(BaseModel):
    digest_too: bool = Field(default=False, description="同时清空 context_digest.md")


class AppendEventPayload(BaseModel):
    role: Literal["system", "assistant"] = "system"
    content: str = Field(..., min_length=1, max_length=16000)
    meta: Optional[Dict[str, Any]] = None


class DigestPayload(BaseModel):
    force: bool = True


def _estimate_run_stats(root: Path) -> dict:
    paths = project_paths(root)
    man = load_manifest_engine(paths["manifest"])
    if not man:
        return {
            "target_chapters": 0,
            "chapter_hi": 0,
            "remaining": 0,
            "approx_calls_run": 0,
        }
    chapter_hi = man.target_chapter_count
    if paths["outline"].is_file():
        ol = load_outline(paths["outline"])
        if ol and ol.chapters:
            chapter_hi = max(c.id for c in ol.chapters)
    remaining = sum(1 for i in range(1, chapter_hi + 1) if not man.is_chapter_done(i))
    approx = estimate_chapter_llm_calls(remaining) + 1 if remaining else 1
    return {
        "target_chapters": man.target_chapter_count,
        "chapter_hi": chapter_hi,
        "remaining": remaining,
        "approx_calls_run": approx,
    }


# 首页现在由Vue前端StaticFiles处理
# 保留API端点供前端调用
@app.get("/api/books")
def api_books():
    logger.info("GET /api/books - 获取书籍列表")
    books = []
    for root in list_book_roots():
        m = load_manifest_engine(project_paths(root)["manifest"])
        if not m:
            continue
        books.append({
            "slug": m.slug,
            "title": m.title,
            "genre": m.genre or "—",
            "stage": m.current_stage,
            "stage_label": m.current_stage or "草稿"
        })
    logger.debug(f"返回 {len(books)} 本书籍")
    return JSONResponse(books)


@app.delete("/api/book/{slug}")
def api_delete_book(slug: str):
    """删除书目（移除项目目录）。后台任务执行中时不允许删除。"""
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再删除")
    if not project_root_for_slug(slug):
        raise HTTPException(status_code=404, detail="not found")
    if not delete_project_by_slug(slug):
        raise HTTPException(status_code=500, detail="删除失败")
    logger.info("DELETE /api/book/%s - 书目已删除", slug)
    return JSONResponse({"ok": True})


@app.get("/api/book/{slug}/desk")
def api_book_desk(slug: str):
    """工作台：书目摘要 + 章节列表（含是否已有正文）。"""
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    info, rows = build_chapter_rows(root)
    if info is None:
        return JSONResponse({"book": None, "chapters": []})
    return JSONResponse({"book": info, "chapters": rows})


@app.get("/api/book/{slug}/chapter/{chapter_id:int}/body")
def api_get_chapter_body(slug: str, chapter_id: int):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    _path, text = read_chapter_body(root, chapter_id)
    return JSONResponse({"content": text, "filename": _path.name if _path else None})


@app.get("/api/book/{slug}/chapter/{chapter_id:int}/review")
def api_get_chapter_review(slug: str, chapter_id: int):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    r = get_chapter_review(root, chapter_id)
    return JSONResponse({"status": r["status"], "memo": r["memo"]})


# 页面路由现在由Vue前端处理
# 以下保留API端点供前端调用

@app.put("/api/book/{slug}/chapter/{chapter_id:int}/body")
def api_save_body(slug: str, chapter_id: int, payload: SaveBodyPayload):
    logger.info(f"PUT /api/book/{slug}/chapter/{chapter_id}/body - 保存章节正文，长度={len(payload.content)}")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    if not write_chapter_body(root, chapter_id, payload.content):
        raise HTTPException(status_code=400, detail="无法保存")
    logger.info(f"章节 {chapter_id} 保存成功")
    return JSONResponse({"ok": True})


@app.put("/api/book/{slug}/chapter/{chapter_id:int}/review")
def api_save_review(slug: str, chapter_id: int, payload: ReviewPayload):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    set_chapter_review(root, chapter_id, payload.status, payload.memo)
    return JSONResponse({"ok": True})


@app.post("/api/book/{slug}/chapter/{chapter_id:int}/review-ai")
def api_chapter_review_ai(slug: str, chapter_id: int, payload: ChapterReviewAiPayload):
    """自动审读：返回 status / memo；可选直接写入 editorial。"""
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    llm = LLMClient(quiet=True)
    if not llm.enabled:
        raise HTTPException(status_code=503, detail=llm.last_error or "LLM 不可用")
    ok, data = run_ai_review(root, chapter_id, llm)
    if not ok:
        raise HTTPException(status_code=400, detail=str(data.get("error") or "审稿失败"))
    status = str(data.get("status") or "pending")
    memo = str(data.get("memo") or "")
    if payload.save:
        set_chapter_review(root, chapter_id, status, memo)
    return JSONResponse({"ok": True, "status": status, "memo": memo, "saved": payload.save})


@app.get("/api/book/{slug}/chapter/{chapter_id:int}/structure")
def api_chapter_structure(slug: str, chapter_id: int):
    """章节目录与 meta（分场景 parts、章节关系）供前端或编务引用。"""
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    paths = project_paths(root)
    cdir = chapter_content_dir(paths["chapters_dir"], chapter_id)
    meta = load_meta(cdir) if cdir.is_dir() else None
    text = read_composite_body(paths["chapters_dir"], chapter_id)
    rel = str(cdir.relative_to(root)).replace("\\", "/") if cdir.is_dir() else None
    return JSONResponse(
        {
            "chapter_id": chapter_id,
            "storage_dir": rel,
            "meta": meta.model_dump() if meta else None,
            "has_content": chapter_has_deliverable(paths["chapters_dir"], chapter_id),
            "composite_char_len": len(text),
        }
    )


@app.get("/api/book/{slug}/bible")
def api_get_bible(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    paths = project_paths(root)
    b = load_bible(paths["bible"])
    if not b:
        return JSONResponse(Bible().model_dump())
    return JSONResponse(b.model_dump())


@app.put("/api/book/{slug}/bible")
def api_put_bible(slug: str, payload: Bible):
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再保存设定")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    paths = project_paths(root)
    save_bible(paths["bible"], payload)
    chat_store.append_message(root, slug, "system", "设定库已更新（侧栏保存）。")
    return JSONResponse({"ok": True})


@app.get("/api/book/{slug}/cast")
def api_get_cast(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    g = cast_load_or_empty(root)
    return JSONResponse(g.model_dump())


@app.put("/api/book/{slug}/cast")
def api_put_cast(slug: str, payload: CastGraph):
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再保存人物关系网")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    cast_save(root, payload)
    chat_store.append_message(root, slug, "system", "人物关系网已更新（页面保存）。")
    return JSONResponse({"ok": True})


@app.get("/api/book/{slug}/cast/search")
def api_cast_search(slug: str, q: str = Query("", description="关键词")):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    g = cast_load_or_empty(root)
    ch, rel = cast_search_graph(g, q)
    return JSONResponse(
        {
            "characters": [c.model_dump() for c in ch],
            "relationships": [r.model_dump() for r in rel],
        }
    )


@app.get("/api/book/{slug}/cast/coverage")
def api_cast_coverage(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(build_cast_coverage(root))


@app.get("/api/book/{slug}/knowledge")
def api_get_knowledge(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    sk = knowledge_load_or_empty(root)
    return JSONResponse(sk.model_dump())


@app.put("/api/book/{slug}/knowledge")
def api_put_knowledge(slug: str, payload: StoryKnowledge):
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再保存知识图谱")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    knowledge_save(root, payload)
    chat_store.append_message(root, slug, "system", "全书知识图谱与章摘要已更新（侧栏保存）。")
    return JSONResponse({"ok": True})


@app.get("/api/book/{slug}/knowledge/search")
def api_knowledge_search(
    slug: str,
    q: str = Query("", description="检索关键词（自然语言）"),
    k: int = Query(6, ge=1, le=30, description="返回条数"),
):
    """全书资料检索：向量召回（人物/关系/章摘要/事实等）。"""
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    hits = vector_query(root, q, top_k=k)
    return JSONResponse({"ok": True, "query": q, "hits": hits})


@app.get("/api/book/{slug}/chat/messages")
def api_chat_messages(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse({"messages": chat_store.list_messages(root, slug)})


@app.post("/api/book/{slug}/chat/clear")
def api_chat_clear(slug: str, payload: ChatClearPayload):
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再试")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    chat_store.clear_thread(root, slug)
    if payload.digest_too:
        chat_store.clear_digest_file(root)
    return JSONResponse({"ok": True})


@app.post("/api/book/{slug}/chat")
def api_chat_turn(slug: str, payload: ChatPayload):
    print(f"[Chat] 收到对话请求 - slug={slug}", flush=True)
    logger.info(f"POST /api/book/{slug}/chat - 非流式对话")
    logger.debug(f"消息内容: {payload.message[:100]}...")
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再发送")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    if payload.clear_thread:
        chat_store.clear_thread(root, slug)
    text = payload.message.strip()
    chat_store.append_message(root, slug, "user", text)
    llm = LLMClient(quiet=True)
    if payload.regenerate_digest and llm.enabled:
        chat_store.regenerate_digest(root, slug, llm, force=True)
    if not llm.enabled:
        err = "服务暂不可用，请检查配置与网络。"
        chat_store.append_message(root, slug, "assistant", err)
        return JSONResponse({"ok": False, "reply": err, "llm_enabled": False, "tool_calls": []})
    print(f"[Chat] 开始调用LLM（history_mode={payload.history_mode}, tools={payload.use_cast_tools}）...", flush=True)
    msgs = chat_store.build_llm_messages(root, slug, history_mode=payload.history_mode)
    from ..clients.llm_chat_tools import run_chat_with_cast_tools

    tool_calls: List[Dict[str, Any]] = []
    reply = ""
    if payload.use_cast_tools:
        raw = run_chat_with_cast_tools(root, slug, msgs)
        if raw is None:
            reply = (llm.request(msgs) or "").strip()
        else:
            reply = (raw.get("reply") or "").strip()
            tool_calls = list(raw.get("tools") or [])
            if not reply:
                reply = (llm.request(msgs) or "").strip()
    else:
        reply = (llm.request(msgs) or "").strip()

    if not reply or not reply.strip():
        err = "暂时无法生成回复，请稍后重试。"
        chat_store.append_message(root, slug, "assistant", err)
        return JSONResponse({"ok": False, "reply": err, "llm_enabled": True, "tool_calls": tool_calls})
    reply = reply.strip()
    print(f"[Chat] LLM回复完成，长度={len(reply)}", flush=True)
    meta = {"tools": tool_calls} if tool_calls else None
    chat_store.append_message(root, slug, "assistant", reply, meta=meta)
    chat_store.schedule_digest_if_needed(root, slug)
    return JSONResponse({"ok": True, "reply": reply, "llm_enabled": True, "tool_calls": tool_calls})


def _sse_chunk_text(reply: str, size: int = 40) -> Iterator[str]:
    """将整段正文切成小块，模拟流式输出（工具路径下最终文为非流式 API 生成）。"""
    if not reply:
        return
    for i in range(0, len(reply), size):
        yield reply[i : i + size]


@app.post("/api/book/{slug}/chat/stream")
def api_chat_stream(slug: str, payload: ChatPayload):
    """流式聊天：纯文本走 LLM 流式；工具模式则 SSE 推送每步工具（类 thinking）再分块推送正文。"""

    logger.info(f"POST /api/book/{slug}/chat/stream - 流式聊天 tools={payload.use_cast_tools}")
    logger.debug(f"消息内容: {payload.message[:100]}...")
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再发送")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")

    from ..clients.llm_chat_tools import iter_chat_tool_events
    from ..clients.llm_stream import stream_llm_response

    text = payload.message.strip()
    if payload.clear_thread:
        chat_store.clear_thread(root, slug)
    chat_store.append_message(root, slug, "user", text)

    llm = LLMClient(quiet=True)
    msgs = chat_store.build_llm_messages(root, slug, history_mode=payload.history_mode)
    if payload.regenerate_digest and llm.enabled:
        chat_store.regenerate_digest(root, slug, llm, force=True)

    def generate() -> Iterator[str]:
        if not llm.enabled:
            err = "服务暂不可用，请检查配置与网络。"
            chat_store.append_message(root, slug, "assistant", err)
            yield f"data: {json.dumps({'type': 'error', 'message': err})}\n\n"
            return

        if payload.use_cast_tools:
            final_reply = ""
            for ev in iter_chat_tool_events(root, slug, msgs):
                k = ev.get("kind")
                if k == "tool":
                    te = {"name": ev.get("name"), "ok": ev.get("ok"), "detail": ev.get("detail")}
                    yield f"data: {json.dumps({'type': 'tool', **te})}\n\n"
                elif k == "error":
                    msg = str(ev.get("message") or "工具对话失败")
                    yield f"data: {json.dumps({'type': 'error', 'message': msg})}\n\n"
                    chat_store.append_message(root, slug, "assistant", msg)
                    return
                elif k == "final":
                    final_reply = ev.get("reply") or ""
                    tool_calls = list(ev.get("tools") or [])
                    for part in _sse_chunk_text(final_reply, 40):
                        yield f"data: {json.dumps({'type': 'chunk', 'text': part})}\n\n"
                    meta = {"tools": tool_calls} if tool_calls else None
                    chat_store.append_message(
                        root, slug, "assistant", final_reply.strip() or "（无正文）", meta=meta
                    )
                    chat_store.schedule_digest_if_needed(root, slug)
                    yield f"data: {json.dumps({'type': 'done', 'reply': final_reply, 'tool_calls': tool_calls})}\n\n"
                    return
            yield f"data: {json.dumps({'type': 'error', 'message': '未收到模型结束事件'})}\n\n"
            return

        full_reply: List[str] = []
        for chunk in stream_llm_response(msgs):
            if chunk:
                full_reply.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
        reply = "".join(full_reply)
        if reply.strip():
            chat_store.append_message(root, slug, "assistant", reply)
            chat_store.schedule_digest_if_needed(root, slug)
            yield f"data: {json.dumps({'type': 'done', 'reply': reply})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'error', 'message': '生成失败'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/book/{slug}/chat/append_event")
def api_chat_append_event(slug: str, payload: AppendEventPayload):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    msg = chat_store.append_message(
        root, slug, payload.role, payload.content.strip(), meta=payload.meta
    )
    return JSONResponse({"ok": True, "id": msg.id})


@app.post("/api/book/{slug}/chat/digest")
def api_chat_digest(slug: str, payload: DigestPayload):
    if jobq.is_slug_busy(slug):
        raise HTTPException(status_code=409, detail="后台任务执行中，请稍后再整理摘要")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    llm = LLMClient(quiet=True)
    if not llm.enabled:
        raise HTTPException(status_code=503, detail="服务暂不可用")
    ok = chat_store.regenerate_digest(root, slug, llm, force=payload.force)
    return JSONResponse({"ok": ok})


@app.post("/api/jobs/create-book")
def api_create_book(payload: CreateBookPayload):
    logger.info(f"POST /api/jobs/create-book - 创建新书: {payload.title}")
    try:
        slug = jobq.create_book(
            title=payload.title.strip(),
            premise=payload.premise.strip(),
            slug=(payload.slug.strip() if payload.slug else None),
            genre=payload.genre.strip(),
            chapter_count=payload.chapters,
            words_per_chapter=payload.words,
            style_hint=payload.style.strip(),
        )
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"新书创建成功: slug={slug}")
    return JSONResponse({"ok": True, "slug": slug})


@app.post("/api/jobs/{slug}/plan")
def api_job_plan(slug: str, payload: PlanJobPayload):
    logger.info(f"POST /api/jobs/{slug}/plan - 提交规划任务")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    job_id = jobq.submit_plan(root, slug, payload.dry_run, mode=payload.mode)
    if not job_id:
        raise HTTPException(status_code=409, detail="该书目尚有任务在执行，请稍候")
    logger.info(f"规划任务已提交: job_id={job_id}")
    return JSONResponse({"ok": True, "job_id": job_id})


@app.post("/api/jobs/{slug}/write")
def api_job_write(slug: str, payload: WriteJobPayload):
    logger.info(f"POST /api/jobs/{slug}/write - 提交写作任务，章节范围: {payload.from_chapter}-{payload.to_chapter}")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    job_id = jobq.submit_write(
        root,
        slug,
        payload.from_chapter,
        payload.to_chapter,
        payload.dry_run,
        payload.continuity,
    )
    if not job_id:
        raise HTTPException(status_code=409, detail="该书目尚有任务在执行，请稍候")
    logger.info(f"写作任务已提交: job_id={job_id}")
    return JSONResponse({"ok": True, "job_id": job_id})


@app.post("/api/jobs/{slug}/run")
def api_job_run(slug: str, payload: RunJobPayload):
    logger.info(f"POST /api/jobs/{slug}/run - 提交完整流水线任务")
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    job_id = jobq.submit_run(root, slug, payload.dry_run, payload.continuity)
    if not job_id:
        raise HTTPException(status_code=409, detail="该书目尚有任务在执行，请稍候")
    logger.info(f"流水线任务已提交: job_id={job_id}")
    return JSONResponse({"ok": True, "job_id": job_id})


@app.post("/api/jobs/{slug}/export")
def api_job_export(slug: str):
    root = project_root_for_slug(slug)
    if not root:
        raise HTTPException(status_code=404, detail="not found")
    result = jobq.run_export_sync(root, slug)
    if result is None:
        raise HTTPException(status_code=409, detail="该书目尚有任务在执行，请稍候")
    if not result:
        raise HTTPException(status_code=400, detail="合并失败，请确认已有大纲与章节正文")
    return JSONResponse({"ok": True})


@app.post("/api/jobs/{job_id}/cancel")
def api_job_cancel(job_id: str):
    """终止后台任务（规划/撰稿/一键成书在检查点停止）。"""
    if not jobq.cancel_job(job_id):
        raise HTTPException(status_code=404, detail="任务不存在或已结束")
    return JSONResponse({"ok": True})


@app.get("/api/jobs/{job_id}")
def api_job_status(job_id: str):
    logger.debug(f"GET /api/jobs/{job_id} - 查询任务状态")
    rec = jobq.get_job(job_id)
    if not rec:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(jobq.job_to_response(rec))


@app.get("/api/logs/stream")
async def api_logs_stream():
    """实时日志流 SSE 端点"""
    async def generate():
        queue = log_stream.subscribe()
        try:
            while True:
                try:
                    log_entry = queue.get_nowait()
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except Empty:
                    yield f": heartbeat\n\n"
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            log_stream.unsubscribe(queue)
            raise
        except Exception as e:
            print(f"日志流异常: {e}", flush=True)
            log_stream.unsubscribe(queue)
            raise

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

