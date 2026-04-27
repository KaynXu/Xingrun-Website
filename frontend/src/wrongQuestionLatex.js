import katex from 'katex';

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function isEscaped(text, index) {
  let backslashCount = 0;
  let cursor = index - 1;

  while (cursor >= 0 && text[cursor] === '\\') {
    backslashCount += 1;
    cursor -= 1;
  }

  return backslashCount % 2 === 1;
}

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

const BARE_LATEX_TEXT_REPLACEMENTS = [
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

function renderSuperscript(content) {
  return Array.from(content).map((character) => {
    if (SUPERSCRIPT_TRANSLATION[character]) {
      return SUPERSCRIPT_TRANSLATION[character];
    }

    return SUPERSCRIPT_LETTER_MAP[character.toLowerCase()] || character;
  }).join('');
}

function renderSubscript(content) {
  const rendered = [];

  for (const character of Array.from(content)) {
    if (SUBSCRIPT_DIGIT_MAP[character]) {
      rendered.push(SUBSCRIPT_DIGIT_MAP[character]);
      continue;
    }

    const mappedLetter = SUBSCRIPT_LETTER_MAP[character.toLowerCase()];
    if (mappedLetter) {
      rendered.push(mappedLetter);
      continue;
    }

    return `_(${content})`;
  }

  return rendered.join('');
}

function normalizeBareLatexText(value) {
  let normalized = String(value ?? '').replaceAll('\\$', '$');

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
  normalized = normalized.replace(/\\mathbb\s*\{?([A-Za-z])\}?/g, (_, letter) => MATHBB_SET_MAP[letter] || letter);
  normalized = normalized.replace(/\^\{([^{}]+)\}/g, (_, content) => renderSuperscript(content));
  normalized = normalized.replace(/\^([0-9n()+\-=i])/g, (_, content) => renderSuperscript(content));
  normalized = normalized.replace(/\^([a-zA-Z])/g, (_, content) => renderSuperscript(content));
  normalized = normalized.replace(/_\{([^{}]+)\}/g, (_, content) => renderSubscript(content));
  normalized = normalized.replace(/_([a-zA-Z0-9])/g, (_, content) => renderSubscript(content));

  for (const [source, target] of BARE_LATEX_TEXT_REPLACEMENTS) {
    normalized = normalized.replaceAll(source, target);
  }

  return normalized;
}

function renderTextSegmentHtml(value, { preserveRaw = false } = {}) {
  const renderedValue = preserveRaw ? String(value).replaceAll('\\$', '$') : normalizeBareLatexText(value);
  return escapeHtml(renderedValue).replaceAll('\n', '<br />');
}

const BROKEN_NEWLINE_LATEX_COMMAND_PATTERN =
  /(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))/g;
const BROKEN_CARRIAGE_RETURN_LATEX_COMMAND_PATTERN =
  /\r(?=(?:ight\b|ightarrow\b))/g;
const LITERAL_NEWLINE_LATEX_COMMAND_PATTERN =
  /\\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))/g;
const LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_PATTERN =
  /\\r(?=(?:ight\b|ightarrow\b))/g;
const LITERAL_NEWLINE_LATEX_COMMAND_TOKEN = 'XR_LITERAL_NEWLINE_LATEX_COMMAND_TOKEN';
const LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_TOKEN = 'XR_LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_TOKEN';

function repairWrongQuestionLatexTransport(value) {
  return String(value ?? '')
    .replaceAll('\r\n', '\n')
    .replaceAll('\\r\\n', '\n')
    .replaceAll('\t', '\\t')
    .replaceAll('\f', '\\f')
    .replaceAll('\b', '\\b')
    .replace(BROKEN_CARRIAGE_RETURN_LATEX_COMMAND_PATTERN, '\\r')
    .replaceAll('\r', '\n')
    .replace(BROKEN_NEWLINE_LATEX_COMMAND_PATTERN, '\\n')
    .replace(LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_PATTERN, LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_TOKEN)
    .replace(LITERAL_NEWLINE_LATEX_COMMAND_PATTERN, LITERAL_NEWLINE_LATEX_COMMAND_TOKEN)
    .replaceAll('\\n', '\n')
    .replaceAll('\\r', '\n')
    .replaceAll(LITERAL_NEWLINE_LATEX_COMMAND_TOKEN, '\\n')
    .replaceAll(LITERAL_CARRIAGE_RETURN_LATEX_COMMAND_TOKEN, '\\r')
    .replace(/(?<!\\)\\\[/g, '$$')
    .replace(/(?<!\\)\\\]/g, '$$')
    .replace(/(?<!\\)\\\(/g, '$')
    .replace(/(?<!\\)\\\)/g, '$');
}

export function parseWrongQuestionLatexSegments(input) {
  const text = repairWrongQuestionLatexTransport(input).replaceAll('\r\n', '\n').replaceAll('\r', '\n');
  const segments = [];
  const errors = [];
  let buffer = '';
  let index = 0;

  while (index < text.length) {
    if (text[index] !== '$' || isEscaped(text, index)) {
      buffer += text[index];
      index += 1;
      continue;
    }

    const isDisplay = text[index + 1] === '$' && !isEscaped(text, index + 1);
    const delimiter = isDisplay ? '$$' : '$';
    const startIndex = index;
    const delimiterLength = delimiter.length;

    if (buffer) {
      segments.push({ type: 'text', value: buffer });
      buffer = '';
    }

    index += delimiterLength;
    let formula = '';
    let closed = false;

    while (index < text.length) {
      if (text[index] === '$' && !isEscaped(text, index)) {
        if (isDisplay) {
          if (text[index + 1] === '$' && !isEscaped(text, index + 1)) {
            closed = true;
            index += 2;
            break;
          }
        } else {
          closed = true;
          index += 1;
          break;
        }
      }

      formula += text[index];
      index += 1;
    }

    if (!closed) {
      const rawValue = `${delimiter}${formula}`;
      segments.push({ type: 'text', value: rawValue });
      break;
    }

    segments.push({
      type: 'math',
      value: formula.trim(),
      raw: `${delimiter}${formula}${delimiter}`,
      displayMode: isDisplay,
      startIndex,
    });
  }

  if (buffer) {
    segments.push({ type: 'text', value: buffer });
  }

  return { segments, errors, normalizedText: text };
}

export function buildWrongQuestionLatexPreviewModel(input) {
  const parsed = parseWrongQuestionLatexSegments(input);
  const errors = [...parsed.errors];
  const htmlParts = parsed.segments.map((segment) => {
    if (segment.type === 'text') {
      return renderTextSegmentHtml(segment.value, { preserveRaw: Boolean(segment.preserveRaw) });
    }

    try {
      const rendered = katex.renderToString(segment.value, {
        displayMode: segment.displayMode,
        output: 'html',
        strict: 'ignore',
        throwOnError: true,
      });

      return segment.displayMode
        ? `<div class="xr-latex-display">${rendered}</div>`
        : rendered;
    } catch (error) {
      return renderTextSegmentHtml(segment.raw);
    }
  });

  return {
    normalizedText: parsed.normalizedText,
    html: htmlParts.join(''),
    errors,
  };
}

export function hasWrongQuestionLatexErrors(input) {
  return buildWrongQuestionLatexPreviewModel(input).errors.length > 0;
}
