import pytest

from src.transactional.sender import UnapprovedEventError, send_transactional


def test_unapproved_event_type_is_rejected():
    with pytest.raises(UnapprovedEventError):
        send_transactional(
            event_type="black_friday_blast",
            to_email="jamie@example.com",
            template_id="tmpl_1",
            dry_run=True,
        )


def test_approved_event_dry_run_succeeds():
    result = send_transactional(
        event_type="account_created",
        to_email="jamie@example.com",
        template_id="tmpl_1",
        dry_run=True,
    )
    assert result["dry_run"] is True
    assert result["payload"]["to"] == "jamie@example.com"
