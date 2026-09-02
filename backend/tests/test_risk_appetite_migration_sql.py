"""The Risk Appetite migration's SQL loader parses to what it claims.

Written after the loader shipped broken. `_load_sql` split the file on ";",
which treats a semicolon inside a `--` comment as a statement boundary -- and
the file's own prose contained one ("...warns against; asking which feeling
actually shows up..."). That cut the header comment in two and handed Postgres
a fragment beginning `asking which feeling actually shows up, or`, failing the
production migration with `syntax error at or near "asking"`.

The bug was invisible until deploy: the migration imports fine, the SQL file
reads fine, and nothing runs the splitter until Alembic does. These tests run
it, so the next semicolon in a comment fails here in a second rather than on a
production migration task after a four-minute deploy.
"""

import importlib.util
import re
from pathlib import Path

import pytest

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic" / "versions"
    / "2026_09_02_1100-a3f81c05e6d7_risk_appetite_dimension.py"
)


def _module():
    """Import the migration directly -- Alembic files are not importable by
    package path, and the revision id makes an invalid module name."""
    spec = importlib.util.spec_from_file_location("risk_appetite_migration", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loader_returns_exactly_the_two_executable_statements():
    statements = _module()._load_sql()

    assert len(statements) == 2, statements
    assert statements[0].startswith("INSERT INTO founder_dna_questions")
    assert statements[1].startswith("SELECT setval(")


def test_no_statement_is_a_stray_comment_fragment():
    """The actual failure mode, asserted directly.

    A fragment is not merely 'unexpected' -- it is executable-looking text that
    Postgres rejects at parse time, which is why this cost a deploy.
    """
    for statement in _module()._load_sql():
        assert not statement.lstrip().startswith("--"), statement
        # Every real statement here begins with a SQL verb.
        assert re.match(r"(?i)^\s*(INSERT|SELECT)\b", statement), statement


def test_semicolon_inside_a_comment_does_not_split_a_statement(tmp_path, monkeypatch):
    """The regression, reproduced from scratch.

    Builds a file with the same shape as the real one -- a comment containing a
    semicolon, then the two statements -- and asserts the loader is not fooled.
    Without the comment-stripping this yields three statements, the middle one
    being prose.
    """
    module = _module()
    fake = tmp_path / "risk_appetite_dimension.sql"
    fake.write_text(
        "-- a comment that warns against something; and then continues\n"
        "INSERT INTO founder_dna_questions (dimension_code) VALUES ('risk_appetite');\n"
        "SELECT setval('some_seq', 1);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_sql_path", lambda: fake)

    statements = module._load_sql()
    assert len(statements) == 2
    assert statements[0].startswith("INSERT INTO founder_dna_questions")
    assert statements[1].startswith("SELECT setval(")


def test_loader_refuses_a_file_with_the_wrong_statement_count(tmp_path, monkeypatch):
    """The guard fails loudly rather than sending half a file to Postgres."""
    module = _module()
    fake = tmp_path / "risk_appetite_dimension.sql"
    fake.write_text("SELECT 1;\nSELECT 2;\nSELECT 3;\n", encoding="utf-8")
    monkeypatch.setattr(module, "_sql_path", lambda: fake)

    with pytest.raises(RuntimeError, match="Expected exactly 2"):
        module._load_sql()


def test_loader_still_rejects_zero_vector_embeddings(tmp_path, monkeypatch):
    """The other guard this file carries, kept covered.

    A zero vector satisfies a NOT NULL column and then hides from the embedding
    backfill's selector, so the row looks embedded and can never be matched.
    """
    module = _module()
    fake = tmp_path / "risk_appetite_dimension.sql"
    fake.write_text(
        "INSERT INTO founder_dna_questions (embedding) "
        "VALUES (array_fill(0, ARRAY[1536])::vector);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_sql_path", lambda: fake)

    with pytest.raises(RuntimeError, match="zero-vector"):
        module._load_sql()


def test_the_real_file_seeds_six_questions_across_three_stage_groups():
    """The content contract, not just the parse.

    A file that parses cleanly but seeds four rows would leave one stage group
    unable to ever resolve the dimension -- and the migration's own post-insert
    assertion would only catch that against a live database.
    """
    insert = _module()._load_sql()[0]

    assert insert.count("'risk_appetite'") == 6
    for stage_group in ("Stage 0", "Stage 0→1", "Stage 1→10+"):
        assert f"'{stage_group}'" in insert, stage_group
    # One opening forced_choice and one closing scenario per group.
    assert insert.count("'forced_choice'") == 3
    assert insert.count("'scenario'") == 3
