"""founder dna phase2 rds schema

Revision ID: b4e9a17c6d32
Revises: 6f1d2c9a4b70
Create Date: 2026-08-18 12:00:00

Brings production RDS up to the Founder DNA phase-2 schema that has been
live on the Supabase copy since 18 Aug 2026 (verified row-for-row against
founder_dna_schema_rds.sql / founder_dna_questions_seed.sql supplied
2026-08-18): founder_dna_questions (14 dimensions, not the original 6),
founder_dna_answers, and two new founders columns.

Supabase is the auth-only database -- it has never been what the running
backend queries for founder_dna_* data (DATABASE_URL points at RDS). So
despite this schema being "done" on Supabase, RDS -- the database the app
actually reads from -- has had none of it until this migration.

Anchor-table guard, same pattern as 905bddfc6aff: if founder_dna_questions
already exists (e.g. someone hand-ran the supplied .sql directly against
RDS before this migration was authored), skip -- don't re-run and collide.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "b4e9a17c6d32"
down_revision: Union[str, Sequence[str], None] = "6f1d2c9a4b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 57 rows, ids 98-154, verbatim from founder_dna_questions_seed.sql
# (2026-08-18) -- do not touch. See that file for provenance.
_SEED_STATEMENTS: list[str] = [
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":98,"dimension_code":"origin","stage_group":"Stage 0","format":"narrative","question_text":"Picture the moment this idea first properly grabbed you -- where were you, and what actually triggered it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":1,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":99,"dimension_code":"archetype","stage_group":"Stage 0","format":"narrative","question_text":"If you were writing the opening line of your own founder origin story, what would it say?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":2,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":100,"dimension_code":"mindset_excellence","stage_group":"Stage 0","format":"forced_choice","question_text":"When you picture doing this really well, what does ''well'' actually mean to you -- being first, being the best, or being trusted?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":3,"is_closing":false,"options":["Being first", "Being the best", "Being trusted"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":101,"dimension_code":"core_motivation","stage_group":"Stage 0","format":"scenario","question_text":"Think about the last thing you built or finished that genuinely satisfied you -- before this venture, even. What about it landed?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":4,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":102,"dimension_code":"emotional_intelligence","stage_group":"Stage 0","format":"scenario","question_text":"Someone far more experienced than you dismisses your idea in one sentence. What''s your honest first internal reaction -- before you compose yourself?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":5,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":103,"dimension_code":"purpose_mission","stage_group":"Stage 0","format":"narrative","question_text":"In one sentence, why does this problem deserve your next few years?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":6,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":104,"dimension_code":"vision","stage_group":"Stage 0","format":"narrative","question_text":"Picture this venture thriving five years from now -- what does ''thriving'' actually look like, concretely?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":7,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":105,"dimension_code":"core_values","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about a time before this venture when you walked away from something because it crossed a line for you. What was the line?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":8,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":106,"dimension_code":"energy_patterns","stage_group":"Stage 0","format":"scenario","question_text":"Think about the last time you finished a day genuinely energised rather than drained. What had you been doing, and who was around?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":9,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":107,"dimension_code":"decision_style","stage_group":"Stage 0","format":"forced_choice","question_text":"When you face a big unknown, do you decide fast and adjust as you go, or gather everything you can before you move?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":10,"is_closing":false,"options":["Decide fast and adjust", "Gather everything first"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":108,"dimension_code":"stress_response","stage_group":"Stage 0","format":"scenario","question_text":"Think of the last time you faced real uncertainty outside of work. What did you actually do -- not what you wish you''d done?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":11,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":109,"dimension_code":"strengths_blind_spots","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last time someone who knows you well pointed out something about how you work that you hadn''t seen. What was it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":12,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":110,"dimension_code":"communication_preference","stage_group":"Stage 0","format":"forced_choice","question_text":"When something''s going wrong, do you want it told to you straight, laid out step by step, or talked through out loud?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":13,"is_closing":false,"options":["Told straight", "Laid out step by step", "Talked through out loud"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":111,"dimension_code":"focus_attention","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last time you sat with one problem for a long stretch without switching to something else. What made that possible?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":14,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":112,"dimension_code":"purpose_mission","stage_group":"Stage 0","format":"narrative","question_text":"If your future self, five years into this, sent you one sentence of advice right now -- what would it say?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":99,"is_closing":true,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":113,"dimension_code":"purpose_mission","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last time you seriously considered dropping this idea. What actually made you stay with it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":90,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":114,"dimension_code":"decision_style","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last real decision you made for this idea. Walk me through how you actually got there.","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":91,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":115,"dimension_code":"energy_patterns","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last time working on this left you completely drained. What had you been doing that day?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":92,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":116,"dimension_code":"emotional_intelligence","stage_group":"Stage 0","format":"scenario","question_text":"Tell me about the last time you had to give someone difficult feedback. How did you handle it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":93,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":117,"dimension_code":"origin","stage_group":"Stage 0→1","format":"scenario","question_text":"Think back to the moment you decided this was worth actually building, not just thinking about. What tipped it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":1,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":118,"dimension_code":"archetype","stage_group":"Stage 0→1","format":"narrative","question_text":"What''s actually different about how you show up now versus before you started building?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":2,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":119,"dimension_code":"mindset_excellence","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last thing you shipped that you weren''t fully happy with, but shipped anyway. Why?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":3,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":120,"dimension_code":"core_motivation","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last win here that actually felt good. What made that one land more than the others?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":4,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":121,"dimension_code":"emotional_intelligence","stage_group":"Stage 0→1","format":"scenario","question_text":"Walk me through the last time you were completely overwhelmed. What did you actually do -- push through, shut down, or reach out?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":5,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":122,"dimension_code":"purpose_mission","stage_group":"Stage 0→1","format":"narrative","question_text":"If you had to defend why this still deserves your time, in one sentence -- has that sentence changed since you started?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":6,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":123,"dimension_code":"vision","stage_group":"Stage 0→1","format":"narrative","question_text":"What''s the one number that, if it moved, would tell you this is really working?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":7,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":124,"dimension_code":"core_values","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last time growth tempted you to compromise on something you''d said mattered. What happened?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":8,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":125,"dimension_code":"energy_patterns","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last stretch of work here that gave you real momentum. What conditions made it possible?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":9,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":126,"dimension_code":"decision_style","stage_group":"Stage 0→1","format":"forced_choice","question_text":"Thinking about how you''re actually building right now -- are you working to a plan you set in advance, or figuring it out as you go?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":10,"is_closing":false,"options":["To a plan set in advance", "Figuring it out as I go"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":127,"dimension_code":"stress_response","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last week here that genuinely got to you. What did you do with it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":11,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":128,"dimension_code":"strengths_blind_spots","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about something you''ve had to learn the hard way since starting to build. What did you get wrong first?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":12,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":129,"dimension_code":"communication_preference","stage_group":"Stage 0→1","format":"forced_choice","question_text":"When something''s going wrong, do you want it told to you straight, laid out step by step, or talked through out loud?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":13,"is_closing":false,"options":["Told straight", "Laid out step by step", "Talked through out loud"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":130,"dimension_code":"focus_attention","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last time you context-switched mid-task and lost real time to it. What pulled you away?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":14,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":131,"dimension_code":"emotional_intelligence","stage_group":"Stage 0→1","format":"narrative","question_text":"What''s the thing about running this that you haven''t told anyone yet?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":99,"is_closing":true,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":132,"dimension_code":"purpose_mission","stage_group":"Stage 0→1","format":"narrative","question_text":"What''s the thing you''re doing right now that isn''t scalable, but you''re doing anyway -- and why?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":90,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":133,"dimension_code":"mindset_excellence","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last time perfectionism cost you real time here. What were you polishing, and what did it delay?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":91,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":134,"dimension_code":"decision_style","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last decision you made here that you''d now call rushed. What did you skip?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":92,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":135,"dimension_code":"energy_patterns","stage_group":"Stage 0→1","format":"scenario","question_text":"Tell me about the last week that left you wiped out. What was different about it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":93,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":136,"dimension_code":"origin","stage_group":"Stage 1→10+","format":"scenario","question_text":"Think back to why you started this in the first place. Tell me about the moment that made it feel necessary rather than optional.","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":1,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":137,"dimension_code":"archetype","stage_group":"Stage 1→10+","format":"narrative","question_text":"Who were you as a leader in year one, and who are you now -- what''s the actual difference?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":2,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":138,"dimension_code":"mindset_excellence","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about a standard you refused to lower, even when it cost you time or money.","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":3,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":139,"dimension_code":"core_motivation","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last thing this business achieved that genuinely moved you. What was it about that one?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":4,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":140,"dimension_code":"emotional_intelligence","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time you were wrong about a person on your team. What did that actually cost you?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":5,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":141,"dimension_code":"purpose_mission","stage_group":"Stage 1→10+","format":"narrative","question_text":"What does this venture being ''done'' even mean to you -- does it end, or does it just change shape?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":6,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":142,"dimension_code":"vision","stage_group":"Stage 1→10+","format":"narrative","question_text":"If you stepped away for a year, what''s the one thing about this business you''d want to still be true when you came back?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":7,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":143,"dimension_code":"core_values","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time someone on your team crossed a line you care about. What actually happened next?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":8,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":144,"dimension_code":"energy_patterns","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last thing you did here that you''d hand off tomorrow if you could, purely because it drains you. What was it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":9,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":145,"dimension_code":"decision_style","stage_group":"Stage 1→10+","format":"forced_choice","question_text":"In your last real crisis, were you closer to steering alone, or bracing with the team?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":10,"is_closing":false,"options":["Steering alone", "Bracing with the team"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":146,"dimension_code":"stress_response","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last stretch here that genuinely wore you down. What did you actually do about it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":11,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":147,"dimension_code":"strengths_blind_spots","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time a senior person on your team told you something about yourself you didn''t want to hear. What was it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":12,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":148,"dimension_code":"communication_preference","stage_group":"Stage 1→10+","format":"forced_choice","question_text":"When you hand something off, do you check in daily, weekly, or only when it''s flagged to you?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":13,"is_closing":false,"options":["Daily", "Weekly", "Only when it''s flagged"]}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":149,"dimension_code":"focus_attention","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time you were pulled into something that should have been someone else''s to handle. Why did it land on you?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":14,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":150,"dimension_code":"purpose_mission","stage_group":"Stage 1→10+","format":"narrative","question_text":"If your company outlives you, what''s the one decision you hope nobody ever has to unmake?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":99,"is_closing":true,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":151,"dimension_code":"purpose_mission","stage_group":"Stage 1→10+","format":"narrative","question_text":"What''s the one thing you still do yourself that you know, honestly, you should have handed off by now?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":90,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":152,"dimension_code":"decision_style","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about a decision you delegated and then regretted delegating. What went wrong in how you handed it over?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":91,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":153,"dimension_code":"energy_patterns","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time you felt genuinely in flow running this. What were you doing?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":92,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
    """INSERT INTO "founder_dna_questions" SELECT * FROM json_populate_record(NULL::founder_dna_questions, '{"founder_dna_question_id":154,"dimension_code":"core_values","stage_group":"Stage 1→10+","format":"scenario","question_text":"Tell me about the last time you turned down money or growth because of something you weren''t willing to trade. What was it?","is_active":true,"created_at":"2026-08-17T18:56:03.239501+00:00","updated_at":"2026-08-17T18:56:03.239501+00:00","arc_position":93,"is_closing":false,"options":null}'::json) ON CONFLICT DO NOTHING;""",
]


def upgrade() -> None:
    bind = op.get_bind()
    if inspect(bind).has_table("founder_dna_questions"):
        # Anchor-table check -- if this exists, the schema+seed effects
        # below already landed some other way (e.g. run by hand). Do not
        # re-run: the seed INSERTs are id-explicit and would either
        # no-op harmlessly (ON CONFLICT DO NOTHING) or, worse, mask a
        # real drift between what's on RDS and what this file expects.
        # Confirm parity manually before trusting this guard silently.
        return

    op.execute("""
        CREATE TABLE founder_dna_questions (
            founder_dna_question_id SERIAL PRIMARY KEY,
            dimension_code VARCHAR(30) NOT NULL,
            stage_group VARCHAR(20) NOT NULL,
            format VARCHAR(20) DEFAULT 'narrative' NOT NULL,
            question_text TEXT NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            arc_position INTEGER NOT NULL DEFAULT 0,
            is_closing BOOLEAN NOT NULL DEFAULT false,
            options JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            CONSTRAINT founder_dna_questions_dimension_code_check
                CHECK (dimension_code = ANY (ARRAY[
                    'purpose_mission','core_values','mindset_excellence',
                    'energy_patterns','decision_style','focus_attention',
                    'archetype','core_motivation','origin','vision',
                    'strengths_blind_spots','stress_response',
                    'communication_preference','emotional_intelligence'
                ]::text[])),
            CONSTRAINT founder_dna_questions_stage_group_check
                CHECK (stage_group = ANY (ARRAY[
                    'Stage 0','Stage 0→1','Stage 1→10+'
                ]::text[])),
            CONSTRAINT founder_dna_questions_format_check
                CHECK (format = ANY (ARRAY[
                    'narrative','scenario','forced_choice'
                ]::text[]))
        )
    """)

    op.execute("""
        CREATE INDEX idx_founder_dna_questions_dimension_stage
        ON founder_dna_questions (dimension_code, stage_group)
    """)

    # At most one closing question per stage (the "wow close" -- engine
    # guarantees exactly one slot for it regardless of adaptive skipping).
    op.execute("""
        CREATE UNIQUE INDEX uq_founder_dna_one_closing_per_stage
        ON founder_dna_questions (stage_group)
        WHERE is_closing
    """)

    op.execute("""
        CREATE TABLE founder_dna_answers (
            founder_dna_answer_id SERIAL PRIMARY KEY,
            founder_id INTEGER NOT NULL
                REFERENCES founders (founder_id) ON DELETE CASCADE,
            founder_dna_question_id INTEGER NOT NULL
                REFERENCES founder_dna_questions (founder_dna_question_id),
            answer_text TEXT NOT NULL,
            answered_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)

    op.execute("""
        CREATE INDEX idx_founder_dna_answers_founder
        ON founder_dna_answers (founder_id)
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_founder_dna_answers_founder_question
        ON founder_dna_answers (founder_id, founder_dna_question_id)
    """)

    op.execute("""
        ALTER TABLE founders
        ADD COLUMN founder_dna_completed_at TIMESTAMP WITH TIME ZONE
    """)

    op.execute("""
        ALTER TABLE founders
        ADD COLUMN founder_dna_resolved_dimensions
        JSONB NOT NULL DEFAULT '[]'::jsonb
    """)

    # 57 seed rows, ids 98-154 -- see founder_dna_questions_seed.sql.
    for statement in _SEED_STATEMENTS:
        op.execute(statement)

    # The seed above inserts explicit ids via json_populate_record, which
    # does NOT advance the SERIAL sequence (it bypasses nextval()). Left
    # alone, the sequence stays at 1 and the very next natural INSERT
    # collides on a duplicate key against row 98. Same bug class the
    # 905bddfc6aff reconciliation had to guard against for its own
    # explicit-id seed inserts -- reset it here too.
    op.execute("""
        SELECT setval(
            'founder_dna_questions_founder_dna_question_id_seq',
            (SELECT COALESCE(MAX(founder_dna_question_id), 1)
             FROM founder_dna_questions)
        )
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE founders DROP COLUMN IF EXISTS founder_dna_resolved_dimensions")
    op.execute("ALTER TABLE founders DROP COLUMN IF EXISTS founder_dna_completed_at")
    op.execute("DROP TABLE IF EXISTS founder_dna_answers CASCADE")
    op.execute("DROP TABLE IF EXISTS founder_dna_questions CASCADE")
