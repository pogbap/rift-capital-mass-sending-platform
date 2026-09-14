# Attio schema — People object fields

The production Attio workspace already had its own overlapping-but-different
outreach schema. Rather than invent a parallel set of fields, this codebase
was adapted to use the fields that already exist wherever possible, and only
a small number of genuinely missing fields are being added.

Slugs are defined in one place, `src/attio/schema.py`
(`PEOPLE_FIELDS`); rename there if a workspace uses different names.

## Fields that already exist (reused as-is)

| Field | Slug | Type | Purpose |
|---|---|---|---|
| Preferred channel | `preferred_channel` | Select (single): linkedin / whatsapp / telegram / email | Drafting default |
| Outreach stage | `outreach_stage` | Select: new / to_review / approved / visited / invited / connected / messaged / replied / meeting / lost / opted_out | Attio's own post-send relationship funnel — used here only to derive suppression (`lost`, `opted_out`); never repurposed as our approval status |
| Do not contact | `do_not_contact` | Checkbox | Suppression gate for the cadence query and Mailchimp enrollment |
| Consent (dealflow) | `consent_dealflow` | Checkbox | Sourced into `Person.marketing_consent`; required before Mailchimp enrollment |
| Consent date | `consent_date` | Date | Informational, alongside `consent_dealflow` |
| Last outreach at | `last_outreach_at` | Timestamp | Cadence baseline (`Person.last_meaningful_interaction`) |

Not currently used by this codebase, left alone: `signal_source`,
`signal_context`, `signal_date`, `icp_score`, `icp_rationale`,
`personae_type`.

## Fields that are new (created for this workflow)

| Field | Slug | Type | Purpose |
|---|---|---|---|
| Relationship owner | `relationship_owner` | Actor reference (single) | One accountable team member |
| Draft body | `draft_body` | Text (long) | Editable proposed copy |
| Draft evidence | `draft_evidence` | Text (long) | Specific supporting context |
| Review status | `review_status` | Select: `suggested` / `in_review` / `approved` / `sent` / `archived` | **Our own** pre-send draft/approval workflow state. Deliberately a separate field from `outreach_stage` (Attio's post-send relationship funnel) so the two concepts are never confused. |

## Views

- **Review queue**: `review_status = suggested OR in_review`, grouped by
  `relationship_owner`.
- **Approved, awaiting routing**: `review_status = approved`.
- **Suppressed**: `do_not_contact = true OR outreach_stage IN (lost, opted_out)`.

## Permissions

- Only a record's `relationship_owner` (or an admin) may change
  `review_status` to `approved`.
- Field-level write access to `consent_dealflow` and `consent_date` should
  be restricted to marketing operations.
- The service account used by this codebase should have write access only
  to the fields above plus Notes/Activities — not to unrelated People or
  Company fields.

## Environments

Use separate `development`, `staging`, and `production` Attio workspaces
(or clearly isolated objects/views) before enabling production writes.
`src/attio/client.py` reads the workspace token from
`ATTIO_API_TOKEN_<ENV>` where `<ENV>` is `RM_ENV` upper-cased, so
accidentally pointing a dev run at production requires actively setting
`RM_ENV=production`.
