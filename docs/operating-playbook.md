# Operating playbook

## Review and approval

- Every recommendation lands in Attio as `outreach_status = suggested`
  with its evidence attached. Nothing is sent at this stage.
- Only the record's `relationship_owner` may move a record to `approved`.
  A material edit to `Draft body` after approval automatically returns
  the record to `in_review` (enforced in `attio/queries.py`) — re-approval
  is required.
- Social-channel recommendations (LinkedIn/WhatsApp/iMessage) are marked
  `sent` only by the owner, only after they have personally sent the
  message in the native app. There is no automated send path for these
  channels — do not build one.

## Consent and Mailchimp

- A person may be enrolled in Mailchimp only when all of the following are
  true at the same time: `marketing_consent` is recorded with evidence,
  `marketing_audience` names an approved segment, `outreach_eligibility`
  is `eligible`, and there is no `suppression_reason`.
- Consent is never inferred from having an email address, from enrichment
  results, or from a prior reply. It must be an explicit, recorded opt-in.
- Enrollment (`mailchimp/sync.py::enroll`) is idempotent: re-running it
  for the same person and segment is a no-op if they're already enrolled
  and current.
- Bounces, unsubscribes, and spam complaints suppress the person
  immediately across all relevant audiences — this happens automatically
  via `mailchimp/sync.py::handle_delivery_event` and is not something an
  owner needs to remember to do manually.

## Attio Sequences

- Reserved for warm, owner-led, low-volume relationship follow-ups only.
- Never used for commercial marketing, cold outreach, or anything
  high-volume. `attio/queries.py` rejects sequence enrollment above a
  configurable per-run cap (`RM_MAX_SEQUENCE_ENROLLMENTS`, default 25).

## Transactional email

- Triggered only by a real product or operational event (e.g. account
  created, document ready), never by the cadence worker.
- Templates must not contain promotional content unless the recipient
  separately qualifies for that marketing communication under the rules
  above.

## Escalation

- Do-not-contact, unsubscribe, legal-hold, duplicate, and
  sensitive-contact states always override cadence — if any of these are
  set, the person is excluded from `eligible_people()` regardless of how
  overdue their cadence is.
- If enrichment (Unipile) returns an ambiguous match, it must not modify
  the record. It creates an Attio review Note instead, for a human to
  resolve.
- Anything unclear about consent, sensitivity, or ownership should stop
  at `review_required` rather than being guessed.

## Rollout

Follow the phased delivery plan in the handoff: Phase 1 dry-run-only
review queue, Phase 2 one approved Mailchimp audience with reconciliation,
Phase 3 role-based access and reporting. Do not skip phases in production.
