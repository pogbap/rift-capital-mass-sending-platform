"""
Eligibility, cadence and drafting logic. This module decides WHO gets a
recommendation and WHETHER there's enough evidence to draft one — it does
not send anything, and it does not pick a Mailchimp/Sequence/transactional
route (that happens later, at approval time, driven by the owner).
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from src.attio.queries import Person
from src.attio.schema import cadence_days_for_tier

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """A concrete, specific reason to reach out. No evidence, no draft."""
    kind: str  # prior_exchange | meeting | shared_project | referral | timely_reason
    description: str

    def is_valid(self) -> bool:
        return bool(self.description and self.description.strip()) and self.kind in (
            "prior_exchange",
            "meeting",
            "shared_project",
            "referral",
            "timely_reason",
        )


@dataclass
class Recommendation:
    person: Person
    evidence: Evidence
    channel: str
    draft_body: str
    reason_skipped: str | None = None

    @property
    def is_actionable(self) -> bool:
        return self.reason_skipped is None


def is_due(person: Person, *, now: dt.datetime | None = None, default_days: int = 60) -> bool:
    now = now or dt.datetime.now(dt.timezone.utc)
    if person.last_meaningful_interaction is None:
        # Never interacted meaningfully — treat as due, but this is exactly
        # the kind of record that should also be checked for evidence
        # before a draft is actually produced.
        return True
    days = cadence_days_for_tier(person.tier or "", default_days)
    elapsed = (now - person.last_meaningful_interaction).days
    return elapsed >= days


def build_recommendation(
    person: Person,
    evidence: Evidence | None,
    *,
    now: dt.datetime | None = None,
    default_cadence_days: int = 60,
) -> Recommendation:
    """
    Pure function: given a person and a candidate evidence item, decide
    whether a recommendation can be produced. Never touches the network.
    """
    if person.is_suppressed:
        return Recommendation(
            person=person,
            evidence=evidence or Evidence("timely_reason", ""),
            channel=person.preferred_channel or "unknown",
            draft_body="",
            reason_skipped="suppressed_or_do_not_contact",
        )

    if not is_due(person, now=now, default_days=default_cadence_days):
        return Recommendation(
            person=person,
            evidence=evidence or Evidence("timely_reason", ""),
            channel=person.preferred_channel or "unknown",
            draft_body="",
            reason_skipped="not_due",
        )

    if evidence is None or not evidence.is_valid():
        return Recommendation(
            person=person,
            evidence=evidence or Evidence("timely_reason", ""),
            channel=person.preferred_channel or "unknown",
            draft_body="",
            reason_skipped="no_evidence",
        )

    channel = person.preferred_channel if person.preferred_channel not in (None, "unknown") else "email"
    draft_body = draft_from_evidence(person, evidence, channel)

    return Recommendation(
        person=person,
        evidence=evidence,
        channel=channel,
        draft_body=draft_body,
    )


def draft_from_evidence(person: Person, evidence: Evidence, channel: str) -> str:
    """
    Produces a short, evidence-grounded draft skeleton for the owner to
    edit. This is deliberately plain and un-promotional — it is a
    relationship note, not a marketing message, and the owner is expected
    to personalize it before approving.
    """
    opener = {
        "prior_exchange": f"Following up on our last exchange — {evidence.description}.",
        "meeting": f"It was great catching up — {evidence.description}.",
        "shared_project": f"Thinking of you given {evidence.description}.",
        "referral": f"Wanted to reconnect — {evidence.description}.",
        "timely_reason": f"{evidence.description}",
    }.get(evidence.kind, evidence.description)

    name = person.name.split(" ")[0] if person.name and person.name != "(unnamed)" else "there"
    return (
        f"Hi {name},\n\n"
        f"{opener}\n\n"
        f"[Owner: personalize before approving — this draft is generated "
        f"from recorded evidence only and has not been sent.]\n"
    )
