import pytest

from src.mailchimp.sync import ConsentError, MailchimpDisabledError, enroll, handle_delivery_event


def test_enroll_refuses_without_consent(person_factory):
    person = person_factory(marketing_consent=False)
    with pytest.raises(ConsentError):
        enroll(person, "jamie@example.com", audience_id="abc123", dry_run=True)


def test_enroll_refuses_without_audience_id(person_factory):
    person = person_factory(marketing_consent=True)
    with pytest.raises(ConsentError):
        enroll(person, "jamie@example.com", audience_id="", dry_run=True)


def test_enroll_refuses_suppressed_person(person_factory):
    person = person_factory(
        marketing_consent=True,
        do_not_contact=True,
    )
    with pytest.raises(ConsentError):
        enroll(person, "jamie@example.com", audience_id="abc123", dry_run=True)


def test_enroll_refuses_bad_email(person_factory):
    person = person_factory(marketing_consent=True)
    with pytest.raises(ConsentError):
        enroll(person, "not-an-email", audience_id="abc123", dry_run=True)


def test_enroll_succeeds_dry_run_with_full_consent(person_factory):
    person = person_factory(marketing_consent=True)
    result = enroll(person, "jamie@example.com", audience_id="abc123", dry_run=True)
    assert result["dry_run"] is True
    assert result["payload"]["email_address"] == "jamie@example.com"


def test_enroll_respects_feature_flag(person_factory, monkeypatch):
    monkeypatch.setenv("RM_MAILCHIMP_ENROLL_ENABLED", "false")
    person = person_factory(marketing_consent=True)
    with pytest.raises(MailchimpDisabledError):
        enroll(person, "jamie@example.com", audience_id="abc123", dry_run=True)


def test_bounce_event_triggers_suppression_dry_run():
    event = {"type": "campaign_bounce", "attio_record_id": "rec_1"}
    result = handle_delivery_event(attio_client=None, event=event, dry_run=True)
    assert result["dry_run"] is True
    assert result["attributes"]["do_not_contact"] is True


def test_open_event_does_not_suppress():
    event = {"type": "open", "attio_record_id": "rec_1"}
    result = handle_delivery_event(attio_client=None, event=event, dry_run=True)
    assert result is None


def test_event_without_resolved_record_id_is_skipped():
    event = {"type": "unsubscribe"}
    result = handle_delivery_event(attio_client=None, event=event, dry_run=True)
    assert result is None
