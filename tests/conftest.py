import datetime as dt

import pytest

from src.attio.queries import Person


def make_person(**overrides) -> Person:
    defaults = dict(
        record_id="rec_1",
        name="Jamie Rivera",
        owner="user_1",
        do_not_contact=False,
        outreach_stage="new",
        last_meaningful_interaction=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=100),
        outreach_status="suggested",
        marketing_consent=False,
        preferred_channel="email",
    )
    defaults.update(overrides)
    return Person(**defaults)


@pytest.fixture
def person_factory():
    return make_person
