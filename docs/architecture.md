# Architecture

## Target stack

```text
Attio People / Companies / Deals / Notes / Activities
│
├── team-owned relationship data and permissions
├── inbound and outbound activity sync (where available)
└── optional enrichment: Unipile → Attio (verified fields only)
│
▼
Relationship Manager service
• selects eligible contacts
• applies cadence, ownership, exclusions and suppression rules
• prepares evidence-backed suggested drafts
• writes recommendations and review status back to Attio
│
▼
Review platform (src/review — Flask app, single front door for all sends)
• every drafted message is read, freely rewritten, and channel-picked by a human
• "Send" is the only way a message leaves this system; nothing is ever automatic
• email → dispatched through mailchimp/sync.py, still fully consent-gated
• LinkedIn/WhatsApp/Telegram → owner sends it themselves, then confirms in the app
│
├── consented commercial segment ─► Mailchimp ─► marketing delivery
├── owner-approved warm follow-up ─► Attio Sequences ─► email delivery
├── product/operational event ─────► Transactional provider ─► email
└── approved social ─► copy/open known direct thread ─► human sends
│
▼
Delivery reconciliation
• delivery events and user-confirmed social sends → Attio activity + status
```

## System boundaries

| Layer | Responsibility | Must not do |
|---|---|---|
| Attio | Canonical people, companies, owners, consent/status, relationship context, activity history, review state; low-volume warm sequences | Act as a high-volume marketing ESP |
| Relationship Manager | Recommend contacts, channel and draft; enforce policy and cadence | Invent context, overwrite user copy, select a campaign without approval |
| Unipile (optional) | Enrich a missing, high-confidence LinkedIn/email field | Write ambiguous matches or act as the outreach sender |
| Mailchimp | Deliver permissioned marketing campaigns, manage audience status and unsubscribes | Become the CRM or receive unconsented CRM/enrichment contacts |
| Transactional provider | Deliver one-to-one operational messages from a product or business event | Send promotional marketing to unconsented contacts |
| Native social apps | Final LinkedIn/WhatsApp/Telegram sending | Be automated by this workflow |

## Data flow, step by step

1. `workers/cadence_worker.py` queries Attio for People who have a
   relationship owner, are not suppressed, and have no active
   draft/send in progress (`attio/queries.py::eligible_people`).
2. `recommendations/engine.py::is_due` compares now against `Last outreach
   at` using a flat cadence baseline (`DEFAULT_CADENCE_DAYS`, 60 days) —
   there is no per-tier cadence concept.
3. `recommendations/engine.py::build_recommendation` requires an evidence
   item (prior exchange, meeting, shared project, referral, timely
   reason). No evidence → no draft, only a review Note explaining why.
4. The recommendation (evidence, channel, register, owner) is written to
   Attio in `suggested` status. It is never sent from here.
5. `src/review/app.py` is where a human takes over. It reads every record
   in `suggested`/`in_review`/`approved` status straight from Attio (one
   source of truth, no separate queue database) and presents it for
   editing:
   - **Save edit** rewrites the draft body and/or channel and moves the
     record to `in_review` (`src/review/queue.py::save_draft`).
   - **Approve** marks it `approved` — still not sent
     (`src/review/queue.py::approve`).
   - **Send / mark sent** is the only function in the whole codebase that
     can move a record to `sent`, and it refuses unless the record is
     already `approved`:
     - channel `email` → `src/review/queue.py::send_email`, which is
       still fully gated by `mailchimp/sync.py::enroll`'s consent checks
       and by the same `RM_ENV=production` + `RM_CONFIRM_PRODUCTION=yes`
       gate the cadence worker uses. Outside that, it's a dry-run.
     - channel `linkedin`/`whatsapp`/`telegram` →
       `src/review/queue.py::confirm_manual_send`. This system has no API
       access to those channels and never will; the owner sends the
       (possibly rewritten) message themselves on the channel of their
       choice, then clicks the button to record that they did.
6. `mailchimp/sync.py::handle_delivery_event` consumes bounce/unsubscribe/
   complaint webhooks and immediately suppresses the person in Attio
   across all relevant audiences.
7. `transactional/sender.py` remains a separate, non-cadence path for
   one-to-one operational events (account created, document ready, etc.)
   — it is never reachable from the review queue.

## Setup note: custom fields required in Attio

Investigation of the real Rift Capital workspace (2026-09-14) found that it
already has its own overlapping outreach schema — `preferred_channel`,
`outreach_stage`, `do_not_contact`, `consent_dealflow`, `consent_date`, and
`last_outreach_at` all already exist and this codebase now reads/writes
them directly (see `docs/attio-schema.md`). Only four fields are genuinely
missing and need to be created on the People object before the worker and
review app can find or queue any records:

- `relationship_owner` (actor reference, single)
- `draft_body` (text, long)
- `draft_evidence` (text, long)
- `review_status` (select: suggested / in_review / approved / sent / archived)

Until these four exist, `eligible_people()` and `list_queue()` will
correctly return zero records rather than fail loudly.
