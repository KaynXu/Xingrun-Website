import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildWrongQuestionLatexPreviewModel,
  hasWrongQuestionLatexErrors,
  parseWrongQuestionLatexSegments,
} from './wrongQuestionLatex.js';

test('parseWrongQuestionLatexSegments keeps prose and extracts inline/display formulas', () => {
  const parsed = parseWrongQuestionLatexSegments('计算 $x^2 + 1$，并化简：\n$$\\frac{x^2+1}{2}$$');

  assert.deepEqual(
    parsed.segments.map((segment) => ({
      type: segment.type,
      value: segment.value,
      displayMode: 'displayMode' in segment ? segment.displayMode : undefined,
    })),
    [
      { type: 'text', value: '计算 ', displayMode: undefined },
      { type: 'math', value: 'x^2 + 1', displayMode: false },
      { type: 'text', value: '，并化简：\n', displayMode: undefined },
      { type: 'math', value: '\\frac{x^2+1}{2}', displayMode: true },
    ],
  );
  assert.equal(parsed.errors.length, 0);
});

test('buildWrongQuestionLatexPreviewModel renders katex markup for valid formulas', () => {
  const preview = buildWrongQuestionLatexPreviewModel('计算 $x^2 + 1$，并化简：\n$$\\frac{x^2+1}{2}$$');

  assert.match(preview.html, /katex/);
  assert.match(preview.html, /xr-latex-display/);
  assert.equal(preview.errors.length, 0);
  assert.equal(hasWrongQuestionLatexErrors('计算 $x^2 + 1$'), false);
});

test('buildWrongQuestionLatexPreviewModel reports invalid latex but keeps the raw source visible', () => {
  const preview = buildWrongQuestionLatexPreviewModel('计算 $\\frac{1}{ $ 的结果。');

  assert.equal(preview.errors.length, 1);
  assert.equal(preview.errors[0]?.type, 'render');
  assert.match(preview.html, /xr-latex-error-source/);
  assert.match(preview.html, /\\frac\{1\}\{ /);
  assert.equal(hasWrongQuestionLatexErrors('计算 $\\frac{1}{ $ 的结果。'), true);
});

test('buildWrongQuestionLatexPreviewModel flags unmatched delimiters as parse errors', () => {
  const preview = buildWrongQuestionLatexPreviewModel('计算 $x^2 + 1 的结果。');

  assert.equal(preview.errors.length, 1);
  assert.equal(preview.errors[0]?.type, 'parse');
  assert.match(preview.errors[0]?.message ?? '', /未闭合/);
  assert.match(preview.html, /\$x\^2 \+ 1 的结果。/);
});
