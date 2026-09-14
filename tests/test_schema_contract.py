"""
Schema-contract test: docs/attio-schema.md and src/attio/schema.py must
describe the same field set, so the docs never silently drift from what
the code actually reads/writes.
"""
import re
from pathlib import Path

from src.attio.schema import PEOPLE_FIELDS

DOCS_PATH = Path(__file__).resolve().parent.parent / "docs" / "attio-schema.md"


def test_every_schema_field_is_documented():
    text = DOCS_PATH.read_text()
    slugs_in_docs = set(re.findall(r"`(\w+)`", text))
    missing = [slug for slug in PEOPLE_FIELDS.values() if slug not in slugs_in_docs]
    assert not missing, f"Fields missing from docs/attio-schema.md: {missing}"
