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


def _parse(resp: httpx.Response) -> dict | list:
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
    client: httpx.Client | None = None,
) -> dict | list:
    kwargs = {
        "method": method,
        "url": url,
        "headers": headers,
        "params": params,
        "json": json,
        "data": data,
        "auth": auth,
    }
    if client is not None:
        return _parse(client.request(**kwargs))
    with httpx.Client(timeout=timeout, verify=_verify()) as http:
        return _parse(http.request(**kwargs))


def json_get(
    url: str,
    *,
    headers: dict | None = None,
    params: dict | None = None,
    auth=None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
) -> dict | list:
    return request("GET", url, headers=headers, params=params, auth=auth, timeout=timeout, client=client)


def json_post(
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    data: dict | None = None,
    auth=None,
) -> dict | list:
    return request("POST", url, headers=headers, json=json, data=data, auth=auth)


def json_put(
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    timeout: float = 30.0,
) -> dict | list:
    return request("PUT", url, headers=headers, json=json, timeout=timeout)
