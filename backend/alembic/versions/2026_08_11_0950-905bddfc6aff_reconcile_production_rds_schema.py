"""reconcile production rds schema

Revision ID: 905bddfc6aff
Revises: c4a71fe38b52
Create Date: 2026-08-11 09:50:31.425608

Reconciles database objects that exist in the RDS target schema/current
application contract but are absent from production RDS.

This revision currently handles:
1. chronic_state_inference
2. psychological_state_signals
3. session_state_bands
4. founder_memory
5. founder_memory_events
6. Exact prepared reference data for the first three tables
7. Sequence resets after explicit-ID seed inserts

Functions, triggers and RLS are added in subsequent reviewed sections before
this migration is deployed to production.
"""

from __future__ import annotations

import re
from typing import Sequence, Union

from alembic import op


revision: str = "905bddfc6aff"
down_revision: Union[str, Sequence[str], None] = "c4a71fe38b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Paste the COMPLETE prepared RDS seed SQL between these triple quotes.
# Required data:
#  5 rows     chronic_state_inference      
#  20 rows    psychological_state_signals  
#  4 rows     session_state_bands            
#
# Do not leave (...) placeholders here.

_REFERENCE_DATA_SQL = r"""
INSERT INTO session_state_bands (band_id, meaning, score_max, score_min, created_at, session_state, source_document, reliability_factor, report_framing_adjustment, closing_protocol_adjustment) VALUES ('1', 'Founder is giving honest, reflective answers. Low performance mode. Psychologically safe.', '10', '0', '2026-07-26T05:12:49.185626+00:00', 'Open and Engaged', 'Psychological State Scoring Table — Session State Scoring', '1.00', 'Report uses direct, specific language. No additional emotional framing needed.', 'Standard closing — three next steps, forward-focused.');

INSERT INTO session_state_bands (band_id, meaning, score_max, score_min, created_at, session_state, source_document, reliability_factor, report_framing_adjustment, closing_protocol_adjustment) VALUES ('2', 'Founder is giving mostly honest answers but filtering some things. Some performance mode present.', '20', '11', '2026-07-26T05:12:49.185626+00:00', 'Mildly Guarded', 'Psychological State Scoring Table — Session State Scoring', '0.95', 'Report opens with a brief acknowledgement of the courage it takes to reflect honestly. Next steps are framed as experiments, not obligations.', 'Close with a normalising statement before next steps. "The things you have shared today are more common than you might think."');

INSERT INTO session_state_bands (band_id, meaning, score_max, score_min, created_at, session_state, source_document, reliability_factor, report_framing_adjustment, closing_protocol_adjustment) VALUES ('3', 'Founder is substantially filtering answers. Performance mode is dominant. Some withdrawal signals present.', '35', '21', '2026-07-26T05:12:49.185626+00:00', 'Significantly Guarded', 'Psychological State Scoring Table — Session State Scoring', '0.85', 'Report leads with empathy statement. Next steps are framed as options, not actions. Report explicitly names that clarity often takes more than one conversation.', 'Before closing, ask: "Is there anything you have wanted to say today that you have not said?" Allow silence.');

INSERT INTO session_state_bands (band_id, meaning, score_max, score_min, created_at, session_state, source_document, reliability_factor, report_framing_adjustment, closing_protocol_adjustment) VALUES ('4', 'Founder is experiencing significant psychological distress. Diagnostic accuracy is low because answers are heavily filtered by emotional state. Also triggered by any single Distress Signal from State D regardless of cumulative score.', NULL, '36', '2026-07-26T05:12:49.185626+00:00', 'High Distress', 'Psychological State Scoring Table — Session State Scoring', NULL, 'Report is de-prioritised. Lead with acknowledgement of difficulty. Next steps include one psychological or support-related recommendation before any business recommendation.', 'Do not complete the standard diagnostic close. Shift to: "Before I share any next steps — I want to check in. How are you feeling right now, honestly?" Offer to pause and resume.');

INSERT INTO chronic_state_inference (created_at, chronic_state, source_document, chronic_state_id, diagnostic_impact, acute_signal_pattern_required, recommended_report_adjustment, question_bank_confirmation_signals) VALUES ('2026-07-26T05:12:49.185626+00:00', 'Burnout — Stage 1 (Emotional Exhaustion)', 'Psychological State Scoring Table — Chronic State Inference', '1', 'All answers are lower energy than the founder actual capability. Business assessments may be more pessimistic than reality.', 'Withdrawal signals score 8+. Stress signals score 6+. At least one "tired of this" type phrase detected.', 'Acknowledge exhaustion explicitly in the report. Frame next steps as "first, recover capacity — then address the business." Include one recovery-oriented next step.', 'Q7 (stress frequency) rated 4-5. Q12 (energy) rated 1-2. Q6 (work-life balance) describes 7-day work weeks.');

INSERT INTO chronic_state_inference (created_at, chronic_state, source_document, chronic_state_id, diagnostic_impact, acute_signal_pattern_required, recommended_report_adjustment, question_bank_confirmation_signals) VALUES ('2026-07-26T05:12:49.185626+00:00', 'Burnout — Stage 2 (Cynicism / Detachment)', 'Psychological State Scoring Table — Chronic State Inference', '2', 'Founder is disengaged from outcomes. Business assessment accuracy is moderate — they see problems but understate their own agency to fix them.', 'Session state score 30+. Flat affirmatives present. "I do not care anymore" type language detected.', 'Report leads with re-engagement rather than problem solving. Ask "what originally made this matter to you" before recommending any action.', 'Q11 (motivation when slow) describes potential quit. Q4 (stress) rated 5. Q21 (goal realism) rated 1-2.');

INSERT INTO chronic_state_inference (created_at, chronic_state, source_document, chronic_state_id, diagnostic_impact, acute_signal_pattern_required, recommended_report_adjustment, question_bank_confirmation_signals) VALUES ('2026-07-26T05:12:49.185626+00:00', 'Imposter Syndrome — Active', 'Psychological State Scoring Table — Chronic State Inference', '3', 'Answers to capability questions are unreliable — understated in some areas, overstated in others. Founder may not accurately assess their own strengths.', 'Defensiveness signals score 8+. Credential leading present 3+ times. Comparison language detected.', 'Report explicitly names a strength the founder demonstrated during the session before discussing gaps. Frame gaps as skills to build, not traits they lack.', 'Q18 (biggest weakness) answered as "none." Q20 (proud achievement outside startup) scored "nothing."');

INSERT INTO chronic_state_inference (created_at, chronic_state, source_document, chronic_state_id, diagnostic_impact, acute_signal_pattern_required, recommended_report_adjustment, question_bank_confirmation_signals) VALUES ('2026-07-26T05:12:49.185626+00:00', 'Fear of Failure — Dominant', 'Psychological State Scoring Table — Chronic State Inference', '4', 'Founder systematically avoids the most important actions because they carry the highest failure risk. Root causes that involve bold action are identified but founder is unlikely to act on them without psychological support first.', 'Avoidance hedging score 6+. Catastrophic thinking detected. Passive voice score 6+.', 'First next step in report is always low-risk and high-certainty. Build momentum before recommending the difficult action. Frame every recommendation as an experiment with a clear exit condition.', 'Q8 (failure scenario) describes quitting. Q9 (risk tolerance) rated 1-2. Q3 (biggest fear) acknowledges fear of failure as dominant.');

INSERT INTO chronic_state_inference (created_at, chronic_state, source_document, chronic_state_id, diagnostic_impact, acute_signal_pattern_required, recommended_report_adjustment, question_bank_confirmation_signals) VALUES ('2026-07-26T05:12:49.185626+00:00', 'Identity Fusion — Severe', 'Psychological State Scoring Table — Chronic State Inference', '5', 'Founder cannot assess the business objectively because the business is their identity. Diagnosis accuracy is lowest. They may minimise serious problems (protecting identity) or catastrophise minor setbacks (identity attack).', 'Identity collapse language detected once or more. Session state score 30+.', 'Report must separate the founder from the business explicitly: "The business has challenges. You are not those challenges." Avoid language that fuses outcomes with character. All next steps focus on action, not self-assessment.', 'Q2 (response to setbacks) describes taking it personally. Q15 (success definition) includes only external outcomes. Q8 describes never trying again.');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '1', '2026-07-26T05:12:17.653652+00:00', 'A', 'Stress / Hyperactivation', 'Speed / urgency language', '''We need to move fast,'' ''There is no time,'' ''Just tell me what to do''', 'Psychological State Scoring Table — Acute State Detection', '6 points in one response', '2', 'Slow the pace. Acknowledge time pressure before continuing. Use one question only.', 'Phrases indicating rush, pressure, no time');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '2', '2026-07-26T05:12:17.653652+00:00', 'A', 'Stress / Hyperactivation', 'Absolutist language', '''This will definitely work,'' ''That is impossible,'' ''We can never recover''', 'Psychological State Scoring Table — Acute State Detection', '4 points across 3 responses', '2', 'Gently test the absolute. ''When you say never — has there been a time where something similar has worked?''', 'Always / never / impossible / definitely in uncertain contexts');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '3', '2026-07-26T05:12:17.653652+00:00', 'A', 'Stress / Hyperactivation', 'Topic jumping / fragmentation', 'Starts answering Q about sales, pivots to team conflict, pivots to funding unprompted', 'Psychological State Scoring Table — Acute State Detection', '3 points in one response', '3', 'Anchor the founder back. ''Let us stay with the sales question for a moment — you mentioned...''', 'Answers jump between unrelated topics without resolution');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '4', '2026-07-26T05:12:17.653652+00:00', 'A', 'Stress / Hyperactivation', 'Excessive detail with no conclusion', '3+ paragraphs of background before stating the actual problem', 'Psychological State Scoring Table — Acute State Detection', '6 points in session', '2', 'Summarise what has been said and ask a direct closed question to anchor.', 'Over-explains context without reaching a point');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '5', '2026-07-26T05:12:17.653652+00:00', 'A', 'Stress / Hyperactivation', 'Rapid escalation language', '''If this fails my family loses everything,'' ''I am out of options''', 'Psychological State Scoring Table — Acute State Detection', '4 points (single instance)', '4', 'Pause. Acknowledge. ''That sounds like a really heavy weight to carry. Before we go further — how are you doing?''', 'Sudden shift to extreme language about stakes');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '6', '2026-07-26T05:12:17.653652+00:00', 'B', 'Withdrawal / Shutdown', 'Minimal responses', '''Fine.'' / ''Not sure.'' / ''It is okay.''', 'Psychological State Scoring Table — Acute State Detection', '6 points across 3 responses', '2', 'Normalise. ''It is completely okay to say you are not sure. What does it actually feel like right now?''', 'One word or one sentence answers to open questions');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '7', '2026-07-26T05:12:17.653652+00:00', 'B', 'Withdrawal / Shutdown', 'Deflection hedging', '''Maybe,'' ''Perhaps,'' ''I think possibly,'' ''It could be''', 'Psychological State Scoring Table — Acute State Detection', '5 points in one response', '1', 'Ask for specificity gently. ''If you had to choose one — which feels most true?''', 'Avoids direct answers with vague qualifiers');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '8', '2026-07-26T05:12:17.653652+00:00', 'B', 'Withdrawal / Shutdown', 'Flat affirmatives', '''Yes,'' ''Exactly,'' ''Right,'' repeated without elaboration', 'Psychological State Scoring Table — Acute State Detection', '6 points across 3 responses', '2', 'Break the pattern. ''Tell me something that is not going well — what is the hardest thing right now?''', 'Agrees with everything without engagement');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '9', '2026-07-26T05:12:17.653652+00:00', 'B', 'Withdrawal / Shutdown', 'Passive voice / third-person deflection', '''Mistakes were made,'' ''Things did not go as planned,'' ''The team decided''', 'Psychological State Scoring Table — Acute State Detection', '3 points in one response', '3', 'Bring the founder back in. ''When you say the team decided — what was your role in that?''', 'Removes self from events');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '10', '2026-07-26T05:12:17.653652+00:00', 'B', 'Withdrawal / Shutdown', 'Repeated reassurance phrases', '''It is fine,'' ''We will figure it out,'' ''Not a big deal'' repeated 3+ times', 'Psychological State Scoring Table — Acute State Detection', '6 points across session', '2', 'Name it without confronting it. ''You have said it is fine a few times — I want to make sure I am not missing something important.''', 'Identical reassuring phrases across multiple answers');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '11', '2026-07-26T05:12:17.653652+00:00', 'C', 'Defensiveness / Performance Mode', 'Positive superlative overuse', '''This is incredible,'' ''We are absolutely going to crush it,'' ''Revolutionary product''', 'Psychological State Scoring Table — Acute State Detection', '8 points in session', '2', 'Test the optimism gently. ''That sounds exciting. What is the one thing that could go wrong that worries you most?''', 'Excessive optimism and enthusiasm about uncertain outcomes');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '12', '2026-07-26T05:12:17.653652+00:00', 'C', 'Defensiveness / Performance Mode', 'Reframing failures as lessons unprompted', '''We actually learned so much from that failure,'' ''It was a blessing in disguise''', 'Psychological State Scoring Table — Acute State Detection', '3 points in one response', '3', 'Acknowledge the reframe, then go deeper. ''That is a healthy perspective. What did it actually feel like in the moment it happened?''', 'Proactively spins setbacks before being asked');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '13', '2026-07-26T05:12:17.653652+00:00', 'C', 'Defensiveness / Performance Mode', 'Credential leading', '''We won X award,'' ''We were covered in Forbes,'' ''Our investors include...''', 'Psychological State Scoring Table — Acute State Detection', '6 points in session', '2', 'Validate, then redirect. ''That is great context. Tell me more about what the business looks like day to day.''', 'Leads with credentials, logos, or social proof before answering diagnostic questions');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '14', '2026-07-26T05:12:17.653652+00:00', 'C', 'Defensiveness / Performance Mode', 'Answering different question', 'Question about sales pipeline → answer about product vision', 'Psychological State Scoring Table — Acute State Detection', '3 points across 3 responses', '3', 'Name it kindly. ''I want to make sure I understood — specifically about the pipeline, how many active conversations do you have right now?''', 'Consistently answers the question they wish they were asked, not the one asked');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '15', '2026-07-26T05:12:17.653652+00:00', 'C', 'Defensiveness / Performance Mode', 'Advisor dropping', '''Our advisor who was ex-Google said...'' / ''Sequoia told us...''', 'Psychological State Scoring Table — Acute State Detection', '6 points in session', '2', 'Accept it without dwelling. Return to the diagnostic question without further attention to the credential.', 'Mentions high-profile advisors or networks to establish credibility under pressure');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '16', '2026-07-26T05:12:17.653652+00:00', 'D', 'Emotional Distress / Crisis Signals', 'Identity collapse language', '''I am a failure,'' ''I cannot do this,'' ''I was not meant for this''', 'Psychological State Scoring Table — Acute State Detection', '5 points (single instance)', '5', 'STOP the diagnostic. Shift fully to empathetic listening. ''That sounds incredibly hard. Can you tell me more about how you are feeling?''', 'Conflates personal failure with business failure');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '17', '2026-07-26T05:12:17.653652+00:00', 'D', 'Emotional Distress / Crisis Signals', 'Helplessness / hopelessness language', '''Nothing will work,'' ''I have tried everything,'' ''It is pointless''', 'Psychological State Scoring Table — Acute State Detection', '5 points (single instance)', '5', 'STOP the diagnostic. Acknowledge. ''I hear you. This sounds really overwhelming. You do not have to have all the answers right now.''', 'Expresses no belief that anything can improve');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '18', '2026-07-26T05:12:17.653652+00:00', 'D', 'Emotional Distress / Crisis Signals', 'Isolation language', '''No one understands,'' ''I cannot tell anyone,'' ''I am completely alone in this''', 'Psychological State Scoring Table — Acute State Detection', '4 points (single instance)', '4', 'Normalise and gently connect. ''Many founders feel this way and it is one of the hardest parts. Do you have anyone you trust outside the business?''', 'Expresses being completely alone with the problem');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '19', '2026-07-26T05:12:17.653652+00:00', 'D', 'Emotional Distress / Crisis Signals', 'Mentions of sleep deprivation or health neglect', '''I have not slept properly in weeks,'' ''I cannot remember the last time I ate a proper meal''', 'Psychological State Scoring Table — Acute State Detection', '3 points (single instance)', '3', 'Acknowledge physical state before continuing. ''Before we go further — how long has it been like this? Your capacity to think clearly matters here.''', 'Reveals extended period of physical neglect');

INSERT INTO psychological_state_signals (is_active, signal_id, created_at, state_code, state_name, signal_type, example_phrases, source_document, trigger_threshold, score_per_instance, protocol_adjustment, observable_indicator) VALUES ('true', '20', '2026-07-26T05:12:17.653652+00:00', 'D', 'Emotional Distress / Crisis Signals', 'Catastrophic certainty', '''We are going to fail,'' ''This is over,'' ''There is no way out''', 'Psychological State Scoring Table — Acute State Detection', '5 points (single instance)', '5', 'STOP the diagnostic. Acknowledge without agreeing or disagreeing. Do not offer solutions. Ask one question: ''What would need to be true for things to feel even slightly more manageable?''', 'States extremely negative outcomes as definite facts');
"""


def _split_sql_statements(sql: str) -> list[str]:
    """Split PostgreSQL SQL into statements while respecting quoted strings."""
    statements: list[str] = []
    current: list[str] = []

    i = 0
    length = len(sql)
    in_single = False
    in_double = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: str | None = None

    while i < length:
        ch = sql[i]

        if in_line_comment:
            current.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            current.append(ch)
            if ch == "*" and i + 1 < length and sql[i + 1] == "/":
                current.append("/")
                i += 2
                in_block_comment = False
                continue
            i += 1
            continue

        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                current.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            current.append(ch)
            i += 1
            continue

        if in_single:
            current.append(ch)
            if ch == "'":
                if i + 1 < length and sql[i + 1] == "'":
                    current.append("'")
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if in_double:
            current.append(ch)
            if ch == '"':
                if i + 1 < length and sql[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                in_double = False
            i += 1
            continue

        if ch == "-" and i + 1 < length and sql[i + 1] == "-":
            current.extend(["-", "-"])
            i += 2
            in_line_comment = True
            continue

        if ch == "/" and i + 1 < length and sql[i + 1] == "*":
            current.extend(["/", "*"])
            i += 2
            in_block_comment = True
            continue

        if ch == "'":
            current.append(ch)
            in_single = True
            i += 1
            continue

        if ch == '"':
            current.append(ch)
            in_double = True
            i += 1
            continue

        if ch == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[i:])
            if match:
                dollar_tag = match.group(0)
                current.append(dollar_tag)
                i += len(dollar_tag)
                continue

        if ch == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)

    return statements


def _run_reference_data() -> None:
    """Execute the exact prepared reference-data SQL."""
    if (
        "PASTE THE COMPLETE PREPARED 29-ROW RDS REFERENCE DATA HERE"
        in _REFERENCE_DATA_SQL
        or "(...)" in _REFERENCE_DATA_SQL
        or "VALUES (...)" in _REFERENCE_DATA_SQL
    ):
        raise RuntimeError(
            "Reference data is still a placeholder in migration 905bddfc6aff."
        )

    statements = _split_sql_statements(_REFERENCE_DATA_SQL)
    if not statements:
        raise RuntimeError(
            "Reference data block is empty in migration 905bddfc6aff."
        )

    for statement in statements:
        op.execute(statement)


def upgrade() -> None:
    # 1. Sequences
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS
        chronic_state_inference_chronic_state_id_seq
    """)

    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS
        psychological_state_signals_signal_id_seq
    """)

    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS
        session_state_bands_band_id_seq
    """)

    # 2. chronic_state_inference
    op.execute("""
        CREATE TABLE chronic_state_inference (
            chronic_state_id int4 NOT NULL
                DEFAULT nextval(
                    'chronic_state_inference_chronic_state_id_seq'::regclass
                ),
            chronic_state text NOT NULL,
            acute_signal_pattern_required text NOT NULL,
            question_bank_confirmation_signals text NOT NULL,
            diagnostic_impact text NOT NULL,
            recommended_report_adjustment text NOT NULL,
            source_document text DEFAULT 'Doc 10 Part 3'::text,
            created_at timestamptz DEFAULT now(),
            PRIMARY KEY (chronic_state_id)
        )
    """)

    # 3. psychological_state_signals
    op.execute("""
        CREATE TABLE psychological_state_signals (
            signal_id int4 NOT NULL
                DEFAULT nextval(
                    'psychological_state_signals_signal_id_seq'::regclass
                ),
            state_code text NOT NULL,
            state_name text NOT NULL,
            signal_type text NOT NULL,
            observable_indicator text NOT NULL,
            example_phrases text,
            score_per_instance int4 NOT NULL,
            trigger_threshold text NOT NULL,
            protocol_adjustment text NOT NULL,
            source_document text DEFAULT 'Doc 10 Part 1'::text,
            is_active bool DEFAULT true,
            created_at timestamptz DEFAULT now(),
            PRIMARY KEY (signal_id)
        )
    """)

    # 4. session_state_bands
    op.execute("""
        CREATE TABLE session_state_bands (
            band_id int4 NOT NULL
                DEFAULT nextval(
                    'session_state_bands_band_id_seq'::regclass
                ),
            session_state text NOT NULL,
            score_min int4 NOT NULL,
            score_max int4,
            meaning text NOT NULL,
            closing_protocol_adjustment text NOT NULL,
            report_framing_adjustment text NOT NULL,
            reliability_factor numeric,
            source_document text DEFAULT 'Doc 10 Part 2'::text,
            created_at timestamptz DEFAULT now(),
            PRIMARY KEY (band_id)
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX session_state_bands_session_state_key
        ON session_state_bands USING btree (session_state)
    """)

    # 5. founder_memory
    op.execute("""
        CREATE TABLE founder_memory (
            memory_id varchar NOT NULL,
            founder_id int4 NOT NULL,
            memory_type varchar NOT NULL,
            content text NOT NULL,
            key varchar,
            retention varchar NOT NULL,
            status varchar NOT NULL DEFAULT 'active'::character varying,
            importance int4 NOT NULL DEFAULT 0,
            tags jsonb NOT NULL DEFAULT '[]'::jsonb,
            session_id int4,
            expires_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            created_by varchar NOT NULL,
            updated_by varchar NOT NULL,
            access_count int4 NOT NULL DEFAULT 0,
            accessed_at timestamptz,
            archived_at timestamptz,
            PRIMARY KEY (memory_id)
        )
    """)

    op.execute("""
        ALTER TABLE founder_memory
        ADD CONSTRAINT fk_founder_memory_founder_id
        FOREIGN KEY (founder_id)
        REFERENCES founders(founder_id)
        ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE founder_memory
        ADD CONSTRAINT founder_memory_importance_check
        CHECK (importance >= 0 AND importance <= 100)
    """)

    op.execute("""
        ALTER TABLE founder_memory
        ADD CONSTRAINT founder_memory_retention_check
        CHECK (retention IN ('permanent', 'temporary', 'session'))
    """)

    op.execute("""
        ALTER TABLE founder_memory
        ADD CONSTRAINT founder_memory_status_check
        CHECK (status IN ('active', 'archived'))
    """)

    op.execute("""
        ALTER TABLE founder_memory
        ADD CONSTRAINT founder_memory_type_check
        CHECK (
            memory_type IN (
                'working',
                'long_term',
                'session',
                'strategic',
                'preference'
            )
        )
    """)

    op.execute("""
        CREATE INDEX idx_founder_memory_active
        ON founder_memory USING btree (founder_id)
        WHERE status = 'active'
    """)

    op.execute("""
        CREATE INDEX idx_founder_memory_founder
        ON founder_memory USING btree (founder_id)
    """)

    # 6. founder_memory_events
    # event_id is generated by PostgreSQL because the current application
    # inserts events without explicitly supplying event_id.
    op.execute("""
        CREATE TABLE founder_memory_events (
            event_id bigserial NOT NULL,
            memory_id varchar NOT NULL,
            founder_id int4 NOT NULL,
            event_type varchar NOT NULL,
            timestamp timestamptz NOT NULL,
            actor varchar NOT NULL,
            details jsonb NOT NULL DEFAULT '{}'::jsonb,
            correlation_id varchar,
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (event_id)
        )
    """)

    op.execute("""
        ALTER TABLE founder_memory_events
        ADD CONSTRAINT fk_founder_memory_events_founder_id
        FOREIGN KEY (founder_id)
        REFERENCES founders(founder_id)
        ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE founder_memory_events
        ADD CONSTRAINT founder_memory_events_type_check
        CHECK (
            event_type IN (
                'created',
                'updated',
                'accessed',
                'archived',
                'expired'
            )
        )
    """)

    op.execute("""
        CREATE INDEX idx_founder_memory_events_founder
        ON founder_memory_events USING btree (founder_id)
    """)

    op.execute("""
        CREATE INDEX idx_founder_memory_events_memory
        ON founder_memory_events USING btree (memory_id)
    """)

    # 7. Exact reference data
    _run_reference_data()

    # 8. Reset sequences after explicit-ID seed inserts
    op.execute("""
        SELECT setval(
            'session_state_bands_band_id_seq',
            (SELECT COALESCE(MAX(band_id), 1) FROM session_state_bands)
        )
    """)

    op.execute("""
        SELECT setval(
            'chronic_state_inference_chronic_state_id_seq',
            (SELECT COALESCE(MAX(chronic_state_id), 1)
             FROM chronic_state_inference)
        )
    """)

    op.execute("""
        SELECT setval(
            'psychological_state_signals_signal_id_seq',
            (SELECT COALESCE(MAX(signal_id), 1)
             FROM psychological_state_signals)
        )
    """)


def downgrade() -> None:
    # Drop dependent memory tables first.
    op.execute("DROP TABLE IF EXISTS founder_memory_events CASCADE")
    op.execute("DROP TABLE IF EXISTS founder_memory CASCADE")

    # Drop reference tables.
    op.execute("DROP TABLE IF EXISTS session_state_bands CASCADE")
    op.execute("DROP TABLE IF EXISTS psychological_state_signals CASCADE")
    op.execute("DROP TABLE IF EXISTS chronic_state_inference CASCADE")

    # Drop explicit reference-table sequences.
    op.execute("""
        DROP SEQUENCE IF EXISTS
        session_state_bands_band_id_seq
    """)
    op.execute("""
        DROP SEQUENCE IF EXISTS
        psychological_state_signals_signal_id_seq
    """)
    op.execute("""
        DROP SEQUENCE IF EXISTS
        chronic_state_inference_chronic_state_id_seq
    """)