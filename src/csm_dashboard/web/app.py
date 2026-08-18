from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from csm_dashboard import __version__
from csm_dashboard.chat.desk_answer import answer_desk
from csm_dashboard.chat.grok import GrokClient
from csm_dashboard.chat.mentions import resolve_account
from csm_dashboard.compose.context import build_compose_context
from csm_dashboard.compose.grok import compose_with_grok, fallback_draft, fallback_reply
from csm_dashboard.config import ROOT, Settings, fixtures_dir, load_secrets, load_settings, save_secrets
from csm_dashboard.connectors.registry import PULL_CONNECTORS, connector_mode, get_connector, list_connectors
from csm_dashboard.ingest.route import route_event
from csm_dashboard.prompts import desk_chat_public, help_public, prompt_system
from csm_dashboard.seed.load import apply_seed, apply_sync_event
from csm_dashboard.storage.errors import CouchbaseLiteNotAvailable
from csm_dashboard.storage.repo import CsmRepo, utcnow

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
_INDEX_HTML: str | None = None


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

    @app.get("/", response_class=HTMLResponse)
    def index():
        global _INDEX_HTML
        if _INDEX_HTML is None:
            _INDEX_HTML = (HERE / "templates" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(_INDEX_HTML.replace("{{ version }}", __version__))

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": __version__, "cblite": "community"}

    @app.get("/openapi.yaml", include_in_schema=False)
    def openapi_yaml():
        path = ROOT / "docs" / "openapi.yaml"
        return Response(path.read_text(encoding="utf-8"), media_type="application/yaml")

    @app.get("/api/status")
    def get_status():
        settings = _settings()
        secrets = load_secrets()
        return {
            "version": __version__,
            "host": settings.host,
            "port": settings.port,
            "tagline": settings.tagline,
            "operator": repo_obj().operator_profile(),
            "world_clock": repo_obj().world_clock(),
            "models": settings.model_list(),
            "default_model": settings.xai_default_model,
            "ai": (repo_obj().get_settings() or {}).get("ai") or {"provider": "grok", "model": settings.xai_default_model},
            "keys": {
                "xai": bool(settings.has_xai_key or secrets.get("xai_api_key")),
                "openai": bool(secrets.get("openai_api_key")),
                "gemini": bool(secrets.get("gemini_api_key")),
            },
            "connectors": list_connectors(),
            "counts": repo_obj().counts(),
            "chat": desk_chat_public(),
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
        return saved

    @app.get("/api/settings")
    def get_settings():
        doc = repo_obj().get_settings()
        return {
            **doc,
            "operator": repo_obj().operator_profile(),
            "world_clock": repo_obj().world_clock(),
            "ai": (doc or {}).get("ai") or {"provider": "grok", "model": _settings().xai_default_model},
        }

    @app.put("/api/settings/keys")
    def put_keys(body: dict):
        allowed = {
            k: v
            for k, v in body.items()
            if k in {"xai_api_key", "openai_api_key", "gemini_api_key"} and v
        }
        save_secrets(allowed)
        log.info("csm.settings.keys_updated fields=%s", ",".join(allowed.keys()))
        return {"ok": True, "fields": list(allowed.keys())}

    @app.post("/api/settings/providers/test")
    def test_provider(body: dict):
        provider = str(body.get("provider") or "grok").strip().lower()
        secrets = load_secrets()
        settings = _settings()
        key_map = {
            "grok": settings.xai_api_key or secrets.get("xai_api_key"),
            "xai": settings.xai_api_key or secrets.get("xai_api_key"),
            "openai": secrets.get("openai_api_key"),
            "gemini": secrets.get("gemini_api_key"),
        }
        key = key_map.get(provider) or ""
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
                    "stats": repo_obj().account_inbox_stats(aid),
                    "next_meeting": repo_obj().next_meeting(aid),
                }
            )
        return items

    @app.get("/api/home")
    def get_home():
        return {"items": _home_items()}

    @app.get("/api/home/agenda")
    def get_home_agenda(date: str | None = None):
        return repo_obj().home_agenda(date or "")

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
        if settings.has_xai_key:
            try:
                client = GrokClient(settings.xai_api_key, settings.xai_base_url, settings.model_list())
                drafted, model = compose_with_grok(client, ctx, settings)
                draft_body = {**draft_body, **drafted}
                result = "grok"
            except Exception as exc:
                log.warning("csm.draft.suggest_reply result=fallback err=%s", exc)
        to_addrs = draft_body.get("to") or []
        if last and last.get("from_addr") and last.get("from_addr") not in to_addrs:
            to_addrs = [last["from_addr"], *to_addrs]
        log.info("csm.draft.suggest_reply result=%s thread_id=%s", result, thread_id)
        return {
            "account_id": account_id,
            "thread_id": thread_id,
            "subject": draft_body.get("subject") or "",
            "body": draft_body.get("body") or "",
            "to_addrs": to_addrs,
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
        if settings.has_xai_key:
            try:
                client = GrokClient(settings.xai_api_key, settings.xai_base_url, settings.model_list())
                draft_body, model = compose_with_grok(client, ctx, settings)
                result = "grok"
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
    def send_draft(draft_id: str):
        if not repo_obj().get_draft(draft_id):
            raise HTTPException(404, "not found")
        log.info("csm.draft.send_blocked draft_id=%s", draft_id)
        raise HTTPException(409, "send_disabled_v0_1")

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
        if settings.has_xai_key:
            try:
                client = GrokClient(settings.xai_api_key, settings.xai_base_url, settings.model_list())
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
            if not settings.has_xai_key or account_id == "desk" or not acct:
                reply = local_reply
                for i in range(0, len(reply), 40):
                    chunk = reply[i : i + 40]
                    yield f"event: token\ndata: {json.dumps(chunk)}\n\n"
                messages.append({"role": "assistant", "content": reply})
                repo_obj().save_chat({**chat, "messages": messages, "account_id": account_id}, chat_id=chat_id)
                log.info("csm.chat.turn result=fallback account_id=%s", account_id)
                yield f"event: done\ndata: {json.dumps({'result': 'fallback', 'chat_id': chat_id, 'account_id': account_id})}\n\n"
                return
            client = GrokClient(settings.xai_api_key, settings.xai_base_url, settings.model_list())
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

    @app.get("/api/connectors")
    def api_list_connectors():
        return {"items": list_connectors()}

    @app.get("/api/connectors/{name}/health")
    def connector_health(name: str):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        return get_connector(name).health()

    @app.post("/api/connectors/{name}/test")
    def connector_test(name: str):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        health = get_connector(name).health()
        health["auth"] = "oauth" if name in {"google_mail", "microsoft365", "google_cal", "m365_cal", "slack", "teams", "salesforce"} else "password"
        log.info("csm.connector.test name=%s ok=%s", name, health.get("ok"))
        return health

    @app.post("/api/connectors/{name}/sync")
    def run_sync(name: str, body: dict | None = None):
        if name not in PULL_CONNECTORS:
            raise HTTPException(404, "unknown connector")
        mode = connector_mode(name)
        if mode == "off":
            raise HTTPException(404, "connector_off")
        body = body or {}
        account_id = body.get("account_id")
        account = repo_obj().get_account(account_id) if account_id else None
        job = repo_obj().save_job(
            {"connector": name, "account_id": account_id or "", "status": "running", "since": body.get("since") or "", "fetched": 0, "upserted": 0, "skipped": 0, "error": ""}
        )
        log.info("csm.sync.started connector=%s", name)
        try:
            events = get_connector(name).pull(body.get("since"), account)
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
