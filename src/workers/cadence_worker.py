"""
Scheduled job: scans Attio for eligible People, builds evidence-backed
recommendations, and writes them back as `suggested`. Never sends
anything and never touches Mailchimp/Sequences/transactional directly —
those are triggered later, by an owner's approval.

Usage:
    python -m src.workers.cadence_worker --dry-run
    RM_ENV=production RM_CONFIRM_PRODUCTION=yes \
        python -m src.workers.cadence_worker --live
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from src.attio.client import AttioClient
from src.attio.queries import eligible_people, write_recommendation
from src.recommendations.engine import Evidence, build_recommendation

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _is_live_allowed(requested_live: bool) -> bool:
    if not requested_live:
        return False
    env = os.environ.get("RM_ENV", "development").strip().lower()
    confirmed = os.environ.get("RM_CONFIRM_PRODUCTION", "").strip().lower() == "yes"
    if env == "production" and not confirmed:
        logger.warning(
            "RM_ENV=production but RM_CONFIRM_PRODUCTION is not 'yes' — "
            "forcing dry-run for safety."
        )
        return False
    return True


def run(dry_run: bool = True, default_cadence_days: int = 60) -> list[dict]:
    client = AttioClient()
    people = eligible_people(client)
    logger.info("Found %d eligible people in %s", len(people), client.env)

    results = []
    for person in people:
        # In a full implementation, evidence is sourced from synced
        # activity/notes (Attio Notes, calendar sync, etc.). This worker
        # takes evidence via a pluggable lookup so it stays testable; see
        # tests/fixtures for how evidence is supplied in dry-run tests.
        evidence = _lookup_evidence(person)
        rec = build_recommendation(person, evidence, default_cadence_days=default_cadence_days)

        if not rec.is_actionable:
            logger.info("Skipping %s: %s", person.record_id, rec.reason_skipped)
            continue

        result = write_recommendation(
            client,
            person,
            evidence=rec.evidence.description,
            channel=rec.channel,
            draft_body=rec.draft_body,
            dry_run=dry_run,
        )
        results.append(result)

    logger.info("Wrote %d recommendation(s) (dry_run=%s)", len(results), dry_run)
    return results


def _lookup_evidence(person) -> Evidence | None:
    """
    Placeholder evidence source. Wire this to Attio Notes/Activities (or a
    synced calendar/email source) before enabling --live in production —
    without it every record will correctly be skipped as no_evidence,
    which is the safe default, not a bug.
    """
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    live_allowed = _is_live_allowed(args.live)
    run(dry_run=not live_allowed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
