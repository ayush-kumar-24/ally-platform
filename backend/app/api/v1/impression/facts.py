"""The founder's onboarding answers, read off the row and made presentable.

Both the model prompt and the deterministic fallback need the same thing: the
founder's answers in their own words, with enum values turned back into the
labels they actually picked. Doing it once here keeps the two paths describing
the same founder.
"""

from dataclasses import dataclass, field

from app.models import Founder

# Mirrors the founders_experience_level_check constraint and the labels shown in
# frontend/src/data/onboardingQuestions.js.
EXPERIENCE_LABELS = {
    "first_time": "First-time founder",
    "one_company": "Built one company",
    "serial": "Serial entrepreneur",
    "investor": "Investor",
    "mentor": "Mentor",
    "executive": "Experienced executive",
}

# Mirrors founders_emotional_state_check.
FEELING_LABELS = {
    "excited": "Excited", "inspired": "Inspired", "confident": "Confident",
    "curious": "Curious", "overwhelmed": "Overwhelmed", "stuck": "Stuck",
    "determined": "Determined", "hopeful": "Hopeful",
}

# Feelings that mean the founder is carrying weight right now. Used to decide
# tone -- never to diagnose.
UNDER_STRAIN = {"overwhelmed", "stuck"}

# Challenges that are really about the founder holding too much themselves.
DELEGATION_CHALLENGES = {"Hiring", "Team", "Leadership", "Operations", "Productivity"}
# Challenges about money and runway.
MONEY_CHALLENGES = {"Cash flow", "Fundraising"}
# Challenges about getting demand.
DEMAND_CHALLENGES = {"Getting customers", "Sales", "Marketing"}


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _first(value) -> str:
    items = _as_list(value)
    return items[0] if items else ""


def prose_list(items: list[str]) -> str:
    """['Hiring', 'Cash flow', 'Scaling'] -> 'Hiring, Cash flow and Scaling'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


@dataclass(frozen=True)
class FounderFacts:
    """Everything the founder told us, ready to put in a sentence."""

    first_name: str = ""
    stage: str = ""
    stage_group: str = ""
    building: str = ""
    problem: str = ""
    why: str = ""
    audience: list[str] = field(default_factory=list)
    audience_other: str = ""
    industry: str = ""
    challenges: list[str] = field(default_factory=list)
    goal_90: str = ""
    vision: str = ""
    support: list[str] = field(default_factory=list)
    experience: str = ""
    feeling: str = ""
    feeling_value: str = ""
    reflection: str = ""

    @property
    def complete_enough(self) -> bool:
        """Enough to say something true about them. Without a stage and at least
        one of the substantive free-text answers there is nothing to read."""
        return bool(self.stage and (self.building or self.problem or self.why))

    @property
    def under_strain(self) -> bool:
        return self.feeling_value in UNDER_STRAIN

    @property
    def top_challenge(self) -> str:
        return self.challenges[0] if self.challenges else ""

    def challenge_kinds(self) -> set[str]:
        """Which pressures the founder named, bucketed."""
        picked = set(self.challenges)
        kinds = set()
        if picked & DELEGATION_CHALLENGES:
            kinds.add("delegation")
        if picked & MONEY_CHALLENGES:
            kinds.add("money")
        if picked & DEMAND_CHALLENGES:
            kinds.add("demand")
        return kinds


def facts_from_founder(founder: Founder) -> FounderFacts:
    """Read the onboarding answers off the founder row."""
    stage = getattr(founder, "stage", None)
    full_name = (founder.full_name or "").strip()
    feeling_value = _first(founder.emotional_state)

    return FounderFacts(
        first_name=full_name.split(" ")[0] if full_name else "",
        stage=(getattr(stage, "stage_name", "") or "") if stage else "",
        stage_group=(getattr(stage, "onboarding_label", "") or "") if stage else "",
        building=(founder.building_summary or "").strip(),
        problem=(founder.problem_statement or "").strip(),
        why=(founder.founder_motivation or "").strip(),
        audience=_as_list(founder.customer_segment),
        audience_other=(founder.customer_segment_other or "").strip(),
        industry=(founder.industry or "").strip(),
        challenges=_as_list(founder.current_challenges),
        goal_90=(founder.goal_90_day or "").strip(),
        vision=(founder.vision_1_year or "").strip(),
        support=_as_list(founder.support_preferences),
        experience=EXPERIENCE_LABELS.get(founder.experience_level or "", ""),
        feeling=FEELING_LABELS.get(feeling_value, ""),
        feeling_value=feeling_value,
        reflection=(founder.adaptive_reflection or "").strip(),
    )
