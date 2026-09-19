"""What ONE diagnostic session learned about a founder, kept out of the profile.

Hand-modelled rather than generated: `schema.py` is a snapshot of the live
database and this table is newer than that snapshot. Same reason `memory.py`
and `suggestions.py` live outside it.

THE BOUNDARY THIS TABLE DEFENDS. `founders` is what the founder STATED about
themselves. A row here is what one session OBSERVED while asking them
questions. The second is an inference drawn from a sentence of free text, and
promoting it into the first would let one ambiguous answer silently rewrite a
founder's record -- invisibly, because nothing in the product shows them what
Ally concluded. So there is deliberately no write path from here to `founders`,
and `FounderContext.with_session_facts` layers these on top of a context built
from the profile with the profile winning every disagreement.

ABSENCE IS UNKNOWN. Only a settled fact is ever written. "We do not know
whether they have a team" is the absence of a row, never `value = false` --
which is what keeps UNKNOWN from being recorded as a denial and then read back
as one.
"""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SessionContextFact(Base):
    __tablename__ = "session_context_facts"
    __table_args__ = (
        PrimaryKeyConstraint("fact_id", name="session_context_facts_pkey"),
        ForeignKeyConstraint(
            ["session_id"], ["sessions.session_id"],
            ondelete="CASCADE", name="session_context_facts_session_id_fkey",
        ),
        # CASCADE, not SET NULL: a fact whose evidence was deleted is a claim
        # nobody can audit. Retracting it with the answer is the honest
        # behaviour -- the founder's eligibility simply returns to UNKNOWN.
        ForeignKeyConstraint(
            ["learned_from_answer_id"], ["answers.answer_id"],
            ondelete="CASCADE", name="session_context_facts_answer_id_fkey",
        ),
        UniqueConstraint("session_id", "token", name="uq_session_context_facts"),
        Index("idx_session_context_facts_session", "session_id"),
    )

    fact_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, nullable=False)
    #: A precondition token, matching `question_tags.precondition_token` and
    #: resolved by `founder_context.family_of`. Unconstrained on purpose:
    #: tokens are data, and an unrecognised one degrades to UNKNOWN rather than
    #: breaking a session.
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: Provenance. "Why did Ally stop asking about my team?" must point at the
    #: sentence that settled it.
    learned_from_answer_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(True), nullable=False, server_default=text("now()")
    )
