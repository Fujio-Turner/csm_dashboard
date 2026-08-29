"""Load the Google OAuth client from credentials.json.

Name and email on the operator profile are only a login hint. The Google
*app* client (client_id + secret) lives in credentials.json. Never log the secret.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from csm_dashboard.config import ROOT

log = logging.getLogger(__name__)


def _in_pytest() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def candidate_paths() -> list[Path]:
    out: list[Path] = []
    env = str(os.environ.get("GOOGLE_CLIENT_SECRETS") or os.environ.get("CSM_GOOGLE_CREDENTIALS") or "").strip()
    if env:
        out.append(Path(env).expanduser())
    if not _in_pytest():
        out.append(ROOT / "__local" / "credentials.json")
        out.append(Path("/app/credentials.json"))
        out.append(ROOT / "credentials.json")
        out.append(Path.home() / "Documents" / "work_scrapper" / "credentials.json")
    return out


def _label(path: Path) -> str:
    try:
        home = str(Path.home())
        text = str(path)
        if text.startswith(home + os.sep):
            return "~/" + text[len(home) + 1 :]
        return path.name
    except Exception:
        return path.name


def load_google_client() -> dict:
    for path in candidate_paths():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log.info("csm.oauth.google_file_unreadable")
            continue
        blob = data.get("web") if isinstance(data.get("web"), dict) else data.get("installed") if isinstance(data.get("installed"), dict) else data
        if not isinstance(blob, dict):
            continue
        client_id = str(blob.get("client_id") or "").strip()
        if not client_id:
            continue
        return {
            "client_id": client_id,
            "client_secret": str(blob.get("client_secret") or "").strip(),
            "path": str(path),
            "label": _label(path),
        }
    return {}


def hydrate_google(repo) -> dict:
    """Copy client_id/secret from credentials.json into CBL if missing."""
    file_creds = load_google_client()
    if not file_creds.get("client_id"):
        return {"found": False, "label": ""}
    stored = repo.get_credential_secret("connector", "google")
    incoming = {}
    if not str(stored.get("client_id") or "").strip():
        incoming["client_id"] = file_creds["client_id"]
    if file_creds.get("client_secret") and not str(stored.get("client_secret") or "").strip():
        incoming["client_secret"] = file_creds["client_secret"]
    if incoming:
        repo.put_credential_secret("connector", "google", incoming)
        log.info("csm.oauth.google_client_from_file")
    return {"found": True, "label": file_creds.get("label") or "credentials.json"}
