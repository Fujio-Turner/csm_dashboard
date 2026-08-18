"""Load Grok prompt objects from repo-root prompts/*.json."""

from __future__ import annotations

import json

from csm_dashboard.config import load_settings, prompts_dir

_CACHE: dict[str, tuple[float, dict]] = {}


def load_prompt(name: str) -> dict:
    path = prompts_dir() / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    mtime = path.stat().st_mtime
    hit = _CACHE.get(name)
    if hit and hit[0] == mtime:
        return hit[1]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"prompt {name} must be a JSON object")
    kind = str(data.get("kind") or "prompt")
    if kind == "prompt" and not str(data.get("system") or "").strip():
        raise ValueError(f"prompt {name} must have a non-empty system string")
    _CACHE[name] = (mtime, data)
    return data


def _inject(text: str) -> str:
    settings = load_settings()
    return (
        text.replace("{operator_name}", settings.operator_name)
        .replace("{operator_email}", settings.operator_email)
        .replace("{tagline}", settings.tagline)
    )


def prompt_system(name: str) -> str:
    spec = load_prompt(name)
    return _inject(str(spec.get("system") or "").strip())


def prompt_user(name: str, payload: str) -> str:
    spec = load_prompt(name)
    tmpl = str(spec.get("user_template") or "{payload}")
    return _inject(tmpl.replace("{payload}", payload))


def help_public() -> dict:
    spec = load_prompt("help")
    return {
        "title": spec.get("title") or "Help",
        "groups": spec.get("groups") or [],
    }


def desk_chat_public() -> dict:
    spec = load_prompt("desk_chat")
    return {
        "title": spec.get("title") or "Coach",
        "welcome": _inject(str(spec.get("welcome") or "")),
        "fallback": _inject(str(spec.get("fallback") or "")),
    }
