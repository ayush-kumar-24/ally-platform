"""The team's own accounts hold every feature -- app/plans/team.py.

The people who build Ally use it on ordinary accounts, mostly Free, so every
gate applied to them as it applies to a founder who has not paid. These pin
the three things that has to mean: the list is matched forgivingly, the tier
is actually written (the scheduled email jobs read the stored value, not a
request-scoped override), and a failure to write costs the founder nothing.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.plans.catalog import Feature, PlanTier
from app.plans.team import TEAM_TIER, ensure_team_plan, is_team_email
from app.plans.service import EntitlementService
from app.plans.usage import InMemoryUsageRepository

TEAM = "info@goxl.in"
OUTSIDER = "someone@example.com"


class FakeFounder:
    def __init__(self, email, plan_type="free", founder_id=1):
        self.email = email
        self.plan_type = plan_type
        self.founder_id = founder_id


class FakeDB:
    def __init__(self, fail=False):
        self.fail = fail
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        if self.fail:
            raise RuntimeError("row-level policy declined the update")
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


# --- who counts as the team ------------------------------------------------

@pytest.mark.parametrize("value", [
    TEAM, TEAM.upper(), f"  {TEAM}  ", "Info@GoXL.in",
])
def test_the_list_is_matched_case_and_whitespace_insensitively(value):
    """Eighteen addresses maintained by hand. A stray capital or a trailing
    space must not quietly cost somebody their access."""
    assert is_team_email(value)


@pytest.mark.parametrize("value", [OUTSIDER, "", None, "  ", "info@goxl.in.attacker.com"])
def test_everyone_else_is_not_the_team(value):
    assert not is_team_email(value)


def test_every_configured_address_resolves():
    """Guards the config itself, not the matcher: a typo that leaves a blank
    entry or a stray comma would silently shorten the list."""
    assert len(settings.team_full_access_emails) == 18
    assert all(e == e.strip().lower() and "@" in e
               for e in settings.team_full_access_emails)


# --- holding the tier ------------------------------------------------------

def test_a_team_account_is_written_to_pro():
    """Written, not computed. send_due_reminders and the notification-email
    sweep run in a scheduled job with no request behind them and read whatever
    is stored, so a request-scoped override would never reach them."""
    db, founder = FakeDB(), FakeFounder(TEAM, plan_type="free")
    assert ensure_team_plan(db, founder) is True
    assert founder.plan_type == TEAM_TIER == PlanTier.PRO.value
    assert db.commits == 1


def test_an_account_already_at_pro_is_not_rewritten():
    """No write, no flush, no log line on every single request."""
    db, founder = FakeDB(), FakeFounder(TEAM, plan_type="pro")
    assert ensure_team_plan(db, founder) is False
    assert db.commits == 0


def test_a_founder_outside_the_list_is_untouched():
    db, founder = FakeDB(), FakeFounder(OUTSIDER, plan_type="free")
    assert ensure_team_plan(db, founder) is False
    assert founder.plan_type == "free"
    assert db.commits == 0


def test_no_founder_at_all_is_not_an_error():
    assert ensure_team_plan(FakeDB(), None) is False


def test_a_failed_write_never_raises_and_rolls_back():
    """This runs on the path that loads the founder for EVERY request. A
    policy that declines the update, or a connection already gone bad, must
    cost the founder nothing more than the access they already had."""
    db, founder = FakeDB(fail=True), FakeFounder(TEAM, plan_type="free")
    assert ensure_team_plan(db, founder) is False
    assert db.rollbacks == 1


# --- what that tier actually buys ------------------------------------------

def test_pro_is_the_whole_feature_set():
    """The reason TEAM_TIER is 'pro' and not a new tier to keep in step."""
    s = EntitlementService(InMemoryUsageRepository())
    for feature in Feature:
        assert s.has_feature(TEAM_TIER, feature), feature


@pytest.mark.parametrize("feature", [
    Feature.VOICE_CHAT, Feature.KNOW_MY_ENERGY, Feature.PRIORITY_CALL,
    Feature.EMAIL_NOTIFICATIONS,
])
def test_the_tier_change_is_what_unlocks_the_gates_free_does_not_have(feature):
    """Free carries a lot during the testing phase, but not these -- which is
    exactly the set a developer testing them would have been blocked on."""
    s = EntitlementService(InMemoryUsageRepository())
    assert s.has_feature(TEAM_TIER, feature)
    if feature is not Feature.EMAIL_NOTIFICATIONS:   # granted to Free for testing
        assert not s.has_feature(PlanTier.FREE, feature)
