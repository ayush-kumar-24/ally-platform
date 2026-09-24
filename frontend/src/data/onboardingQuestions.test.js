/**
 * Path-scoping regression tests for the onboarding question model.
 *
 * Uses Node's built-in test runner (`node --test`) deliberately: this project
 * has no test framework, and the module under test has zero imports, so
 * covering it needs no new dependency.
 *
 * These exist because of a live bug: a founder who selected Ideation (Stage 0)
 * was shown the Business Reality block -- "Revenue is predictable",
 * "Financials are clear - cost, margin, runway", "Team operates without
 * dependency" -- which is PATH_2-only precisely because a Stage 0 founder has
 * no business to assess structure on.
 */

import test from 'node:test';
import assert from 'node:assert/strict';

import {
  activeParts,
  PATH_1,
  PATH_2,
  QUESTIONS,
  STAGE_BY_NAME,
} from './onboardingQuestions.js';

const group = (key) => QUESTIONS.find((q) => q.key === key);
const keys = (parts) => parts.map((p) => p.key);

const reality = group('reality');
const stageExperience = group('stageExperience');

test('1. PATH_1 excludes the PATH_2-only businessReality block', () => {
  assert.ok(!keys(activeParts(reality, PATH_1)).includes('businessReality'));
});

test('2. PATH_2 still receives businessReality', () => {
  assert.ok(keys(activeParts(reality, PATH_2)).includes('businessReality'));
});

test('3. null path excludes parts scoped to a subset of paths', () => {
  assert.ok(!keys(activeParts(reality, null)).includes('businessReality'));
});

test('4. null path keeps parts eligible on every path', () => {
  // invisibleGaps is [PATH_1, PATH_2]: applicable whoever the founder turns
  // out to be, so an unknown path must not hide it.
  assert.ok(keys(activeParts(reality, null)).includes('invisibleGaps'));
});

test('5. Ideation maps to PATH_1', () => {
  assert.equal(STAGE_BY_NAME.Ideation.path, PATH_1);
});

test('6. a Stage 0 founder never sees businessReality, even if the stored '
  + 'stage value yields an unknown/null path', () => {
  // The reported failure mode: STAGE_BY_NAME[stored] is undefined, so
  // ProfileBuild derives `path = null` and every path-scoped part rendered.
  for (const stored of [undefined, null, '', 'Ideation ', 'ideation', 'stage_0',
    'Stage 0', 'Just exploring ideas', 1, 'Early Traction ']) {
    const derived = STAGE_BY_NAME[stored]?.path || null;
    assert.ok(
      !keys(activeParts(reality, derived)).includes('businessReality'),
      `businessReality leaked for stored stage ${JSON.stringify(stored)}`,
    );
  }
});

test('7. the guard does not empty the group that holds the stage question', () => {
  // Every part in every group declares an explicit `paths`, so a naive
  // "exclude anything path-scoped when path is null" empties Q3 -- and the
  // founder could then never answer the question that SETS the path.
  assert.ok(keys(activeParts(stageExperience, null)).includes('stage'));
});

test('8. no group is emptied by an unknown path', () => {
  for (const q of QUESTIONS.filter((x) => x.type === 'group')) {
    assert.ok(activeParts(q, null).length > 0, `group ${q.key} emptied at null path`);
  }
});

test('9. every known path still receives every part scoped to it', () => {
  for (const q of QUESTIONS.filter((x) => x.type === 'group')) {
    for (const path of [PATH_1, PATH_2]) {
      const expected = q.parts.filter((p) => !p.paths || p.paths.includes(path));
      assert.deepEqual(keys(activeParts(q, path)), keys(expected));
    }
  }
});

test('10. revenue, the other PATH_2-only part, is also excluded at null', () => {
  assert.ok(!keys(activeParts(stageExperience, null)).includes('revenue'));
  assert.ok(keys(activeParts(stageExperience, PATH_2)).includes('revenue'));
});
