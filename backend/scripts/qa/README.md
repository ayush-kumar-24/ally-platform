# Question-keyed QA personas

An answer map is `{phase: {question_id: {"a": text, "status": ...}}}`, fed to
`e2e_journey_check.py --answer-map`. Answers are looked up by question id.
Nothing is matched by topic.

## Why these exist

The topic-keyed persona bank in `e2e_journey_check.py` was built to prove one
thing: that the engine separates a capable founder from an incapable one. For
that only the aggregate matters, and it works.

It cannot support a question-by-question audit. A stage asks several questions
per topic, so the topic-keyed bank either serves one answer repeatedly -- run
#24 served a single answer to five questions, among them "what does it cost to
acquire one paying customer", which it does not address, and two of three root
causes rested on it -- or, with consume-once matching, the repeats become
deflections that the classifier reads as evasion: run #25 had 17 of 30 answers
non-substantive and returned Critical Gap on five of six pillars for a founder
whose own answers produced two reds.

Either way the diagnosis under review is a diagnosis of the harness.

## Building one

The reachable question set is not a fixed list. Scope is 1,390 questions for a
Stage-4 founder (`questions.primary_stage_group` matching the stage's
`onboarding_label`), and which 30 get asked depends on the answers given, so
the set cannot be enumerated in advance. Iterate to a fixed point instead:

1. run with `--answer-map`
2. every question with no entry is reported as a HARNESS MISS and listed
3. write an answer for each, keyed to that question id
4. re-run

`siddharth_answers.json` converged in five rounds, 61 answers to 73. The run it
produced served 51 questions with 0 misses and 0 reuse -- and stopped at 29 of
30 on `routing_state: generate_report`, confidence 80, rather than exhausting
the budget, which no contaminated run had done.

## Statuses

- `ANSWERED` -- the founder answered the question
- `GENUINELY_UNKNOWN` -- he does not know, and says so
- `GENUINELY_NON_APPLICABLE` -- the question does not apply to this business

These stay distinct from a HARNESS MISS, which is our bug. Collapsing them is
how an honest "we don't track that" becomes evidence of a weakness.

## Contents

Synthetic personas only. No real founder data belongs here, or anywhere in the
repository.
