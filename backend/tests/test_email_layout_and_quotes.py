"""The branded email shell and the quote it carries.

Ally's emails were unstyled paragraphs -- no logo, no identity, a default-blue
link -- because each of twelve senders wrote its own markup. These cover the
shared shell that replaces that, and the quote rule the founders asked for:
a motivational line that differs from person to person.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.emails.layout import TONES, render
from app.emails.quotes import QUOTES, TOTAL, Quote, quote_for, slot_for

NOON = datetime(2026, 9, 15, 13, 0)


# --- the quote set ---------------------------------------------------------

def test_there_are_fifty_quotes():
    assert TOTAL == 50
    assert sum(len(g) for g in QUOTES.values()) == 50


def test_every_group_has_enough_to_not_repeat_quickly():
    """A founder can get two emails a day. A group of three would repeat
    inside a week and read as a template."""
    for slot, group in QUOTES.items():
        assert len(group) >= 12, f"{slot} has only {len(group)}"


def test_no_quote_appears_twice():
    """Across the whole set, not just within a group -- a line that shows up in
    both morning and evening halves its own odds of feeling fresh."""
    texts = [q.text for group in QUOTES.values() for q in group]
    assert len(texts) == len(set(texts))


def test_no_quote_is_blank():
    for group in QUOTES.values():
        for q in group:
            assert q.text.strip()


@pytest.mark.parametrize("hour,expected", [
    (0, "night"), (4, "night"), (5, "morning"), (11, "morning"),
    (12, "afternoon"), (17, "afternoon"), (18, "evening"), (21, "evening"),
    (22, "night"), (23, "night"),
])
def test_the_slot_boundaries_match_the_frontends(hour, expected):
    """Shared with the dashboard card's timeSlot(), so a founder who sees both
    in the same hour is not told two different times of day."""
    assert slot_for(datetime(2026, 9, 15, hour, 30)) == expected


# --- picking one ------------------------------------------------------------

def test_two_founders_get_different_quotes():
    """The actual request: 'random to each person, not same'."""
    picked = {quote_for(founder_id=i, moment=NOON, kind="task_reminder").text
              for i in range(1, 30)}
    assert len(picked) > 1


def test_the_same_founder_gets_a_stable_answer():
    """Deterministic, so a test can assert it and so one founder is never
    handed the same line twice by accident."""
    a = quote_for(founder_id=42, moment=NOON, kind="task_reminder")
    b = quote_for(founder_id=42, moment=NOON, kind="task_reminder")
    assert a == b


def test_the_two_emails_for_one_task_never_carry_the_same_line():
    """The confirmation and the reminder land on the same day for the same
    founder, and a repeat across them reads like a template rather than a note.

    `kind` alone only makes a clash unlikely -- thirteen lines in a group means
    two independent hashes collide about once in thirteen, which is often
    enough to be seen. avoid_kinds makes it impossible, and this walks 500
    founders rather than one so a lucky seed cannot make it pass."""
    for founder_id in range(1, 501):
        scheduled = quote_for(founder_id=founder_id, moment=NOON,
                              kind="task_scheduled")
        reminder = quote_for(founder_id=founder_id, moment=NOON,
                             kind="task_reminder",
                             avoid_kinds=("task_scheduled",))
        assert scheduled.text != reminder.text, f"clash for founder {founder_id}"


def test_avoiding_everything_still_returns_a_quote():
    """A group smaller than the avoid list would leave nothing to pick. An
    email with no quote is worse than a repeated one."""
    every_kind = tuple(f"k{i}" for i in range(80))
    assert quote_for(founder_id=1, moment=NOON, kind="x",
                     avoid_kinds=every_kind).text


def test_the_quote_suits_the_hour():
    night = quote_for(founder_id=1, moment=datetime(2026, 9, 15, 23, 30), kind="x")
    assert night in QUOTES["night"]
    morning = quote_for(founder_id=1, moment=datetime(2026, 9, 15, 8, 0), kind="x")
    assert morning in QUOTES["morning"]


def test_an_unknown_founder_still_gets_a_quote():
    """founder_id is None on any path that has no founder row to hand."""
    assert quote_for(founder_id=None, moment=NOON, kind="x").text


# --- the shell --------------------------------------------------------------

def _render(**over):
    args = dict(
        kicker="Due in 5 minutes", heading="Starting soon.",
        lede="This is the nudge you asked for.",
        cta_label="Open Plan Your Day", cta_url="https://app.goxlally.ai/app/plan",
        footer_note="Turn these off in Profile > Notifications.",
        panel_label="Tuesday, 15 September at 03:39 PM", panel_value="reminder test 2",
        body_line="Tick it off when it is done.",
        quote=Quote("Close the loop on one thing before you open another."),
    )
    args.update(over)
    return render(**args)


def test_the_logo_is_a_hosted_url():
    """Not a data: URI (Gmail blocks those) and not an attachment (that would
    make every sender build a multipart message)."""
    assert settings.EMAIL_LOGO_URL.startswith("https://")
    assert settings.EMAIL_LOGO_URL in _render().html


def test_the_header_survives_a_client_that_blocks_images():
    """Which is the default in Gmail and Outlook. The word Ally has to be
    readable on the green band without the mark loading."""
    html = _render().html
    assert 'alt="Ally"' in html


def test_founder_typed_content_is_escaped():
    """A task title is whatever the founder typed. An ampersand in it must not
    break the markup of their own reminder."""
    html = _render(panel_value='Pricing & "positioning" <review>').html
    assert "&amp;" in html and "&lt;review&gt;" in html
    assert "<review>" not in html


def test_the_quote_reaches_both_halves():
    """A text-only client gets the whole email, not a degraded one."""
    line = "Close the loop on one thing before you open another."
    out = _render()
    assert line in out.html and line in out.text


def test_an_attribution_shows_when_there_is_one():
    out = _render(quote=Quote("Make something people want.", "Paul Graham"))
    assert "Paul Graham" in out.html and "Paul Graham" in out.text


def test_the_plain_text_twin_carries_the_link_as_a_link():
    """There is no anchor to click in text/plain -- the URL has to be spelled
    out or the CTA is dead for that reader."""
    assert "https://app.goxlally.ai/app/plan" in _render().text


@pytest.mark.parametrize("tone", list(TONES))
def test_each_tone_paints_its_kicker(tone):
    bg, fg = TONES[tone]
    html = _render(tone=tone).html
    assert bg in html and fg in html


def test_an_unknown_tone_falls_back_rather_than_raising():
    """A new sender passing a tone nobody added must still send an email."""
    assert _render(tone="carnival").html


def test_the_optional_blocks_vanish_cleanly():
    out = _render(panel_value="", panel_label="", panel_sub="", body_line="",
                  quote=None, greeting="")
    assert "While you" not in out.html          # no empty quote rule
    assert out.html.count("<table") >= 3        # shell still intact
    assert "Open Plan Your Day" in out.text


def test_it_is_tables_and_inline_styles():
    """Gmail strips <style> blocks and Outlook has no flexbox. This is the
    compatibility floor, not a preference -- a refactor to semantic divs would
    look fine in a browser and break in half the inboxes we send to."""
    html = _render().html
    assert "<style" not in html
    assert 'role="presentation"' in html
    assert "display:flex" not in html and "display:grid" not in html
