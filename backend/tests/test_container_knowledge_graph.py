"""Tests for Container.knowledge_graph(db)'s caching + fail-open behaviour.

Uses a fresh Container() (not the process-level `container` singleton) so tests
don't share cache state with each other or with anything else that imported the
module-level singleton first.
"""

from datetime import timedelta

from app.api.v1.ally.kg.schemas import NodeType
from app.core.container import Container


class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _StubSession:
    def __init__(self, tables, *, fail=False):
        self._tables = tables
        self.fail = fail
        self.calls = 0

    def execute(self, clause, *a, **k):
        self.calls += 1
        if self.fail:
            raise RuntimeError("db unavailable")
        sql = str(clause)
        for table, rows in self._tables.items():
            if f"from {table}" in sql:
                return _StubResult(rows)
        return _StubResult([])


_ONE_ROOT_CAUSE = {
    "root_causes": [{"root_cause_id": 1, "root_cause_name": "RC", "problem_id": None}],
    "problems": [], "blind_spots": [], "interventions": [],
}


def test_no_db_returns_the_empty_fallback_service():
    c = Container()
    svc = c.knowledge_graph()
    assert svc.expand([1]).is_empty


def test_db_backed_load_is_cached_across_calls():
    c = Container()
    db = _StubSession(_ONE_ROOT_CAUSE)

    first = c.knowledge_graph(db)
    second = c.knowledge_graph(db)

    assert first is second                    # served from cache, not rebuilt
    assert db.calls == 4                       # one load: 4 tables, once


def test_expired_cache_triggers_a_reload():
    c = Container()
    db = _StubSession(_ONE_ROOT_CAUSE)
    c.knowledge_graph(db)
    assert db.calls == 4

    c._kg_cache_built_at -= (Container._KG_CACHE_TTL + timedelta(seconds=1))
    c.knowledge_graph(db)

    assert db.calls == 8                        # reloaded, not served stale


def test_a_failed_refresh_keeps_serving_the_last_good_cache():
    c = Container()
    good_db = _StubSession(_ONE_ROOT_CAUSE)
    good = c.knowledge_graph(good_db)
    assert good.expand([1]).metadata.node_type_counts.get(NodeType.ROOT_CAUSE.value) == 1

    c._kg_cache_built_at -= (Container._KG_CACHE_TTL + timedelta(seconds=1))
    broken_db = _StubSession({}, fail=True)
    served = c.knowledge_graph(broken_db)

    assert served is good                       # stale-but-real beats empty
    assert served.expand([1]).metadata.node_type_counts.get(NodeType.ROOT_CAUSE.value) == 1


def test_a_failed_refresh_with_no_prior_cache_falls_back_to_empty():
    c = Container()
    broken_db = _StubSession({}, fail=True)
    served = c.knowledge_graph(broken_db)
    assert served.expand([1]).is_empty
