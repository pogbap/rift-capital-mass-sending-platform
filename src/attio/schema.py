"""
Canonical field slugs for the Attio People object additions.

Kept in one place so docs/attio-schema.md and the code never drift, and so
a workspace using different slugs only needs to edit this file.

Some of these slugs point at fields that already exist in the production
Attio workspace under names we don't otherwise control (e.g. our
`outreach_status` concept is stored in Attio's `review_status` field, and
our `marketing_consent` concept is stored in Attio's `consent_dealflow`
field). Others (draft_body, draft_evidence, review_status,
relationship_owner) are new fields created specifically for this workflow.
"""

PEOPLE_FIELDS = {
    "relationship_owner": "relationship_owner",
    "preferred_channel": "preferred_channel",
    "last_meaningful_interaction": "last_outreach_at",
    "outreach_status": "review_status",
    "draft_body": "draft_body",
    "draft_evidence": "draft_evidence",
    "marketing_consent": "consent_dealflow",
    "consent_date": "consent_date",
    "do_not_contact": "do_not_contact",
    "outreach_stage": "outreach_stage",
}

# Our own pre-send draft/approval workflow status (Attio slug: review_status).
# Deliberately a separate field/concept from Attio's own `outreach_stage`
# (the post-send relationship funnel), so the two are never conflated.
OUTREACH_STATUS = (
    "suggested",
    "in_review",
    "approved",
    "sent",
    "archived",
)

# Attio's own post-send relationship funnel. Not our approval workflow —
# used only to derive suppression (lost/opted_out) via Person.is_suppressed.
OUTREACH_STAGE_SUPPRESSING = ("lost", "opted_out")

PREFERRED_CHANNELS = ("email", "linkedin", "whatsapp", "telegram")

# Statuses that make a record ineligible for a new recommendation because
# one is already in flight.
ACTIVE_DRAFT_STATUSES = ("suggested", "in_review", "approved")

# Cadence baseline in days. There is no relationship-tier concept anymore;
# every record uses the same flat default.
DEFAULT_CADENCE_DAYS = 60


def cadence_days_for_tier(tier: str | None = None, default: int = DEFAULT_CADENCE_DAYS) -> int:
    """
    No per-tier cadence overrides exist anymore (the relationship-tier
    concept was dropped). Kept as a function, rather than inlining
    DEFAULT_CADENCE_DAYS at every call site, so callers don't need to
    change; it always returns `default`.
    """
    return default
