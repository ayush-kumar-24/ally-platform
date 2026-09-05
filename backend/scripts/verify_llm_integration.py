"""Preflight: is the reasoning stack actually talking to a real model?

    python scripts/verify_llm_integration.py

Needs no database and writes nothing. It answers one question the test suite
cannot: with the keys and flags THIS environment holds, will a founder's
diagnosis be reasoned by a model, or quietly by a fallback?

Why this script has to exist
----------------------------
Every LLM-backed behaviour in the reasoning stack is behind its own flag, and
all ten default to OFF. Nothing fails when they are off -- the engines degrade
to deterministic paths and the API keeps returning 200s. So "we ran a diagnosis
and got a report" is not evidence that any model was involved.

The chat path is worse than merely off. `build_routing_policy` falls back to the
mock provider whenever the selected one has no key, and `FailoverLLMProvider`
keeps mock as the last link "so the chain always yields an answer rather than
failing closed". That is a deliberate resilience choice, but it means an
unconfigured deployment answers founders with fabricated text and reports
success. This module's own history records exactly that happening once already.

So this script asserts the two things a green test run cannot:

  1. the provider the app RESOLVES is not the mock, and
  2. a real request to each configured provider comes back from that vendor.

Exit code 0 = the stack is genuinely wired to a model. Non-zero = something is
degraded, and the report says which flag or key is responsible.
"""

from __future__ import annotations

import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.v1.ally.execution.schemas import ProviderRequest  # noqa: E402
from app.core.config import settings as app_settings  # noqa: E402
from app.integrations.llm.settings import (  # noqa: E402
    LLMSettings,
    build_providers,
    build_routing_policy,
)

GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")

failures: list[str] = []
warnings: list[str] = []


def head(text: str) -> None:
    print(f"\n{BOLD}{text}{OFF}\n" + "-" * len(text))


def ok(text: str) -> None:
    print(f"  {GREEN}PASS{OFF}  {text}")


def bad(text: str) -> None:
    print(f"  {RED}FAIL{OFF}  {text}")
    failures.append(text)


def warn(text: str) -> None:
    print(f"  {YELLOW}WARN{OFF}  {text}")
    warnings.append(text)


# --------------------------------------------------------------------------
# 1. The diagnosis flags
# --------------------------------------------------------------------------
#: (attribute, the value that means "a model is involved", what it does when off)
DIAGNOSIS_FLAGS: list[tuple[str, object, str]] = [
    ("ADAPTIVE_QUESTIONS", True,
     "answers are never scored Green/Amber/Red at submit time, and the next "
     "question is picked deterministically"),
    ("ANSWER_CLASSIFIER", "llm",
     "answers are banded from the stored score_label instead of being read"),
    ("ARCHETYPE_LLM", True, "the founder archetype comes from the rubric only"),
    ("STAGE_INFERENCE_LLM", True, "business stage is taken as self-reported"),
    ("ANSWER_CONSISTENCY_LLM", True,
     "the consistency signal stays UNAVAILABLE and confidence renormalises "
     "over the other four inputs"),
    ("DISTRESS_LLM", True,
     "distress falls back to the deterministic proxy (distress-tagged Red answers)"),
    ("REPORT_NARRATIVE_LLM", True, "every report section is template prose"),
    ("RECOMMENDATION_FALLBACK_LLM", True, "recommendations come from the catalog only"),
    ("ACTION_PLAN_BALANCE_LLM", True, "the action plan is not balanced by a model"),
]


def check_flags() -> None:
    head("1. Reasoning flags")
    on = 0
    for name, wanted, degradation in DIAGNOSIS_FLAGS:
        actual = getattr(app_settings, name, None)
        if actual == wanted:
            ok(f"{name} = {actual!r}")
            on += 1
        else:
            warn(f"{name} = {actual!r} (want {wanted!r}) -- {degradation}")
    print(f"\n  {on}/{len(DIAGNOSIS_FLAGS)} reasoning flags engage a model.")

    # This one is not a preference. With both of its inputs off, every answer
    # reaches the pipeline unscored and the report has no evidence behind it --
    # the P0 that `Settings.diagnosis_scoring_configured` exists to name.
    if app_settings.diagnosis_scoring_configured:
        ok("diagnosis_scoring_configured -- answers will be banded")
    else:
        bad("diagnosis_scoring_configured is FALSE: no answer will be scored, so "
            "every diagnosis produces a report with no evidence. Set "
            "ADAPTIVE_QUESTIONS=true (preferred) or ANSWER_CLASSIFIER=llm")


def check_classifier_provider() -> None:
    head("2. Classifier provider (diagnosis path)")
    provider = (app_settings.LLM_PROVIDER or "").strip()
    if not provider:
        if app_settings.diagnosis_scoring_configured:
            bad("LLM_PROVIDER is empty while a reasoning flag is on -- the "
                "classifier has no vendor to call")
        else:
            warn("LLM_PROVIDER is empty (consistent with the flags being off)")
        return
    ok(f"LLM_PROVIDER = {provider!r}, LLM_MODEL = "
       f"{app_settings.LLM_MODEL or '<adapter default>'!r}")
    key = {"openai": app_settings.OPENAI_API_KEY,
           "anthropic": app_settings.ANTHROPIC_API_KEY,
           "gemini": app_settings.GEMINI_API_KEY}.get(provider, "")
    if key:
        ok(f"an API key for {provider!r} is present")
    else:
        bad(f"LLM_PROVIDER={provider!r} but no API key is set for it")


# --------------------------------------------------------------------------
# 3. What the chat path actually resolves to
# --------------------------------------------------------------------------
def check_chat_routing() -> LLMSettings:
    head("3. Chat provider resolution")
    s = LLMSettings()
    providers = build_providers(s)
    policy = build_routing_policy(s, providers)

    print(f"  registry:        {', '.join(sorted(providers))}")
    print(f"  ALLY_LLM_PROVIDER requested: {s.provider!r}")
    print(f"  resolved:        {policy.default_provider!r} / {policy.default_model!r}")
    print(f"  fallback chain:  {', '.join(s.fallback) or '<none>'}")

    if policy.default_provider == "mock":
        if s.provider == "mock":
            bad("the chat provider is the MOCK: ALLY_LLM_PROVIDER is unset or "
                "'mock', so founders would receive fabricated answers reported "
                "as successes")
        else:
            bad(f"ALLY_LLM_PROVIDER={s.provider!r} was requested but SILENTLY "
                f"resolved to the mock -- its API key is missing. This does not "
                f"raise; chat would answer from the mock and report success")
    else:
        ok(f"chat resolves to the real provider {policy.default_provider!r}")

    if "mock" in s.fallback:
        warn("'mock' appears in ALLY_LLM_FALLBACK -- a provider outage would "
             "fabricate answers rather than fail")
    return s


# --------------------------------------------------------------------------
# 4. A real call to each configured provider
# --------------------------------------------------------------------------
PROBE_SYSTEM = "You are a health check. Reply with exactly one word."
PROBE_USER = "Reply with the single word: ready"


def probe_providers(s: LLMSettings) -> None:
    head("4. Live provider probe")
    providers = build_providers(s)
    real = {n: p for n, p in providers.items() if n != "mock"}
    if not real:
        bad("no real provider is configured -- set OPENAI_API_KEY, "
            "ANTHROPIC_API_KEY or GEMINI_API_KEY")
        return

    models = {"openai": s.openai_model, "anthropic": s.anthropic_model,
              "gemini": s.gemini_model}
    for name, provider in sorted(real.items()):
        model = models.get(name, "")
        request = ProviderRequest(
            system=PROBE_SYSTEM, user=PROBE_USER, model=model,
            temperature=Decimal("0"), max_tokens=16,
        )
        started = time.monotonic()
        try:
            response = provider.generate(request)
        except Exception as exc:  # noqa: BLE001 -- the probe reports, never raises
            bad(f"{name} ({model}) raised {type(exc).__name__}: {exc}")
            continue
        elapsed = int((time.monotonic() - started) * 1000)

        body = (response.content or "").strip().replace("\n", " ")
        # The vendor a response CLAIMS is the only proof the call left the
        # process. A mock answers instantly and says so.
        if response.provider == "mock":
            bad(f"{name} returned a response stamped provider='mock'")
        elif not body:
            bad(f"{name} ({model}) returned an empty body in {elapsed}ms")
        else:
            ok(f"{name} -> {response.provider}/{response.model} in {elapsed}ms: "
               f"{DIM}{body[:60]}{OFF}")


# --------------------------------------------------------------------------
# 5. Retrieval / embeddings
# --------------------------------------------------------------------------
def check_retrieval() -> None:
    head("5. Retrieval and embeddings")
    if not app_settings.RETRIEVAL_ENABLED:
        warn("RETRIEVAL_ENABLED is false -- grounded retrieval is off, so Ally "
             "answers without the knowledge base")
        return
    ok("RETRIEVAL_ENABLED is true")
    provider = (app_settings.EMBEDDING_PROVIDER or "").strip()
    if not provider:
        bad("RETRIEVAL_ENABLED is true but EMBEDDING_PROVIDER is empty -- "
            "text cannot be turned into a query vector")
        return
    key = {"openai": app_settings.OPENAI_API_KEY,
           "gemini": app_settings.GEMINI_API_KEY}.get(provider, "")
    (ok if key else bad)(
        f"EMBEDDING_PROVIDER={provider!r} model={app_settings.EMBEDDING_MODEL!r} "
        f"dim={app_settings.EMBEDDING_DIMENSION}"
        + ("" if key else " -- but no API key is set for it"))


def main() -> int:
    print(f"{BOLD}Ally -- LLM integration preflight{OFF}")
    print(f"{DIM}environment={app_settings.ENVIRONMENT}{OFF}")

    check_flags()
    check_classifier_provider()
    s = check_chat_routing()
    probe_providers(s)
    check_retrieval()

    head("Result")
    if failures:
        print(f"  {RED}{len(failures)} blocking problem(s){OFF}"
              + (f", {len(warnings)} warning(s)" if warnings else ""))
        for f in failures:
            print(f"    - {f}")
        print("\n  The reasoning stack is NOT fully wired to a real model.")
        return 1
    if warnings:
        print(f"  {YELLOW}No blocking problems, {len(warnings)} warning(s).{OFF}")
        print("  Every warning is a surface running deterministically rather "
              "than by model -- fine if deliberate.")
        return 0
    print(f"  {GREEN}Every checked surface is wired to a real model.{OFF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
