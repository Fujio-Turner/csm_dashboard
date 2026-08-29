from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "healthz",
    "getStatus",
    "seedDemo",
    "getHome",
    "getHomeAgenda",
    "listAccounts",
    "createAccount",
    "getAccountByAbbr",
    "getAccount",
    "patchAccount",
    "rescoreAccount",
    "listTimeline",
    "listTickets",
    "patchTicketOperator",
    "listThreads",
    "patchThreadOperator",
    "composeDraft",
    "sendDraft",
    "runSync",
    "listSyncJobs",
    "postChat",
    "patchChat",
    "listTeamsMessages",
    "listSalesforceOpportunities",
    "listSalesforceCases",
    "getSlackMessage",
    "getTeamsMessage",
    "getCalendarEvent",
    "listNotes",
    "createNote",
    "getActivity",
    "patchActivity",
    "deleteAccount",
    "suggestThreadReply",
    "sendTask",
    "testProvider",
    "putKeys",
    "getKeys",
    "startOauth",
    "oauthCallback",
    "disconnectOauth",
    "uploadAccountLogo",
    "getAccountLogo",
}


def test_openapi_lists_v0_1_operations():
    spec = yaml.safe_load((ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8"))
    assert spec["openapi"].startswith("3.1")
    found = set()
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if isinstance(op, dict) and op.get("operationId"):
                found.add(op["operationId"])
    missing = REQUIRED - found
    assert not missing, missing
    assert "/api/connectors/{name}/sync" in spec["paths"]
    assert "/api/sync/jobs" in spec["paths"]
    assert "/api/drafts/{draft_id}/send" in spec["paths"]
