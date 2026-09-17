"""Replace the non-functional industry ranking factor with evidence breadth.

WEIGHT_INDUSTRY_PROBABILITY has never been able to contribute: `root_cause_weights`
carries only `stage_weight` and has no industry column, so an industry-adjusted
prior cannot be read for any root cause. It occupied 0.15 of the ranking budget
while returning a neutral zero.

Measured in a three-persona QA pass, that left evidence count with no influence
on ranking at all: a founder-dependency cause supported by two corroborating
answers ranked below four causes each resting on a single answer.

Moves the 0.15 to WEIGHT_EVIDENCE_BREADTH. The value is not a guess --
scripts/qa/breadth_sensitivity.py reports it as the minimum that lets converging
evidence outrank an isolated severe signal WITHOUT flipping the repeated
single-dimension counter-case or the severity guard.

`check_scoring_weights_sum()` enumerates the factors explicitly, so it has to
count the new code or it would enforce the sum over a strict subset and reject a
valid configuration. The trigger is never disabled: the rule is seeded at 0.0000
first (sum stays 1.0), then a single UPDATE swaps both values, so the invariant
holds at every check point.

Revision ID: d3e8b41c9a52
Revises: c7d18a3f420b
"""
from alembic import op

revision = "d3e8b41c9a52"
down_revision = "c7d18a3f420b"
branch_labels = None
depends_on = None

_FACTORS_WITH_BREADTH = """
        'WEIGHT_CATEGORY_RISK',
        'WEIGHT_CONFIRMATION_STATUS',
        'WEIGHT_STAGE_PROBABILITY',
        'WEIGHT_INDUSTRY_PROBABILITY',
        'WEIGHT_EVIDENCE_BREADTH'
"""
_FACTORS_ORIGINAL = """
        'WEIGHT_CATEGORY_RISK',
        'WEIGHT_CONFIRMATION_STATUS',
        'WEIGHT_STAGE_PROBABILITY',
        'WEIGHT_INDUSTRY_PROBABILITY'
"""


def _sum_check(factors: str) -> str:
    return f"""
CREATE OR REPLACE FUNCTION public.check_scoring_weights_sum()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    v_total DECIMAL(8,4);
BEGIN
    SELECT SUM(rule_value) INTO v_total
    FROM scoring_rules
    WHERE rule_code IN ({factors});

    IF v_total IS NOT NULL AND ABS(v_total - 1.0000) > 0.0001 THEN
        RAISE EXCEPTION 'Scoring weight factors must sum to 1.0. Current sum: %', v_total;
    END IF;
    RETURN NEW;
END;
$function$;
"""


def upgrade() -> None:
    # The reference dump inserts scoring_rules with explicit ids, so a restored
    # database leaves the sequence behind the data and the next insert collides.
    op.execute(
        "SELECT setval('scoring_rules_rule_id_seq', "
        "(SELECT MAX(rule_id) FROM scoring_rules))"
    )
    op.execute(_sum_check(_FACTORS_WITH_BREADTH))
    op.execute(
        "INSERT INTO scoring_rules "
        "(rule_code, rule_name, rule_value, rule_description, source_document, is_active) "
        "VALUES ('WEIGHT_EVIDENCE_BREADTH', 'Evidence Breadth Weight', 0.0000, "
        "'Ranking weight for corroboration across independent dimensions, not raw "
        "answer count. Funded from WEIGHT_INDUSTRY_PROBABILITY, which can never "
        "contribute: root_cause_weights has no industry column.', "
        "'QA cross-case audit A/B/C', true) "
        "ON CONFLICT (rule_code) DO NOTHING"
    )
    # Single statement: the sum is 1.0 before and after, never in between.
    op.execute(
        "UPDATE scoring_rules SET rule_value = CASE rule_code "
        "WHEN 'WEIGHT_INDUSTRY_PROBABILITY' THEN 0.0000 "
        "WHEN 'WEIGHT_EVIDENCE_BREADTH' THEN 0.1500 END "
        "WHERE rule_code IN ('WEIGHT_INDUSTRY_PROBABILITY','WEIGHT_EVIDENCE_BREADTH')"
    )


def downgrade() -> None:
    # Reverse order, same invariant: restore the budget first, then narrow the
    # check, then drop the row -- so the sum is 1.0 at every point.
    op.execute(
        "UPDATE scoring_rules SET rule_value = CASE rule_code "
        "WHEN 'WEIGHT_INDUSTRY_PROBABILITY' THEN 0.1500 "
        "WHEN 'WEIGHT_EVIDENCE_BREADTH' THEN 0.0000 END "
        "WHERE rule_code IN ('WEIGHT_INDUSTRY_PROBABILITY','WEIGHT_EVIDENCE_BREADTH')"
    )
    op.execute(_sum_check(_FACTORS_ORIGINAL))
    op.execute("DELETE FROM scoring_rules WHERE rule_code = 'WEIGHT_EVIDENCE_BREADTH'")
