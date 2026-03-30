"""
流式LLM客户端，支持SSE输出
"""
import json
import logging
from typing import List, Dict, Any, Iterator
import httpx

from ..config import Config

logger = logging.getLogger("aitext.clients.llm_stream")


def stream_llm_response(messages: List[Dict[str, str]]) -> Iterator[str]:
    """
    流式调用LLM，返回文本片段迭代器

    Args:
        messages: 消息列表 [{"role": "user"/"assistant"/"system", "content": "..."}]

    Yields:
        文本片段
    """
    print(f"[LLM Stream] 开始流式请求，消息数: {len(messages)}", flush=True)
    logger.info(f"[LLM Stream] 开始流式请求，消息数: {len(messages)}")

    # 获取配置
    provider = (Config.LLM_PROVIDER or "anthropic").strip().lower()
    logger.debug(f"[LLM Stream] Provider: {provider}")

    if provider == "anthropic":
        api_key = Config.ANTHROPIC_API_KEY
        base_url = Config.ANTHROPIC_BASE_URL.rstrip("/") + "/v1/messages"
        model = Config.ANTHROPIC_MODEL
        print(f"[LLM Stream] Model: {model}", flush=True)
        logger.debug(f"[LLM Stream] Model: {model}, Base URL: {base_url}")
    else:
        logger.error(f"不支持的provider: {provider}")
        return

    if not api_key or not model:
        logger.error("API Key 或 Model 未配置")
        return

    # 分离system消息和对话消息
    system_content = ""
    chat_messages = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_content += content + "\n"
        else:
            chat_messages.append({"role": role, "content": content})

    # Anthropic API格式
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": model,
        "max_tokens": 8192,
        "messages": chat_messages,
        "stream": True,  # 启用流式
    }
    if system_content.strip():
        payload["system"] = system_content.strip()

    try:
        print(f"[LLM Stream] 发送请求到 API...", flush=True)
        logger.info(f"[LLM Stream] 发送请求到 {base_url}")
        with httpx.Client(timeout=120) as client:
            with client.stream(
                "POST",
                base_url,
                headers=headers,
                json=payload,
            ) as response:
                print(f"[LLM Stream] 收到响应，状态码: {response.status_code}", flush=True)
                logger.info(f"[LLM Stream] 收到响应，状态码: {response.status_code}")
                response.raise_for_status()

                chunk_count = 0
                for line in response.iter_lines():
                    if not line:
                        continue

                    line = line.decode('utf-8') if isinstance(line, bytes) else line

                    # SSE格式: data: {...}
                    if line.startswith("data: "):
                        data_str = line[6:]  # 去掉 "data: " 前缀

                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)

                            # 提取内容
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text", "")
                                    if text:
                                        chunk_count += 1
                                        yield text

                            # 另一种格式
                            elif "delta" in data and "text" in data.get("delta", {}):
                                text = data["delta"]["text"]
                                if text:
                                    chunk_count += 1
                                    yield text

                        except json.JSONDecodeError:
                            continue

                print(f"[LLM Stream] 流式响应完成，共 {chunk_count} 个文本块", flush=True)
                logger.info(f"[LLM Stream] 流式响应完成，共 {chunk_count} 个文本块")

    except Exception as e:
        print(f"[LLM Stream] 异常: {e}", flush=True)
        logger.exception(f"[LLM Stream] 异常: {e}")
        return
