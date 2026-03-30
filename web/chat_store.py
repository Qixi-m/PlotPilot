"""书目级对话线程：thread.json、context_digest.md、组装 LLM 上下文。"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ..clients.llm import LLMClient
from ..config import Config
from ..story.engine import (
    compact_bible,
    compact_outline,
    load_bible,
    load_manifest,
    load_outline,
    project_paths,
)
from .cast_store import compact_for_prompt, load_or_empty as load_cast_or_empty
from .story_knowledge_store import compact_for_prompt as novel_knowledge_compact
from .vector_memory import query as vector_query

logger = logging.getLogger("aitext.web.chat_store")

_registry = threading.Lock()
_thread_locks: Dict[str, threading.Lock] = {}


def _thread_lock(slug: str) -> threading.Lock:
    with _registry:
        if slug not in _thread_locks:
            _thread_locks[slug] = threading.Lock()
        return _thread_locks[slug]


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    ts: str
    meta: Optional[Dict[str, Any]] = None


class ChatThreadFile(BaseModel):
    thread_id: str
    updated_at: str
    messages: List[ChatMessage] = Field(default_factory=list)


def load_thread(root: Path) -> ChatThreadFile:
    paths = project_paths(root)
    paths["chat_dir"].mkdir(parents=True, exist_ok=True)
    p = paths["chat_thread"]
    if not p.is_file():
        return ChatThreadFile(thread_id=str(uuid.uuid4()), updated_at=_now_iso(), messages=[])
    try:
        return ChatThreadFile.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("load_thread failed, reset")
        return ChatThreadFile(thread_id=str(uuid.uuid4()), updated_at=_now_iso(), messages=[])


def save_thread(root: Path, data: ChatThreadFile) -> None:
    paths = project_paths(root)
    paths["chat_dir"].mkdir(parents=True, exist_ok=True)
    data.updated_at = _now_iso()
    paths["chat_thread"].write_text(
        data.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def append_message(
    root: Path,
    slug: str,
    role: Literal["user", "assistant", "system"],
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> ChatMessage:
    print(f"[Chat Store] 添加消息 - role={role}, 长度={len(content)}", flush=True)
    logger.info(f"[Chat] 添加消息 - slug={slug}, role={role}, 长度={len(content)}")
    with _thread_lock(slug):
        t = load_thread(root)
        msg = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            ts=_now_iso(),
            meta=meta,
        )
        t.messages.append(msg)
        save_thread(root, t)
        return msg


def list_messages(root: Path, slug: str) -> List[Dict[str, Any]]:
    with _thread_lock(slug):
        t = load_thread(root)
        return [m.model_dump() for m in t.messages]


def message_count(root: Path, slug: str) -> int:
    with _thread_lock(slug):
        return len(load_thread(root).messages)


def read_digest_text(root: Path) -> str:
    paths = project_paths(root)
    p = paths["chat_digest"]
    if not p.is_file():
        return ""
    s = p.read_text(encoding="utf-8")
    return s[: Config.CHAT_DIGEST_MAX_CHARS]


def clear_thread(root: Path, slug: str) -> None:
    """清空对话线程（不删侧栏设定/叙事文件）。"""
    with _thread_lock(slug):
        t = load_thread(root)
        t.messages = []
        save_thread(root, t)


def clear_digest_file(root: Path) -> None:
    """删除远期摘要 context_digest.md。"""
    paths = project_paths(root)
    p = paths["chat_digest"]
    if p.is_file():
        try:
            p.unlink()
        except OSError:
            logger.exception("clear_digest_file failed")


def append_digest(root: Path, text: str) -> None:
    paths = project_paths(root)
    p = paths["chat_digest"]
    p.parent.mkdir(parents=True, exist_ok=True)
    sep = "\n\n---\n" + _now_iso() + "\n\n"
    if p.is_file():
        cur = p.read_text(encoding="utf-8")
        p.write_text(cur + sep + text.strip(), encoding="utf-8")
    else:
        p.write_text("# 会话远期摘要\n\n" + text.strip(), encoding="utf-8")


def build_llm_messages(
    root: Path, slug: str, *, history_mode: Literal["full", "fresh"] = "full"
) -> List[dict]:
    print(f"[Chat Store] 构建LLM消息上下文...", flush=True)
    logger.info(f"[Chat] 构建LLM消息上下文 - slug={slug} history_mode={history_mode}")
    """基于当前 thread 组装 messages（含合并后的 system）。
    full：带近期 user/assistant 对话历史。
    fresh：仅本轮用户句 + 全书 system（不带此前多轮对话，仍含设定/梗概等侧栏注入）。
    """
    paths = project_paths(root)
    bible = load_bible(paths["bible"])
    outline = load_outline(paths["outline"])
    digest = read_digest_text(root)
    manifest = load_manifest(paths["manifest"])
    premise = manifest.premise if manifest else ""
    novel_ctx = novel_knowledge_compact(root, premise)
    # 向量检索：用最新一条用户消息作为 query，检索相关片段注入（避免全量塞上下文）。
    with _thread_lock(slug):
        t = load_thread(root)
    last_user = None
    for m in reversed(t.messages):
        if m.role == "user" and (m.content or "").strip():
            last_user = m
            break
    retrieved = []
    if last_user is not None:
        try:
            retrieved = vector_query(root, last_user.content, top_k=Config.VECTOR_TOP_K)
        except Exception:
            retrieved = []
    # t 已读取
    bible_s = (
        compact_bible(bible)
        if bible
        else "（尚无设定库，请先执行「结构规划」或在侧栏填写后保存。）"
    )
    outline_s = (
        compact_outline(outline)
        if outline
        else "（尚无分章大纲。）"
    )
    cast_g = load_cast_or_empty(root)
    cast_s = compact_for_prompt(cast_g)
    sys_parts = [
        """你是专业长篇小说编务助手（可支撑百万字量级创作），擅长：
1. 剧情与结构：对齐全书梗概、分章大纲与已写章摘要，发现矛盾与跑篇风险
2. 人物一致性：姓名、称谓、动机、关系以侧栏「设定 + 关系图 + 叙事知识」为准，不凭空改人设
3. 写作落地：给出可执行的修改建议（章号、场景、篇幅），避免空泛点评
4. 工具与资料：可调用 cast_* / story_* / kg_* 更新关系图与叙事知识，修改后简要说明

长篇小说 · 上下文工程（防跑偏）：
- 最高优先级：manifest 梗概、叙事侧栏「梗概锁定」、分章大纲；若用户建议与上述冲突，必须指出并给出修正路径
- 已写章节以「章摘要 / 知识三元组 / 滚动摘要」为准；不得编造与已记录事实矛盾的情节
- 人物以「设定库」与「人物关系网」为锚；若正文出现新角色，应提醒用户补全关系图或设定表
- 回答尽量带章号与实体名；避免与后文未写内容强行定论（可标注「待第 N 章收束」）
- 全书极长时，侧栏资料可能截断；若发现信息不足，明确提示用户补充梗概锁定或章摘要
- 章节正文存储：每章对应目录 chapters/NNN/（NNN 为三位章号），默认合并正文为 body.md；可在同目录下使用 parts/ 多个 .md，并在 chapter.json 中配置 use_parts 与 parts_order 做分场景编排，全书章号仍连续。对话中修改某章时请指明章号；合并后的正文与 GET 章节正文接口一致。
- 审稿：可调用后端自动审读接口生成意见并写入 editorial（与人工审稿字段相同）。

示例：
用户：主角动机不够清晰 → 建议在第3章增加回忆场景（约500字），用物品触发回忆，揭示动机…
用户：第5章与第7章时间矛盾 → 指出具体表述，建议改第7章开头并补第6章过渡句。""",
        "【设定库】\n" + bible_s,
        "【分章大纲摘要】\n" + outline_s,
        cast_s,
        "【全书叙事 / 章摘要 / 知识图谱上下文】\n" + novel_ctx,
    ]
    if retrieved:
        lines = []
        for i, r in enumerate(retrieved, 1):
            meta = r.get("meta") or {}
            tag = meta.get("type") or "记忆片段"
            lines.append(f"{i}. ({tag}) {r.get('text') or ''}")
        sys_parts.append("【相关资料（检索片段）】\n" + "\n".join(lines))
    if digest.strip():
        sys_parts.append(
            "【往期对话与决策摘要】\n" + digest.strip()[: Config.CHAT_DIGEST_MAX_CHARS]
        )
    ua: List[ChatMessage]
    if history_mode == "fresh":
        last_user: Optional[ChatMessage] = None
        for m in reversed(t.messages):
            if m.role == "user":
                last_user = m
                break
        ua = [last_user] if last_user else []
        logger.debug(f"[Chat] fresh 模式：仅本轮用户消息 {len(ua)} 条")
    else:
        ua = [m for m in t.messages if m.role in ("user", "assistant")]
        win = max(4, Config.CHAT_WINDOW_MESSAGES)
        ua = ua[-win:]
        total = sum(len(m.content) for m in ua)
        logger.debug(f"[Chat] 初始消息窗口: {len(ua)} 条, 总字符: {total}")
        while ua and total > Config.CHAT_MAX_CONTEXT_CHARS:
            ua = ua[1:]
            total = sum(len(m.content) for m in ua)
        logger.debug(f"[Chat] 截断后消息窗口: {len(ua)} 条, 总字符: {total}")
    messages: List[dict] = [{"role": "system", "content": "\n\n".join(sys_parts)}]
    for m in ua:
        messages.append({"role": m.role, "content": m.content})
    logger.info(f"[Chat] 最终LLM消息数: {len(messages)} (含system)")
    return messages


def regenerate_digest(root: Path, slug: str, llm: LLMClient, force: bool = False) -> bool:
    logger.info(f"[Chat] 重新生成摘要 - slug={slug}, force={force}")
    """将较早消息压缩追加到 context_digest.md。"""
    with _thread_lock(slug):
        t = load_thread(root)
    n = len(t.messages)
    if n == 0:
        return False
    if not force and n < Config.CHAT_DIGEST_TRIGGER_COUNT:
        return False
    keep = max(6, Config.CHAT_WINDOW_MESSAGES // 2)
    if n <= keep:
        if not force:
            return False
        old_msgs = t.messages
    else:
        old_msgs = t.messages[: n - keep]
    if not old_msgs:
        return False
    lines = []
    for m in old_msgs[-500:]:
        lines.append(f"{m.role}: {m.content[:2000]}")
    blob = "\n".join(lines)
    prompt = (
        "将下列编务对话与系统记录压缩为简洁中文摘要（条目或小段落），"
        "保留人设要点、剧情决策与待办。未出现的信息不要编造。\n\n" + blob[:14000]
    )
    out = llm.request(
        [
            {"role": "system", "content": "只输出摘要正文，不要标题或代码围栏。"},
            {"role": "user", "content": prompt},
        ]
    )
    if not out or not out.strip():
        return False
    append_digest(root, out.strip())
    return True


def schedule_digest_if_needed(root: Path, slug: str) -> None:
    """消息数超阈值时在后台线程更新摘要。"""
    if message_count(root, slug) < Config.CHAT_DIGEST_TRIGGER_COUNT:
        return

    def run():
        try:
            llm = LLMClient(quiet=True)
            if llm.enabled:
                regenerate_digest(root, slug, llm, force=False)
        except Exception:
            logger.exception("background digest failed")

    threading.Thread(target=run, daemon=True).start()
