# Attio schema — People object additions

Add these fields to the **People** object. Slugs below are the suggested
API slugs used by `src/attio/queries.py`; rename in one place
(`src/attio/schema.py`) if your workspace uses different names.

| Field | Slug | Type | Purpose |
|---|---|---|---|
| Relationship owner | `relationship_owner` | User reference | One accountable team member |
| Relationship tier | `relationship_tier` | Select: strategic / active / nurture / do_not_contact | Cadence + priority |
| Preferred channel | `preferred_channel` | Select: email / linkedin / whatsapp / imessage / unknown | Drafting default |
| Outreach eligibility | `outreach_eligibility` | Select: eligible / review_required / paused / do_not_contact | Gate for the cadence query |
| Last meaningful interaction | `last_meaningful_interaction` | Date-time | Cadence baseline |
| Next outreach date | `next_outreach_date` | Date | Recommendation only, never a send trigger |
| Outreach status | `outreach_status` | Select: none / suggested / in_review / approved / sent / deferred / archived | Workflow state |
| Draft body | `draft_body` | Long text | Editable proposed copy |
| Draft evidence | `draft_evidence` | Long text (or linked Note) | Specific supporting context |
| Approved send channel | `approved_send_channel` | Select | Final human-approved destination |
| Marketing consent | `marketing_consent` | Select/date/source | Required before Mailchimp enrollment |
| Marketing audience / segment | `marketing_audience` | Text | Mailchimp destination, approved by marketing ops |
| Attio sequence ID | `attio_sequence_id` | Text | Optional, low-volume owner-led follow-up only |
| Transactional template ID | `transactional_template_id` | Text | Used only for an approved operational trigger |
| Suppression reason | `suppression_reason` | Long text | Opt-out, conflict, duplicate, sensitivity, other |

## Views

- **Review queue**: `outreach_status = suggested OR in_review`, grouped by
  `relationship_owner`.
- **Approved, awaiting routing**: `outreach_status = approved`.
- **Suppressed**: `outreach_eligibility = do_not_contact OR suppression_reason is not empty`.

## Permissions

- Only a record's `relationship_owner` (or an admin) may change
  `outreach_status` to `approved`.
- Field-level write access to `marketing_consent` and
  `marketing_audience` should be restricted to marketing operations.
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
