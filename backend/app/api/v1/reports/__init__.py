"""Report Narrative Generator (#20) + the Reports APIs.

Architecture: a FIXED TEMPLATE with slots. The engine owns every fact (scores,
root causes, interventions, archetype); the narrative layer owns only prose. The
prose writer receives already-computed values and phrases them -- it never
computes, infers, adjusts or invents a number, a finding, or a claim. A missing
value omits its section; it is never filled with a guess.
"""
