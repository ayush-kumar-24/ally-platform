"""The migration graph has exactly one head.

It forked at b7e4f2a91c58 and stayed forked: two revisions on the same day,
each branched off the same parent, neither merged. Nothing complained, because
nothing in this repository ran the migrations against an empty database --
`alembic upgrade head` against the live project is a no-op when the live
project is already at one of the heads.

What it costs when nobody notices:

    $ alembic upgrade head
    Multiple head revisions are present for given argument 'head'

A deploy that migrates on boot fails there. A new environment -- the AWS RDS
move in DEPLOY_AWS.md, a restored backup, a reviewer's laptop -- cannot be
built at all. This test fails the moment a second head appears, which is the
moment it is cheap to fix with `alembic merge`.
"""

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.paths import BACKEND_DIR


def _scripts() -> ScriptDirectory:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return ScriptDirectory.from_config(config)


def test_exactly_one_head():
    heads = _scripts().get_heads()
    assert len(heads) == 1, (
        f"the migration graph has {len(heads)} heads: {heads}. "
        "`alembic upgrade head` refuses to run in this state. Rejoin them "
        "with: alembic merge -m 'rejoin the migration heads' " + " ".join(heads)
    )


def test_every_revision_is_reachable_from_that_head():
    """A revision hanging off nothing would never be applied by an upgrade."""
    scripts = _scripts()
    head = scripts.get_heads()[0]
    reachable = {rev.revision for rev in scripts.walk_revisions("base", head)}
    everything = {rev.revision for rev in scripts.walk_revisions()}
    assert everything - reachable == set(), (
        f"unreachable revisions: {everything - reachable}")


def test_the_merge_revision_carries_no_ddl():
    """A merge revision exists to rejoin the graph. Schema changes hidden in
    one are invisible in a history that reads as a bookkeeping entry."""
    for rev in _scripts().walk_revisions():
        parents = rev.down_revision
        if not isinstance(parents, tuple) or len(parents) < 2:
            continue
        source = rev.path and open(rev.path, encoding="utf-8").read() or ""
        body = source.split("def upgrade", 1)[-1].split("def downgrade", 1)[0]
        for verb in ("op.create_", "op.add_", "op.drop_", "op.alter_",
                     "op.execute", "op.bulk_insert"):
            assert verb not in body, (
                f"merge revision {rev.revision} carries {verb} -- put schema "
                "changes in their own revision")
