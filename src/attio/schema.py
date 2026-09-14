"""
Canonical field slugs for the Attio People object additions.

Kept in one place so docs/attio-schema.md and the code never drift, and so
a workspace using different slugs only needs to edit this file.
"""

PEOPLE_FIELDS = {
    "relationship_owner": "relationship_owner",
    "relationship_tier": "relationship_tier",
    "preferred_channel": "preferred_channel",
    "outreach_eligibility": "outreach_eligibility",
    "last_meaningful_interaction": "last_meaningful_interaction",
    "next_outreach_date": "next_outreach_date",
    "outreach_status": "outreach_status",
    "draft_body": "draft_body",
    "draft_evidence": "draft_evidence",
    "approved_send_channel": "approved_send_channel",
    "marketing_consent": "marketing_consent",
    "marketing_audience": "marketing_audience",
    "attio_sequence_id": "attio_sequence_id",
    "transactional_template_id": "transactional_template_id",
    "suppression_reason": "suppression_reason",
}

RELATIONSHIP_TIERS = ("strategic", "active", "nurture", "do_not_contact")

OUTREACH_ELIGIBILITY = ("eligible", "review_required", "paused", "do_not_contact")

OUTREACH_STATUS = (
    "none",
    "suggested",
    "in_review",
    "approved",
    "sent",
    "deferred",
    "archived",
)

PREFERRED_CHANNELS = ("email", "linkedin", "whatsapp", "imessage", "unknown")

# Statuses that make a record ineligible for a new recommendation because
# one is already in flight.
ACTIVE_DRAFT_STATUSES = ("suggested", "in_review", "approved")

# Cadence baseline in days, overridable per tier.
DEFAULT_CADENCE_DAYS = 60
TIER_CADENCE_OVERRIDES_DAYS = {
    "strategic": 30,
    "active": 45,
    "nurture": 90,
}


def cadence_days_for_tier(tier: str, default: int = DEFAULT_CADENCE_DAYS) -> int:
    return TIER_CADENCE_OVERRIDES_DAYS.get(tier, default)
