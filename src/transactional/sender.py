"""
Transactional email: one-to-one operational messages triggered only by a
real product or business event (account created, document ready, etc.),
never by the cadence worker and never containing promotional content
unless the recipient separately qualifies for that marketing
communication under the consent rules in mailchimp/sync.py.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

# Templates are pre-approved outside this codebase (with marketing ops
# sign-off recorded per docs/operating-playbook.md); this module only
# ever references a template_id, never constructs promotional copy.
APPROVED_TRANSACTIONAL_EVENTS = {
    "account_created",
    "document_ready",
    "meeting_confirmed",
    "password_reset",
}


class UnapprovedEventError(ValueError):
    pass


def send_transactional(
    *,
    event_type: str,
    to_email: str,
    template_id: str,
    merge_vars: dict | None = None,
    dry_run: bool = True,
) -> dict:
    if event_type not in APPROVED_TRANSACTIONAL_EVENTS:
        raise UnapprovedEventError(
            f"'{event_type}' is not an approved transactional trigger. "
            f"Add it to APPROVED_TRANSACTIONAL_EVENTS only after operational "
            f"sign-off — do not use this path for marketing."
        )

    payload = {
        "to": to_email,
        "template_id": template_id,
        "merge_vars": merge_vars or {},
    }

    if dry_run:
        logger.info("[dry-run] would send transactional email: %s", payload)
        return {"dry_run": True, "payload": payload}

    api_key = os.environ.get("TRANSACTIONAL_API_KEY", "")
    provider = os.environ.get("TRANSACTIONAL_PROVIDER", "")
    if not api_key or not provider:
        raise RuntimeError("TRANSACTIONAL_API_KEY and TRANSACTIONAL_PROVIDER must be set")

    # Provider-specific request construction lives behind this single call
    # site so swapping providers doesn't touch calling code.
    resp = requests.post(
        f"https://api.{provider}.com/v1/send",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
