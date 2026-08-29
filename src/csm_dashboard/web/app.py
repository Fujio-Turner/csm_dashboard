from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from csm_dashboard import __version__
from csm_dashboard.chat.desk_answer import answer_desk
from csm_dashboard.chat.mentions import resolve_account
from csm_dashboard.chat.providers import provider_spec, resolve_ai_client, selected_provider
from csm_dashboard.compose.context import build_compose_context
from csm_dashboard.compose.grok import (
    assist_task_with_grok,
    compose_with_grok,
    fallback_draft,
    fallback_reply,
    fallback_task_assist,
)
from csm_dashboard.config import ROOT, Settings, fixtures_dir, load_settings
from csm_dashboard.connectors import oauth as oauth_flow
from csm_dashboard.connectors.smtp_imap import SendFailed, SendNotConfigured, deliver_mail, parse_attachments
from csm_dashboard.connectors.registry import PULL_CONNECTORS, connector_mode, get_connector, list_connectors
from csm_dashboard.credentials import (
    AI_KEY_ALIASES,
    AI_PROVIDERS,
    VENDOR_CLIENT_FIELDS,
    VENDOR_CONNECTORS,
    connector_auth,
    connector_cred_name,
    connector_fields,
    normalize_ai_provider,
)
from csm_dashboard.ingest.activities import emit_email_activity
from csm_dashboard.ingest.route import route_event
from csm_dashboard.prompts import help_public, prompt_system
from csm_dashboard.seed.load import apply_seed, apply_sync_event
from csm_dashboard.sso import public_sso
from csm_dashboard.storage.errors import CouchbaseLiteNotAvailable
from csm_dashboard.storage.repo import TASK_KINDS, CsmRepo, utcnow

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
_INDEX_HTML: str | None = None


def _send_mail(
    repo,
    *,
    from_addr: str,
    to_addrs: list,
    cc_addrs: list,
    subject: str,
    body: str,
    bcc_addrs: list | None = None,
    attachments: list | None = None,
) -> dict:
    try:
        files = parse_attachments(attachments)
        return deliver_mail(
            repo,
            from_addr=from_addr,
            to_addrs=list(to_addrs or []),
            cc_addrs=list(cc_addrs or []),
            bcc_addrs=list(bcc_addrs or []),
            subject=subject,
            body=body,
            attachments=files,
        )
    except SendNotConfigured as exc:
        raise HTTPException(409, str(exc) or "send_not_configured") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SendFailed as exc:
        log.warning("csm.mail.send_failed err=%s", exc.message)
        raise HTTPException(502, "send_failed") from exc


def _settings() -> Settings:
    return load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    injected = getattr(app.state, "repo", None)
    store = None
    if injected is None:
        settings = load_settings()
        try:
            from csm_dashboard.storage.cbl_store import CBLStore

            store = CBLStore(settings.db_path)
        except CouchbaseLiteNotAvailable as exc:
            log.error("csm.cbl.unavailable err=%s", exc)
            raise
        app.state.repo = CsmRepo(store)
        app.state.settings = settings
        if settings.host == "0.0.0.0":
            log.warning("csm.boot.bind host=0.0.0.0 auth=none")
        log.info(
            "csm.boot version=%s db=%s host=%s accounts=%s",
            __version__,
            settings.db_path,
            settings.host,
            app.state.repo.store.count("accounts"),
        )
    try:
        yield
    finally:
        if store is not None:
            store.close()


def create_app(repo: CsmRepo | None = None) -> FastAPI:
    app = FastAPI(title="CSM Dashboard", version=__version__, lifespan=lifespan)
    if repo is not None:
        app.state.repo = repo
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    def repo_obj() -> CsmRepo:
        return app.state.repo

    def apply_key_body(body: dict) -> list[str]:
        repo = repo_obj()
        updated: list[str] = []
        for key, value in (body or {}).items():
            if key in {"ai", "connectors"}:
                continue
            alias = AI_KEY_ALIASES.get(str(key))
            if not alias:
                continue
            repo.put_credential_secret("ai", alias, {"api_key": "" if value is None else value})
            updated.append(f"ai.{alias}")
        nested_ai = (body or {}).get("ai")
        if isinstance(nested_ai, dict):
            for name, value in nested_ai.items():
                provider = normalize_ai_provider(name)
                if provider not in AI_PROVIDERS:
                    continue
                fields = value if isinstance(value, dict) else {"api_key": value}
                repo.put_credential_secret("ai", provider, fields)
                updated.append(f"ai.{provider}")
        nested_conn = (body or {}).get("connectors")
        if isinstance(nested_conn, dict):
            for name, fields in nested_conn.items():
                if not isinstance(fields, dict):
                    continue
                key = str(name)
                if key == "okta":
                    target, allowed = "okta", set(connector_fields("okta"))
                elif key in VENDOR_CONNECTORS:
                    target, allowed = key, set(VENDOR_CLIENT_FIELDS.get(key) or ("client_id", "client_secret"))
                elif key in PULL_CONNECTORS:
                    target, allowed = connector_cred_name(key), set(connector_fields(key))
                else:
                    continue
                clean = {k: v for k, v in fields.items() if k in allowed}
                repo.put_credential_secret("connector", target, clean)
                updated.append(f"connector.{target}")
        return updated

    def ai_client():
        return resolve_ai_client(repo_obj(), _settings())

    @app.get("/", response_class=HTMLResponse)
    def index():
        global _INDEX_HTML
        if _INDEX_HTML is None:
            _INDEX_HTML = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(
            _INDEX_HTML.replace("{{ version }}", __version__),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": __version__, "cblite": "community"}

    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml():
        path = ROOT / "docs" / "openapi.yaml"
        return Response(path.read_text(encoding="utf-8"), media_type="application/yaml")

    @app.get("/api/status")
    def get_status():
        from csm_dashboard.connectors.google_secrets import hydrate_google

        settings = _settings()
        repo = repo_obj()
        google_file = hydrate_google(repo)
        doc = repo.get_settings() or {}
        creds = repo.list_credentials_public()
        provider = selected_provider(doc)
        spec = provider_spec(provider)
        grok_on = bool(creds["ai"]["grok"]["present"] or settings.has_xai_key)
        ai = doc.get("ai") or {}
        return {
            "version": __version__,
            "host": settings.host,
            "port": settings.port,
            "tagline": settings.tagline,
            "operator": repo.operator_profile(doc),
            "world_clock": repo.world_clock(doc),
            "preferences": repo.preferences(doc),
            "models": spec["models"],
            "default_model": spec["default_model"],
            "ai": {
                "provider": provider,
                "model": str(ai.get("model") or spec["default_model"]),
            },
            "keys": {
                "grok": grok_on,
                "xai": grok_on,
                "openai": bool(creds["ai"]["openai"]["present"]),
                "gemini": bool(creds["ai"]["gemini"]["present"]),
            },
            "credentials": creds,
            "connectors": list_connectors(doc, creds.get("connectors"), repo),
            "sso": {
                **public_sso(
                    doc,
                    operator_email=str((repo.operator_profile(doc) or {}).get("email") or ""),
                    identity=repo.get_credential_secret("connector", "okta"),
                    okta_redirect=oauth_flow.redirect_uri("okta"),
                ),
                "clients": {
                    "google": bool(repo.get_credential_secret("connector", "google").get("client_id")),
                    "google_secret": bool(repo.get_credential_secret("connector", "google").get("client_secret")),
                    "microsoft": bool(repo.get_credential_secret("connector", "microsoft").get("client_id")),
                    "slack": bool(repo.get_credential_secret("connector", "slack").get("client_id")),
                },
                "google_redirect": oauth_flow.redirect_uri("google"),
                "google_file": bool(google_file.get("found")),
                "google_file_label": google_file.get("label") or "",
                "microsoft_redirect": oauth_flow.redirect_uri("microsoft"),
                "slack_redirect": oauth_flow.redirect_uri("slack"),
            },
        }

    @app.get("/api/help")
    def get_help():
        return help_public()

    @app.put("/api/settings")
    def put_settings(body: dict):
        saved = repo_obj().save_settings(body)
        log.info("csm.settings.updated changed_fields=%s", ",".join(body.keys()))
        if "world_clock" in body or (
            isinstance(body.get("operator"), dict) and "timezones" in (body.get("operator") or {})
        ):
            clock = repo_obj().world_clock()
            log.info(
                "csm.world_clock.updated count=%s hour24=%s",
                len(clock.get("timezones") or []),
                clock.get("hour24"),
            )
        if "preferences" in body:
            prefs = repo_obj().preferences()
            log.info(
                "csm.preferences.updated week_start=%s hidden=%s theme=%s",
                prefs.get("week_start"),
                ",".join(str(d) for d in (prefs.get("hidden_weekdays") or [])),
                prefs.get("theme"),
            )
        return saved

    @app.get("/api/settings")
    def get_settings():
        doc = repo_obj().get_settings() or {}
        repo = repo_obj()
        op = repo.operator_profile(doc)
        return {
            **doc,
            "operator": op,
            "world_clock": repo.world_clock(doc),
            "preferences": repo.preferences(doc),
            "ai": doc.get("ai") or {"provider": "grok", "model": _settings().xai_default_model},
            "sso": public_sso(
                doc,
                operator_email=str((op or {}).get("email") or ""),
                identity=repo.get_credential_secret("connector", "okta"),
                okta_redirect=oauth_flow.redirect_uri("okta"),
            ),
        }

    @app.put("/api/settings/keys")
    def put_keys(body: dict):
        fields = apply_key_body(body or {})
        log.info("csm.settings.keys_updated fields=%s", ",".join(fields))
        return {"ok": True, "fields": fields, "credentials": repo_obj().list_credentials_public()}

    @app.get("/api/settings/keys")
    def get_keys():
        return repo_obj().list_credentials_public()

    @app.post("/api/settings/providers/test")
    def test_provider(body: dict):
        provider = normalize_ai_provider(str((body or {}).get("provider") or "grok"))
        repo = repo_obj()
        key = repo.ai_api_key(provider)
        if not key and provider == "grok":
            key = _settings().xai_api_key
        if not key:
            log.info("csm.settings.provider_test provider=%s result=missing_key", provider)
            return {"ok": False, "provider": provider, "message": "No API key saved"}
        log.info("csm.settings.provider_test provider=%s result=ok", provider)
        return {"ok": True, "provider": provider, "message": "Key present. Auth method: API key header."}

    @app.post("/api/settings/seed")
    def seed_demo():
        counts = apply_seed(repo_obj(), fixtures_dir() / "seed")
        return {"ok": True, "counts": counts}

    @app.post("/api/settings/reset")
    def reset_store(body: dict):
        if str(body.get("confirm") or "") != "RESET":
            raise HTTPException(400, "confirm must be RESET")
        repo_obj().reset_store()
        log.info("csm.store.reset")
        return {"ok": True}

    def _home_items():
        items = []
        for acct in repo_obj().list_accounts():
            aid = acct.get("account_id") or acct.get("_id")
            items.append(
                {
                    "account_id": aid,
                    "name": acct.get("name"),
                    "abbr": acct.get("abbr"),
                    "color": acct.get("color"),
                    "has_logo": repo_obj().account_has_logo(aid, acct),
                    "logo_updated_at": acct.get("logo_updated_at") or "",
                    "health": acct.get("health"),
                    "contract": {"renewal_on": (acct.get("contract") or {}).get("renewal_on")},
                    "stats": acct.get("stats")
                    if isinstance(acct.get("stats"), dict) and acct["stats"].get("refreshed_at")
                    else repo_obj().account_inbox_stats(aid),
                    "next_meeting": repo_obj().next_meeting(aid),
                }
            )
        return items

    @app.get("/api/home")
    def get_home():
        return {"items": _home_items()}

    @app.get("/api/home/agenda")
    def get_home_agenda(date: str | None = None, start: str | None = None, end: str | None = None):
        return repo_obj().home_agenda(date or "", start=start, end=end)

    @app.get("/api/accounts")
    def list_accounts(q: str | None = None, status: str | None = None, include: str | None = None):
        hidden = str(include or "") in {"all", "hidden"}
        return {"items": repo_obj().list_accounts(q=q, status=status, include_hidden=hidden)}

    @app.post("/api/accounts")
    def create_account(body: dict):
        try:
            doc = repo_obj().create_account(body)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        log.info("csm.account.created account_id=%s", doc.get("account_id"))
        return doc

    @app.get("/api/accounts/by-abbr/{abbr}")
    def get_account_by_abbr(abbr: str):
        doc = repo_obj().get_account_by_abbr(abbr)
        if not doc:
            raise HTTPException(404, "not found")
        return repo_obj().expand_account(doc)

    @app.post("/api/accounts/{account_id}/rescore")
    def rescore_account(account_id: str):
        try:
            repo_obj().refresh_account_stats(account_id)
            return repo_obj().score_account(account_id)
        except KeyError:
            raise HTTPException(404, "not found") from None

    @app.get("/api/accounts/{account_id}/timeline")
    def list_timeline(
        account_id: str,
        since: str | None = None,
        until: str | None = None,
        kind: str | None = None,
        project_id: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return {
            "items": repo_obj().page_timeline(
                account_id,
                since=since,
                until=until,
                kind=kind,
                project_id=project_id,
                q=q,
                limit=limit,
                offset=offset,
            )
        }

    @app.get("/api/activities/{activity_id:path}")
    def get_activity(activity_id: str):
        doc = repo_obj().get_activity(activity_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/activities/{activity_id:path}")
    def patch_activity(activity_id: str, body: dict):
        try:
            doc = repo_obj().patch_activity(activity_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.activity.tagged activity_id=%s project_id=%s",
            activity_id,
            doc.get("project_id") or "",
        )
        return doc

    @app.get("/api/accounts/{account_id}")
    def get_account(account_id: str):
        doc = repo_obj().get_account(account_id)
        if not doc:
            raise HTTPException(404, "not found")
        return repo_obj().expand_account(doc)

    @app.patch("/api/accounts/{account_id}")
    def patch_account(account_id: str, body: dict):
        try:
            doc = repo_obj().patch_account(account_id, body)
        except PermissionError:
            raise HTTPException(409, "slug_immutable") from None
        except KeyError:
            raise HTTPException(404, "not found") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        log.info("csm.account.updated account_id=%s changed_fields=%s", account_id, ",".join(body.keys()))
        return doc

    @app.delete("/api/accounts/{account_id}")
    def delete_account(account_id: str):
        try:
            doc = repo_obj().remove_account(account_id)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.account.removed account_id=%s", account_id)
        return doc

    @app.get("/api/accounts/{account_id}/logo")
    def get_account_logo(account_id: str):
        pair = repo_obj().get_account_logo(account_id)
        if not pair:
            raise HTTPException(404, "not found")
        blob, mime = pair
        return Response(content=blob, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})

    @app.post("/api/accounts/{account_id}/logo")
    def post_account_logo(account_id: str, body: dict):
        try:
            doc = repo_obj().save_account_logo(account_id, str(body.get("image") or ""))
        except KeyError:
            raise HTTPException(404, "not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info("csm.account.logo_saved account_id=%s", account_id)
        return doc

    @app.delete("/api/accounts/{account_id}/logo")
    def delete_account_logo(account_id: str):
        try:
            doc = repo_obj().delete_account_logo(account_id)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.account.logo_deleted account_id=%s", account_id)
        return doc

    @app.get("/api/people")
    def list_people(
        account_id: str,
        kind: str | None = None,
        q: str | None = None,
        project_id: str | None = None,
        function: str | None = None,
    ):
        return {
            "items": repo_obj().list_people(
                account_id, kind=kind, q=q, project_id=project_id, function=function
            )
        }

    @app.post("/api/people")
    def create_person(body: dict):
        try:
            doc = repo_obj().create_person(body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.person.saved account_id=%s fields=%s",
            doc.get("account_id"),
            "name,email,location,title,project_ids,functions",
        )
        return doc

    @app.patch("/api/people/{person_id:path}")
    def patch_person(person_id: str, body: dict):
        try:
            doc = repo_obj().patch_person(person_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info(
            "csm.person.saved person_id=%s changed_fields=%s",
            person_id,
            ",".join(body.keys()),
        )
        return doc

    @app.get("/api/projects")
    def list_projects(
        account_id: str,
        q: str | None = None,
        status: str | None = None,
        kind: str | None = None,
    ):
        return {
            "items": repo_obj().list_projects(account_id, q=q, status=status, kind=kind)
        }

    @app.post("/api/projects")
    def create_project(body: dict):
        try:
            doc = repo_obj().create_project(body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.project.saved account_id=%s fields=%s",
            doc.get("account_id"),
            "name,kind,status,owner_person_id,group_email,tags",
        )
        return doc

    @app.patch("/api/projects/{project_id}")
    def patch_project(project_id: str, body: dict):
        try:
            doc = repo_obj().patch_project(project_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.project.saved project_id=%s changed_fields=%s",
            project_id,
            ",".join(body.keys()),
        )
        return doc

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str):
        try:
            doc = repo_obj().delete_project(project_id)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.project.deleted project_id=%s", project_id)
        return doc

    @app.get("/api/tickets")
    def list_tickets(
        account_id: str,
        status: str | None = None,
        priority: str | None = None,
        q: str | None = None,
        project_id: str | None = None,
    ):
        items, total = repo_obj().page_tickets(
            account_id, status=status, priority=priority, q=q, project_id=project_id
        )
        return {"items": items, "total": total}

    @app.get("/api/tickets/{ticket_id:path}")
    def get_ticket(ticket_id: str):
        if ticket_id.endswith("/operator"):
            raise HTTPException(404, "not found")
        doc = repo_obj().get_ticket(ticket_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/tickets/{ticket_id:path}/operator")
    def patch_ticket_operator(ticket_id: str, body: dict):
        allowed = {k: body[k] for k in ("triage", "ignore") if k in body}
        try:
            doc = repo_obj().patch_ticket_operator(ticket_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=tickets id=%s fields=%s", ticket_id, ",".join(allowed))
        return doc

    @app.get("/api/threads")
    def list_threads(account_id: str):
        items, total = repo_obj().page_threads(account_id)
        return {"items": items, "total": total}

    @app.get("/api/threads/{thread_id}")
    def get_thread(thread_id: str, include: str | None = None):
        doc = repo_obj().get_thread(thread_id)
        if not doc:
            raise HTTPException(404, "not found")
        if include == "messages":
            msgs, _ = repo_obj().page_emails(doc.get("account_id") or "", thread_id=thread_id, limit=50)
            doc = {**doc, "messages": msgs}
        return doc

    @app.post("/api/threads/{thread_id}/suggest-reply")
    def suggest_thread_reply(thread_id: str):
        thread = repo_obj().get_thread(thread_id)
        if not thread:
            raise HTTPException(404, "not found")
        account_id = str(thread.get("account_id") or "")
        acct = repo_obj().get_account(account_id)
        if not acct:
            raise HTTPException(404, "account not found")
        msgs, _ = repo_obj().page_emails(account_id, thread_id=thread_id, limit=50)
        last = msgs[-1] if msgs else None
        ctx = build_compose_context(repo_obj(), account_id, thread_id=thread_id)
        settings = _settings()
        result = "fallback"
        model = ""
        draft_body = fallback_reply(acct, thread, last)
        client = ai_client()
        if client:
            try:
                drafted, model = compose_with_grok(client, ctx, settings)
                draft_body = {**draft_body, **drafted}
                result = selected_provider(repo_obj().get_settings())
            except Exception as exc:
                log.warning("csm.draft.suggest_reply result=fallback err=%s", exc)
        to_addrs = draft_body.get("to") or []
        if last and last.get("from_addr") and last.get("from_addr") not in to_addrs:
            to_addrs = [last["from_addr"], *to_addrs]
        saved = repo_obj().create_draft(
            {
                "account_id": account_id,
                "subject": draft_body.get("subject") or "",
                "body": draft_body.get("body") or "",
                "to_addrs": to_addrs,
                "prompt_name": "email_draft",
                "model": model,
                "created_by": "grok" if result != "fallback" else "you",
                "context_ref": {"thread_id": thread_id},
                "status": "ready",
                "channel": "email",
            }
        )
        log.info("csm.draft.suggest_reply result=%s thread_id=%s draft_id=%s", result, thread_id, saved.get("_id"))
        return {
            "account_id": account_id,
            "thread_id": thread_id,
            "draft_id": saved.get("_id") or "",
            "subject": saved.get("subject") or "",
            "body": saved.get("body") or "",
            "to_addrs": saved.get("to_addrs") or to_addrs,
            "result": result,
            "model": model,
        }

    @app.patch("/api/threads/{thread_id}/operator")
    def patch_thread_operator(thread_id: str, body: dict):
        allowed = {k: body[k] for k in ("unread", "pinned") if k in body}
        try:
            doc = repo_obj().patch_thread_operator(thread_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=threads id=%s fields=%s", thread_id, ",".join(allowed))
        return doc

    @app.get("/api/emails")
    def list_emails(account_id: str, thread_id: str | None = None):
        items, total = repo_obj().page_emails(account_id, thread_id=thread_id)
        return {"items": items, "total": total}

    @app.get("/api/emails/{email_id}")
    def get_email(email_id: str):
        doc = repo_obj().get_email(email_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.post("/api/tasks/assist")
    def assist_task(body: dict):
        account_id = str((body or {}).get("account_id") or "").strip()
        acct = repo_obj().get_account(account_id)
        if not acct:
            raise HTTPException(400, "account required")
        people = repo_obj().list_people(account_id)
        tickets, _ = repo_obj().page_tickets(account_id, limit=8)
        open_tickets = [
            {
                "key": t.get("key"),
                "summary": t.get("summary"),
                "status": t.get("status"),
                "priority": t.get("priority"),
            }
            for t in tickets
            if t.get("status") not in {"done", "cancelled"}
        ][:5]
        people_slice = [
            {
                "name": p.get("name"),
                "email": p.get("email"),
                "role": p.get("role"),
                "title": p.get("title"),
            }
            for p in people
            if p.get("email")
        ]
        kind = str((body or {}).get("task_kind") or "").strip()
        if kind not in TASK_KINDS:
            kind = TASK_KINDS[0]
        hint = {
            "account_id": account_id,
            "company": acct.get("name") or acct.get("abbr"),
            "abbr": acct.get("abbr"),
            "health": acct.get("health"),
            "task_kind": kind,
            "task_name": str((body or {}).get("task_name") or "").strip(),
            "due_at": str((body or {}).get("due_at") or "").strip(),
            "body": str((body or {}).get("body") or "").strip(),
            "cc_addrs": (body or {}).get("cc_addrs") or [],
            "people": people_slice,
            "open_tickets": open_tickets,
        }
        settings = _settings()
        result = "fallback"
        drafted = fallback_task_assist(
            acct,
            kind=kind,
            name=hint["task_name"],
            body=hint["body"],
            people=people,
        )
        client = ai_client()
        if client:
            try:
                drafted, _model = assist_task_with_grok(client, hint, settings)
                result = selected_provider(repo_obj().get_settings())
            except Exception as exc:
                log.warning("csm.task.assist result=fallback err=%s", exc)
        allowed = {p.get("email", "").lower() for p in people_slice}
        cc = []
        for addr in drafted.get("cc_addrs") or []:
            email = str(addr or "").strip()
            if email and email.lower() in allowed and email not in cc:
                cc.append(email)
        use_kind = str(drafted.get("task_kind") or kind)
        if use_kind not in TASK_KINDS:
            use_kind = kind
        due = str(drafted.get("due_at") or "")
        if len(due) >= 16 and due[4] == "-" and due[10] == "T":
            due = due[:16]
        elif len(due) == 10 and due[4] == "-":
            due = due + "T15:00"
        else:
            due = fallback_task_assist(acct, kind=use_kind)["due_at"]
        out = {
            "task_name": str(drafted.get("task_name") or hint["task_name"] or "").strip(),
            "task_kind": use_kind,
            "due_at": due,
            "cc_addrs": cc,
            "body": str(drafted.get("body") or hint["body"] or "").strip(),
            "result": result,
        }
        if not out["task_name"]:
            out["task_name"] = fallback_task_assist(acct, kind=use_kind)["task_name"]
        log.info(
            "csm.task.assist result=%s account_id=%s task_kind=%s",
            result,
            account_id,
            out["task_kind"],
        )
        return out

    @app.post("/api/tasks")
    def create_task(body: dict):
        try:
            doc = repo_obj().save_task(body or {})
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.task.created account_id=%s task_kind=%s cc_count=%s",
            doc.get("account_id"),
            doc.get("task_kind"),
            len(doc.get("cc_addrs") or []),
        )
        return doc

    @app.post("/api/tasks/{email_id:path}/send")
    def send_task(email_id: str, body: dict | None = None):
        body = body or {}
        repo = repo_obj()
        doc = repo.task_public(email_id)
        if not doc:
            raise HTTPException(404, "not found")
        me = str(repo.operator_profile().get("email") or "").strip()
        to_addrs = [addr for addr in (body.get("to_addrs") or doc.get("to_addrs") or []) if addr] or ([me] if me else [])
        cc_addrs = list(body.get("cc_addrs") if "cc_addrs" in body else (doc.get("cc_addrs") or []))
        bcc_addrs = list(body.get("bcc_addrs") if "bcc_addrs" in body else (doc.get("bcc_addrs") or []))
        sent = _send_mail(
            repo,
            from_addr=str(doc.get("from_addr") or me),
            to_addrs=to_addrs,
            cc_addrs=cc_addrs,
            bcc_addrs=bcc_addrs,
            subject=str(body.get("subject") or doc.get("subject") or ""),
            body=str(body.get("body") or doc.get("body_text") or doc.get("content") or ""),
            attachments=body.get("attachments") or [],
        )
        out = repo.mark_task_sent(email_id)
        log.info("csm.task.sent email_id=%s via=%s", email_id, sent.get("via"))
        return {**out, "sent": sent}

    @app.get("/api/tasks/{email_id:path}")
    def get_task(email_id: str):
        doc = repo_obj().task_public(email_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.put("/api/tasks/{email_id:path}")
    def update_task(email_id: str, body: dict):
        try:
            doc = repo_obj().save_task(body or {}, email_id=email_id)
        except KeyError:
            raise HTTPException(404, "not found") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        log.info(
            "csm.task.updated account_id=%s task_kind=%s",
            doc.get("account_id"),
            doc.get("task_kind"),
        )
        return doc

    @app.patch("/api/emails/{email_id}/operator")
    def patch_email_operator(email_id: str, body: dict):
        allowed = {k: body[k] for k in ("unread",) if k in body}
        try:
            doc = repo_obj().patch_email_operator(email_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=emails id=%s fields=%s", email_id, ",".join(allowed))
        return doc

    @app.get("/api/slack/channels")
    def list_slack_channels(account_id: str):
        return {"items": repo_obj().list_slack_channels(account_id)}

    @app.get("/api/slack/messages")
    def list_slack_messages(account_id: str, channel_id: str | None = None, limit: int = 50):
        items, total = repo_obj().page_slack(account_id, channel_id=channel_id, limit=limit)
        return {"items": items, "total": total}

    @app.get("/api/slack/messages/{message_id:path}")
    def get_slack_message(message_id: str):
        if message_id.endswith("/operator"):
            raise HTTPException(404, "not found")
        doc = repo_obj().get_slack_message(message_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/slack/messages/{message_id:path}/operator")
    def patch_slack_operator(message_id: str, body: dict):
        allowed = {k: body[k] for k in ("pin",) if k in body}
        try:
            doc = repo_obj().patch_slack_operator(message_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=slack_messages id=%s fields=%s", message_id, ",".join(allowed))
        return doc

    @app.get("/api/teams/channels")
    def list_teams_channels(account_id: str):
        return {"items": repo_obj().list_teams_channels(account_id)}

    @app.get("/api/teams/messages")
    def list_teams_messages(account_id: str, channel_id: str | None = None, limit: int = 50):
        items, total = repo_obj().page_teams(account_id, channel_id=channel_id, limit=limit)
        return {"items": items, "total": total}

    @app.get("/api/teams/messages/{message_id:path}")
    def get_teams_message(message_id: str):
        if message_id.endswith("/operator"):
            raise HTTPException(404, "not found")
        doc = repo_obj().get_teams_message(message_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/teams/messages/{message_id:path}/operator")
    def patch_teams_operator(message_id: str, body: dict):
        allowed = {k: body[k] for k in ("pin",) if k in body}
        try:
            doc = repo_obj().patch_teams_operator(message_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=teams_messages id=%s fields=%s", message_id, ",".join(allowed))
        return doc

    @app.get("/api/salesforce/opportunities")
    def list_salesforce_opportunities(account_id: str, q: str | None = None):
        items = repo_obj().page_salesforce_opportunities(account_id, q=q)
        return {"items": items, "total": len(items)}

    @app.get("/api/salesforce/opportunities/{opp_id:path}")
    def get_salesforce_opportunity(opp_id: str):
        doc = repo_obj().get_salesforce_opportunity(opp_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.get("/api/salesforce/cases")
    def list_salesforce_cases(account_id: str, q: str | None = None):
        items = repo_obj().page_salesforce_cases(account_id, q=q)
        return {"items": items, "total": len(items)}

    @app.get("/api/salesforce/cases/{case_id:path}")
    def get_salesforce_case(case_id: str):
        doc = repo_obj().get_salesforce_case(case_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.get("/api/calendar")
    def list_calendar(
        account_id: str,
        start: str | None = None,
        end: str | None = None,
        from_: str | None = None,
        to: str | None = None,
    ):
        return {"items": repo_obj().page_calendar(account_id, start=start or from_, end=end or to)}

    @app.get("/api/calendar/{event_id:path}")
    def get_calendar(event_id: str):
        if event_id.endswith("/operator"):
            raise HTTPException(404, "not found")
        doc = repo_obj().get_calendar(event_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/calendar/{event_id:path}/operator")
    def patch_calendar_operator(event_id: str, body: dict):
        allowed = {k: body[k] for k in ("prep_note",) if k in body}
        try:
            doc = repo_obj().patch_calendar_operator(event_id, allowed)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.operator.patched collection=calendar_events id=%s fields=%s", event_id, ",".join(allowed))
        return doc

    @app.get("/api/actions")
    def list_actions(account_id: str | None = None, status: str | None = None, due: str = "all"):
        return {"items": repo_obj().page_actions(account_id=account_id, status=status, due=due)}

    @app.post("/api/actions")
    def create_action(body: dict):
        doc = repo_obj().create_action(body)
        log.info("csm.action.created account_id=%s", doc.get("account_id"))
        return doc

    @app.patch("/api/actions/{action_id}")
    def patch_action(action_id: str, body: dict):
        try:
            doc = repo_obj().patch_action(action_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        verb = "done" if doc.get("status") == "done" else "updated"
        log.info("csm.action.%s action_id=%s", verb, action_id)
        return doc

    @app.get("/api/drafts")
    def list_drafts(account_id: str):
        return {"items": repo_obj().list_drafts(account_id)}

    @app.post("/api/drafts")
    def create_draft(body: dict):
        doc = repo_obj().create_draft(body)
        log.info("csm.draft.created account_id=%s", doc.get("account_id"))
        return doc

    @app.post("/api/drafts/compose")
    def compose_draft(body: dict):
        account_id = str(body.get("account_id") or "")
        acct = repo_obj().get_account(account_id)
        if not acct:
            raise HTTPException(404, "account not found")
        ctx = build_compose_context(
            repo_obj(),
            account_id,
            thread_id=body.get("thread_id"),
            ticket_ids=body.get("ticket_ids") or [],
            slack_refs=body.get("slack_refs") or [],
        )
        settings = _settings()
        result = "fallback"
        model = ""
        draft_body = fallback_draft(acct, ctx)
        client = ai_client()
        if client:
            try:
                draft_body, model = compose_with_grok(client, ctx, settings)
                result = selected_provider(repo_obj().get_settings())
            except Exception as exc:
                log.warning("csm.draft.compose result=fallback err=%s", exc)
        to_addrs = draft_body.get("to") or []
        if not to_addrs:
            people = repo_obj().list_people(account_id, kind="customer")
            champ = next((p for p in people if p.get("role") == "champion"), None)
            if champ and champ.get("email"):
                to_addrs = [champ["email"]]
        doc = repo_obj().create_draft(
            {
                "account_id": account_id,
                "subject": draft_body.get("subject") or "",
                "body": draft_body.get("body") or "",
                "to_addrs": to_addrs,
                "cc_addrs": draft_body.get("cc") or [],
                "prompt_name": "email_draft",
                "model": model,
                "created_by": "grok" if result == "grok" else "you",
                "context_ref": {
                    "thread_id": body.get("thread_id") or "",
                    "ticket_ids": body.get("ticket_ids") or [],
                    "slack_refs": body.get("slack_refs") or [],
                },
                "status": "ready",
            }
        )
        log.info("csm.draft.compose result=%s prompt_name=email_draft account_id=%s", result, account_id)
        return {**doc, "next_steps": draft_body.get("next_steps") or [], "risks": draft_body.get("risks") or [], "result": result}

    @app.get("/api/drafts/{draft_id}")
    def get_draft(draft_id: str):
        doc = repo_obj().get_draft(draft_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/drafts/{draft_id}")
    def patch_draft(draft_id: str, body: dict):
        try:
            doc = repo_obj().patch_draft(draft_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info("csm.draft.updated draft_id=%s", draft_id)
        return doc

    @app.post("/api/drafts/{draft_id}/send")
    def send_draft(draft_id: str, body: dict | None = None):
        body = body or {}
        repo = repo_obj()
        doc = repo.get_draft(draft_id)
        if not doc:
            raise HTTPException(404, "not found")
        patch = {
            k: body[k]
            for k in ("to_addrs", "cc_addrs", "bcc_addrs", "subject", "body", "attachment_names")
            if k in body
        }
        if patch:
            try:
                doc = repo.patch_draft(draft_id, patch)
            except KeyError:
                raise HTTPException(404, "not found") from None
        me = str(repo.operator_profile().get("email") or "").strip()
        to_addrs = [addr for addr in (doc.get("to_addrs") or []) if addr]
        try:
            sent = _send_mail(
                repo,
                from_addr=me,
                to_addrs=to_addrs,
                cc_addrs=list(doc.get("cc_addrs") or []),
                bcc_addrs=list(doc.get("bcc_addrs") or []),
                subject=str(doc.get("subject") or ""),
                body=str(doc.get("body") or ""),
                attachments=body.get("attachments") or [],
            )
        except HTTPException as exc:
            if exc.status_code == 502:
                repo.mark_draft_sent(draft_id, error="send_failed")
            raise
        out = repo.mark_draft_sent(draft_id)
        outbound = repo.upsert_email(
            {
                "account_id": doc.get("account_id") or "",
                "direction": "outbound",
                "from_addr": sent.get("from_addr") or me,
                "to_addrs": sent.get("to_addrs") or to_addrs,
                "cc_addrs": list(doc.get("cc_addrs") or []),
                "bcc_addrs": list(doc.get("bcc_addrs") or []),
                "subject": doc.get("subject") or "",
                "body_text": doc.get("body") or "",
                "snippet": str(doc.get("body") or "")[:180],
                "has_attachments": bool(sent.get("attach_count")),
                "sent_at": out.get("sent_at") or utcnow(),
                "message_id": f"<draft.{draft_id.split(':')[-1]}@csm.local>",
                "operator": {"unread": False},
                "sources": {"smtp": {"draft_id": draft_id}},
            }
        )
        emit_email_activity(repo, outbound)
        log.info("csm.draft.sent draft_id=%s via=%s", draft_id, sent.get("via"))
        return {**out, "sent": sent}

    @app.get("/api/reports")
    def list_reports(account_id: str | None = None):
        return {"items": repo_obj().list_reports(account_id)}

    @app.post("/api/reports/generate")
    def generate_report(body: dict):
        account_id = str(body.get("account_id") or "")
        acct = repo_obj().get_account(account_id)
        if not acct:
            raise HTTPException(404, "account not found")
        ctx = build_compose_context(repo_obj(), account_id)
        settings = _settings()
        period_end = utcnow()[:10]
        period_start = (datetime.now(timezone.utc) - timedelta(days=6)).date().isoformat()
        title = f"{acct.get('abbr')} weekly — {period_end}"
        body_md = (
            f"Health: {(acct.get('health') or {}).get('score')} "
            f"{(acct.get('health') or {}).get('status')}\n"
            f"Open tickets: {(acct.get('stats') or {}).get('open_tickets')}\n"
            f"Overdue actions: {(acct.get('stats') or {}).get('overdue_actions')}\n"
        )
        model = ""
        client = ai_client()
        if client:
            try:
                data, model = client.complete_json(
                    [
                        {"role": "system", "content": prompt_system("weekly_report")},
                        {"role": "user", "content": ctx.serialized()},
                    ]
                )
                body_md = data.get("body") or data.get("body_md") or json.dumps(data)
            except Exception as exc:
                log.warning("csm.report.generated fallback err=%s", exc)
        doc = repo_obj().create_report(
            {
                "account_id": account_id,
                "kind": body.get("kind") or "weekly",
                "period_start": period_start,
                "period_end": period_end,
                "title": title,
                "body_md": body_md,
                "model": model,
            }
        )
        log.info("csm.report.generated kind=weekly account_id=%s", account_id)
        return doc

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: str):
        doc = repo_obj().get_report(report_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.post("/api/chat")
    def post_chat(body: dict):
        message = str(body.get("message") or "").strip()
        if not message:
            raise HTTPException(400, "message required")
        hinted = str(body.get("account_id") or "").strip()
        acct = resolve_account(repo_obj(), message, hinted)
        account_id = (acct or {}).get("account_id") or hinted or "desk"
        chat_id = body.get("chat_id")
        chat = repo_obj().get_chat(chat_id) if chat_id else None
        if not chat:
            title = "Desk chat" if account_id == "desk" else "Account coach"
            chat = repo_obj().save_chat({"account_id": account_id, "title": title, "messages": []})
            chat_id = chat["_id"]
        messages = list(chat.get("messages") or [])
        messages.append({"role": "user", "content": message})
        settings = _settings()
        local_reply = answer_desk(repo_obj(), message, acct)

        def sse():
            client = ai_client()
            if not client or account_id == "desk" or not acct:
                reply = local_reply
                for i in range(0, len(reply), 40):
                    chunk = reply[i : i + 40]
                    yield f"event: token\ndata: {json.dumps(chunk)}\n\n"
                messages.append({"role": "assistant", "content": reply})
                repo_obj().save_chat({**chat, "messages": messages, "account_id": account_id}, chat_id=chat_id)
                log.info("csm.chat.turn result=fallback account_id=%s", account_id)
                yield f"event: done\ndata: {json.dumps({'result': 'fallback', 'chat_id': chat_id, 'account_id': account_id})}\n\n"
                return
            sys = [
                {"role": "system", "content": prompt_system("desk_chat")},
                {"role": "system", "content": "Local brief:\n" + local_reply},
            ]
            try:
                text, model, working = client.complete(sys + messages, repo_obj(), account_id)
            except Exception as exc:
                log.warning("csm.chat.turn result=fallback err=%s", exc)
                text = local_reply
                model = ""
                working = messages + [{"role": "assistant", "content": text}]
            for piece in [text[i : i + 40] for i in range(0, len(text), 40)] or [""]:
                yield f"event: token\ndata: {json.dumps(piece)}\n\n"
            repo_obj().save_chat(
                {**chat, "messages": working if working else messages + [{"role": "assistant", "content": text}], "account_id": account_id, "model": model},
                chat_id=chat_id,
            )
            yield f"event: done\ndata: {json.dumps({'result': 'grok' if model else 'fallback', 'chat_id': chat_id, 'account_id': account_id})}\n\n"

        return StreamingResponse(sse(), media_type="text/event-stream")

    @app.get("/api/chats")
    def list_chats(account_id: str):
        return {"items": repo_obj().list_chats(account_id)}

    @app.get("/api/chats/{chat_id:path}")
    def get_chat(chat_id: str):
        doc = repo_obj().get_chat(chat_id)
        if not doc:
            raise HTTPException(404, "not found")
        return doc

    @app.patch("/api/chats/{chat_id:path}")
    def patch_chat(chat_id: str, body: dict):
        try:
            doc = repo_obj().patch_chat(chat_id, body)
        except KeyError:
            raise HTTPException(404, "not found") from None
        log.info(
            "csm.chat.updated chat_id=%s changed_fields=%s",
            chat_id,
            ",".join(body.keys()),
        )
        return doc

    @app.get("/api/oauth/{vendor}/start")
    def oauth_start(vendor: str):
        try:
            repo = repo_obj()
            if vendor == "google":
                from csm_dashboard.connectors.google_secrets import hydrate_google

                hydrate_google(repo)
            okta = repo.get_credential_secret("connector", "okta")
            hint = str(okta.get("email") or (repo.operator_profile() or {}).get("email") or "")
            org = str(okta.get("org_url") or (repo.get_settings() or {}).get("sso", {}).get("org_url") or "")
            url = oauth_flow.start_url(vendor, repo, login_hint=hint, org_url=org)
        except KeyError:
            raise HTTPException(404, "unknown_oauth_vendor") from None
        except ValueError as exc:
            code = str(exc)
            log.info("csm.oauth.start vendor=%s result=%s", vendor, code)
            if code == "oauth_client_id_missing":
                names = {
                    "google": "local credentials.json (or paste Google client ID on Sign in)",
                    "microsoft": "Microsoft client ID on Settings → Sign in",
                    "slack": "Slack client ID on Settings → Sign in",
                    "okta": "SSO client ID on Settings → Sign in",
                    "salesforce": "Salesforce consumer key on the Salesforce connector",
                }
                message = "Missing " + names.get(vendor, "OAuth client ID") + ". Save it, then Connect again."
            else:
                message = code.replace("_", " ")
            return HTMLResponse(oauth_flow.callback_html(ok=False, message=message), status_code=400)
        log.info("csm.oauth.start vendor=%s", vendor)
        return RedirectResponse(url, status_code=302)

    @app.get("/api/oauth/{vendor}/callback")
    def oauth_callback(vendor: str, request: Request):
        params = request.query_params
        if params.get("error"):
            log.info("csm.oauth.callback vendor=%s result=denied", vendor)
            return HTMLResponse(
                oauth_flow.callback_html(ok=False, message="The provider denied access."),
                status_code=400,
            )
        try:
            oauth_flow.finish(vendor, params.get("code") or "", params.get("state") or "", repo_obj())
        except KeyError:
            raise HTTPException(404, "unknown_oauth_vendor") from None
        except ValueError as exc:
            log.info("csm.oauth.callback vendor=%s result=invalid", vendor)
            return HTMLResponse(
                oauth_flow.callback_html(ok=False, message=str(exc).replace("_", " ")),
                status_code=400,
            )
        except Exception:
            log.exception("csm.oauth.callback vendor=%s result=error", vendor)
            return HTMLResponse(
                oauth_flow.callback_html(
                    ok=False,
                    message="Could not finish sign-in. Check the OAuth client ID and redirect URI.",
                ),
                status_code=502,
            )
        log.info("csm.oauth.callback vendor=%s result=ok", vendor)
        return HTMLResponse(oauth_flow.callback_html(ok=True, message="You can close this tab and return to Settings."))

    @app.get("/oauth2callback")
    def google_oauth2_callback(request: Request):
        return oauth_callback("google", request)

    @app.post("/api/oauth/{vendor}/disconnect")
    def oauth_disconnect(vendor: str):
        try:
            oauth_flow.disconnect(vendor, repo_obj())
        except KeyError:
            raise HTTPException(404, "unknown_oauth_vendor") from None
        return {"ok": True, "vendor": vendor}

    @app.get("/api/connectors")
    def api_list_connectors():
        repo = repo_obj()
        creds = repo.list_credentials_public()
        return {"items": list_connectors(repo.get_settings(), creds.get("connectors"), repo)}

    @app.get("/api/connectors/{name}/health")
    def connector_health(name: str):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        return get_connector(name, repo_obj()).health()

    @app.post("/api/connectors/{name}/test")
    def connector_test(name: str):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        repo = repo_obj()
        conn = get_connector(name, repo)
        probe = getattr(conn, "probe", None)
        health = probe() if callable(probe) else conn.health()
        health["auth"] = connector_auth(name)
        if callable(probe) and health.get("ok"):
            repo.save_settings({"connectors": {name: {"mode": "live"}}})
            health["mode"] = "live"
        log.info("csm.connector.test name=%s ok=%s", name, health.get("ok"))
        return health

    @app.post("/api/connectors/{name}/sync")
    def run_sync(name: str, body: dict | None = None):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        mode = connector_mode(name, repo_obj().get_settings())
        if mode != "live":
            raise HTTPException(409, "connector_disabled")
        body = body or {}
        account_id = body.get("account_id")
        account = repo_obj().get_account(account_id) if account_id else None
        job = repo_obj().save_job(
            {"connector": name, "account_id": account_id or "", "status": "running", "since": body.get("since") or "", "fetched": 0, "upserted": 0, "skipped": 0, "error": ""}
        )
        log.info("csm.sync.started connector=%s", name)
        try:
            events = get_connector(name, repo_obj()).pull(body.get("since"), account)
            accounts = repo_obj().list_accounts(include_hidden=True)
            upserted = 0
            ours = repo_obj().operator_domains()
            for event in events:
                aid = route_event(accounts, event, operator_domains=ours)
                event["account_id"] = aid
                if aid:
                    payload = dict(event.get("payload") or {})
                    payload["account_id"] = aid
                    event["payload"] = payload
                apply_sync_event(repo_obj(), event)
                upserted += 1
            if account_id:
                repo_obj().refresh_account_stats(account_id)
                repo_obj().score_account(account_id)
            job = repo_obj().save_job({**job, "status": "done", "fetched": len(events), "upserted": upserted}, job_id=job["_id"])
            log.info("csm.sync.finished connector=%s fetched=%s upserted=%s", name, len(events), upserted)
            return job
        except Exception as exc:
            job = repo_obj().save_job({**job, "status": "error", "error": str(exc)}, job_id=job["_id"])
            log.error("csm.sync.failed connector=%s err=%s", name, exc)
            return job

    @app.get("/api/sync/jobs")
    def list_sync_jobs():
        return {"items": repo_obj().list_jobs()}

    @app.get("/api/notes")
    def list_notes(account_id: str, ref_id: str | None = None, q: str | None = None):
        return {"items": repo_obj().list_notes(account_id, ref_id=ref_id, q=q)}

    @app.post("/api/notes")
    def create_note(body: dict):
        if not body.get("account_id") or not body.get("body"):
            raise HTTPException(400, "account_id and body required")
        doc = repo_obj().add_note(body)
        log.info(
            "csm.note.added account_id=%s ref_id=%s",
            body.get("account_id"),
            (body.get("ref") or {}).get("id") or "",
        )
        return doc

    return app
