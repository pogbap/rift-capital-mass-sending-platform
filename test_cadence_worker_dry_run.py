"""
Dry-run fixture test for the cadence worker's safety gates — does not hit
the network. Full end-to-end worker behaviour (Attio query -> recommendation
-> write) is exercised via unit tests on the underlying functions; this
file checks the go-live gating logic specifically, since that's the
guardrail most worth regression-testing.
"""
from src.workers.cadence_worker import _is_live_allowed


def test_live_requires_env_var_confirmation(monkeypatch):
    monkeypatch.setenv("RM_ENV", "production")
    monkeypatch.delenv("RM_CONFIRM_PRODUCTION", raising=False)
    assert _is_live_allowed(requested_live=True) is False


def test_live_allowed_in_production_with_confirmation(monkeypatch):
    monkeypatch.setenv("RM_ENV", "production")
    monkeypatch.setenv("RM_CONFIRM_PRODUCTION", "yes")
    assert _is_live_allowed(requested_live=True) is True


def test_live_allowed_outside_production_without_confirmation(monkeypatch):
    monkeypatch.setenv("RM_ENV", "staging")
    monkeypatch.delenv("RM_CONFIRM_PRODUCTION", raising=False)
    assert _is_live_allowed(requested_live=True) is True


def test_dry_run_default_when_live_not_requested(monkeypatch):
    monkeypatch.setenv("RM_ENV", "production")
    monkeypatch.setenv("RM_CONFIRM_PRODUCTION", "yes")
    assert _is_live_allowed(requested_live=False) is False
