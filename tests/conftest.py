import datetime as dt

import pytest

from src.attio.queries import Person


def make_person(**overrides) -> Person:
    defaults = dict(
        record_id="rec_1",
        name="Jamie Rivera",
        owner="user_1",
        tier="active",
        eligibility="eligible",
        last_meaningful_interaction=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=100),
        outreach_status="none",
        suppression_reason=None,
        marketing_consent=False,
        marketing_audience=None,
        preferred_channel="email",
    )
    defaults.update(overrides)
    return Person(**defaults)


@pytest.fixture
def person_factory():
    return make_person
