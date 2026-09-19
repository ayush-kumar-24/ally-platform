"""question -> capability: the semantic bridge, curated at the PROBLEM level.

WHY PROBLEM-LEVEL AND NOT QUESTION-LEVEL. 3,340 questions hang off 273 problems,
and a problem is the unit an editor actually reasoned about. Curating 202
decisions that a reviewer can read beats 1,466 opaque pairs nobody will ever
audit -- so this migration carries the DECISIONS and expands them in SQL. The
expanded rows are captured by the reference dump like every other seeded table.

WHY NOT ALL 273 PROBLEMS. Problem size turned out to be a proxy for semantic
purity, and the large ones were used as dumping grounds. Verified by reading
them:

  PRD-002 "Lack of User Feedback Loop" (157 questions) contains questions about
          data infrastructure, incident response and board reporting.
  TM-006  "Cultural and Communication Problems" (110) contains "When did you
          last take a real day off?" and "Is key process knowledge documented?".
  FIN-001 "No Ongoing Cash Flow Monitoring" (37) contains budget questions.

So a problem is admitted at HIGH confidence only when it names ONE observable
practice AND a read of its questions showed them homogeneous. 51 problems are
MEDIUM -- reported in backend/docs/QUESTION-CAPABILITY-MAPPING.md for review and
deliberately NOT seeded -- and 20 are rejected outright.

THE ADMISSION TEST is the capability's own evidence criteria: an answer must be
able to inform one of them directly. Not "is this related to" -- "can the answer
tell us this". That test is what demoted the five employment-policy problems
(OPS-026/051/056/061/066): "Have your employment practices ever been reviewed by
a lawyer?" does not evidence "How-to knowledge is written down", and there is no
Compliance & Governance capability in the 34 for it to go to instead. The gap is
reported rather than papered over.

FOUNDER PSYCHOLOGY IS MOSTLY REJECTED, for the reason the step brief gives: a
trait is not a capability and evidence must not be inferred from consequences.
20 of the 30 PSY problems map to nothing. The ten that survive do so because
they name an observable practice rather than a feeling -- PSY-019 "No
Accountability Culture in the Team", PSY-011 "Poor Communication When
Delegating" -- not because psychology eventually affects the business.

ONE CAPABILITY PER QUESTION, everywhere. Nothing here maps a question to two
capabilities: the brief asks for one strong direct mapping over several
speculative ones, and no problem earned a second.

Purely additive. No existing row is touched, nothing is deleted, and downgrade
removes exactly the rows this inserted.
"""

from alembic import op
import sqlalchemy as sa

revision = "c5e7b1a94f60"
down_revision = "a8d34f7e2b91"
branch_labels = None
depends_on = None


#: (problem_code, capability_code) -- HIGH confidence, seeded.
#: Every question under the problem receives the mapping.
HIGH_CONFIDENCE = [
    ("BMD-001", "FIN-UNIT"), ("BMD-002", "STR-MODEL"),
    ("BMD-016", "STR-MODEL"), ("BMD-021", "STR-MODEL"),
    ("BMD-026", "STR-MODEL"), ("BPL-001", "STR-PLAN"),
    ("BPL-003", "STR-PLAN"), ("BPL-016", "STR-PLAN"),
    ("BPL-021", "STR-PLAN"), ("CMA-001", "STR-COMPETE"),
    ("CMA-002", "FIN-UNIT"), ("CMA-015", "STR-COMPETE"),
    ("CMA-020", "STR-POSITION"), ("CMA-025", "STR-COMPETE"),
    ("FIN-011", "FIN-VIS"), ("FIN-016", "FIN-PLAN"),
    ("FIN-021", "FIN-PLAN"), ("FIN-026", "FIN-VIS"),
    ("FIN-031", "FIN-CASH"), ("FIN-036", "FIN-CASH"),
    ("FIN-041", "FIN-CASH"), ("FIN-046", "FIN-CASH"),
    ("FIN-051", "FIN-CASH"), ("FIN-056", "FIN-CASH"),
    ("FIN-061", "FIN-CASH"), ("FIN-066", "FIN-CASH"),
    ("FIN-071", "FIN-UNIT"), ("FIN-076", "FIN-VIS"),
    ("FIN-081", "FIN-VIS"), ("FIN-086", "FIN-UNIT"),
    ("FIN-091", "FIN-PLAN"), ("FIN-096", "FIN-PLAN"),
    ("FIN-101", "FIN-PLAN"), ("FIN-106", "FIN-PLAN"),
    ("FIN-111", "FIN-PLAN"), ("FIN-116", "FIN-PLAN"),
    ("FIN-121", "FIN-PLAN"), ("FIN-126", "FIN-VIS"),
    ("FIN-131", "FIN-VIS"), ("FIN-136", "FIN-VIS"),
    ("FIN-141", "FIN-VIS"), ("FIN-146", "FIN-INVEST"),
    ("FIN-151", "FIN-VIS"), ("FND-001", "FIN-INVEST"),
    ("FND-002", "FIN-INVEST"), ("FND-003", "FIN-INVEST"),
    ("FND-004", "FIN-INVEST"), ("FND-005", "FIN-INVEST"),
    ("FND-007", "FIN-CASH"), ("GTM-003", "GTM-ACQ"),
    ("GTM-004", "STR-POSITION"), ("GTM-006", "GTM-SALES"),
    ("GTM-007", "GTM-RETAIN"), ("GTM-028", "GTM-ACQ"),
    ("IVA-003", "GTM-ICP"), ("IVA-004", "PRD-DISCOVER"),
    ("IVA-006", "PRD-FEEDBACK"), ("MEX-001", "GTM-ACQ"),
    ("MEX-006", "GTM-ACQ"), ("MEX-016", "GTM-ACQ"),
    ("MEX-021", "GTM-ACQ"), ("MEX-026", "GTM-ACQ"),
    ("MEX-031", "GTM-ACQ"), ("MEX-036", "GTM-ACQ"),
    ("MEX-041", "GTM-ACQ"), ("MEX-046", "GTM-ACQ"),
    ("MEX-051", "GTM-ACQ"), ("MEX-056", "GTM-ACQ"),
    ("MEX-061", "GTM-ACQ"), ("MEX-066", "GTM-ACQ"),
    ("MEX-071", "GTM-ACQ"), ("MEX-076", "STR-COMPETE"),
    ("MEX-081", "GTM-ACQ"), ("MEX-086", "GTM-ACQ"),
    ("MEX-091", "GTM-ACQ"), ("MEX-096", "GTM-ACQ"),
    ("MEX-101", "GTM-ACQ"), ("OPE-003", "STR-PLAN"),
    ("OPE-016", "STR-PLAN"), ("OPE-021", "STR-PLAN"),
    ("OPS-002", "FND-INDEP"), ("OPS-004", "FIN-VIS"),
    ("OPS-005", "OPS-MONITOR"), ("OPS-021", "OPS-SOP"),
    ("OPS-031", "OPS-SOP"), ("OPS-036", "OPS-SOP"),
    ("OPS-041", "OPS-SOP"), ("OPS-046", "OPS-SOP"),
    ("PRD-004", "OPS-QUALITY"), ("PSY-011", "FND-DELEG"),
    ("PSY-017", "STR-PLAN"), ("PSY-018", "FND-FOCUS"),
    ("PSY-019", "ORG-PERF"), ("PSY-020", "ORG-CULTURE"),
    ("PSY-021", "ORG-CULTURE"), ("PSY-022", "ORG-CULTURE"),
    ("RSK-001", "STR-PLAN"), ("RSK-002", "STR-PLAN"),
    ("RSK-003", "FND-INDEP"), ("RSK-021", "ORG-ROLES"),
    ("SAL-001", "GTM-PIPE"), ("SAL-003", "FIN-UNIT"),
    ("SAL-004", "STR-MODEL"), ("SCL-001", "OPS-PROCESS"),
    ("SCL-002", "OPS-PROCESS"), ("SCL-003", "OPS-SOP"),
    ("SCL-004", "FND-INDEP"), ("SCL-005", "ORG-CADENCE"),
    ("SCL-006", "ORG-CADENCE"), ("SCL-007", "ORG-HIRE"),
    ("SCL-008", "OPS-QUALITY"), ("SCL-009", "ORG-ROLES"),
    ("SCL-010", "FND-DELEG"), ("SCL-011", "FND-DELEG"),
    ("SCL-012", "FIN-VIS"), ("SCL-013", "FIN-UNIT"),
    ("SCL-014", "GTM-RETAIN"), ("SCL-015", "GTM-RETAIN"),
    ("SCL-016", "GTM-PIPE"), ("SCL-017", "FIN-PLAN"),
    ("SCL-018", "FIN-CASH"), ("SCL-019", "FIN-UNIT"),
    ("SCL-020", "GTM-OWN"), ("SCL-021", "FIN-VIS"),
    ("SCL-022", "GTM-RETAIN"), ("SCL-023", "FIN-PLAN"),
    ("SCL-024", "FND-LEAD"), ("SCL-025", "ORG-PERF"),
    ("SCL-026", "OPS-SOP"), ("SCL-028", "ORG-CULTURE"),
    ("SCL-029", "ORG-CULTURE"), ("SCL-030", "ORG-CULTURE"),
    ("SCL-031", "FND-LEAD"), ("SCL-032", "ORG-ROLES"),
    ("SCL-033", "ORG-CULTURE"), ("SCL-034", "STR-COMPETE"),
    ("SCL-035", "STR-COMPETE"), ("SCL-036", "GTM-ICP"),
    ("SCL-037", "STR-POSITION"), ("SCL-039", "STR-MODEL"),
    ("SCL-040", "GTM-RETAIN"), ("SCL-041", "STR-MODEL"),
    ("SCL-043", "FND-LEAD"), ("SCL-044", "FND-DELEG"),
    ("SCL-045", "FND-LEAD"), ("SCL-046", "FIN-INVEST"),
    ("SCL-047", "FIN-INVEST"), ("SCL-048", "FND-FOCUS"),
    ("SLX-001", "GTM-SALES"), ("SLX-006", "GTM-ACQ"),
    ("SLX-011", "GTM-SALES"), ("SLX-016", "GTM-SALES"),
    ("SLX-021", "GTM-PIPE"), ("SLX-026", "GTM-PIPE"),
    ("SLX-031", "GTM-RETAIN"), ("SLX-036", "GTM-PIPE"),
    ("SLX-041", "GTM-ACQ"), ("SLX-046", "GTM-SALES"),
    ("SLX-051", "GTM-SALES"), ("SLX-056", "GTM-ACQ"),
    ("SLX-061", "GTM-ACQ"), ("SLX-066", "GTM-ACQ"),
    ("SLX-071", "GTM-ACQ"), ("SLX-076", "GTM-SALES"),
    ("SLX-081", "GTM-SALES"), ("SLX-086", "GTM-SALES"),
    ("SLX-091", "GTM-SALES"), ("SLX-096", "GTM-SALES"),
    ("SLX-101", "GTM-SALES"), ("SLX-106", "GTM-PIPE"),
    ("SLX-111", "GTM-PIPE"), ("SLX-116", "GTM-PIPE"),
    ("SLX-121", "GTM-PIPE"), ("SLX-126", "GTM-PIPE"),
    ("SLX-136", "GTM-PIPE"), ("SLX-141", "GTM-PIPE"),
    ("SLX-146", "GTM-PIPE"), ("SLX-151", "GTM-PIPE"),
    ("SLX-156", "GTM-RETAIN"), ("SLX-161", "GTM-RETAIN"),
    ("SLX-166", "GTM-RETAIN"), ("SLX-171", "GTM-RETAIN"),
    ("SLX-172", "GTM-ACQ"), ("SLX-180", "GTM-ACQ"),
    ("SLX-185", "GTM-ACQ"), ("SLX-190", "GTM-ACQ"),
    ("SLX-195", "GTM-ACQ"), ("TCI-001", "PRD-DISCOVER"),
    ("TCI-002", "GTM-ICP"), ("TCI-011", "GTM-ICP"),
    ("TCI-016", "GTM-ICP"), ("TM-025", "ORG-HIRE"),
    ("TM-030", "ORG-PERF"), ("TM-035", "ORG-HIRE"),
    ("TM-041", "ORG-HIRE"), ("TM-046", "ORG-HIRE"),
    ("TM-051", "ORG-HIRE"), ("TM-056", "ORG-PERF"),
    ("TM-061", "ORG-PERF"), ("TM-066", "ORG-PERF"),
    ("TM-071", "ORG-PERF"), ("TM-076", "ORG-PERF"),
]

#: MEDIUM: reported for review, NEVER seeded. Either the problem is too large to
#: certify from a sample, or it spans two capabilities, or -- for the compliance
#: ones -- no capability's criteria can be informed by it at all.
#: `None` means "no capability was even a candidate".
MEDIUM_FOR_REVIEW = [('BPL-002', 'STR-PLAN'), ('FIN-001', 'FIN-CASH'), ('FIN-006', 'FIN-CASH'), ('FIN-152', 'FIN-VIS'), ('FIN-153', 'OPS-TOOLING'), ('FND-006', 'FIN-INVEST'), ('GTM-001', 'GTM-ACQ'), ('GTM-002', 'GTM-ICP'), ('GTM-005', 'FIN-UNIT'), ('IVA-001', 'PRD-DISCOVER'), ('IVA-002', None), ('IVA-005', None), ('IVA-007', 'PRD-DISCOVER'), ('MEX-011', 'GTM-ACQ'), ('MEX-102', None), ('MEX-103', 'OPS-TOOLING'), ('OPE-001', 'STR-PLAN'), ('OPE-002', 'FND-FOCUS'), ('OPS-001', 'OPS-PROCESS'), ('OPS-003', None), ('OPS-006', None), ('OPS-026', None), ('OPS-051', None), ('OPS-056', None), ('OPS-061', None), ('OPS-066', None), ('PRD-001', 'PRD-ROADMAP'), ('PRD-002', 'PRD-FEEDBACK'), ('PRD-003', 'PRD-ROADMAP'), ('PRD-005', 'PRD-ROADMAP'), ('PRD-006', None), ('PRD-007', None), ('PSY-005', 'FND-DELEG'), ('PSY-008', 'FND-DELEG'), ('PSY-009', 'FND-INDEP'), ('PSY-027', 'FND-TIME'), ('RSK-016', None), ('SAL-002', 'GTM-SALES'), ('SAL-005', 'GTM-RETAIN'), ('SCL-027', None), ('SCL-038', 'PRD-ROADMAP'), ('SCL-042', 'STR-MODEL'), ('SCL-049', 'PRD-ROADMAP'), ('SLX-131', 'STR-COMPETE'), ('SLX-196', 'OPS-TOOLING'), ('TM-001', None), ('TM-002', 'ORG-ROLES'), ('TM-004', 'ORG-HIRE'), ('TM-005', 'ORG-ROLES'), ('TM-006', 'ORG-CULTURE'), ('TM-077', 'OPS-TOOLING')]

#: REJECTED: a trait, a demographic fact, or a question whose answer cannot
#: evidence any capability. These stay unmapped on purpose.
REJECTED = ['PSY-001', 'PSY-002', 'PSY-003', 'PSY-004', 'PSY-006', 'PSY-007', 'PSY-010', 'PSY-012', 'PSY-013', 'PSY-014', 'PSY-015', 'PSY-016', 'PSY-023', 'PSY-024', 'PSY-025', 'PSY-026', 'PSY-028', 'PSY-029', 'PSY-030', 'TM-003']


def upgrade() -> None:
    conn = op.get_bind()
    capability_ids = {
        code: cid for code, cid in conn.execute(
            sa.text("SELECT capability_code, capability_id FROM capabilities")).all()
    }
    missing = {c for _p, c in HIGH_CONFIDENCE} - set(capability_ids)
    if missing:
        raise RuntimeError(f"mapping references unknown capabilities: {sorted(missing)}")

    for problem_code, capability_code in HIGH_CONFIDENCE:
        # Expanded here rather than enumerated above: the decision is
        # problem-level, so the migration states the decision and lets the
        # database find the questions. ON CONFLICT keeps this idempotent, and a
        # problem_code absent from a given database is simply a no-op.
        conn.execute(sa.text(
            "INSERT INTO question_capabilities (question_id, capability_id)"
            " SELECT q.question_id, :cap"
            "   FROM questions q JOIN problems p ON p.problem_id = q.problem_id"
            "  WHERE p.problem_code = :pcode"
            " ON CONFLICT DO NOTHING"
        ), {"cap": capability_ids[capability_code], "pcode": problem_code})


def downgrade() -> None:
    conn = op.get_bind()
    capability_ids = {
        code: cid for code, cid in conn.execute(
            sa.text("SELECT capability_code, capability_id FROM capabilities")).all()
    }
    # Removes exactly what upgrade inserted -- by (problem, capability), not by
    # truncating the table, so a mapping added by a later curation pass survives.
    for problem_code, capability_code in HIGH_CONFIDENCE:
        if capability_code not in capability_ids:
            continue
        conn.execute(sa.text(
            "DELETE FROM question_capabilities qc"
            " USING questions q, problems p"
            " WHERE qc.question_id = q.question_id"
            "   AND q.problem_id = p.problem_id"
            "   AND p.problem_code = :pcode"
            "   AND qc.capability_id = :cap"
        ), {"cap": capability_ids[capability_code], "pcode": problem_code})
