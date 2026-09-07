"""Reads over `support_bot_answers`.

The table is loaded from data/help_content/export/ally_help_content.sql and is
edited in the database, not in code -- that is the whole reason it exists, so
the team can correct an answer without a deploy. Nothing here writes to it.

EVERY QUERY FILTERS ON `is_published`. The table also holds questions that are
unanswered, held until a product change, or retired, and none of those may reach
a founder. The column is the single gate, and the schema's own check constraint
guarantees a published row has an answer.

NO QUERY SELECTS `finding` OR `note`. See schemas.py for why.

THE TABLE MAY NOT EXIST. It is created by a SQL script somebody runs against
RDS, not by a migration, so a fresh clone or a CI database will not have it.
Every method degrades to empty rather than raising, and `is_available()` says
which state we are in -- an endpoint that 500s because content has not been
loaded yet is a worse failure than one that says it cannot answer.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.support_bot.schemas import AnswerRef, FaqEntry, IndexEntry

TABLE = "support_bot_answers"


class SupportContentRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- availability -----------------------------------------------------

    def is_available(self) -> bool:
        """True when the content table exists and holds at least one published row."""
        try:
            if self.db.execute(text("select to_regclass(:t)"), {"t": TABLE}).scalar() is None:
                return False
            return bool(self.db.execute(
                text(f"select 1 from {TABLE} where is_published limit 1")).first())
        except SQLAlchemyError as exc:
            logger.warning("support content availability check failed", exc_info=exc)
            return False

    # --- reads ------------------------------------------------------------

    def index(self) -> list[IndexEntry]:
        """Every published question, without its answer, for the routing step.

        Ordered by id so the prompt built from it is byte-identical between
        calls while the content is unchanged -- which is what makes it worth
        caching upstream.
        """
        try:
            rows = self.db.execute(text(
                f"select question_id, question from {TABLE} "
                f"where is_published order by question_id")).fetchall()
        except SQLAlchemyError as exc:
            logger.warning("support content index unavailable", exc_info=exc)
            return []
        return [IndexEntry(question_id=r[0], question=r[1]) for r in rows]

    def by_ids(self, ids: list[int]) -> list[AnswerRef]:
        """Published answers for these ids, in the order asked for.

        Unknown or unpublished ids are dropped silently: the caller is a
        language model choosing from an index, and a hallucinated id must
        produce one fewer source rather than an error.
        """
        if not ids:
            return []
        try:
            rows = self.db.execute(text(
                f"select question_id, question, answer, links, group_title "
                f"from {TABLE} where is_published and question_id = any(:ids)"),
                {"ids": list(ids)}).fetchall()
        except SQLAlchemyError as exc:
            logger.warning("support content fetch failed", exc_info=exc)
            return []
        found = {r[0]: AnswerRef(question_id=r[0], question=r[1], answer=r[2],
                                 links=tuple(r[3] or ()), group_title=r[4] or "")
                 for r in rows}
        return [found[i] for i in ids if i in found]

    def search(self, query: str, limit: int = 5) -> list[AnswerRef]:
        """Keyword fallback, used only when the model is unavailable.

        Calls the support_bot_search function that ships with the content
        script. It ORs the words and weights the question above the answer body,
        because the obvious plainto_tsquery ANDs every word and returns nothing
        for a founder typing a whole sentence.

        This is a fallback and is treated as one: keyword matching misses things
        a person would catch, so the service presents its results as "this might
        help" rather than as an answer.
        """
        if not query.strip():
            return []
        try:
            rows = self.db.execute(
                text("select question_id, question, answer, links "
                     "from support_bot_search(:q, :n)"),
                {"q": query, "n": limit}).fetchall()
        except SQLAlchemyError as exc:
            # The function ships with the table; its absence means partially
            # loaded content, not a bug worth failing the request over.
            logger.warning("support keyword search unavailable", exc_info=exc)
            return []
        return [AnswerRef(question_id=r[0], question=r[1], answer=r[2],
                          links=tuple(r[3] or ())) for r in rows]

    def faq(self, limit: int | None = None) -> list[FaqEntry]:
        """Published answers for the Help page's own list.

        Exists so the Help page can stop shipping a hardcoded FAQ array. The
        one it had went stale badly -- it told founders there was no download or
        share button on the report months after both shipped, and described a
        plan ladder that no longer existed. Content in the database cannot drift
        from itself.
        """
        sql = (f"select question_id, question, answer, group_number, group_title, links "
               f"from {TABLE} where is_published order by group_number, question_id")
        if limit:
            sql += f" limit {int(limit)}"
        try:
            rows = self.db.execute(text(sql)).fetchall()
        except SQLAlchemyError as exc:
            logger.warning("support faq unavailable", exc_info=exc)
            return []
        return [FaqEntry(question_id=r[0], question=r[1], answer=r[2],
                         group_number=r[3], group_title=r[4], links=tuple(r[5] or ()))
                for r in rows]


class SupportMissRepository:
    """Writes to `support_bot_misses` -- the questions we could not answer.

    SEPARATE CLASS ON PURPOSE. SupportContentRepository is read-only over the
    content table and its docstring promises exactly that; bolting a write onto
    it would make that promise false for the next person who reads it.

    BEST EFFORT, ALWAYS. This runs on the path where a founder is already being
    told we have no answer. Failing to record that must not turn their honest
    "I don't know" into a 500 -- so every failure is swallowed, and the session
    is rolled back so a poisoned transaction cannot surface later as an
    unrelated error somewhere else in the request.
    """

    TABLE = "support_bot_misses"

    def __init__(self, db: Session):
        self.db = db

    def record(self, *, founder_id: int, question: str, reason: str) -> bool:
        question = (question or "").strip()
        if not question:
            return False
        try:
            self.db.execute(
                text(
                    f"INSERT INTO {self.TABLE} (founder_id, question, reason) "
                    "VALUES (:founder_id, :question, :reason)"
                ),
                {"founder_id": founder_id, "question": question[:2000], "reason": reason[:40]},
            )
            self.db.commit()
            return True
        except SQLAlchemyError:
            # Table missing on a fresh clone, RLS, anything. Never fatal.
            logger.warning("could not record support bot miss", exc_info=True)
            try:
                self.db.rollback()
            except SQLAlchemyError:
                pass
            return False
