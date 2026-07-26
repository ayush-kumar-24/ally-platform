"""Send a test email, or show that email is in stub mode.

    python scripts/send_test_email.py you@example.com

- Stub mode (no EMAIL_HOST set): logs the message and reports it was NOT sent.
- Real mode (EMAIL_HOST/USER/PASSWORD set): actually sends via SMTP.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.services.email import send_email  # noqa: E402


def main() -> int:
    to = sys.argv[1] if len(sys.argv) > 1 else None
    if not to:
        print("Usage: python scripts/send_test_email.py you@example.com")
        return 2

    print(f"email_enabled : {settings.email_enabled}")
    print(f"EMAIL_HOST    : {settings.EMAIL_HOST or '(none -> stub mode)'}")
    print(f"sending to    : {to}\n")

    sent = send_email(
        to,
        "GoXL backend — test email",
        "This is a plain-text test email from the Ally backend.",
        "<p>This is an <b>HTML</b> test email from the Ally backend.</p>",
    )

    if sent:
        print("RESULT: delivered via SMTP -- check the inbox.")
    elif settings.email_enabled:
        print("RESULT: SMTP send FAILED (bad credentials or connection). Check EMAIL_USER/PASSWORD.")
    else:
        print("RESULT: stub mode -- logged, NOT sent. Set EMAIL_HOST/USER/PASSWORD to send for real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
