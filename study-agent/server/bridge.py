from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Generator
from typing import Any


class BridgeError(RuntimeError):
    pass


def extract_sse_text_event(data: str) -> tuple[str | None, bool, str | None]:
    if not data or data == "[DONE]":
        return None, data == "[DONE]", None
    try:
        event = json.loads(data)
    except json.JSONDecodeError:
        return None, False, None
    event_type = event.get("type")
    if event_type == "response.output_text.delta":
        return event.get("delta", ""), False, None
    if event_type == "response.completed":
        return None, True, None
    if event_type in {"response.failed", "error"}:
        error = event.get("error") or event.get("response", {}).get("error") or {}
        message = error.get("message") if isinstance(error, dict) else str(error)
        return None, True, message or "模型生成失败"
    return None, False, None


class CopilotBridgeClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        accept: str = "application/json",
        timeout: int = 180,
    ):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Accept": accept}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        return urllib.request.urlopen(request, timeout=timeout)

    def list_models(self) -> list[str]:
        try:
            with self._request("/v1/models", timeout=8) as response:
                if response.status != 200:
                    raise BridgeError("模型列表暂时不可用。")
                document = json.loads(response.read().decode("utf-8"))
                models = document.get("data", []) if isinstance(document, dict) else []
                model_ids = {
                    item.get("id") for item in models
                    if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
                }
                return sorted(model_ids)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise BridgeError("暂时无法读取可用模型。") from error

    def health(self) -> bool:
        try:
            return self.model in self.list_models()
        except BridgeError:
            return False

    def stream_response(
        self,
        instructions: str,
        history: list[dict[str, str]],
        user_text: str,
        image_data_url: str | None,
        reasoning_effort: str = "medium",
        model: str | None = None,
    ) -> Generator[str, None, None]:
        input_items: list[dict[str, Any]] = [
            {"role": item["role"], "content": item["content"]} for item in history
        ]
        if image_data_url:
            content: Any = [
                {"type": "input_text", "text": user_text or "请识别并讲解这张题目图片。"},
                {"type": "input_image", "image_url": image_data_url},
            ]
        else:
            content = user_text
        input_items.append({"role": "user", "content": content})
        body = {
            "model": model or self.model,
            "instructions": instructions,
            "input": input_items,
            "stream": True,
            "reasoning": {"effort": reasoning_effort},
            "max_output_tokens": 3000,
        }
        try:
            with self._request("/v1/responses", method="POST", body=body, accept="text/event-stream") as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    delta, completed, error = extract_sse_text_event(line[5:].strip())
                    if error:
                        raise BridgeError(error)
                    if delta:
                        yield delta
                    if completed:
                        return
        except urllib.error.HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8", errors="replace"))
                message = payload.get("error", {}).get("message")
            except (json.JSONDecodeError, AttributeError):
                message = None
            raise BridgeError(message or f"模型服务返回错误（{error.code}）") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise BridgeError("暂时无法连接模型服务，请稍后再试。") from error
