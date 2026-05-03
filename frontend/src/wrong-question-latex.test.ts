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

test('buildWrongQuestionLatexPreviewModel supports bracket-style latex delimiters', () => {
  const preview = buildWrongQuestionLatexPreviewModel('计算 \\(x^2 + 1\\)，并化简：\\[\\frac{x^2+1}{2}\\]');

  assert.match(preview.html, /katex/);
  assert.doesNotMatch(preview.html, /\\\(|\\\)|\\\[|\\\]/);
  assert.doesNotMatch(preview.html, /\\frac/);
  assert.equal(preview.errors.length, 0);
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

test('parseWrongQuestionLatexSegments repairs latex commands eaten by json escaping', () => {
  const parsed = parseWrongQuestionLatexSegments('计算 $$f(3)=1+\text{lim}_{x \to 3^-}f(x)+\frac{1}{2}$$，并判断 $f(3) \neq \text{lim}_{x \to 3} f(x)$');

  assert.equal(parsed.errors.length, 0);
  assert.equal(parsed.segments[1]?.type, 'math');
  assert.equal(
    parsed.segments[1]?.type === 'math' ? parsed.segments[1].value : '',
    'f(3)=1+\\text{lim}_{x \\to 3^-}f(x)+\\frac{1}{2}',
  );
  assert.equal(parsed.segments[3]?.type, 'math');
  assert.equal(
    parsed.segments[3]?.type === 'math' ? parsed.segments[3].value : '',
    'f(3) \\neq \\text{lim}_{x \\to 3} f(x)',
  );
});

test('parseWrongQuestionLatexSegments repairs right delimiters eaten by json escaping', () => {
  const rootPreview = buildWrongQuestionLatexPreviewModel(
    '计算 $\\sqrt[4]{4 - \\left(\\frac{3}{5}' + '\right)^2} \\times \\sqrt[3]{\\frac{8}{27}} - \\sqrt[3]{-1}$',
  );
  const absoluteValuePreview = buildWrongQuestionLatexPreviewModel(
    '记 $Q(M) = \\left| \\frac{4d - 3c}{2b - a}' + '\right|$',
  );

  assert.equal(rootPreview.errors.length, 0);
  assert.equal(absoluteValuePreview.errors.length, 0);
  assert.match(rootPreview.html, /katex/);
  assert.match(absoluteValuePreview.html, /katex/);
});

test('buildWrongQuestionLatexPreviewModel normalizes bare latex fragments inside prose', () => {
  const preview = buildWrongQuestionLatexPreviewModel(
    '已知函数 f(x)=(x-1)e^{-ax}（a \\in \\mathbbR），e=2.71828\\ldots，且 a<m<a\\frac{a+e}{ae}-1。',
  );

  assert.equal(preview.errors.length, 0);
  assert.doesNotMatch(preview.html, /\\in|\\mathbb|\\ldots|\\frac/);
  assert.match(preview.html, /∈/);
  assert.match(preview.html, /ℝ|R/);
  assert.match(preview.html, /\.\.\./);
  assert.match(preview.html, /\/\(/);
});

test('buildWrongQuestionLatexPreviewModel turns literal newline escapes back into line breaks without breaking latex commands', () => {
  const preview = buildWrongQuestionLatexPreviewModel(
    '第一步先看条件\\n\\n(2) 若 a > e，证明 $f(3) \\neq 1$。',
  );

  assert.equal(preview.errors.length, 0);
  assert.doesNotMatch(preview.html, /\\n/);
  assert.match(preview.html, /<br \/><br \/>/);
  assert.match(preview.html, /katex/);
});

test('buildWrongQuestionLatexPreviewModel repairs malformed escape sequences and readable bare latex fragments', () => {
  const malformedText = '已知函数 f(x)='
    + '\f'
    + 'rac{x^2+1}{2}，且 '
    + '\t'
    + 'ext{lim}_{x '
    + '\t'
    + 'o 3^-}f(x) '
    + '\n'
    + 'eq 1，向量 '
    + String.raw`\overrightarrow{AB}`
    + ' 长度为 '
    + String.raw`\sqrt{16}`
    + '。';

  const preview = buildWrongQuestionLatexPreviewModel(malformedText);

  assert.equal(preview.errors.length, 0);
  assert.doesNotMatch(preview.html, /\\(?:frac|text|to|neq|overrightarrow|sqrt)/);
  assert.match(preview.html, /\(x²\+1\)\/\(2\)/);
  assert.match(preview.html, /lim/);
  assert.match(preview.html, /≠/);
  assert.match(preview.html, /向量 AB 长度为 √\(16\)/);
});
