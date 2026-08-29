"""Resolve the selected Settings AI provider into an OpenAI-compatible client."""

from __future__ import annotations

from csm_dashboard.chat.grok import GrokClient
from csm_dashboard.config import Settings
from csm_dashboard.credentials import AI_PROVIDERS, normalize_ai_provider

AI_ENDPOINTS = {
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-4.6",
        "models": ["grok-4.6", "grok-4.5", "grok-4-fast"],
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1",
        "models": ["gpt-4.1", "gpt-4o", "gpt-4o-mini"],
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
    },
}


def selected_provider(settings_doc: dict | None) -> str:
    ai = (settings_doc or {}).get("ai") or {}
    name = normalize_ai_provider(str(ai.get("provider") or "grok"))
    return name if name in AI_PROVIDERS else "grok"


def provider_spec(name: str) -> dict:
    key = normalize_ai_provider(name)
    return dict(AI_ENDPOINTS.get(key) or AI_ENDPOINTS["grok"])


def resolve_ai_client(repo, settings: Settings) -> GrokClient | None:
    doc = repo.get_settings() or {}
    provider = selected_provider(doc)
    spec = provider_spec(provider)
    key = repo.ai_api_key(provider)
    if not key and provider == "grok":
        key = settings.xai_api_key or ""
    if not key:
        return None
    ai = doc.get("ai") or {}
    model = str(ai.get("model") or "").strip()
    models = [model, *spec["models"]] if model else list(spec["models"])
    seen: list[str] = []
    for item in models:
        if item and item not in seen:
            seen.append(item)
    return GrokClient(key, spec["base_url"], seen)
