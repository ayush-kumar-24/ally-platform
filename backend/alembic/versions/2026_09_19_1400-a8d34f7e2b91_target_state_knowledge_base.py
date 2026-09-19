"""Target-state context on `founders`, and the capability requirements it selects.

WHAT THIS STEP ADDS, AND WHAT IT DELIBERATELY DOES NOT. Two profile columns and
one reference table that answers exactly one question:

    "For this founder's context and intended destination, which capabilities are
     required, at what level, and why?"

It does NOT look at a single answer the founder gave. There is no comparison
with evidence here, no MISSING, no GAP, no readiness verdict -- those need
current-state evidence, which is Step 7, and the engine that compares them,
which is Step 8. A requirement is a statement about the DESTINATION.

TARGET REVENUE IS NOT A DIAGNOSIS, and the schema is what enforces it. The band
and horizon are inputs to a row lookup and nothing else; no numeric difference
between current and target revenue is computed anywhere, and there is no column
in which such a number could be stored. A founder who states a 10x target and
answers nothing produces a set of requirements and zero findings.

WHY target_revenue_band IS NOT CurrentRevenue. `founders_current_revenue_check`
tops out at `above_1Cr`. That is adequate for describing where a founder IS and
useless for describing where they are GOING: a 1.5Cr target and a 10Cr target
would be the same band, so the column could not select different requirement
rows -- which is its only job. The new vocabulary keeps the lower four band
names IDENTICAL so the two sit on one ordered ladder (schemas/founder.py
REVENUE_LADDER) and extends upward. `current_revenue` is not touched.

NULL IS WILDCARD, AND UNKNOWN STILL FAILS OPEN. A requirement row with NULL
industry applies to every industry. A founder whose industry is unknown still
matches every wildcard row -- unknown context narrows nothing and fabricates
nothing. It only means the more specific rows cannot activate. This is the same
rule Step 4 established for question applicability, applied to requirements.

THE CASCADE IS RESOLVED IN PYTHON, NOT IN SQL. See
app/api/v1/diagnosis/target_state.py. The table is a rules table; the specificity
ordering and the ambiguity error belong with the code that has to explain
itself, not in a query nobody can read.

Additive and reversible. The two columns are nullable with no backfill: every
existing founder keeps NULL, which reads as "we never asked", and a founder with
no target simply resolves to no requirements.
"""

from alembic import op
import sqlalchemy as sa

revision = "a8d34f7e2b91"
down_revision = "f2a91c3d7b58"
branch_labels = None
depends_on = None

#: Mirrors schemas/founder.TargetRevenueBand. Inlined rather than imported: a
#: migration is a snapshot and must keep working when the literal later changes.
TARGET_REVENUE_BANDS = (
    "under_1L", "1L_5L", "5L_25L", "25L_1Cr", "1Cr_5Cr", "5Cr_25Cr", "above_25Cr",
)
TARGET_TIME_HORIZONS = ("6_months", "12_months", "24_months", "36_months_plus")
NECESSITY = ("core", "contextual")


#: The seed knowledge base. CURATED REFERENCE DATA -- never LLM-generated.
#:
#: (capability_code, industry_code, business_model, from_stage_order,
#:  target_revenue_band, target_time_horizon, required_level, necessity,
#:  rationale)
#:
#: None = wildcard. Organised as four bands of baseline requirements plus a
#: small number of business-model, industry, horizon and stage modifiers that
#: exist to exercise -- and to prove -- the cascade. Deliberately NOT a full
#: cross product: 30 industries x 6 models x 8 stages x 7 bands x 4 horizons is
#: 40,320 contexts, and a row that nobody can defend is worse than no row.
REQUIREMENTS = [
    ('GTM-ICP', None, None, None, '25L_1Cr', None, 2, 'core', 'Below a crore, growth still comes from knowing exactly who buys; a vague target customer is the most common reason revenue plateaus here.'),
    ('GTM-SALES', None, None, None, '25L_1Cr', None, 2, 'core', 'The founder can still be the seller at this size, but the process has to exist outside their head or it cannot be repeated on a bad month.'),
    ('PRD-DISCOVER', None, None, None, '25L_1Cr', None, 2, 'core', "Revenue at this band is still fragile; build decisions have to cite evidence from real customers rather than the founder's conviction."),
    ('FIN-VIS', None, None, None, '25L_1Cr', None, 2, 'core', 'You cannot manage toward a crore on numbers you cannot see on a schedule.'),
    ('FIN-UNIT', None, None, None, '25L_1Cr', None, 2, 'core', 'Knowing what one unit of business earns and costs is what separates growing revenue from growing losses.'),
    ('STR-POSITION', None, None, None, '25L_1Cr', None, 2, 'contextual', 'Being able to say why you are the right choice becomes load-bearing once you are selling to strangers rather than your network.'),
    ('GTM-ICP', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Segment clarity is what lets acquisition be delegated; without it, only the founder knows who to chase.'),
    ('GTM-ACQ', None, None, None, '1Cr_5Cr', None, 2, 'core', 'At this band referrals and founder network stop being enough; at least one channel has to work on purpose.'),
    ('GTM-SALES', None, None, None, '1Cr_5Cr', None, 2, 'core', 'A documented sales process is the precondition for anyone other than the founder ever closing.'),
    ('GTM-PIPE', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Forecasting becomes necessary once the business is committing to spend against expected revenue.'),
    ('FND-DELEG', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Decisions need owners other than the founder, or the founder becomes the ceiling on throughput.'),
    ('OPS-PROCESS', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Core work has to happen the same way twice before more people can be added to it.'),
    ('FIN-VIS', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Monthly numbers on a schedule, trusted enough to decide on.'),
    ('FIN-UNIT', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Margin by product or segment is what tells you which part of the growth to fund.'),
    ('FIN-CASH', None, None, None, '1Cr_5Cr', None, 2, 'core', 'Growth consumes cash; runway has to be forecast rather than discovered.'),
    ('STR-PLAN', None, None, None, '1Cr_5Cr', None, 2, 'contextual', 'Stated goals for a period, and knowing whether you are hitting them.'),
    ('GTM-SALES', None, None, None, '5Cr_25Cr', None, 3, 'core', 'The sales process has to be owned and improved by someone whose job it is, not maintained by the founder between other things.'),
    ('GTM-OWN', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Someone other than the founder has to be able to win business. This is the single capability that most often blocks this band.'),
    ('GTM-PIPE', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Pipeline has to be visible to the person accountable for it, not only to the founder.'),
    ('GTM-ACQ', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Acquisition has to run as a system with a named owner and a budget.'),
    ('GTM-RETAIN', None, None, None, '5Cr_25Cr', None, 2, 'core', 'At this size, churn quietly cancels out new sales unless it is measured and managed.'),
    ('FND-DELEG', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Routine decisions must not reach the founder at all.'),
    ('FND-INDEP', None, None, None, '5Cr_25Cr', None, 3, 'core', 'The business has to keep running when the founder is away, or every holiday is a risk event.'),
    ('FND-TIME', None, None, None, '5Cr_25Cr', None, 2, 'core', "The founder's week has to have a deliberate shape, or it fills with whatever is loudest."),
    ('ORG-ROLES', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Written scopes and unambiguous ownership -- the prerequisite for holding anyone accountable.'),
    ('ORG-HIRE', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Hiring becomes a repeated act at this band; doing it by instinct each time is how a team gets expensive and uneven.'),
    ('ORG-PERF', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Performance has to be discussed on a schedule rather than when something goes wrong.'),
    ('ORG-CADENCE', None, None, None, '5Cr_25Cr', None, 2, 'core', 'A rhythm for deciding and informing, so information does not route through the founder.'),
    ('OPS-PROCESS', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Processes need an owner who improves them, not just a founder who remembers them.'),
    ('OPS-SOP', None, None, None, '5Cr_25Cr', None, 2, 'core', 'How-to knowledge outside individual heads, or every departure is a crisis.'),
    ('OPS-MONITOR', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Operational health visible without asking someone.'),
    ('FIN-VIS', None, None, None, '5Cr_25Cr', None, 3, 'core', 'Reporting owned by someone competent, on a cycle, and used for decisions.'),
    ('FIN-CASH', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Cash position known at any time, with a tight scenario already thought through.'),
    ('FIN-PLAN', None, None, None, '5Cr_25Cr', None, 2, 'core', 'A budget that spending is reviewed against.'),
    ('STR-POSITION', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Positioning consistent across channels, because the founder is no longer in every conversation.'),
    ('STR-PLAN', None, None, None, '5Cr_25Cr', None, 2, 'core', 'Goals for a period, with risks identified and owned.'),
    ('FND-INDEP', None, None, None, 'above_25Cr', None, 3, 'core', 'Nothing critical may depend on the founder personally.'),
    ('FND-LEAD', None, None, None, 'above_25Cr', None, 3, 'core', 'The founder leads through others; doing the work themselves is now the failure mode.'),
    ('ORG-ROLES', None, None, None, 'above_25Cr', None, 3, 'core', 'Ownership of each outcome is unambiguous and revisited as the business changes.'),
    ('ORG-CADENCE', None, None, None, 'above_25Cr', None, 3, 'core', 'The operating rhythm has to survive busy periods without the founder enforcing it.'),
    ('ORG-CULTURE', None, None, None, 'above_25Cr', None, 2, 'core', 'At this size retention costs are real and culture stops being implicit.'),
    ('OPS-QUALITY', None, None, None, 'above_25Cr', None, 2, 'core', 'Defects have to be caught before the customer finds them, systematically.'),
    ('OPS-MONITOR', None, None, None, 'above_25Cr', None, 3, 'core', 'Monitoring that drives action, owned by someone.'),
    ('PRD-DELIVERY', None, None, None, 'above_25Cr', None, 2, 'core', 'What is promised ships when it was said to, without heroics.'),
    ('GTM-PIPE', None, 'B2B', None, '1Cr_5Cr', None, 3, 'core', 'B2B cycles are long enough that pipeline has to be owned and forecast, not reviewed occasionally.'),
    ('GTM-ACQ', None, 'B2C', None, '1Cr_5Cr', None, 3, 'core', 'A B2C business at this band lives or dies on repeatable paid or organic acquisition, so it needs an owner rather than a process.'),
    ('GTM-RETAIN', None, 'B2C', None, '1Cr_5Cr', None, 2, 'core', 'Repeat purchase is the economics of B2C; without measurement, acquisition spend is unbounded.'),
    ('GTM-RETAIN', 'saas', None, None, '1Cr_5Cr', None, 3, 'core', 'Retention IS the business model in SaaS; it has to be owned and improved, not merely measured.'),
    ('GTM-RETAIN', 'saas', 'B2C', None, '1Cr_5Cr', None, 3, 'core', "A B2C SaaS business is hit by both rules above -- retention is the model AND consumer churn is higher -- so the combined case is stated explicitly rather than left for the resolver to guess between them."),
 ('FIN-UNIT', 'ecommerce_d2c', None, None, '1Cr_5Cr', None, 3, 'core', 'In D2C, contribution margin per order decides whether growth is progress; it needs a dedicated owner.'),
    ('FIN-VIS', 'fintech', None, None, '1Cr_5Cr', None, 3, 'core', 'Fintech reporting is subject to external scrutiny from early on, so visibility has to be owned rather than adequate.'),
    ('FND-INDEP', None, None, None, '5Cr_25Cr', '6_months', 3, 'core', 'Six months is not long enough to build founder independence from scratch; it has to be close to true already.'),
    ('OPS-SOP', None, None, None, '5Cr_25Cr', '6_months', 3, 'core', 'With this little time, documentation has to be current and owned rather than something to start.'),
    ('GTM-OWN', None, None, None, '5Cr_25Cr', '12_months', 3, 'core', 'Twelve months means hiring and ramping a seller now; the capability cannot wait for revenue to justify it.'),
    ('PRD-DISCOVER', None, None, 2, '1Cr_5Cr', None, 2, 'core', 'A founder still at or past Validation reaching for 1-5Cr has not yet proven the thing they intend to scale; discovery stays load-bearing.'),
]


def upgrade() -> None:
    # --- target context on the profile ------------------------------------
    op.add_column("founders", sa.Column("target_revenue_band", sa.String(length=50),
                                        nullable=True))
    op.add_column("founders", sa.Column("target_time_horizon", sa.String(length=30),
                                        nullable=True))
    # Named to match the existing founders_*_check convention, and written the
    # same way as founders_current_revenue_check so the two read alike.
    op.create_check_constraint(
        "founders_target_revenue_band_check", "founders",
        sa.text("target_revenue_band IS NULL OR target_revenue_band IN "
                + _sql_tuple(TARGET_REVENUE_BANDS)),
    )
    op.create_check_constraint(
        "founders_target_time_horizon_check", "founders",
        sa.text("target_time_horizon IS NULL OR target_time_horizon IN "
                + _sql_tuple(TARGET_TIME_HORIZONS)),
    )

    # --- the knowledge base ------------------------------------------------
    op.create_table(
        "capability_requirements",
        sa.Column("requirement_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("capability_id", sa.Integer(), nullable=False),
        # Context predicate. Every one of these is NULLABLE, and NULL means
        # "applies whatever this founder's value is" -- not "applies when this
        # is unknown". The distinction is the whole cascade.
        sa.Column("industry_code", sa.String(length=20), nullable=True),
        sa.Column("business_model", sa.String(length=100), nullable=True),
        # Lower bound, inclusive: a row with from_stage_order = 2 applies to a
        # founder at stage 2 or later. Chosen over an exact match so the table
        # does not need a row per stage; the tightest bound wins, which is what
        # keeps it deterministic. See target_state.resolve_requirements.
        sa.Column("from_stage_order", sa.Integer(), nullable=True),
        sa.Column("target_revenue_band", sa.String(length=50), nullable=True),
        sa.Column("target_time_horizon", sa.String(length=30), nullable=True),
        # What is required.
        sa.Column("required_level", sa.SmallInteger(), nullable=False),
        sa.Column("necessity", sa.String(length=16), nullable=False),
        # Shown to the founder. A requirement nobody can explain is a rule
        # nobody can challenge, so this is NOT NULL.
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_document", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("requirement_id", name="capability_requirements_pkey"),
        sa.ForeignKeyConstraint(["capability_id"], ["capabilities.capability_id"],
                                ondelete="CASCADE",
                                name="capability_requirements_capability_id_fkey"),
        # The level scale is CapabilityLevel (0-3) from Step 5. Constrained here
        # so a bad row cannot reach the resolver at all.
        sa.CheckConstraint("required_level BETWEEN 0 AND 3",
                           name="capability_requirements_required_level_check"),
        sa.CheckConstraint("necessity IN ('core', 'contextual')",
                           name="capability_requirements_necessity_check"),
        sa.CheckConstraint("from_stage_order IS NULL OR from_stage_order BETWEEN 1 AND 8",
                           name="capability_requirements_from_stage_order_check"),
        # One row per (capability, exact context). Two rows with the same
        # predicate are a curation mistake, and the resolver would have to call
        # them ambiguous -- so the database refuses them instead. NULLS NOT
        # DISTINCT is what makes the constraint see two wildcards as equal.
        sa.UniqueConstraint(
            "capability_id", "industry_code", "business_model", "from_stage_order",
            "target_revenue_band", "target_time_horizon",
            name="uq_capability_requirements_context",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("idx_capability_requirements_capability",
                    "capability_requirements", ["capability_id"])
    op.create_index("idx_capability_requirements_band",
                    "capability_requirements", ["target_revenue_band"])

    _seed()


def _sql_tuple(values) -> str:
    return "(" + ", ".join("'" + v + "'" for v in values) + ")"


def _seed() -> None:
    conn = op.get_bind()
    capability_ids = {
        code: cid for code, cid in conn.execute(
            sa.text("SELECT capability_code, capability_id FROM capabilities")).all()
    }
    missing = {r[0] for r in REQUIREMENTS} - set(capability_ids)
    if missing:
        raise RuntimeError(
            "capability_requirements seed references capabilities that do not "
            f"exist: {sorted(missing)}"
        )
    for (code, industry, model, stage, band, horizon,
         level, necessity, rationale) in REQUIREMENTS:
        conn.execute(sa.text(
            "INSERT INTO capability_requirements"
            " (capability_id, industry_code, business_model, from_stage_order,"
            "  target_revenue_band, target_time_horizon, required_level,"
            "  necessity, rationale)"
            " VALUES (:cap, :ind, :bm, :stage, :band, :hz, :lvl, :nec, :why)"
        ), {"cap": capability_ids[code], "ind": industry, "bm": model,
            "stage": stage, "band": band, "hz": horizon, "lvl": level,
            "nec": necessity, "why": rationale})


def downgrade() -> None:
    op.drop_table("capability_requirements")
    op.drop_constraint("founders_target_time_horizon_check", "founders", type_="check")
    op.drop_constraint("founders_target_revenue_band_check", "founders", type_="check")
    op.drop_column("founders", "target_time_horizon")
    op.drop_column("founders", "target_revenue_band")
