"""Data access for the Reports APIs: ownership-checked reads, share tokens, and
the report-framing lookups (session_state_bands, prompt_library)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.schema import ReportShares


class ReportsRepository:
    # --- framing (spec-owned text) ----------------------------------------
    def session_state_framing(self, db: Session, session_state: str | None) -> str | None:
        """report_framing_adjustment for the founder's session state. The session
        column stores 'stable' / 'significantly_guarded' / 'high_distress'; the band
        table keys on the label, so map through the state name."""
        if not session_state:
            return None
        label = {
            "stable": "Open and Engaged",
            "significantly_guarded": "Significantly Guarded",
            "high_distress": "High Distress",
        }.get(session_state, session_state)
        return db.execute(
            text("select report_framing_adjustment from session_state_bands "
                 "where session_state = :s"),
            {"s": label},
        ).scalar()

    def distress_protocol_text(self, db: Session, code: str = "PROMPT-EMPATHY-DISTRESS") -> str | None:
        return db.execute(
            text("select prompt_text from prompt_library "
                 "where prompt_code = :c and category = 'distress' and is_active is true"),
            {"c": code},
        ).scalar()

    def intervention_codes(self, db: Session, ids) -> list[str]:
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return []
        rows = db.execute(
            text("select intervention_code from interventions where intervention_id = any(:ids)"),
            {"ids": ids},
        ).all()
        return [r[0] for r in rows if r[0]]

    # --- shares -----------------------------------------------------------
    def create_share(
        self, db: Session, *, founder_id: int, report_id: int, token: str,
        base_url: str, ttl_hours: int = 24,
    ) -> ReportShares:
        share = ReportShares(
            founder_id=founder_id, report_id=report_id, share_token=token,
            share_url=f"{base_url}/api/v1/reports/shared/{token}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
            is_active=True, access_count=0,
        )
        db.add(share)
        db.commit()
        db.refresh(share)
        return share

    def get_active_share(self, db: Session, token: str) -> ReportShares | None:
        share = db.execute(
            text("select share_id, founder_id, report_id, is_active, expires_at "
                 "from report_shares where share_token = :t"),
            {"t": token},
        ).mappings().first()
        if share is None or not share["is_active"]:
            return None
        if share["expires_at"] is not None and share["expires_at"] <= datetime.now(timezone.utc):
            return None
        # bump access counter (best-effort)
        db.execute(
            text("update report_shares set access_count = access_count + 1, "
                 "last_accessed_at = now() where share_id = :id"),
            {"id": share["share_id"]},
        )
        db.commit()
        return db.get(ReportShares, share["share_id"])


reports_repository = ReportsRepository()
