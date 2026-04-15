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

function renderTextSegmentHtml(value) {
  return escapeHtml(String(value).replaceAll('\\$', '$')).replaceAll('\n', '<br />');
}

const BROKEN_NEWLINE_LATEX_COMMAND_PATTERN =
  /(?<![。！？.!?：:；;])\n(?=(?:eq\b|otin\b|abla\b|mid\b|parallel\b|subset(?:eq)?\b|supset(?:eq)?\b|rightarrow\b|leftarrow\b|Rightarrow\b|Leftarrow\b|iff\b))/g;

function repairWrongQuestionLatexTransport(value) {
  return String(value ?? '')
    .replaceAll('\r\n', '\n')
    .replaceAll('\t', '\\t')
    .replaceAll('\f', '\\f')
    .replaceAll('\b', '\\b')
    .replaceAll('\r', '\\r')
    .replace(BROKEN_NEWLINE_LATEX_COMMAND_PATTERN, '\\n');
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
      errors.push({
        type: 'parse',
        source: rawValue,
        message: `未闭合的${isDisplay ? '块级' : '行内'}公式分隔符`,
      });
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
      return renderTextSegmentHtml(segment.value);
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
      const message = error instanceof Error ? error.message : '公式渲染失败';
      errors.push({
        type: 'render',
        source: segment.raw,
        formula: segment.value,
        message,
      });
      return `<span class="xr-latex-error-source" title="${escapeHtml(message)}">${escapeHtml(segment.raw)}</span>`;
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
