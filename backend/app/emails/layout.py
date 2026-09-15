"""One branded shell for every email Ally sends.

WHAT WAS WRONG. Each sender built its own HTML inline -- a run of bare <p>
tags, a default-blue <a>, and a grey disclaimer. Twelve senders, twelve
hand-written variants, no logo, nothing that looked like the product the
founder had just been using. They read as machine output because they were:
markup written to be correct, never to be seen.

This is the shell they all get instead. Callers pass CONTENT -- a kicker, a
heading, the one fact that matters, a call to action -- and never markup.

WHY IT IS ALL TABLES AND INLINE STYLES, which no one would write by choice:
Gmail strips <style> blocks in several of its clients, Outlook's renderer is
Word's and has no flexbox or grid, and a stylesheet cannot be linked at all.
Tables with inline attributes are what survives everywhere. This is a
compatibility floor, not a preference, and it is worth writing once here so
that no sender has to know it.

TWO MORE THINGS EMAIL FORCES:

  * The logo is a hosted URL. Gmail blocks data: URIs outright, and a CID
    attachment would make every sender build a multipart message. The mark
    already ships to S3 with the frontend, so it is already public -- and the
    header still reads correctly when a client blocks images, because the alt
    text is the word "Ally" sitting on the green band.
  * Every email keeps its plain-text twin. `render` returns both halves from
    the same arguments so they cannot drift, and the quote appears in both --
    a text-only client gets the whole email, not a degraded one.

EVERYTHING IS ESCAPED HERE. Callers pass plain strings: a task title is
whatever the founder typed, and an ampersand in it must not break the markup
of their own reminder.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.core.config import settings
from app.emails.quotes import Quote

# --- palette ---------------------------------------------------------------
# The app's own tokens (frontend/src/styles/tokens.css), so the inbox and the
# product look like one company rather than two.
_FOREST = "#1B4332"
_EMERALD = "#10B981"
_MINT = "#EFFAF4"
_INK = "#16241c"
_BODY = "#4a5a50"
_MUTED = "#96a69c"
_LINE = "#e7e0d6"
_ON_DARK_MUTED = "#a7c0b4"
_GROUND = "#f2ede6"

_SANS = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
#: Georgia, not a web font: @font-face is unreliable-to-blocked across email
#: clients, and Georgia is present on effectively every desktop and phone. The
#: quote is the one place the emails are allowed a different voice.
_SERIF = "Georgia,'Times New Roman',serif"

#: Kicker colours. Two tones only: something that is merely confirmed, and
#: something that is about to happen. A third would stop meaning anything.
TONES = {
    "calm": (_MINT, "#0f7a5a"),
    "due": ("#FFF4E5", "#9a5b00"),
}


@dataclass(frozen=True)
class Rendered:
    html: str
    text: str


def _logo_url() -> str:
    return settings.EMAIL_LOGO_URL


def render(
    *,
    kicker: str,
    heading: str,
    lede: str,
    cta_label: str,
    cta_url: str,
    footer_note: str,
    tone: str = "calm",
    panel_label: str = "",
    panel_value: str = "",
    panel_sub: str = "",
    body_line: str = "",
    quote: Quote | None = None,
    greeting: str = "",
) -> Rendered:
    """The branded email, in both halves.

    `panel_*` is the one fact the email exists to deliver -- the task and when
    it is due. It is a panel rather than a bold run in a sentence because that
    is the thing the founder opened the email to find.
    """
    kicker_bg, kicker_fg = TONES.get(tone, TONES["calm"])

    # --- plain text twin ---------------------------------------------------
    text_parts = []
    if greeting:
        text_parts.append(f"{greeting}\n")
    text_parts.append(f"{heading}\n")
    if lede:
        text_parts.append(f"{lede}\n")
    if panel_value:
        line = panel_value if not panel_label else f"{panel_value} -- {panel_label}"
        text_parts.append(f"\n{line}")
        if panel_sub:
            text_parts.append(panel_sub)
        text_parts.append("")
    text_parts.append(f"{cta_label}: {cta_url}\n")
    if body_line:
        text_parts.append(f"{body_line}\n")
    if quote is not None:
        attribution = f"\n  -- {quote.by}" if quote.by else ""
        text_parts.append(f'"{quote.text}"{attribution}\n')
    text_parts.append("The GoXL Team\n\n--\n" + footer_note)
    text = "\n".join(text_parts)

    # --- html --------------------------------------------------------------
    greeting_html = (
        f'<p style="margin:0 0 10px;font-size:15px;line-height:23px;color:{_BODY};">'
        f"{escape(greeting)}</p>" if greeting else ""
    )
    panel_html = ""
    if panel_value:
        sub = (f'<div style="margin:6px 0 0;font-size:13px;line-height:20px;color:#6c7a70;">'
               f"{escape(panel_sub)}</div>" if panel_sub else "")
        label = (f'<div style="font-size:11px;font-weight:700;letter-spacing:.1em;'
                 f'text-transform:uppercase;color:{_FOREST};">{escape(panel_label)}</div>'
                 if panel_label else "")
        panel_html = f"""
  <tr><td style="padding:20px 28px 0;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
           style="background:{_MINT};border-radius:10px;border-left:4px solid {_EMERALD};">
      <tr><td style="padding:16px 18px;font-family:{_SANS};">
        {label}
        <div style="margin:6px 0 0;font-size:17px;line-height:24px;font-weight:700;
                    color:{_INK};">{escape(panel_value)}</div>
        {sub}
      </td></tr>
    </table>
  </td></tr>"""

    body_html = (f'<p style="margin:16px 0 0;font-family:{_SANS};font-size:14px;'
                 f'line-height:22px;color:{_BODY};">{escape(body_line)}</p>'
                 if body_line else "")

    quote_html = ""
    if quote is not None:
        by = (f'<div style="margin:8px 0 0;font-family:{_SERIF};font-size:12px;'
              f'color:#6c7a70;letter-spacing:.04em;">&#8212; {escape(quote.by)}</div>'
              if quote.by else "")
        quote_html = f"""
  <tr><td style="padding:24px 28px 0;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
           style="border-top:1px solid {_LINE};">
      <tr><td style="padding:20px 0 0;">
        <div style="font-family:{_SANS};font-size:10px;font-weight:700;letter-spacing:.14em;
                    text-transform:uppercase;color:{_MUTED};">While you&#8217;re here</div>
        <div style="margin:10px 0 0;font-family:{_SERIF};font-size:16px;line-height:25px;
                    font-style:italic;color:{_FOREST};">&#8220;{escape(quote.text)}&#8221;</div>
        {by}
      </td></tr>
    </table>
  </td></tr>"""

    html = f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(heading)}</title></head>
<body style="margin:0;padding:0;background:{_GROUND};">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:{_GROUND};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600"
       style="width:600px;max-width:100%;background:#ffffff;border-radius:14px;
              overflow:hidden;border:1px solid {_LINE};">

  <tr><td style="background:{_FOREST};padding:20px 28px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td width="36" style="width:36px;vertical-align:middle;">
        <img src="{escape(_logo_url(), quote=True)}" width="32" height="32" alt="Ally"
             style="display:block;width:32px;height:32px;border:0;">
      </td>
      <td style="padding-left:12px;vertical-align:middle;">
        <div style="font-family:{_SANS};font-size:15px;font-weight:700;color:#ffffff;
                    letter-spacing:-.01em;">Ally</div>
        <div style="font-family:{_SANS};font-size:11px;color:{_ON_DARK_MUTED};
                    letter-spacing:.06em;text-transform:uppercase;">by GoXL</div>
      </td>
    </tr></table>
  </td></tr>

  <tr><td style="padding:30px 28px 8px;font-family:{_SANS};">
    {greeting_html}
    <div style="display:inline-block;padding:4px 10px;border-radius:999px;
                background:{kicker_bg};color:{kicker_fg};font-size:11px;font-weight:700;
                letter-spacing:.1em;text-transform:uppercase;">{escape(kicker)}</div>
    <h1 style="margin:16px 0 0;font-size:22px;line-height:29px;font-weight:700;
               color:{_INK};letter-spacing:-.02em;">{escape(heading)}</h1>
    <p style="margin:10px 0 0;font-size:15px;line-height:23px;color:{_BODY};">{escape(lede)}</p>
  </td></tr>
{panel_html}
  <tr><td style="padding:22px 28px 0;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td style="background:{_EMERALD};border-radius:8px;">
        <a href="{escape(cta_url, quote=True)}"
           style="display:inline-block;padding:12px 24px;font-family:{_SANS};font-size:14px;
                  font-weight:700;color:#ffffff;text-decoration:none;">{escape(cta_label)}</a>
      </td>
    </tr></table>
    {body_html}
  </td></tr>
{quote_html}
  <tr><td style="padding:24px 28px 26px;">
    <div style="border-top:1px solid {_LINE};padding-top:16px;font-family:{_SANS};">
      <div style="font-size:13px;color:{_BODY};">The GoXL Team</div>
      <div style="margin:8px 0 0;font-size:11px;line-height:17px;color:{_MUTED};">
        {escape(footer_note)}</div>
    </div>
  </td></tr>

</table>
</td></tr></table>
</body></html>"""

    return Rendered(html=html, text=text)
