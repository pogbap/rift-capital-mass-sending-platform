# Relationship Manager — Attio Edition

Team-owned relationship outreach system. **Attio is the system of record.**
This service reads eligible People from Attio, proposes evidence-backed
outreach drafts, and writes recommendations back to Attio for a named owner
to review and approve. Nothing is sent automatically.

- **Mailchimp** delivers permissioned commercial marketing only, and only
  after recorded consent + an approved audience/segment.
- **Attio Sequences** handles low-volume, owner-led warm follow-ups.
- **Transactional provider** sends operational email triggered by product
  events, never promotional content.
- **LinkedIn / WhatsApp / iMessage** stay manual, human sends. The owner
  marks a recommendation `sent` after confirming it themselves.

See `docs/architecture.md` for the full target stack and system boundaries,
and `docs/operating-playbook.md` for review/consent/escalation rules before
turning anything on in production.

## Why this exists

This replaces a personal, single-user relationship-manager workflow with a
team-safe version: Attio holds ownership, consent, suppression and review
state so no message goes out without a human approving it, and so consent
and do-not-contact rules are enforced in one place instead of per-channel.

## Quick start

```bash
cp .env.example .env        # fill in real values in your secret manager, not here
pip install -r requirements.txt
pytest                      # unit + schema-contract + dry-run fixture tests

# Dry run only — never writes to Mailchimp/Attio outreach fields for real
python -m src.workers.cadence_worker --dry-run
```

Production writes require `--live` **and** `RM_ENV=production` **and** a
non-empty `RM_CONFIRM_PRODUCTION=yes`. This is intentional friction — see
`docs/runbook.md`.

## Project layout

```text
src/
├── attio/            # REST client, queries, webhook validation
├── recommendations/  # eligibility, cadence, evidence, drafting interface
├── mailchimp/         # consent-gated audience sync + delivery-event intake
├── transactional/     # event-triggered operational email interface
└── workers/           # scheduled jobs (cadence scan, reconciliation)
tests/                 # unit, schema-contract, dry-run fixture tests
docs/                  # architecture, Attio schema, playbook, runbook
```

## Non-negotiable guardrails (enforced in code, not just policy)

1. No bulk enrollment from a cadence query — Mailchimp writes are one
   person at a time, each independently consent-checked.
2. No automatic social outreach — there is no "send" function for
   LinkedIn/WhatsApp/iMessage, only a `mark_sent(confirmed_by_owner=True)`.
3. No Mailchimp enrollment without recorded marketing consent, an approved
   audience/segment, and non-suppressed status (`mailchimp/sync.py`).
4. No Attio Sequence use for cold or high-volume sends — the client caps
   sequence enrollment volume and rejects unapproved sequence IDs.
5. Do-not-contact/suppression always wins over cadence, checked first in
   `recommendations/engine.py`.
6. A draft requires an evidence item; the engine will not produce a draft
   without one.
7. Editing `Draft body` after approval returns the record to `in review`
   (enforced in `attio/queries.py::write_recommendation`).
8. Secrets are read from environment variables only; `.env.example` holds
   names, not values, and nothing here writes secrets into Attio fields,
   logs, or source control.
