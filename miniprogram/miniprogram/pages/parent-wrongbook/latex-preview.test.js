const assert = require('node:assert/strict');
const test = require('node:test');

const { normalizeWrongQuestionLatexPreviewText } = require('./latex-preview');

test('normalizeWrongQuestionLatexPreviewText removes latex delimiters and keeps formulas readable', () => {
  const preview = normalizeWrongQuestionLatexPreviewText(
    '已知函数 $f(x)=(x-1)e^{-ax}$（$a \\in \\mathbb{R}$），$e=2.71828\\ldots$，且 $a<m<a\\frac{a+e}{ae}-1$。',
  );

  assert.doesNotMatch(preview, /\$|\\in|\\mathbb|\\ldots|\\frac/);
  assert.match(preview, /f\(x\)=\(x-1\)/);
  assert.match(preview, /∈/);
  assert.match(preview, /ℝ/);
  assert.match(preview, /\.\.\./);
  assert.match(preview, /\(a\+e\)\/\(ae\)/);
});

test('normalizeWrongQuestionLatexPreviewText repairs transport-damaged latex commands', () => {
  const preview = normalizeWrongQuestionLatexPreviewText(
    'The function $f$ is continuous at $x=3$.\n$$f(3)=1+\text{lim}_{x \\to 3^-}f(x)+\text{lim}_{x \\to 3^+}f(x)$$',
  );

  assert.doesNotMatch(preview, /\$/);
  assert.match(preview, /f\(3\)=1\+lim/);
  assert.match(preview, /→/);
  assert.match(preview, /3⁻/);
  assert.match(preview, /3⁺/);
});
