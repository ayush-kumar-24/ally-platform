"""Print entry point: the founder's report, rendered for paper.

Thin on purpose. This module used to hold a SECOND, hand-written implementation
of the report -- its own hero, its own cards, its own type scale -- which mirrored
the screen's design language without reproducing it. That is precisely how a PDF
drifts from the page it claims to be: two codebases for one document, kept in
step by whoever remembers to update both.

Now it does one thing: look up the founder's name and hand everything to the
shared builder with `for_print=True`. The markup a founder downloads is the same
markup they were just reading -- see app/api/v1/reports/document.py.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.reports.document import build_report_document
from app.models import Founder


def build_report_html(db: Session, report, narrative) -> str:
    """This report as a self-contained print document, ready for Gotenberg.

    Takes the report row rather than just the narrative because the visuals --
    pillar bars, the strength/gap split, the confidence arc -- are driven by
    `report.insights`, and a PDF without them would be the drift this module was
    rewritten to prevent.
    """
    founder = db.get(Founder, report.founder_id)
    return build_report_document(
        narrative,
        report.insights,
        founder_name=getattr(founder, "full_name", None),
        generated_at=report.generated_at,
        for_print=True,
    )
