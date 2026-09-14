# Team Relationship Manager — Attio Handoff

## Outcome

This is the team-ready version of the personal relationship manager. It keeps
the useful part of the original system—prioritising authentic, timely
one-to-one outreach—but replaces the personal Obsidian contact universe with
**Attio** as the shared system of record.

**Mailchimp is the final sending platform for permissioned commercial email.**
It is not a source of truth and must not choose recipients or create its own
audience. Attio Sequences handles low-volume, owner-led relationship
follow-ups. Transactional emails use Mailchimp Transactional (or an approved
equivalent) and are triggered only by a product or operational event.
LinkedIn, WhatsApp, and iMessage remain manual sends in their native
applications.

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

## Attio data model

Keep existing native Attio fields where possible. Add the following fields to
the **People** object (names can be adapted to the workspace convention):

| Field | Type | Purpose |
|---|---|---|
| Relationship owner | User/reference | One accountable team member |
| Relationship tier | Select | Strategic / active / nurture / do-not-contact |
| Preferred channel | Select | Email / LinkedIn / WhatsApp / iMessage / unknown |
| Outreach eligibility | Select | Eligible / review required / paused / do-not-contact |
| Last meaningful interaction | Date-time | Cadence baseline; derived from synced or confirmed activity |
| Next outreach date | Date | Recommendation only, never an automatic send trigger |
| Outreach status | Select | None / suggested / in review / approved / sent / deferred / archived |
| Draft body | Long text | Editable proposed copy |
| Draft evidence | Long text or linked Note | Specific conversation, meeting, or shared context supporting the draft |
| Approved send channel | Select | Final human-approved destination |
| Marketing consent | Select/date/source | Required before Mailchimp enrollment; retain consent evidence |
| Marketing audience / segment | Text | Mailchimp destination, approved by marketing operations |
| Attio sequence ID | Text | Optional; for a low-volume owner-led warm follow-up |
| Transactional template ID | Text | Used only for an approved operational trigger |
| Suppression reason | Long text | Opt-out, conflict, duplicate, sensitivity, or other exclusion |

Use Attio Notes/Activities for durable rationale and message history. Avoid
putting private conversation exports or credentials into GitHub.

## Core workflow

1. Attio is the input. Query only eligible People with a relationship owner,
   no suppression, and no active draft/send already in progress.
2. Calculate cadence from the last *meaningful* interaction. A starting point
   is 60 days, with per-tier overrides set by the team.
3. Require an evidence item before a draft is created: a known prior exchange,
   meeting, shared project, referral, or a real timely reason to write.
4. Write a recommendation to Attio with its evidence, recommended channel,
   language/register, and owner. Do not send it.
5. Route the record by message class:
   - permissioned commercial marketing → approved Mailchimp audience/segment;
   - warm, owner-led relationship follow-up → Attio Sequence; or
   - product/operational event → transactional provider.
6. An Attio workflow may add a person to Mailchimp only when marketing consent,
   consent evidence, eligibility, and the approved audience/segment are all
   present. It must be idempotent and must never infer consent from an email
   address or enrichment result.
7. Only a named owner may approve a warm relationship follow-up. Attio
   Sequences are for this low-volume use only—not commercial marketing or cold,
   high-volume prospecting.
8. Consume campaign delivery, bounce, unsubscribe, and complaint events and
   write the outcome to Attio. A bounced, unsubscribed, or complained-about
   person is immediately suppressed across all relevant audiences.
9. For social channels, the owner sends manually in the known direct thread
   and marks the Attio recommendation `sent` only after confirming the send.

## Guardrails

- No bulk enrollment from a cadence query.
- No automatic social outreach.
- No Mailchimp enrollment without recorded, verifiable marketing permission,
  an approved audience/segment, and an active non-suppressed status.
- No Attio Sequence for commercial marketing, cold outreach, or high-volume
  sends; it is reserved for warm, owner-led relationship follow-ups.
- No transactional template may contain promotional content unless the
  recipient separately qualifies for that marketing communication.
- Do-not-contact, unsubscribe, legal-hold, duplicate, and sensitive-contact
  states always win over cadence.
- Preserve the exact approved draft; a material edit returns it to review.
- Store API keys only in the deployment secret manager/environment—not in
  Attio fields, logs, source control, or tickets.
- Enrichment may fill missing fields only at high confidence. Ambiguous
  matches create an Attio review Note rather than changing the record.

## GitHub package

Publish a new repository without personal data or source exports:

```text
relationship-manager-attio/
├── README.md                 # product overview and local setup
├── docs/
│   ├── architecture.md       # this target stack and boundaries
│   ├── attio-schema.md       # field IDs, views, and permissions
│   ├── operating-playbook.md # review, copy, consent and escalation rules
│   └── runbook.md            # deploy, rollback, incident and reconciliation
├── src/
│   ├── attio/                # queries, writes and webhook validation
│   ├── recommendations/      # eligibility, cadence and drafting interface
│   ├── mailchimp/            # consent-gated audience sync and event intake
│   ├── transactional/        # event-triggered operational email interface
│   └── workers/              # scheduled jobs
├── tests/
├── .env.example              # variable names only; no values
└── .github/workflows/ci.yml
```

Use separate `development`, `staging`, and `production` Attio workspaces (or
clearly isolated objects/views) before enabling production writes. CI should
run unit tests, schema-contract tests, and a dry-run against fixtures; it must
never use production tokens.

## Existing reusable foundation

`Downloads/attio_unipile_enrichment/` already contains a small Attio + Unipile
enrichment implementation and a legacy, intentionally guarded Lemlist
handoff. The Lemlist code is not part of this target architecture; the project
is useful as a reference for:

- Attio REST client patterns;
- high-confidence-only enrichment and review Notes for uncertain matches;
- paced Unipile access; and
- explicit confirmation gates before any external write.

Move only the generic code and tests into the new repository after a secrets
and personal-data review. Do not publish its local logs, `.env` files, account
IDs, or any contact records.

## Delivery plan

**Phase 1 — Attio-first review queue:** define the fields and views, import or
sync the authorised team contact set, establish owner/suppression rules, and
run recommendations as dry-run only.

**Phase 2 — permissioned commercial email:** connect Mailchimp, map consent
and suppression fields, launch one approved audience/segment, and reconcile
delivery events back into Attio. Keep an audit log.

**Phase 3 — team operation:** add role-based access, reporting, SLAs for
review, and carefully scoped enrichment. A dedicated review UI is optional;
Attio can remain the operator surface if it supports the required approval
state and audit trail.

## Open decisions for the team

- Which Attio workspace/object and fields are authoritative?
- Who may approve email sends, and who may create/edit drafts?
- Which Mailchimp audiences, sending domains, preference centre, and consent
  rules are approved?
- Which transactional provider and templates are approved for operational
  email?
- What counts as a meaningful interaction for each relationship tier?
- Do you need per-company, per-person, or per-domain frequency caps beyond the
  sending platform's safeguards?
- Which sources may sync interaction history into Attio, and what retention
  policy applies?
