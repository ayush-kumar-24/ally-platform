"""Prompting the model to read a founder's onboarding answers.

The whole value of this screen is that it says something the founder did not
literally type. The risk is the model inventing facts about a real person, so
the prompt is grounded hard: it is given only their answers, told to work from
those alone, and told to say less rather than guess.
"""

import json

from app.api.v1.impression.facts import FounderFacts, prose_list

SYSTEM = (
    "You are Ally, an experienced co-founder forming a first read of a founder "
    "you have just met, from the answers they gave during onboarding.\n\n"
    "Rules, in order of importance:\n"
    "1. Use ONLY what they told you. Never invent a metric, a company detail, a "
    "team size, a funding position or an event. If you did not read it, it did "
    "not happen.\n"
    "2. Say something they did not literally type. Connect two of their answers "
    "and name what the combination suggests. That is the whole job.\n"
    "3. Be specific to this founder. If your sentence would fit any founder at "
    "their stage, it is wrong.\n"
    "4. Be warm and plain. No consultant vocabulary, no 'leverage', no "
    "'synergies', no bullet-point management-speak.\n"
    "5. If they said they are overwhelmed or stuck, do not talk past it and do "
    "not perform sympathy. Acknowledge it once, plainly.\n"
    "6. Never claim certainty. This is a first read, offered for correction.\n"
    "7. Write in British English, second person ('you'), present tense."
)

SCHEMA_NOTE = (
    'Return ONLY a JSON object, no prose around it, shaped exactly:\n'
    '{\n'
    '  "bullets": [4 strings, each under 90 characters, each an observation you '
    'formed — start with a verb like Placed/Heard/Flagged/Noted/Read],\n'
    '  "read": "one paragraph, 45-75 words, your early read of them",\n'
    '  "instinct": "one sentence beginning \'Your instinct when\' naming how they '
    'likely behave under the pressure they described — something they can '
    'confirm or correct"\n'
    '}'
)


def build_prompt(f: FounderFacts) -> str:
    """The founder's answers, labelled, plus the instructions."""
    answers: dict[str, str] = {}

    def put(label: str, value: str) -> None:
        if value:
            answers[label] = value

    put("Stage", f"{f.stage} ({f.stage_group})" if f.stage_group else f.stage)
    put("Experience", f.experience)
    put("What they are building", f.building)
    put("Problem they are solving", f.problem)
    put("Why it matters to them", f.why)
    put("Who they serve", prose_list(f.audience) + (f", plus {f.audience_other}" if f.audience_other else ""))
    put("Industry", f.industry)
    put("Biggest challenges right now", prose_list(f.challenges))
    put("90-day breakthrough they want", f.goal_90)
    put("What success looks like in a year", f.vision)
    put("How they want to be supported", prose_list(f.support))
    put("How they feel today", f.feeling)
    put("Their answer to the stage question", f.reflection)

    return (
        "Here is everything this founder told you. Nothing else is known about "
        "them.\n\n"
        f"{json.dumps(answers, indent=2, ensure_ascii=False)}\n\n"
        f"{SCHEMA_NOTE}"
    )
