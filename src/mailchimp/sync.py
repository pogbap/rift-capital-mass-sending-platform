"""
Mailchimp is the final sending platform for permissioned commercial email
only. It is never a source of truth and never chooses recipients — every
enrollment here is one person at a time, gated on recorded Attio consent.

No bulk enrollment function exists in this module on purpose.
"""
from __future__ import annotations

import hashlib
import logging
import os

import requests

from src.attio.client import AttioClient
from src.attio.queries import Person, suppress

logger = logging.getLogger(__name__)

MAILCHIMP_API_BASE_TMPL = "https://{server}.api.mailchimp.com/3.0"


class ConsentError(ValueError):
    pass


class MailchimpDisabledError(RuntimeError):
    pass


def _enroll_enabled() -> bool:
    return os.environ.get("RM_MAILCHIMP_ENROLL_ENABLED", "true").strip().lower() != "false"


def _subscriber_hash(email: str) -> str:
    return hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()


def _client_config() -> tuple[str, str]:
    api_key = os.environ.get("MAILCHIMP_API_KEY", "")
    server = os.environ.get("MAILCHIMP_SERVER_PREFIX", "")
    if not api_key or not server:
        raise RuntimeError("MAILCHIMP_API_KEY and MAILCHIMP_SERVER_PREFIX must be set")
    return api_key, server


def enroll(
    person: Person,
    email: str,
    *,
    audience_id: str,
    dry_run: bool = True,
) -> dict:
    """
    Enrolls exactly one person into exactly one Mailchimp audience.

    Refuses unless ALL of these hold:
      - marketing_consent is recorded True on the Attio record
      - person.marketing_audience names an approved segment (matches audience_id's
        expected segment, passed by the caller after checking approval)
      - eligibility is not suppressed / do-not-contact
      - the RM_MAILCHIMP_ENROLL_ENABLED feature flag is on

    Idempotent: Mailchimp's PUT-by-subscriber-hash upsert semantics mean
    re-running this for an already-current subscriber is a no-op write.
    """
    if not _enroll_enabled():
        raise MailchimpDisabledError(
            "Mailchimp enrollment is frozen via RM_MAILCHIMP_ENROLL_ENABLED=false"
        )

    if person.is_suppressed:
        raise ConsentError(f"{person.record_id} is suppressed; refusing to enroll")

    if not person.marketing_consent:
        raise ConsentError(
            f"{person.record_id} has no recorded marketing_consent; refusing to enroll"
        )

    if not person.marketing_audience:
        raise ConsentError(
            f"{person.record_id} has no approved marketing_audience segment; refusing to enroll"
        )

    if not email or "@" not in email:
        raise ConsentError(f"{person.record_id} has no usable email address")

    payload = {
        "email_address": email,
        "status_if_new": "subscribed",
        "merge_fields": {"FNAME": person.name.split(" ")[0] if person.name else ""},
        "tags": [person.marketing_audience],
    }

    if dry_run:
        logger.info("[dry-run] would enroll %s (%s) into %s", person.record_id, email, audience_id)
        return {"dry_run": True, "record_id": person.record_id, "payload": payload}

    api_key, server = _client_config()
    subscriber_hash = _subscriber_hash(email)
    url = (
        f"{MAILCHIMP_API_BASE_TMPL.format(server=server)}"
        f"/lists/{audience_id}/members/{subscriber_hash}"
    )
    resp = requests.put(url, json=payload, auth=("anystring", api_key), timeout=30)
    resp.raise_for_status()
    return resp.json()


def handle_delivery_event(
    attio_client: AttioClient,
    event: dict,
    *,
    dry_run: bool = True,
) -> dict | None:
    """
    Consumes a Mailchimp webhook event (bounce/unsubscribe/complaint/open/
    click) and, for bounce/unsubscribe/complaint, immediately suppresses
    the person in Attio. Expects the caller to have already verified the
    webhook signature (see attio.client.verify_webhook_signature or the
    Mailchimp-specific equivalent) before this is invoked.

    `event` is expected to carry `type` and `data.email` plus, ideally, an
    Attio record id the caller resolved from the email (resolution by
    email lookup is intentionally left to the caller so this stays
    testable without a live Attio query).
    """
    event_type = event.get("type")
    record_id = event.get("attio_record_id")
    if not record_id:
        logger.warning("Delivery event %s has no resolved attio_record_id; skipping", event_type)
        return None

    suppressive_events = {"unsubscribe", "cleaned", "campaign_bounce", "spam_report"}
    if event_type not in suppressive_events:
        # Opens/clicks are just reconciliation signal, not suppression.
        return None

    reason = f"mailchimp:{event_type}"
    return suppress(attio_client, record_id, reason=reason, dry_run=dry_run)
