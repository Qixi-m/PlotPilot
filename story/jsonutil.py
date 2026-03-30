"""从 LLM 返回文本中解析 JSON。"""
import json
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def strip_markdown_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if len(lines) < 2:
        return t
    # ```json ... ``` or ``` ... ```
    inner = lines[1:-1] if lines[-1].strip().startswith("```") else lines[1:]
    return "\n".join(inner).strip()


def parse_json_loose(text: str) -> Optional[Any]:
    if not text or not isinstance(text, str):
        return None
    raw = strip_markdown_fence(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # object
    start, end = raw.find("{"), raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    # array
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    return None


def parse_model(text: str, model_cls: Type[T]) -> Optional[T]:
    data = parse_json_loose(text)
    if data is None:
        return None
    try:
        return model_cls.model_validate(data)
    except Exception:
        return None
