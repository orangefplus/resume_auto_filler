"""Qwen LLM 客户端封装。"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from backend.config import Config, get_config

logger = logging.getLogger(__name__)


class LLMClient:
    """DashScope OpenAI 兼容接口客户端。支持同步 JSON 输出。"""

    def __init__(self, config: Optional[Config] = None, timeout: float = 60.0):
        self.config = config or get_config()
        self.client = httpx.Client(timeout=timeout)

    @property
    def api_key(self) -> str:
        return self.config.dashscope_api_key

    @property
    def base_url(self) -> str:
        return self.config.base_url

    @property
    def text_model(self) -> str:
        return self.config.text_model

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        """普通对话，返回字符串。"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self.text_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        start = time.time()
        resp = self.client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        elapsed = time.time() - start
        content = data["choices"][0]["message"]["content"]
        logger.info("LLM call %.2fs model=%s", elapsed, payload["model"])
        return content

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 3000,
    ) -> Any:
        """对话并强制解析 JSON。失败时抛出 ValueError。"""
        # 在 system 中追加 JSON-only 指令
        json_messages = list(messages)
        if json_messages and json_messages[0].get("role") == "system":
            json_messages[0] = {
                "role": "system",
                "content": json_messages[0]["content"]
                + "\n\n[重要] 你必须只输出合法 JSON，不要任何解释或 Markdown 代码块标记。",
            }
        else:
            json_messages.insert(
                0,
                {
                    "role": "system",
                    "content": "你是一个严格的 JSON 生成器。只能输出合法 JSON。",
                },
            )

        raw = self.chat(json_messages, model=model, temperature=temperature, max_tokens=max_tokens)
        return _parse_json_loose(raw)


def _parse_json_loose(text: str) -> Any:
    """宽松 JSON 解析：兼容 ```json ... ``` 包裹、混入说明文字等情况。"""
    text = text.strip()

    # 1. 直接尝试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 去除 Markdown 代码块
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    # 3. 截取第一个 { ... } 或 [ ... ]
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for end in range(start, len(text)):
            if text[end] == opener:
                depth += 1
            elif text[end] == closer:
                depth -= 1
                if depth == 0:
                    snippet = text[start : end + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"LLM 输出无法解析为 JSON: {text[:300]}...")
