"""
LLM 客户端：支持 ARK/豆包 和 Anthropic/Claude
"""
import json
import logging
import os
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("aitext.clients.llm")

try:
    import httpx
except ImportError:
    httpx = None


class LLMClient:
    """通用LLM客户端，支持多种Provider"""

    def __init__(
        self,
        provider: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        quiet: bool = True,
    ):
        from ..config import Config as C

        self.provider = (provider or C.LLM_PROVIDER or "anthropic").strip().lower()
        self.timeout = int(timeout if timeout is not None else getattr(C, 'ARK_TIMEOUT', 120))
        self.quiet = quiet
        self.last_error = ""

        # 根据provider加载配置
        if self.provider == "ark":
            self.api_key = api_key or C.ARK_API_KEY
            self.base_url = (base_url or C.ARK_BASE_URL).strip()
            self.model = model or C.ARK_MODEL
        else:  # anthropic 或 openai兼容格式
            self.api_key = api_key or C.ANTHROPIC_API_KEY
            self.base_url = (base_url or C.ANTHROPIC_BASE_URL).strip()
            self.model = model or C.ANTHROPIC_MODEL

        # 确保base_url格式正确
        if self.provider == "anthropic":
            self.base_url = self.base_url.rstrip("/")
            # Anthropic原生API使用 /v1/messages
            if not self.base_url.endswith("/v1/messages"):
                self.base_url += "/v1/messages"

    @property
    def enabled(self) -> bool:
        """检查是否已配置"""
        return bool(self.api_key and self.base_url and self.model)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """转换消息格式为OpenAI兼容格式"""
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 处理system角色（Anthropic在chat completion中不支持system，需要转换为user）
            if role == "system" and self.provider == "anthropic":
                converted.append({
                    "role": "user",
                    "content": f"[System Instruction]\n{content}"
                })
            else:
                converted.append({"role": role, "content": str(content)})
        return converted

    def _request_http(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """通过HTTP请求API"""
        if not httpx:
            self.last_error = "请安装 httpx: pip install httpx"
            return None

        if not self.api_key:
            self.last_error = f"API Key 未配置"
            return None

        try:
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
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }

            payload = {
                "model": self.model,
                "max_tokens": 8192,
                "messages": chat_messages,
            }
            if system_content.strip():
                payload["system"] = system_content.strip()

            if not self.quiet:
                logger.info(f"[LLM] Request to {self.base_url}")
                logger.info(f"[LLM] Model: {self.model}")
                logger.info(f"[LLM] Messages: {len(chat_messages)}")

            t0 = time.perf_counter()

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            elapsed = time.perf_counter() - t0

            # 提取内容
            content = self._extract_content(data)
            if content:
                if not self.quiet:
                    logger.info(f"[LLM] Response received in {elapsed:.2f}s, length: {len(content)}")
                return content.strip()
            else:
                self.last_error = "响应中未找到内容"
                logger.warning(f"[LLM] {self.last_error}, response: {json.dumps(data)[:500]}")
                return None

        except httpx.TimeoutException:
            self.last_error = f"请求超时 ({self.timeout}s)"
            logger.error(f"[LLM] {self.last_error}")
            return None
        except httpx.HTTPStatusError as e:
            self.last_error = f"HTTP错误: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                self.last_error += f" - {error_detail.get('error', {}).get('message', str(error_detail))}"
            except:
                self.last_error += f" - {e.response.text[:200]}"
            logger.error(f"[LLM] {self.last_error}")
            return None
        except Exception as e:
            self.last_error = str(e)
            logger.exception(f"[LLM] 请求异常")
            return None

    def _extract_content(self, data: Dict[str, Any]) -> Optional[str]:
        """从响应中提取内容"""
        if not isinstance(data, dict):
            return None

        # OpenAI/Anthropic chat completion格式
        choices = data.get("choices", [])
        if choices and isinstance(choices, list):
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            # 处理content为list的情况
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                return "\n".join(text_parts)

        # Anthropic原生格式（messages API）
        content = data.get("content", [])
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            if text_parts:
                return "\n".join(text_parts)

        return None

    def request(self, messages: List[Dict[str, str]]) -> Optional[str]:
        """
        发送请求到LLM

        Args:
            messages: 消息列表，格式为 [{"role": "system"/"user"/"assistant", "content": "..."}]

        Returns:
            生成的文本内容，失败返回None
        """
        print(f"[LLM] 开始请求，消息数: {len(messages)}", flush=True)
        logger.info(f"[LLM] 开始请求，消息数: {len(messages)}")

        if not self.enabled:
            self.last_error = "LLM未配置：请检查 API_KEY 和 MODEL"
            logger.warning(f"[LLM] {self.last_error}")
            return None

        print(f"[LLM] 调用 {self.provider} - {self.model}", flush=True)
        content = self._request_http(messages)

        if content:
            print(f"[LLM] 生成完成，长度: {len(content)} 字符", flush=True)
            logger.debug(f"[LLM] Generated {len(content)} characters")
        else:
            print(f"[LLM] 请求失败: {self.last_error}", flush=True)
            logger.warning(f"[LLM] Empty response: {self.last_error}")

        return content
