"""
Attio People queries and writes used by the recommendation engine and
workers. Business rules (what counts as eligible, evidence requirements,
etc.) live in recommendations/engine.py — this module is the data-access
layer plus a few invariants that must always hold regardless of caller.
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from typing import Any

from src.attio.client import AttioClient
from src.attio.schema import (
    ACTIVE_DRAFT_STATUSES,
    OUTREACH_STAGE_SUPPRESSING,
    PEOPLE_FIELDS,
)

logger = logging.getLogger(__name__)

PEOPLE_OBJECT = "people"


@dataclass
class Person:
    record_id: str
    name: str
    owner: str | None
    do_not_contact: bool
    outreach_stage: str | None
    last_meaningful_interaction: dt.datetime | None
    outreach_status: str | None
    marketing_consent: bool
    preferred_channel: str | None
    raw: dict = field(default_factory=dict)

    @property
    def is_suppressed(self) -> bool:
        return bool(self.do_not_contact) or self.outreach_stage in OUTREACH_STAGE_SUPPRESSING


def _get_value(values: dict, slug: str) -> Any:
    entries = values.get(slug) or []
    if not entries:
        return None
    entry = entries[0]
    # Attio attribute values are typed wrappers; pull the common shapes.
    for key in ("value", "option", "text", "date", "referenced_actor_id"):
        if key in entry:
            return entry[key]
    return entry


def _parse_person(record: dict) -> Person:
    values = record.get("values", {})
    return Person(
        record_id=record["id"]["record_id"],
        name=_get_value(values, "name") or "(unnamed)",
        owner=_get_value(values, PEOPLE_FIELDS["relationship_owner"]),
        do_not_contact=bool(_get_value(values, PEOPLE_FIELDS["do_not_contact"])),
        outreach_stage=_get_value(values, PEOPLE_FIELDS["outreach_stage"]),
        last_meaningful_interaction=_parse_date(
            _get_value(values, PEOPLE_FIELDS["last_meaningful_interaction"])
        ),
        outreach_status=_get_value(values, PEOPLE_FIELDS["outreach_status"]),
        marketing_consent=bool(_get_value(values, PEOPLE_FIELDS["marketing_consent"])),
        preferred_channel=_get_value(values, PEOPLE_FIELDS["preferred_channel"]),
        raw=record,
    )


def _parse_date(value: Any) -> dt.datetime | None:
    if not value:
        return None
    if isinstance(value, dt.datetime):
        return value
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def eligible_people(client: AttioClient, limit: int = 200) -> list[Person]:
    """
    People with an owner, not suppressed, and with no draft/send already
    in progress. Suppression and do-not-contact are always excluded here —
    callers should never need to re-check this, but recommendations/engine.py
    re-checks it anyway as defense in depth before writing anything.
    """
    filter_body = {
        "filter": {
            "$and": [
                {PEOPLE_FIELDS["relationship_owner"]: {"$is_not_empty": True}},
                {PEOPLE_FIELDS["do_not_contact"]: {"$eq": False}},
                {
                    PEOPLE_FIELDS["outreach_status"]: {
                        "$not_in": list(ACTIVE_DRAFT_STATUSES)
                    }
                },
            ]
        },
        "limit": limit,
    }
    result = client.query_records(PEOPLE_OBJECT, filter_body)
    records = result.get("data", []) if isinstance(result, dict) else []
    people = [_parse_person(r) for r in records]
    # Defense in depth: never return a suppressed person even if the
    # upstream filter was misconfigured.
    return [p for p in people if not p.is_suppressed]


def write_recommendation(
    client: AttioClient,
    person: Person,
    *,
    evidence: str,
    channel: str,
    draft_body: str,
    dry_run: bool = True,
) -> dict:
    """
    Writes a `suggested` recommendation. Never sends anything. If the
    record already has a non-empty, approved Draft body that differs from
    what's being written, this returns it to `in_review` instead of
    silently overwriting an owner's edited copy.
    """
    existing_status = person.outreach_status
    existing_draft = getattr(person, "draft_body", None)

    new_status = "suggested"
    if existing_status == "approved" and existing_draft and existing_draft != draft_body:
        new_status = "in_review"
        logger.info(
            "Record %s had an approved draft that differs from the new "
            "proposal; returning to in_review instead of overwriting.",
            person.record_id,
        )

    attributes = {
        PEOPLE_FIELDS["draft_body"]: draft_body,
        PEOPLE_FIELDS["draft_evidence"]: evidence,
        PEOPLE_FIELDS["outreach_status"]: new_status,
        PEOPLE_FIELDS["preferred_channel"]: channel,
    }

    if dry_run:
        logger.info("[dry-run] would update %s with %s", person.record_id, attributes)
        return {"dry_run": True, "record_id": person.record_id, "attributes": attributes}

    return client.update_record(PEOPLE_OBJECT, person.record_id, attributes)


def mark_sent(
    client: AttioClient,
    person: Person,
    *,
    channel: str,
    confirmed_by_owner: bool,
    dry_run: bool = True,
) -> dict:
    """
    The only way a record can reach `sent` for a manual channel
    (LinkedIn/WhatsApp/Telegram). Refuses unless the caller explicitly
    confirms a human sent it — there is intentionally no automated path
    that can set this.
    """
    if not confirmed_by_owner:
        raise ValueError(
            "mark_sent requires confirmed_by_owner=True; this system never "
            "sends social messages itself."
        )
    attributes = {
        PEOPLE_FIELDS["outreach_status"]: "sent",
    }
    if dry_run:
        logger.info("[dry-run] would mark %s sent via %s", person.record_id, channel)
        return {"dry_run": True, "record_id": person.record_id, "attributes": attributes}
    return client.update_record(PEOPLE_OBJECT, person.record_id, attributes)


def suppress(
    client: AttioClient,
    record_id: str,
    *,
    reason: str,
    dry_run: bool = True,
) -> dict:
    """Immediately suppresses a person, e.g. on bounce/unsubscribe/complaint."""
    attributes = {
        PEOPLE_FIELDS["do_not_contact"]: True,
    }
    if dry_run:
        logger.info("[dry-run] would suppress %s: %s", record_id, reason)
        return {"dry_run": True, "record_id": record_id, "attributes": attributes}
    return client.update_record(PEOPLE_OBJECT, record_id, attributes)
