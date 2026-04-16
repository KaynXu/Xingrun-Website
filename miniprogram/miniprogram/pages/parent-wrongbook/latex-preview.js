const SUPERSCRIPT_TRANSLATION = {
  0: '⁰',
  1: '¹',
  2: '²',
  3: '³',
  4: '⁴',
  5: '⁵',
  6: '⁶',
  7: '⁷',
  8: '⁸',
  9: '⁹',
  '+': '⁺',
  '-': '⁻',
  '=': '⁼',
  '(': '⁽',
  ')': '⁾',
  n: 'ⁿ',
  i: 'ⁱ',
};

const SUPERSCRIPT_LETTER_MAP = {
  a: 'ᵃ',
  b: 'ᵇ',
  c: 'ᶜ',
  d: 'ᵈ',
  e: 'ᵉ',
  f: 'ᶠ',
  g: 'ᵍ',
  h: 'ʰ',
  j: 'ʲ',
  k: 'ᵏ',
  l: 'ˡ',
  m: 'ᵐ',
  o: 'ᵒ',
  p: 'ᵖ',
  r: 'ʳ',
  s: 'ˢ',
  t: 'ᵗ',
  u: 'ᵘ',
  v: 'ᵛ',
  w: 'ʷ',
  x: 'ˣ',
  y: 'ʸ',
};

const SUBSCRIPT_DIGIT_MAP = {
  0: '₀',
  1: '₁',
  2: '₂',
  3: '₃',
  4: '₄',
  5: '₅',
  6: '₆',
  7: '₇',
  8: '₈',
  9: '₉',
};

const SUBSCRIPT_LETTER_MAP = {
  a: 'ₐ',
  e: 'ₑ',
  h: 'ₕ',
  k: 'ₖ',
  l: 'ₗ',
  m: 'ₘ',
  n: 'ₙ',
  o: 'ₒ',
  p: 'ₚ',
  s: 'ₛ',
  t: 'ₜ',
  x: 'ₓ',
};

const MATHBB_SET_MAP = {
  C: 'ℂ',
  N: 'ℕ',
  Q: 'ℚ',
  R: 'ℝ',
  Z: 'ℤ',
};

const TEXT_REPLACEMENTS = [
  ['\\infty', '∞'],
  ['\\Rightarrow', '⇒'],
  ['\\Leftarrow', '⇐'],
  ['\\rightarrow', '→'],
  ['\\leftarrow', '←'],
  ['\\subseteq', '⊆'],
  ['\\supseteq', '⊇'],
  ['\\subset', '⊂'],
  ['\\supset', '⊃'],
  ['\\notin', '∉'],
  ['\\approx', '≈'],
  ['\\geq', '≥'],
  ['\\ge', '≥'],
  ['\\leq', '≤'],
  ['\\le', '≤'],
  ['\\neq', '≠'],
  ['\\times', '×'],
  ['\\cdot', '·'],
  ['\\ldots', '...'],
  ['\\cdots', '...'],
  ['\\dots', '...'],
  ['\\div', '÷'],
  ['\\pm', '±'],
  ['\\in', '∈'],
  ['\\to', '→'],
  ['\\left', ''],
  ['\\right', ''],
];

const LITERAL_DOLLAR_PLACEHOLDER = '__XR_LITERAL_DOLLAR__';

function replaceAll(value, search, replacement) {
  return String(value).split(search).join(replacement);
}

function renderSuperscript(content) {
  return Array.from(String(content || '')).map((character) => {
    if (SUPERSCRIPT_TRANSLATION[character]) {
      return SUPERSCRIPT_TRANSLATION[character];
    }
    return SUPERSCRIPT_LETTER_MAP[String(character).toLowerCase()] || character;
  }).join('');
}

function renderSubscript(content) {
  const rendered = [];
  const characters = Array.from(String(content || ''));

  for (let index = 0; index < characters.length; index += 1) {
    const character = characters[index];
    if (SUBSCRIPT_DIGIT_MAP[character]) {
      rendered.push(SUBSCRIPT_DIGIT_MAP[character]);
      continue;
    }

    const mappedLetter = SUBSCRIPT_LETTER_MAP[String(character).toLowerCase()];
    if (mappedLetter) {
      rendered.push(mappedLetter);
      continue;
    }

    return '_(' + content + ')';
  }

  return rendered.join('');
}

function repairWrongQuestionLatexTransport(value) {
  let repaired = String(value || '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\t/g, '\\t')
    .replace(/\f/g, '\\f');

  repaired = replaceAll(repaired, String.fromCharCode(8), '\\b');
  return repaired;
}

function normalizeBareLatexText(value) {
  let normalized = replaceAll(String(value || ''), '\\$', '$');

  for (let loop = 0; loop < 5; loop += 1) {
    const next = normalized
      .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '($1)/($2)')
      .replace(/\\sqrt\{([^{}]+)\}/g, '√($1)');
    if (next === normalized) {
      break;
    }
    normalized = next;
  }

  normalized = normalized.replace(/\\text\{([^{}]+)\}/g, '$1');
  normalized = normalized.replace(/\\mathbb\s*\{?([A-Za-z])\}?/g, function (_match, letter) {
    return MATHBB_SET_MAP[letter] || letter;
  });
  normalized = normalized.replace(/\^\{([^{}]+)\}/g, function (_match, content) {
    return renderSuperscript(content);
  });
  normalized = normalized.replace(/\^([0-9n()+\-=i])/g, function (_match, content) {
    return renderSuperscript(content);
  });
  normalized = normalized.replace(/\^([a-zA-Z])/g, function (_match, content) {
    return renderSuperscript(content);
  });
  normalized = normalized.replace(/_\{([^{}]+)\}/g, function (_match, content) {
    return renderSubscript(content);
  });
  normalized = normalized.replace(/_([a-zA-Z0-9])/g, function (_match, content) {
    return renderSubscript(content);
  });

  for (let index = 0; index < TEXT_REPLACEMENTS.length; index += 1) {
    const replacement = TEXT_REPLACEMENTS[index];
    normalized = replaceAll(normalized, replacement[0], replacement[1]);
  }

  return normalized;
}

function normalizeWrongQuestionLatexPreviewText(value) {
  let normalized = repairWrongQuestionLatexTransport(value);

  normalized = replaceAll(normalized, '\\$', LITERAL_DOLLAR_PLACEHOLDER);
  normalized = normalized.replace(/\$\$/g, '\n');
  normalized = normalized.replace(/\$/g, '');
  normalized = normalizeBareLatexText(normalized);
  normalized = replaceAll(normalized, LITERAL_DOLLAR_PLACEHOLDER, '$');
  normalized = normalized
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return normalized;
}

module.exports = {
  normalizeWrongQuestionLatexPreviewText,
};
