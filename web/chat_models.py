"""书目主会话 thread.json 的 Pydantic 模型。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ChatRole = Literal["user", "assistant", "system"]


def _ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: ChatRole
    content: str
    ts: str = Field(default_factory=_ts)
    meta: Optional[Dict[str, Any]] = None


class ChatThread(BaseModel):
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    updated_at: str = Field(default_factory=_ts)
    messages: List[ChatMessage] = Field(default_factory=list)

    def touch(self) -> None:
        self.updated_at = _ts()
