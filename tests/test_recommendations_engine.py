import datetime as dt

from src.recommendations.engine import Evidence, build_recommendation, is_due


def test_suppressed_person_never_gets_a_recommendation(person_factory):
    person = person_factory(suppression_reason="unsubscribed")
    rec = build_recommendation(person, Evidence("meeting", "coffee last week"))
    assert not rec.is_actionable
    assert rec.reason_skipped == "suppressed_or_do_not_contact"


def test_do_not_contact_eligibility_is_never_recommended(person_factory):
    person = person_factory(eligibility="do_not_contact")
    rec = build_recommendation(person, Evidence("meeting", "coffee last week"))
    assert not rec.is_actionable
    assert rec.reason_skipped == "suppressed_or_do_not_contact"


def test_not_due_person_is_skipped(person_factory):
    person = person_factory(
        last_meaningful_interaction=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=5),
        tier="active",
    )
    rec = build_recommendation(person, Evidence("meeting", "coffee last week"))
    assert not rec.is_actionable
    assert rec.reason_skipped == "not_due"


def test_no_evidence_means_no_draft(person_factory):
    person = person_factory()
    rec = build_recommendation(person, evidence=None)
    assert not rec.is_actionable
    assert rec.reason_skipped == "no_evidence"


def test_empty_evidence_description_is_invalid(person_factory):
    person = person_factory()
    rec = build_recommendation(person, Evidence("meeting", "   "))
    assert not rec.is_actionable
    assert rec.reason_skipped == "no_evidence"


def test_valid_evidence_and_due_produces_actionable_recommendation(person_factory):
    person = person_factory()
    evidence = Evidence("prior_exchange", "discussed the Q3 fund update over email")
    rec = build_recommendation(person, evidence)
    assert rec.is_actionable
    assert "Jamie" in rec.draft_body
    assert "Q3 fund update" in rec.draft_body
    assert rec.channel == "email"


def test_unknown_preferred_channel_defaults_to_email(person_factory):
    person = person_factory(preferred_channel="unknown")
    evidence = Evidence("referral", "introduced by a mutual contact")
    rec = build_recommendation(person, evidence)
    assert rec.channel == "email"


def test_tier_cadence_override_strategic_is_shorter():
    from src.attio.schema import cadence_days_for_tier

    assert cadence_days_for_tier("strategic") < cadence_days_for_tier("nurture")


def test_is_due_true_when_never_interacted(person_factory):
    person = person_factory(last_meaningful_interaction=None)
    assert is_due(person) is True
