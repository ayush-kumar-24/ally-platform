# GOXL × ALLY — "You don't have to build alone" campaign

7-slide LinkedIn carousel, 1080 × 1350 px (4:5). Rendered slides live in `carousel-renders/campaign/`.

The ₹1 offer is the doorway. The hero is trust: an ally is someone who stands with you.

---

## 1. Final copy per slide

### Slide 1 — The emotional hook
- Eyebrow: `GOXL × ALLY`
- Headline (serif caps, largest on the slide): `YOU DON'T HAVE TO` / `BUILD ALONE.`
- Supporting: `That's what an Ally is for.`
- Footer: `GOXL × ALLY` · `01 / 07`

### Slide 2 — What Ally means
- Eyebrow: `WHAT ALLY MEANS`
- Headline: `An ally` / *`stands with you.`*
- Supporting, three lines: `Not ahead of you.` / `Not above you.` / `Beside you.`
- Body: `We're building Ally for founders who need someone to understand before giving answers.`
- Journey line labels: `IDEA · FIRST PRODUCT · FIRST CUSTOMERS · TRACTION · SCALING`, with `ALLY` running beside the line, not at its end.

### Slide 3 — We start by understanding
- Eyebrow: `STEP ONE`
- Headline: `First, we` / *`understand you.`*
- Supporting list: `Your journey.` / `Your business.` / `Your challenges.` / `Your stage.` / `Your context.`
- Body: `Because the right recommendation starts with the right understanding.`
- UI fragment fields: `Where you are` · `What you're building` · `Your biggest challenge right now` · `Your 90-day goal` · `How you like to be told things`. No values filled in beyond a cursor.

### Slide 4 — Then we diagnose
- Eyebrow: `STEP TWO`
- Headline: `Then we look` / *`underneath the symptoms.`*
- Sequence: `UNDERSTAND → DIAGNOSE → ROOT CAUSE → CLARITY`
- Body: `Ally doesn't just ask what's wrong. It helps you understand what's actually happening underneath.`
- UI fragment: the report's reasoning chain, as labels only: `What you described` · `What Ally ruled out` · `The signal` · `The link to you` · `The conclusion`. Plus the six pillar names with empty tracks.

### Slide 5 — From clarity to action
- Eyebrow: `STEP THREE`
- Headline: `Clarity should` / *`lead somewhere.`*
- Supporting: `Recommendations aren't the finish line.` / `Your next move is.`
- Sequence: `ROOT CAUSE → RECOMMENDATION → ACTION → LEARNING`
- Body: `Ally helps turn what you understand into practical next steps.`

### Slide 6 — The 100 founder invitation
- Eyebrow: `AN INVITATION`
- Headline: `WE WANT 100 FOUNDERS` / `TO BUILD THIS WITH US.`
- Large numeral: `100`
- Offer line: `1 month of Ally Pro for ₹1.`
- Supporting: `Use it on your real business.` / `Give us your honest feedback.` / `Help us make Ally better for founders.`
- Small: `INDIA · 100 FOUNDERS · EARLY FEEDBACK`

### Slide 7 — Final CTA
- Eyebrow: `GOXL × ALLY`
- Headline: `LET ALLY` / `STAND WITH YOU.`
- Supporting: `Wherever you are in your journey, we'll start by understanding.`
- Offer block, three rows: `100 FOUNDERS` · `₹1` · `1 MONTH OF ALLY PRO`
- CTA: `Comment "ALLY" or DM me.`
- Final line: `Let's figure out the next move — together.`
- Footer: `GOXL × ALLY` · `goxlally.ai`

---

## 2. Visual composition per slide

All slides: 88 px margins, top bar (GOXL ⁕ ALLY left, goxlally.ai right), eyebrow with a short emerald dash, serif headline, thin emerald rule, one content block, footer with slide counter. Background: near-black forest green with faint topographic contour lines and a ghosted compass ring, positioned differently per slide so the set feels alive but related.

| Slide | Composition | Visual metaphor |
|---|---|---|
| 1 | Headline in the upper half. Lower half is one drawing: two thin lines enter from bottom-left and bottom-right, curve toward each other and continue as one emerald line upward. The word `ALLY` sits large, letterspaced, in mint at 14% opacity behind the drawing. | Two paths becoming one path. Not people, not hands. |
| 2 | Headline top. Middle: a horizontal founder journey line with five stage ticks. A second line, mint, runs parallel and slightly below it with a small `ALLY` label. The two lines never merge; they travel together. | Beside, not ahead or above. |
| 3 | Headline top-left, list of five "Your…" lines. Right-bottom: a card fragment of the context-intake UI with five labelled fields, one showing a cursor. | Listening before speaking. The interface is a form with room for the founder's own words. |
| 4 | Headline top. Left column: the four-step vertical sequence. Right column: a diagnostic card with the reasoning-chain labels and the six pillar names on empty tracks. | Looking underneath. Layers, not a chat bubble. |
| 5 | Headline and two-line supporting. Middle: four chips joined by arrows on one horizontal line. Body copy below. Nothing else. | A line that goes somewhere. |
| 6 | Headline top. A very large serif `100` occupies the centre-left, with the offer line and three supporting lines to its right and below. | A room with 100 seats, not a price tag. |
| 7 | Headline top. Offer block as a bordered card with three rows. CTA line in mint. Final line in serif italic. | The door is open. |

---

## 3. Typography hierarchy

| Level | Face | Size | Colour | Use |
|---|---|---|---|---|
| Eyebrow | Inter 500, caps, +30% tracking | 20 px | mint | Orientation |
| Headline | Playfair Display 400 (italic for emphasis words) | 84–104 px | off-white, emphasis in mint | The story beat |
| Headline caps variant | Playfair Display 500, caps, +6% tracking | 68–76 px | off-white | Slides 1, 6, 7 |
| Supporting | Inter 400 | 28–30 px | muted, key line in off-white 600 | One or two lines |
| Sequence chips | Inter 600, caps, +24% tracking | 20–22 px | off-white on card | Process steps |
| UI text | Inter 400/500 | 12–16 px | off-white / muted | Interface fragments |
| Numeral | Playfair Display 400 | 320 px | off-white | Slide 6 |
| Footer | Inter 600, caps, +30% tracking | 15 px | dim, URL in mint | Brand line |

Colour tokens: bg #0B1F17 · card #12291F · line #1C3D2E · emerald #2ECC71 · mint #BFE8D2 · text #F3EFE6 · muted #8FA69A · dim #5F7A6D. No other colours anywhere in this campaign.

---

## 4. Generation prompts (for an image model, if regenerating outside the HTML renderer)

Shared prefix for every prompt:

> Premium editorial LinkedIn carousel slide, 1080 by 1350 portrait, near-black forest green background (#0B1F17) with faint topographic contour lines in #2A5A42 at 10–20% opacity and a ghosted compass ring in emerald at 7% opacity. Top-left "GOXL ⁕ ALLY" in small letterspaced caps, top-right "goxlally.ai" in green-grey. A small mint caps eyebrow with a short emerald dash. High-contrast editorial serif (Playfair Display) for headlines in warm off-white (#F3EFE6) with emphasis words in soft mint (#BFE8D2) italic. Clean grotesque sans (Inter) for everything else. Emerald (#2ECC71) is the only saturated colour, used sparingly. Generous negative space. McKinsey × Linear × Stripe restraint. Negative: robots, humanoid figures, hands, handshakes, stock photos, neon, cyberpunk, glassmorphism, 3D renders, decorative gradients, icons beyond arrows, clutter.

1. **Hook.** Eyebrow "GOXL × ALLY". Serif caps headline "YOU DON'T HAVE TO / BUILD ALONE." at 76 px in the upper half. Beneath, "That's what an Ally is for." in green-grey sans. Lower half: a single line drawing of two thin lines entering from bottom-left and bottom-right, curving toward each other and continuing upward as one emerald line; behind it, the word "ALLY" in mint at 14% opacity, very large and letterspaced. Footer "GOXL × ALLY" left, "01 / 07" right.
2. **What Ally means.** Eyebrow "WHAT ALLY MEANS". Serif headline "An ally / stands with you." with the second line in mint italic. Three short sans lines: "Not ahead of you. / Not above you. / Beside you." Body line in green-grey. Middle-lower: a horizontal founder journey line in #1C3D2E with five small emerald ticks labelled IDEA, FIRST PRODUCT, FIRST CUSTOMERS, TRACTION, SCALING; a parallel mint line runs just beneath it, labelled "ALLY", travelling alongside and never merging. Footer "02 / 07".
3. **First, we understand you.** Eyebrow "STEP ONE". Serif headline "First, we / understand you." Five stacked sans lines "Your journey. Your business. Your challenges. Your stage. Your context." Body: "Because the right recommendation starts with the right understanding." Lower-right: a dark UI card (#12291F, 1 px #1C3D2E border, 20 px radius) titled "FOUNDER CONTEXT" with five labelled empty input fields — "Where you are", "What you're building", "Your biggest challenge right now", "Your 90-day goal", "How you like to be told things" — the first showing a blinking emerald cursor. No chat bubbles. Footer "03 / 07".
4. **Underneath the symptoms.** Eyebrow "STEP TWO". Serif headline "Then we look / underneath the symptoms." Left: a vertical sequence UNDERSTAND → DIAGNOSE → ROOT CAUSE → CLARITY joined by a thin emerald line. Right: a UI card titled "ROOT CAUSE ANALYSIS" listing five reasoning labels "What you described / What Ally ruled out / The signal / The link to you / The conclusion" as numbered rows, and beneath a small list of six pillar names (Founder Readiness, Market Clarity, Revenue Maturity, Product & Execution, Team & Leadership, Strategic Clarity) each with an empty track. Body: "Ally doesn't just ask what's wrong. It helps you understand what's actually happening underneath." Footer "04 / 07".
5. **Clarity should lead somewhere.** Eyebrow "STEP THREE". Serif headline "Clarity should / lead somewhere." Two sans lines: "Recommendations aren't the finish line." in green-grey and "Your next move is." in off-white. Middle: four bordered chips on one line — ROOT CAUSE → RECOMMENDATION → ACTION → LEARNING — with thin emerald arrows; the last chip outlined in emerald. Body: "Ally helps turn what you understand into practical next steps." Footer "05 / 07".
6. **100 founders.** Eyebrow "AN INVITATION". Serif caps headline "WE WANT 100 FOUNDERS / TO BUILD THIS WITH US." A very large serif numeral "100" in off-white, roughly 320 px, centre-left. Beside and beneath: "1 month of Ally Pro for ₹1." in off-white sans 600, then three green-grey lines "Use it on your real business. / Give us your honest feedback. / Help us make Ally better for founders." Small caps line "INDIA · 100 FOUNDERS · EARLY FEEDBACK". No price-tag graphics, no badges, no strike-through prices. Footer "06 / 07".
7. **Final CTA.** Eyebrow "GOXL × ALLY". Serif caps headline "LET ALLY / STAND WITH YOU." Sans line "Wherever you are in your journey, we'll start by understanding." A bordered card with three rows in letterspaced caps: "100 FOUNDERS", "₹1", "1 MONTH OF ALLY PRO", the ₹1 row in serif at larger size. Below: "Comment "ALLY" or DM me." in mint, then serif italic "Let's figure out the next move — together." Footer "GOXL × ALLY" left, "goxlally.ai" right in mint.

---

## 5. Consistency rules

- One content block per slide. If a second visual appears, remove it.
- The journey/sequence motif appears on slides 1, 2, 4 and 5 with the same stroke weight (1 px lines, 11 px emerald dots).
- The UI card style on slides 3 and 4 is identical to the NyayaSetu dashboard card: #12291F fill, 1 px #1C3D2E border, 20 px radius, no shadow.
- Slides 1, 6 and 7 use the serif caps headline; slides 2 to 5 use the serif sentence-case headline with a mint italic second line. This alternation marks the emotional slides from the explanatory ones.
- No UI fragment shows a real founder's data. Fields are empty and reasoning labels are structural. That keeps the campaign honest and avoids implying a result.
- Nothing promises growth. "Grow with Ally" is not used on any slide; the closest line is "Let's figure out the next move — together."
