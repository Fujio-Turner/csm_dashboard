from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import httpx

from csm_dashboard.chat.tools import get_tools, run_tool

log = logging.getLogger(__name__)


class GrokClient:
    def __init__(self, api_key: str, base_url: str, models: list[str]) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = models
        self._http = httpx.Client(timeout=90.0)

    def close(self) -> None:
        self._http.close()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _post(self, model: str, messages: list[dict], *, stream: bool = False, tools: bool = True) -> dict:
        body: dict = {"model": model, "messages": messages, "stream": stream, "temperature": 0.3}
        if tools:
            body["tools"] = get_tools()
        resp = self._http.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=body)
        resp.raise_for_status()
        return resp.json()

    def complete(self, messages: list[dict], repo, account_id: str) -> tuple[str, str, list[dict]]:
        working = list(messages)
        last_err: Exception | None = None
        for model in self.models:
            try:
                text, working = self._loop(model, working, repo, account_id)
                return text, model, working
            except httpx.HTTPStatusError as exc:
                last_err = exc
                code = exc.response.status_code if exc.response is not None else 0
                if code in (404, 400, 422, 429, 500, 502, 503):
                    log.warning("csm.chat.fallback model=%s status=%s", model, code)
                    continue
                raise
            except httpx.HTTPError as exc:
                last_err = exc
                log.warning("csm.chat.fallback model=%s err=%s", model, exc)
                continue
        raise RuntimeError(f"All models failed: {last_err}")

    def _loop(self, model: str, messages: list[dict], repo, account_id: str) -> tuple[str, list[dict]]:
        working = list(messages)
        tools_used: list[str] = []
        for _round in range(6):
            data = self._post(model, working, stream=False)
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                working.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": tool_calls})
                for call in tool_calls:
                    fn = call.get("function") or {}
                    name = fn.get("name") or ""
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    tools_used.append(name)
                    result = run_tool(repo, account_id, name, args or {})
                    working.append({"role": "tool", "tool_call_id": call.get("id") or name, "content": result})
                continue
            text = msg.get("content") or ""
            working.append({"role": "assistant", "content": text})
            log.info("csm.chat.turn model=%s tools=%s result=grok", model, ",".join(tools_used) or "none")
            return text, working
        return "Stopped after too many tool rounds.", working

    def stream_final(self, messages: list[dict], model: str) -> Iterator[str]:
        with self._http.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={"model": model, "messages": messages, "stream": True, "temperature": 0.4},
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8", "replace")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                piece = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if piece:
                    yield piece

    def complete_json(self, messages: list[dict]) -> tuple[dict, str]:
        last_err: Exception | None = None
        for model in self.models:
            try:
                data = self._post(model, messages, stream=False, tools=False)
                choice = (data.get("choices") or [{}])[0]
                text = (choice.get("message") or {}).get("content") or ""
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    return json.loads(text[start : end + 1]), model
                raise ValueError("no json")
            except Exception as exc:
                last_err = exc
                log.warning("csm.chat.fallback model=%s err=%s", model, exc)
                continue
        raise RuntimeError(f"All models failed: {last_err}")
