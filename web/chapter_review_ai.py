"""自动审读：基于合并正文与大纲一句纲，输出 editorial 可写入的 status + memo。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..clients.llm import LLMClient
from ..story.chapter_fs import read_composite_body
from ..story.engine import load_outline, outline_chapter, project_paths
from ..story.jsonutil import parse_json_loose

logger = logging.getLogger("aitext.web.chapter_review_ai")

SYSTEM = """你是资深网络小说责编。只输出合法 JSON，不要 markdown 围栏，不要解释性前后文。
JSON 须可被标准库 json.loads 直接解析。
键名固定：status（字符串，取 pending / ok / revise 之一）、memo（字符串，审稿意见，可多条分段）。"""


def build_review_prompt(chapter_id: int, title: str, one_liner: str, body_excerpt: str) -> str:
    ol = (one_liner or "").strip() or "（大纲未填一句纲）"
    return f"""请审读下列第 {chapter_id} 章正文节选（相对全书可能截断），对照本章标题与一句纲，从连载可读性、人设一致、节奏与伏笔三方面给出意见。

【本章标题】{title}
【大纲一句纲】{ol}

【正文节选】
{body_excerpt}

输出 JSON 示例：
{{"status":"revise","memo":"1. …\\n2. …"}}
status 说明：ok=可收稿；revise=建议修改后再审；pending=信息不足无法判断。"""


def run_ai_review(
    root: Path,
    chapter_id: int,
    llm: LLMClient,
    *,
    max_body_chars: int = 14000,
) -> Tuple[bool, Dict[str, Any]]:
    """成功时返回 (True, {{status, memo}})；失败 (False, {{error}})。"""
    paths = project_paths(root)
    outline = load_outline(paths["outline"])
    oc = outline_chapter(outline, chapter_id) if outline else None
    title = ""
    one_liner = ""
    if oc:
        _, title, one_liner = oc

    body = read_composite_body(paths["chapters_dir"], chapter_id)
    if not body.strip():
        return False, {"error": "本章尚无正文（含分场景 parts 合并后为空）"}

    excerpt = body.strip()
    if len(excerpt) > max_body_chars:
        excerpt = excerpt[: max_body_chars - 20] + "\n…（以下截断）"

    if not llm.enabled:
        return False, {"error": llm.last_error or "LLM 不可用"}

    text = llm.request(
        [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": build_review_prompt(chapter_id, title or f"第{chapter_id}章", one_liner, excerpt),
            },
        ]
    )
    if not text:
        return False, {"error": "模型无返回"}

    data = parse_json_loose(text)
    if not isinstance(data, dict):
        return False, {"error": "无法解析审稿 JSON"}

    status = str(data.get("status") or "pending").lower()
    if status not in ("pending", "ok", "revise"):
        status = "pending"
    memo = str(data.get("memo") or "").strip()
    return True, {"status": status, "memo": memo}
