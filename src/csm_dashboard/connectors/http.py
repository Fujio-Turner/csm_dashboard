"""Outbound HTTP for live connectors. Never log bodies or Authorization."""

from __future__ import annotations

import os
from typing import Any

import httpx


class HttpError(RuntimeError):
    def __init__(self, status: int, code: str = "") -> None:
        self.status = int(status)
        self.code = str(code or f"http_{status}")
        super().__init__(self.code)


def _verify() -> str | bool:
    return os.environ.get("SSL_CERT_FILE") or True


def request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    json: Any = None,
    data: dict | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 30.0,
) -> dict | list:
    with httpx.Client(timeout=timeout, verify=_verify()) as client:
        resp = client.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            auth=auth,
        )
    if resp.status_code >= 400:
        raise HttpError(resp.status_code)
    if not resp.content:
        return {}
    try:
        payload = resp.json()
    except Exception as exc:
        raise HttpError(resp.status_code, "http_not_json") from exc
    if isinstance(payload, (dict, list)):
        return payload
    return {}


def json_get(url: str, *, headers: dict | None = None, params: dict | None = None, auth=None) -> dict | list:
    return request("GET", url, headers=headers, params=params, auth=auth)


def json_post(
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    data: dict | None = None,
    auth=None,
) -> dict | list:
    return request("POST", url, headers=headers, json=json, data=data, auth=auth)
