"""Unit tests for the Ally Prompt Manager + Library (Phase 5, Milestone 2).

Hermetic: builds AllyContext DTOs directly and an in-memory template repository.
No database, no LLM.
"""

from decimal import Decimal

import pytest

from app.api.v1.ally.context.schemas import (
    AllyContext,
    DiagnosisContext,
    FounderProfileContext,
    RootCauseContext,
)
from app.api.v1.ally.prompts import (
    CATEGORY_DIAGNOSIS_ANSWER,
    InMemoryPromptRepository,
    MissingPromptVariableError,
    PromptManager,
    PromptMetadata,
    PromptNotFoundError,
    PromptTemplate,
    RenderedPrompt,
    TemplateVersionError,
    UnsupportedLanguageError,
    default_prompt_manager,
)

D = Decimal


def make_ctx(*, distress=False, name="Asha", stage="Growth / Scaling",
             summary="Focus on activation.", conf=D("72"), with_rc=True):
    founder = FounderProfileContext(1, name, 5, stage, "SaaS")
    diagnosis = DiagnosisContext(
        session_id=42, overall_confidence=conf, routing_state="validate",
        distress_mode=distress, session_state="stable", executive_summary=summary,
        priority_actions=("Interview churned users",), next_steps=("Book a call",),
    )
    rcs = (
        RootCauseContext(10, "RC-010", "Weak activation", "Sales & Revenue", 1,
                         "unconfirmed", D("0.8"), True),
    ) if with_rc else ()
    return AllyContext(founder=founder, has_diagnosis=True, diagnosis=diagnosis, root_causes=rcs)


def tmpl(key, category, user, *, version=1, required=(), stage=None, distress=False,
         variant=None, system="sys"):
    return PromptTemplate(
        template_key=key, version=version, category=category, system_prompt=system,
        user_prompt=user, required_variables=tuple(required), stage=stage,
        distress_mode=distress, metadata=PromptMetadata(variant=variant),
    )


# A test library spanning the selection dimensions, each in its own category so
# concerns don't interfere.
TEMPLATES = [
    tmpl("ver.v1", "ver", "Hi {{founder_name}} at {{stage_name}}.", version=1,
         required=("founder_name", "stage_name")),
    tmpl("ver.v2", "ver", "Hello {{founder_name}}!", version=2, required=("founder_name",)),
    tmpl("stg.any", "stg", "Any {{founder_name}}", required=("founder_name",)),
    tmpl("stg.growth", "stg", "Growth {{founder_name}}", required=("founder_name",),
         stage="Growth / Scaling"),
    tmpl("dst.normal", "dst", "Normal {{founder_name}}", required=("founder_name",)),
    tmpl("dst.care", "dst", "We are here, {{founder_name}}", required=("founder_name",),
         distress=True),
    tmpl("var.a", "var", "A {{founder_name}}", required=("founder_name",), variant="A"),
    tmpl("var.b", "var", "B {{founder_name}}", required=("founder_name",), variant="B"),
    tmpl("req.sum", "req", "{{executive_summary}}", required=("executive_summary",)),
    tmpl("bad.ref", "bad", "{{unknown_var}}", required=()),
]


def mgr():
    return PromptManager(InMemoryPromptRepository(TEMPLATES))


# --- Selection -------------------------------------------------------------


def test_returns_rendered_prompt_not_string():
    out = mgr().render(make_ctx(), category="ver")
    assert isinstance(out, RenderedPrompt)
    assert isinstance(out.user_prompt, str)


def test_selects_by_category_and_interpolates():
    out = mgr().render(make_ctx(), category="ver")  # latest = v2
    assert out.version == 2
    assert out.user_prompt == "Hello Asha!"
    assert out.variables["founder_name"] == "Asha"


def test_latest_version_selected_when_unspecified():
    assert mgr().render(make_ctx(), category="ver").version == 2


def test_explicit_version_selected():
    out = mgr().render(make_ctx(), category="ver", version=1)
    assert out.version == 1
    assert out.user_prompt == "Hi Asha at Growth / Scaling."


def test_unknown_version_fails_closed():
    with pytest.raises(TemplateVersionError):
        mgr().render(make_ctx(), category="ver", version=99)


def test_stage_specific_beats_wildcard():
    out = mgr().render(make_ctx(stage="Growth / Scaling"), category="stg")
    assert out.template_key == "stg.growth"


def test_wildcard_used_for_other_stage():
    out = mgr().render(make_ctx(stage="Ideation"), category="stg")
    assert out.template_key == "stg.any"


def test_distress_context_selects_distress_template():
    out = mgr().render(make_ctx(distress=True), category="dst")
    assert out.template_key == "dst.care"
    assert out.distress_mode is True


def test_non_distress_context_selects_normal_template():
    out = mgr().render(make_ctx(distress=False), category="dst")
    assert out.template_key == "dst.normal"
    assert out.distress_mode is False


def test_variant_selection():
    assert mgr().render(make_ctx(), category="var", variant="B").template_key == "var.b"
    assert mgr().render(make_ctx(), category="var", variant="A").template_key == "var.a"


# --- Fail-closed ------------------------------------------------------------


def test_missing_template_fails_closed():
    with pytest.raises(PromptNotFoundError):
        mgr().render(make_ctx(), category="does_not_exist")


def test_missing_required_variable_fails_closed():
    # executive_summary is required but the context omits it (None).
    ctx = make_ctx(summary=None)
    with pytest.raises(MissingPromptVariableError):
        mgr().render(ctx, category="req")


def test_placeholder_referencing_unknown_variable_fails_closed():
    with pytest.raises(MissingPromptVariableError):
        mgr().render(make_ctx(), category="bad")


def test_unsupported_language_fails_closed():
    with pytest.raises(UnsupportedLanguageError):
        mgr().render(make_ctx(), category="ver", language="fr")


def test_never_substitutes_a_default_for_missing_variable():
    ctx = make_ctx(summary=None)
    try:
        mgr().render(ctx, category="req")
    except MissingPromptVariableError as e:
        assert "executive_summary" in str(e)
    else:
        pytest.fail("expected fail-closed, got a silent substitution")


# --- Determinism ------------------------------------------------------------


def test_repeated_rendering_is_identical():
    m, ctx = mgr(), make_ctx()
    first = m.render(ctx, category="ver")
    assert all(m.render(ctx, category="ver") == first for _ in range(5))


def test_equal_context_gives_equal_output():
    a = mgr().render(make_ctx(), category="ver")
    b = mgr().render(make_ctx(), category="ver")
    assert a == b


# --- Prompt fingerprint -----------------------------------------------------


def test_fingerprint_is_deterministic_and_stable():
    m, ctx = mgr(), make_ctx()
    fp = m.render(ctx, category="ver").prompt_fingerprint
    assert len(fp) == 64 and all(c in "0123456789abcdef" for c in fp)  # sha256 hex
    assert all(m.render(ctx, category="ver").prompt_fingerprint == fp for _ in range(5))


def test_identical_prompts_produce_same_fingerprint():
    a = mgr().render(make_ctx(), category="ver")
    b = mgr().render(make_ctx(), category="ver")
    assert a.prompt_fingerprint == b.prompt_fingerprint


def test_changing_content_changes_fingerprint():
    base = mgr().render(make_ctx(name="Asha"), category="ver")
    # Different founder name -> different rendered user text -> different hash.
    other = mgr().render(make_ctx(name="Bkhil"), category="ver")
    assert base.user_prompt != other.user_prompt
    assert base.prompt_fingerprint != other.prompt_fingerprint


def test_fingerprint_matches_sha256_of_rendered_payload():
    import hashlib
    import json
    r = mgr().render(make_ctx(), category="ver")
    expected = hashlib.sha256(
        json.dumps({"system": r.system_prompt, "user": r.user_prompt},
                   sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    assert r.prompt_fingerprint == expected


def test_system_prompt_change_also_changes_fingerprint():
    # Two templates, identical user text, different system text -> different hash.
    repo = InMemoryPromptRepository([
        tmpl("s.a", "sys_test", "Same {{founder_name}}", system="System A"),
        tmpl("s.b", "sys_test", "Same {{founder_name}}", system="System B", version=2),
    ])
    m = PromptManager(repo)
    a = m.render(make_ctx(), category="sys_test", version=1)
    b = m.render(make_ctx(), category="sys_test", version=2)
    assert a.user_prompt == b.user_prompt
    assert a.prompt_fingerprint != b.prompt_fingerprint


# --- Built-in library -------------------------------------------------------


def test_builtin_standard_answer_is_grounded():
    out = default_prompt_manager().render(make_ctx(), category=CATEGORY_DIAGNOSIS_ANSWER)
    assert out.template_key == "diagnosis_answer.standard"
    assert "Asha" in out.user_prompt
    assert "Weak activation" in out.user_prompt          # root cause grounded
    assert "72" in out.user_prompt                        # confidence surfaced


def test_builtin_distress_answer_is_wellbeing_first():
    out = default_prompt_manager().render(make_ctx(distress=True), category=CATEGORY_DIAGNOSIS_ANSWER)
    assert out.template_key == "diagnosis_answer.distress"
    assert out.distress_mode is True
    # Wellbeing-first: no scores or root-cause breakdown leaked.
    assert "72" not in out.user_prompt
    assert "Weak activation" not in out.user_prompt
