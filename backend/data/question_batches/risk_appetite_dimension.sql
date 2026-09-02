-- ============================================================
-- Risk Appetite -- the fifteenth Founder DNA dimension.
--
-- Six questions, two per stage group: an opening forced_choice at arc 15 and
-- a closing scenario at arc 96, the shape every other dimension uses. Arc 15
-- and 96 are free across all three stage groups.
--
-- Risk Appetite is about what a founder does when a decision could genuinely
-- cost them, which DECISION_STYLE does not cover -- that one is about HOW they
-- decide (fast/slow, gut/data), not what they do with downside they cannot
-- model.
--
-- The forced choices deliberately avoid a brave/cautious framing. A founder
-- self-rating on courage picks the flattering option, which is what the source
-- doc's Section 1 warns against; asking which feeling actually shows up, or
-- where they sit RELATIVE to their team, is answerable honestly.
--
-- IDs 159-164 mirror Supabase, where this content is already live. They are
-- asserted free before the insert -- the two databases do not share an ID
-- space, so "it worked on Supabase" is not evidence about RDS.
--
-- NOTE ON EMBEDDINGS: founder_dna_questions.embedding is nullable, so these
-- rows are inserted WITHOUT a vector rather than with an
-- `array_fill(0, ARRAY[1536])` placeholder. That is deliberate and the
-- migration loader enforces it: a zero vector is not NULL, so it would be
-- skipped by the embedding backfill and the questions would be permanently
-- invisible to similarity search. NULL is the honest "not embedded yet", and
-- 02_regenerate_embeddings.py fills it.
-- ============================================================

INSERT INTO founder_dna_questions
  (founder_dna_question_id, dimension_code, stage_group, arc_position,
   format, question_text, options, is_closing, is_active)
VALUES
  -- Stage 0 -- the idea stage. Risk is still personal: time and money the
  -- founder puts in themselves, with nobody else depending on the outcome.
  (159, 'risk_appetite', 'Stage 0', 15, 'forced_choice',
   'When this idea could fail in a way that costs you real time or money, does that possibility excite you or unsettle you?',
   '["It excites me", "It unsettles me"]'::jsonb, false, true),
  (160, 'risk_appetite', 'Stage 0', 96, 'scenario',
   'Tell me about the biggest risk you''ve taken on this idea so far, the one where you genuinely didn''t know how it would turn out. What made you go ahead?',
   NULL, false, true),

  -- Stage 0->1 -- a team exists, so the question becomes positional: are they
  -- the accelerator or the brake relative to the people around them.
  (161, 'risk_appetite', 'Stage 0→1', 15, 'forced_choice',
   'Right now, when a decision could go badly, are you the one pushing to move despite the risk, or the one asking the team to slow down and de-risk it first?',
   '["Pushing to move despite the risk", "Asking to slow down and de-risk"]'::jsonb, false, true),
  (162, 'risk_appetite', 'Stage 0→1', 96, 'scenario',
   'Tell me about a risk you talked yourself into taking here, that in hindsight you wouldn''t take again. What did you miss?',
   NULL, false, true),

  -- Stage 1->10+ -- at scale the interesting failure is over-caution, so the
  -- closing scenario asks about a risk NOT taken and names the thing founders
  -- rarely admit unprompted.
  (163, 'risk_appetite', 'Stage 1→10+', 15, 'forced_choice',
   'At this scale, when a bet could set the company back significantly if it fails, do you find yourself more willing to take it than your team is, or less?',
   '["More willing than my team", "Less willing than my team"]'::jsonb, false, true),
  (164, 'risk_appetite', 'Stage 1→10+', 96, 'scenario',
   'Tell me about the last major risk you chose not to take. Was that caution, or was it actually fear dressed up as caution?',
   NULL, false, true)
;

-- Keep the sequence ahead of the explicit IDs above, or the next natural
-- insert collides with one of them.
SELECT setval(
  pg_get_serial_sequence('founder_dna_questions', 'founder_dna_question_id'),
  (SELECT MAX(founder_dna_question_id) FROM founder_dna_questions)
);
