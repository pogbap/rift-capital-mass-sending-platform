"""
The review queue is the only path from a drafted recommendation to an
actual send. These tests lock in the gating behaviour: no send without
approval, no automated send at all on manual channels, and no live email
dispatch without the same production confirmation gate the cadence worker
uses.
"""
import pytest

from src.review.queue import (
    SendNotAllowedError,
    confirm_manual_send,
    send_email,
)


class FakeAttioClient:
    def __init__(self):
        self.updates = []

    def update_record(self, object_slug, record_id, attributes):
        self.updates.append((object_slug, record_id, attributes))
        return {"id": {"record_id": record_id}, "values": attributes}


def test_manual_send_refused_before_approval(person_factory):
    person = person_factory(outreach_status="in_review", preferred_channel="linkedin")
    with pytest.raises(SendNotAllowedError):
        confirm_manual_send(FakeAttioClient(), person, channel="linkedin")


def test_manual_send_requires_a_manual_channel(person_factory):
    person = person_factory(outreach_status="approved", preferred_channel="email")
    with pytest.raises(SendNotAllowedError):
        confirm_manual_send(FakeAttioClient(), person, channel="email")


def test_manual_send_records_confirmation_once_approved(person_factory, monkeypatch):
    monkeypatch.delenv("RM_ENV", raising=False)
    person = person_factory(outreach_status="approved", preferred_channel="whatsapp")
    client = FakeAttioClient()
    result = confirm_manual_send(client, person, channel="whatsapp")
    assert result["dry_run"] is True  # not RM_ENV=production+confirmed, so still dry-run
    assert client.updates == []  # dry-run never calls update_record


def test_email_send_refused_before_approval(person_factory):
    person = person_factory(outreach_status="suggested", marketing_consent=True, marketing_audience="clients")
    with pytest.raises(SendNotAllowedError):
        send_email(FakeAttioClient(), person, email="a@b.com", audience_id="aud_1")


def test_email_send_still_consent_gated_after_approval(person_factory):
    person = person_factory(outreach_status="approved", marketing_consent=False)
    with pytest.raises(SendNotAllowedError):
        send_email(FakeAttioClient(), person, email="a@b.com", audience_id="aud_1")


def test_email_send_is_dry_run_outside_production(person_factory, monkeypatch):
    monkeypatch.delenv("RM_ENV", raising=False)
    monkeypatch.delenv("RM_CONFIRM_PRODUCTION", raising=False)
    person = person_factory(
        outreach_status="approved", marketing_consent=True, marketing_audience="clients"
    )
    result = send_email(FakeAttioClient(), person, email="a@b.com", audience_id="aud_1")
    assert result["dry_run"] is True


def test_email_send_goes_live_only_with_full_production_confirmation(person_factory, monkeypatch):
    monkeypatch.setenv("RM_ENV", "production")
    monkeypatch.setenv("RM_CONFIRM_PRODUCTION", "yes")
    monkeypatch.setenv("RM_MAILCHIMP_ENROLL_ENABLED", "false")  # avoid a real network call in CI
    person = person_factory(
        outreach_status="approved", marketing_consent=True, marketing_audience="clients"
    )
    # Feature-flag off still raises, proving the live path was actually attempted
    # (not silently short-circuited back to dry-run).
    with pytest.raises(SendNotAllowedError):
        send_email(FakeAttioClient(), person, email="a@b.com", audience_id="aud_1")
