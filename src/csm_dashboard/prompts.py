"""Load Grok prompt objects from ai/prompts/*.json. See ai/prompts/CATALOG.md."""

from __future__ import annotations

import json
from pathlib import Path

from csm_dashboard.config import load_settings, prompts_dir

_CACHE: dict[str, tuple[float, dict]] = {}


def load_prompt(name: str) -> dict:
    rel = Path(str(name).replace("..", "").strip("/\\") + ".json")
    path = (prompts_dir() / rel).resolve()
    root = prompts_dir().resolve()
    if root not in path.parents and path != root:
        raise FileNotFoundError(f"prompt not found: {name}")
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


def list_prompts() -> list[dict]:
    rows = []
    root = prompts_dir()
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root).with_suffix("").as_posix()
        try:
            spec = load_prompt(rel)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        rows.append(
            {
                "id": str(spec.get("id") or rel),
                "title": str(spec.get("title") or rel),
                "kind": str(spec.get("kind") or "prompt"),
                "source": str(spec.get("source") or "core"),
                "used_by": str(spec.get("used_by") or ""),
                "when": str(spec.get("when") or ""),
            }
        )
    return rows


INTENT_MAX = 4000
DEFAULT_PERSONA = "csm"


def _name_from_email(email: str) -> str:
    local = str(email or "").split("@", 1)[0].strip()
    parts = [p for p in local.replace(".", " ").replace("_", " ").replace("-", " ").split() if p]
    return " ".join(p.capitalize() for p in parts)


def operator_identity(operator: dict | None = None) -> dict:
    """Name/email for prompt tokens. Settings CBL wins over config.json seed defaults."""
    settings = load_settings()
    op = operator or {}
    email = str(op.get("email") or "").strip()
    name = str(op.get("name") or "").strip()
    role = str(op.get("role") or "").strip()
    seed_email = str(settings.operator_email or "").strip()
    seed_name = str(settings.operator_name or "").strip()
    if not email:
        email = seed_email
    if not name:
        if email and email.lower() != (seed_email or "").lower():
            name = _name_from_email(email)
        else:
            name = seed_name
        if not name:
            name = _name_from_email(email) or seed_name
    if not role:
        role = str(settings.operator_role or "csm").strip() or "csm"
    return {"name": name, "email": email, "role": role}


def _inject(text: str, operator: dict | None = None) -> str:
    ident = operator_identity(operator)
    settings = load_settings()
    return (
        text.replace("{operator_name}", ident["name"])
        .replace("{operator_email}", ident["email"])
        .replace("{tagline}", settings.tagline)
    )


def operator_personas() -> list[dict]:
    spec = load_prompt("operator_persona")
    rows = spec.get("personas")
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        out.append(
            {
                "id": pid,
                "label": str(row.get("label") or pid).strip(),
                "hint": str(row.get("hint") or "").strip(),
                "intent": str(row.get("intent") or "").strip()[:INTENT_MAX],
            }
        )
    return out


def operator_intent_block(operator: dict | None = None) -> str:
    personas = {row["id"]: row for row in operator_personas()}
    pid = str((operator or {}).get("persona") or DEFAULT_PERSONA).strip() or DEFAULT_PERSONA
    if pid not in personas:
        pid = DEFAULT_PERSONA
    preset = personas.get(pid) or {}
    intent = str((operator or {}).get("intent") or "").strip()[:INTENT_MAX]
    if not intent:
        intent = str(preset.get("intent") or "").strip()[:INTENT_MAX]
    if not intent:
        return ""
    label = str(preset.get("label") or pid)
    return (
        f"Operator persona: {label}.\n"
        "Flavor and organize every reply for this operator. "
        "Do not invent tickets, people, meetings, or opportunities. Stay on the open book.\n"
        f"{intent}"
    )


def prompt_system(name: str, operator: dict | None = None) -> str:
    spec = load_prompt(name)
    base = _inject(str(spec.get("system") or "").strip(), operator)
    flavor = operator_intent_block(operator)
    if flavor:
        return base + "\n\n" + flavor
    return base


def prompt_user(name: str, payload: str, operator: dict | None = None) -> str:
    spec = load_prompt(name)
    tmpl = str(spec.get("user_template") or "{payload}")
    return _inject(tmpl.replace("{payload}", payload), operator)


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
