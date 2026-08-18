from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema"


def test_schema_headers():
    files = list(SCHEMA.glob("*.schema.json"))
    assert files
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert str(data["$id"]).startswith("https://csm-dashboard.local/schema/")


def test_config_example_validates():
    schema = json.loads((SCHEMA / "config.schema.json").read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(cfg)


@pytest.mark.parametrize(
    "filename,schema_name",
    [
        ("accounts.json", "account.schema.json"),
        ("tickets.json", "ticket.schema.json"),
        ("emails.json", "email.schema.json"),
        ("action_items.json", "action_item.schema.json"),
        ("people.json", "person.schema.json"),
    ],
)
def test_seed_rows_validate(filename, schema_name):
    schema = json.loads((SCHEMA / schema_name).read_text(encoding="utf-8"))
    rows = json.loads((ROOT / "fixtures" / "seed" / filename).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for row in rows:
        validator.validate(row)
