# Runbook

## Deploy

1. Provision separate Attio workspaces/views for `development`, `staging`,
   `production` (see `docs/attio-schema.md`).
2. Set environment variables (see `.env.example`) in your deployment
   secret manager. Never put real values in `.env` inside source control.
3. Run `pytest` — unit tests, schema-contract tests against the field list
   in `src/attio/schema.py`, and a dry-run against `tests/fixtures/`.
4. Deploy `src/workers/cadence_worker.py` as a scheduled job (e.g. daily).
   Start in `--dry-run` mode in every environment, including production,
   for at least one full review cycle before flipping to `--live`.

## Going live

Production writes require all three:

```bash
RM_ENV=production
RM_CONFIRM_PRODUCTION=yes
python -m src.workers.cadence_worker --live
```

Missing any one of these causes the worker to run in dry-run mode and log
a warning rather than fail silently.

## Rollback

- The worker only ever writes `suggested`-status recommendations and
  suppression/consent updates — it does not delete Attio records. To roll
  back a bad batch, filter Attio by the run's `Draft evidence` timestamp
  tag and bulk-reset `Outreach status` to `none`.
- Mailchimp enrollments are additive and idempotent; to undo an
  incorrect enrollment, remove the person from the Mailchimp audience
  directly (Mailchimp is the delivery system, not the record of truth —
  removing them there does not affect Attio, so also clear
  `marketing_audience` in Attio if the enrollment was a mistake).

## Incident response

- **Send went out that shouldn't have**: this system never sends
  directly — a bad send means either Mailchimp campaign configuration or
  an owner approval error. Check Mailchimp campaign audience/segment
  first, then the Attio approval history on the record.
- **Consent gate bypassed**: treat as a data-integrity incident. Freeze
  `mailchimp/sync.py::enroll` (feature flag `RM_MAILCHIMP_ENROLL_ENABLED`),
  audit recent enrollments against `marketing_consent` evidence, and fix
  forward before re-enabling.
- **Attio API errors / rate limits**: `attio/client.py` retries with
  exponential backoff and gives up after `RM_MAX_RETRIES` (default 5),
  logging the failed record IDs for manual review rather than silently
  dropping them.

## Reconciliation

- `mailchimp/sync.py::handle_delivery_event` should be wired to
  Mailchimp's webhook (bounce/unsubscribe/complaint/open/click) and run
  as its own small service or scheduled poll, writing outcomes back to
  Attio activity history.
- Reconcile daily: count of `sent` in Attio vs. delivered/bounced in
  Mailchimp should match; alert on drift beyond a small tolerance.
