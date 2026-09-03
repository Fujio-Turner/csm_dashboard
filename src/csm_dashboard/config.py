from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _secrets_path() -> Path:
    return Path(os.environ.get("CSM_DASHBOARD_SECRETS", ROOT / "data" / "secrets.json"))


def prompts_dir() -> Path:
    env = os.environ.get("CSM_DASHBOARD_PROMPTS")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        for cand in (parent / "ai" / "prompts", parent / "prompts"):
            if cand.is_dir() and any(cand.glob("*.json")):
                return cand
    raise FileNotFoundError(
        "No ai/prompts/ folder found. Create ai/prompts/*.json or set CSM_DASHBOARD_PROMPTS."
    )


def fixtures_dir() -> Path:
    env = os.environ.get("CSM_DASHBOARD_FIXTURES")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "fixtures"
        if cand.is_dir() and (cand / "seed").is_dir():
            return cand
    raise FileNotFoundError(
        "No fixtures/ folder found. Create fixtures/seed/ or set CSM_DASHBOARD_FIXTURES."
    )


def load_secrets() -> dict:
    path = _secrets_path()
    data = _load_json(path)
    return data if isinstance(data, dict) else {}


def save_secrets(updates: dict) -> dict:
    path = _secrets_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    current = load_secrets()
    for key, value in updates.items():
        if value:
            current[key] = value
    path.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    invalidate_settings()
    return current


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8788
    public_port: int = 8788
    db_path: str = str(ROOT / "data" / "csm_dashboard.cblite2")
    xai_base_url: str = "https://api.x.ai/v1"
    xai_default_model: str = "grok-4.6"
    xai_models: list[str] = field(default_factory=lambda: ["grok-4.6", "grok-4.5", "grok-4-fast"])
    xai_api_key: str = ""
    operator_name: str = "Jordan Lee"
    operator_email: str = "jordan@example.com"
    operator_role: str = "csm"
    tagline: str = "Accounts · tickets · mail · Slack · Teams · Salesforce"
    thread_tail: int = 8
    slack_tail: int = 20
    max_context_chars: int = 24000
    timeline_page: int = 50
    home_meetings_hours: int = 24
    default_color: str = "#0B3D91"
    health: dict = field(default_factory=dict)
    connectors: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @property
    def has_xai_key(self) -> bool:
        return bool(self.xai_api_key)

    def model_list(self) -> list[str]:
        seen: list[str] = []
        for name in [self.xai_default_model, *self.xai_models]:
            if name and name not in seen:
                seen.append(name)
        return seen


_SETTINGS: Settings | None = None
_SETTINGS_STAMP: tuple | None = None


def _settings_stamp() -> tuple:
    cfg = ROOT / "config.json"
    if not cfg.is_file():
        cfg = ROOT / "config.example.json"
    secrets = _secrets_path()
    env = ROOT / ".env"
    return (
        cfg.stat().st_mtime if cfg.is_file() else 0.0,
        secrets.stat().st_mtime if secrets.is_file() else 0.0,
        env.stat().st_mtime if env.is_file() else 0.0,
        os.environ.get("XAI_API_KEY") or "",
        os.environ.get("CSM_DASHBOARD_DB_PATH") or "",
        os.environ.get("CSM_DASHBOARD_PORT") or "",
        os.environ.get("CSM_DASHBOARD_PUBLIC_PORT") or "",
        os.environ.get("CSM_DASHBOARD_BIND") or "",
    )


def invalidate_settings() -> None:
    global _SETTINGS, _SETTINGS_STAMP
    _SETTINGS = None
    _SETTINGS_STAMP = None


def load_settings(*, force: bool = False) -> Settings:
    global _SETTINGS, _SETTINGS_STAMP
    stamp = _settings_stamp()
    if not force and _SETTINGS is not None and _SETTINGS_STAMP == stamp:
        return _SETTINGS
    load_dotenv(ROOT / ".env")
    cfg = _load_json(ROOT / "config.json") or _load_json(ROOT / "config.example.json")
    secrets = load_secrets()
    server = cfg.get("server") or {}
    cblite = cfg.get("cblite") or {}
    xai = cfg.get("xai") or {}
    operator = cfg.get("operator") or {}
    desk = cfg.get("desk") or {}
    accounts = cfg.get("accounts") or {}

    db_path = os.environ.get("CSM_DASHBOARD_DB_PATH") or cblite.get("db_path") or "data/csm_dashboard.cblite2"
    db = Path(db_path)
    if not db.is_absolute():
        db = ROOT / db

    bind = os.environ.get("CSM_DASHBOARD_BIND") or server.get("host") or "127.0.0.1"
    port = int(os.environ.get("CSM_DASHBOARD_PORT") or server.get("port") or 8788)
    public_port = int(
        os.environ.get("CSM_DASHBOARD_PUBLIC_PORT") or server.get("public_port") or port
    )
    models = xai.get("models") or ["grok-4.6", "grok-4.5", "grok-4-fast"]
    if isinstance(models, str):
        models = [m.strip() for m in models.split(",") if m.strip()]

    loaded = Settings(
        host=str(bind),
        port=port,
        public_port=public_port,
        db_path=str(db),
        xai_base_url=str(xai.get("base_url") or "https://api.x.ai/v1"),
        xai_default_model=str(xai.get("default_model") or "grok-4.6"),
        xai_models=list(models),
        xai_api_key=os.environ.get("XAI_API_KEY") or secrets.get("xai_api_key") or "",
        operator_name=str(operator.get("name") or "Jordan Lee"),
        operator_email=str(operator.get("email") or "jordan@example.com"),
        operator_role=str(operator.get("role") or "csm"),
        tagline=str(desk.get("tagline") or "Accounts · tickets · mail · Slack · Teams · Salesforce"),
        thread_tail=int(desk.get("thread_tail") or 8),
        slack_tail=int(desk.get("slack_tail") or 20),
        max_context_chars=int(desk.get("max_context_chars") or 24000),
        timeline_page=int(desk.get("timeline_page") or 50),
        home_meetings_hours=int(desk.get("home_meetings_hours") or 24),
        default_color=str(accounts.get("default_color") or "#0B3D91"),
        health=dict(cfg.get("health") or {}),
        connectors=dict(cfg.get("connectors") or {}),
        raw=cfg,
    )
    _SETTINGS = loaded
    _SETTINGS_STAMP = stamp
    return loaded
