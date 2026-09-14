"""
The review queue: the ONLY path by which a message this system drafted can
be edited, approved, and dispatched. Nothing in src/workers or
src/recommendations ever sends anything — they only ever write a
`suggested` draft. Getting from `suggested` to `sent` always passes
through a human, on every channel, via the functions in this module.

Design intent (see RELATIONSHIP_MANAGER_ATTIO_HANDOFF.md and
docs/architecture.md): the owner sees each drafted message, can rewrite it
freely, picks which channel to use, and only then triggers a send (email)
or confirms they sent it themselves (LinkedIn/WhatsApp/iMessage — this
system has no API access to those and never will). There is intentionally
no "send all" or bulk-approve function.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from src.attio.client import AttioClient
from src.attio.queries import Person, mark_sent
from src.attio.schema import PEOPLE_FIELDS
from src.mailchimp.sync import ConsentError, MailchimpDisabledError, enroll

logger = logging.getLogger(__name__)

QUEUE_OBJECT = "people"
QUEUE_STATUSES = ("suggested", "in_review", "approved")
MANUAL_CHANNELS = ("linkedin", "whatsapp", "imessage")


class SendNotAllowedError(RuntimeError):
    pass


def _draft_from_record(record: dict) -> str:
    values = record.get("values", {})
    entries = values.get(PEOPLE_FIELDS["draft_body"]) or []
    if not entries:
        return ""
    return entries[0].get("value") or entries[0].get("text") or ""


@dataclass
class QueueItem:
    person: Person
    draft_body: str
    evidence: str
    status: str

    @property
    def record_id(self) -> str:
        return self.person.record_id


def list_queue(client: AttioClient, limit: int = 100) -> list[QueueItem]:
    """Every record awaiting a human decision — never auto-refreshed by a send."""
    filter_body = {
        "filter": {PEOPLE_FIELDS["outreach_status"]: {"$in": list(QUEUE_STATUSES)}},
        "limit": limit,
    }
    result = client.query_records(QUEUE_OBJECT, filter_body)
    records = result.get("data", []) if isinstance(result, dict) else []
    items = []
    for record in records:
        from src.attio.queries import _parse_person  # local import: internal helper

        person = _parse_person(record)
        values = record.get("values", {})
        evidence_entries = values.get(PEOPLE_FIELDS["draft_evidence"]) or []
        evidence = evidence_entries[0].get("value", "") if evidence_entries else ""
        items.append(
            QueueItem(
                person=person,
                draft_body=_draft_from_record(record),
                evidence=evidence,
                status=person.outreach_status or "suggested",
            )
        )
    return items


def save_draft(
    client: AttioClient,
    record_id: str,
    *,
    draft_body: str,
    channel: str,
    dry_run: bool = True,
) -> dict:
    """
    Records the owner's edited version. Editing always moves the record to
    `in_review` — it is not approved until the owner separately says so,
    and it is not sent until they separately trigger a send.
    """
    attributes = {
        PEOPLE_FIELDS["draft_body"]: draft_body,
        PEOPLE_FIELDS["preferred_channel"]: channel,
        PEOPLE_FIELDS["outreach_status"]: "in_review",
    }
    if dry_run:
        logger.info("[dry-run] would save edited draft for %s: %s", record_id, attributes)
        return {"dry_run": True, "record_id": record_id, "attributes": attributes}
    return client.update_record(QUEUE_OBJECT, record_id, attributes)


def approve(client: AttioClient, record_id: str, *, dry_run: bool = True) -> dict:
    """Marks a reviewed draft approved. Still does not send anything."""
    attributes = {PEOPLE_FIELDS["outreach_status"]: "approved"}
    if dry_run:
        logger.info("[dry-run] would approve %s", record_id)
        return {"dry_run": True, "record_id": record_id, "attributes": attributes}
    return client.update_record(QUEUE_OBJECT, record_id, attributes)


def _live_writes_allowed() -> bool:
    """
    Same production gate as the cadence worker: an actual send requires
    RM_ENV=production AND RM_CONFIRM_PRODUCTION=yes. Anywhere else, every
    action in this module is dry-run only and never reaches a real API.
    """
    env = os.environ.get("RM_ENV", "development").strip().lower()
    confirmed = os.environ.get("RM_CONFIRM_PRODUCTION", "").strip().lower() == "yes"
    return env == "production" and confirmed


def send_email(
    client: AttioClient,
    person: Person,
    *,
    email: str,
    audience_id: str,
    dry_run: bool | None = None,
) -> dict:
    """
    The only automated dispatch path this system has, and only for email —
    still fully consent-gated by mailchimp.sync.enroll. Only reachable
    after the owner has approved the (possibly rewritten) draft in the
    review queue; the Flask layer enforces that ordering.
    """
    if person.outreach_status != "approved":
        raise SendNotAllowedError(
            f"{person.record_id} is not approved yet — the owner must approve "
            f"the (possibly edited) draft before it can be sent."
        )
    live = _live_writes_allowed() if dry_run is None else not dry_run
    try:
        result = enroll(person, email, audience_id=audience_id, dry_run=not live)
    except (ConsentError, MailchimpDisabledError) as exc:
        raise SendNotAllowedError(str(exc)) from exc
    mark_sent(client, person, channel="email", confirmed_by_owner=True, dry_run=not live)
    return result


def confirm_manual_send(
    client: AttioClient,
    person: Person,
    *,
    channel: str,
    dry_run: bool | None = None,
) -> dict:
    """
    For LinkedIn/WhatsApp/iMessage: this system cannot send on your behalf
    and never will. This records that YOU sent the approved (and possibly
    rewritten) message yourself, on the channel you chose. Calling this
    without having actually sent the message is on the owner, not the
    system — there is no way for code to verify a manual send happened.
    """
    if channel not in MANUAL_CHANNELS:
        raise SendNotAllowedError(f"'{channel}' is not a manual channel: {MANUAL_CHANNELS}")
    if person.outreach_status != "approved":
        raise SendNotAllowedError(
            f"{person.record_id} is not approved yet — approve the (possibly "
            f"edited) draft before confirming it was sent."
        )
    live = _live_writes_allowed() if dry_run is None else not dry_run
    return mark_sent(client, person, channel=channel, confirmed_by_owner=True, dry_run=not live)
