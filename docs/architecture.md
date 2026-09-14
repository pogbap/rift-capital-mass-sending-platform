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
Attio review queue
• Attio list/view initially; dedicated web UI later if needed
• a named owner edits and explicitly approves relationship messages
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
| Native social apps | Final LinkedIn/WhatsApp/iMessage sending | Be automated by this workflow |

## Data flow, step by step

1. `workers/cadence_worker.py` queries Attio for People who have a
   relationship owner, are not suppressed, and have no active
   draft/send in progress (`attio/queries.py::eligible_people`).
2. `recommendations/engine.py::compute_cadence` derives the tier-specific
   cadence baseline (default 60 days) from `Last meaningful interaction`.
3. `recommendations/engine.py::build_recommendation` requires an evidence
   item (prior exchange, meeting, shared project, referral, timely
   reason). No evidence → no draft, only a review Note explaining why.
4. The recommendation (evidence, channel, register, owner) is written to
   Attio in `suggested` status. It is never sent from here.
5. Routing by message class happens at approval time, driven by the
   `Outreach status` transition an owner makes in Attio:
   - `approved` + marketing consent + approved segment → `mailchimp/sync.py`
   - `approved` + warm follow-up → Attio Sequence (owner-led, low volume)
   - product/operational event → `transactional/sender.py`
6. `mailchimp/sync.py::enroll` is idempotent and consent-gated (see
   guardrails in README). It never infers consent from an email address.
7. `mailchimp/sync.py::handle_delivery_event` consumes bounce/unsubscribe/
   complaint webhooks and immediately suppresses the person in Attio
   across all relevant audiences.
8. Social channels are never sent by this system; an owner sends manually
   and calls `attio/queries.py::mark_sent(confirmed_by_owner=True)`.
