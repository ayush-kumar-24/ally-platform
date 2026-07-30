"""Dashboard backend tests -- pure aggregation, no DB needed for the unit tests
(the repository layer is mocked). Asserts the five journey states, the NULL rule,
band-not-number, no forbidden fields, and zero LLM involvement.
"""

from pathlib import Path
from types import SimpleNamespace

from app.api.v1.dashboard import service as dash_service
from app.api.v1.dashboard.service import _state, build_overview
from app.schemas.dashboard import DashboardOverview, DashboardState


def _founder(**over):
    base = dict(founder_id=1, full_name="Test Founder", profile_completed=True, tour_seen_at=None)
    base.update(over)
    return SimpleNamespace(**base)


def _mock_repo(monkeypatch, *, report=None, sess=None, counts=None, stage=None,
               actions=None, call=None, convos=None, reports=None):
    r = dash_service.dashboard_repository
    monkeypatch.setattr(r, "session_stats", lambda db, fid: sess or {})
    monkeypatch.setattr(r, "counts", lambda db, fid: counts or {})
    monkeypatch.setattr(r, "current_stage", lambda db, fid: stage)
    monkeypatch.setattr(r, "upcoming_actions", lambda db, fid, limit=5: actions or [])
    monkeypatch.setattr(r, "upcoming_call", lambda db, fid: call)
    monkeypatch.setattr(r, "recent_conversations", lambda db, fid, limit=5: convos or [])
    monkeypatch.setattr(r, "recent_reports", lambda db, fid, limit=5: reports or [])
    monkeypatch.setattr(dash_service.intelligence_repository, "get_latest_active_report",
                        lambda db, fid: report)


def _report(**over):
    base = dict(report_id=25, title="Clarity Report", summary="A summary.",
                generated_at=None, top_root_cause_ids=[10, 3],
                business_dna={"band": "Developing", "red_flags": [],
                              "pillars": [{"pillar_id": 1, "pillar_name": "Founder Readiness",
                                           "band": "Developing", "red_flag_triggered": False}]})
    base.update(over)
    return SimpleNamespace(**base)


# ---- STEP 7: the five journey states -------------------------------------
def test_state_new_when_no_profile():
    assert _state(profile_completed=False, has_report=False, in_progress=0, completed=0, reports_count=0) is DashboardState.NEW

def test_state_profile_done():
    assert _state(True, False, 0, 0, 0) is DashboardState.PROFILE_DONE

def test_state_diagnosis_in_progress():
    assert _state(True, False, 1, 0, 0) is DashboardState.DIAGNOSIS_IN_PROGRESS

def test_state_report_ready():
    assert _state(True, True, 0, 1, 1) is DashboardState.REPORT_READY

def test_state_returning_with_history():
    assert _state(True, True, 0, 3, 2) is DashboardState.RETURNING


def test_overview_new_founder_is_all_empty(monkeypatch):
    _mock_repo(monkeypatch)  # no report, no sessions, no counts
    o = build_overview(None, _founder(profile_completed=False))
    assert o.state is DashboardState.NEW
    assert o.business_health.available is False
    assert o.latest_diagnosis.available is False
    assert o.upcoming_call.available is False
    assert o.upcoming_actions == [] and o.recent_reports == []


# ---- STEP 3: NULL, never 0 -----------------------------------------------
def test_no_report_health_is_null_not_zero(monkeypatch):
    _mock_repo(monkeypatch)  # no report
    o = build_overview(None, _founder())
    assert o.business_health.available is False
    assert o.business_health.band is None       # NOT 0, NOT "Critical Gap"
    assert o.business_health.fill_pct is None

def test_pillar_with_no_data_band_is_null(monkeypatch):
    snap = {"band": "Developing", "red_flags": [],
            "pillars": [{"pillar_id": 2, "pillar_name": "Market Clarity", "band": None,
                         "red_flag_triggered": False}]}   # a pillar with no answers
    _mock_repo(monkeypatch, report=_report(business_dna=snap), counts={"reports": 1})
    o = build_overview(None, _founder())
    p = o.business_health.pillars[0]
    assert p.band is None                        # NULL preserved, never coerced to 0


# ---- STEP 5: bands, not numbers; STEP 6: no forbidden fields --------------
def test_overview_is_bands_not_numbers(monkeypatch):
    _mock_repo(monkeypatch, report=_report(), counts={"reports": 1},
               reports=[{"report_id": 25, "title": "Clarity Report", "band": "Developing", "generated_at": None}])
    o = build_overview(None, _founder())
    assert o.business_health.band == "Developing"
    blob = o.model_dump_json().lower()
    for forbidden in ("confidence", "fit_score", "overall_score", "final_weighted", '"score"'):
        assert forbidden not in blob

def test_schema_has_no_score_or_confidence_fields():
    # Structural guarantee: the overview response can never carry these.
    import app.schemas.dashboard as s
    for model in (s.BusinessHealthSummary, s.PillarBand, s.ReportListItem,
                  s.DashboardMetrics, s.LatestDiagnosis, s.StageContext):
        fields = set(model.model_fields)
        assert not (fields & {"score", "overall_score", "confidence_score", "fit_score", "final_weighted_score"})


# ---- health agrees with the report ---------------------------------------
def test_dashboard_band_matches_report_snapshot(monkeypatch):
    snap = {"band": "Needs Attention", "red_flags": [], "pillars": []}
    _mock_repo(monkeypatch, report=_report(business_dna=snap), counts={"reports": 1})
    o = build_overview(None, _founder())
    # dashboard reads the SAME snapshot the report renders from -> cannot disagree
    assert o.business_health.band == snap["band"]


# ---- STEP 7: zero LLM ------------------------------------------------------
def test_dashboard_source_makes_no_llm_calls():
    """Assert (not assume) zero LLM: no import of a generation/LLM/embedding module,
    and no generation call. Prose/docstrings are ignored -- only code lines count."""
    base = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "dashboard"
    forbidden_imports = ("llm", "openai", "anthropic", "embedding", "reasoning.service",
                         "narrator", "generator", "provider")
    forbidden_calls = (".generate(", ".complete(", ".embed(", "build_report_html(",
                       "build_report_payload(", "ReportNarrativeGenerator")
    for path in base.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                low = stripped.lower()
                assert not any(f in low for f in forbidden_imports), f"{path.name}: {stripped}"
            for call in forbidden_calls:
                assert call not in line, f"{path.name} calls {call}"


def test_overview_type(monkeypatch):
    _mock_repo(monkeypatch, report=_report(), counts={"reports": 1})
    assert isinstance(build_overview(None, _founder()), DashboardOverview)
