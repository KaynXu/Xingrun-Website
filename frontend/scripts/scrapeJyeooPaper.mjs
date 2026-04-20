import { mkdir, writeFile } from 'node:fs/promises';
import { basename, dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { JSDOM } from 'jsdom';

const DEFAULT_USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36';

const OPERATOR_LATEX_MAP = new Map([
  ['＜', ' < '],
  ['＞', ' > '],
  ['=', ' = '],
  ['≤', ' \\le '],
  ['≥', ' \\ge '],
  ['∈', ' \\in '],
  ['∉', ' \\notin '],
  ['∥', ' \\parallel '],
  ['⊥', ' \\perp '],
  ['•', ' \\cdot '],
  ['…', '\\ldots '],
  ['，', ', '],
  ['．', '.'],
  ['。', '.'],
  ['（', '('],
  ['）', ')'],
  ['【', '['],
  ['】', ']'],
]);

const FUNCTION_PREFIXES = ['sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'ln', 'log', 'lim'];

function normalizeWhitespace(value, { preserveLineBreaks = false } = {}) {
  const source = String(value ?? '')
    .replaceAll('\u00a0', ' ')
    .replaceAll('\r', '');

  if (preserveLineBreaks) {
    return source
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n[ \t]+/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .replace(/[ \t]{2,}/g, ' ')
      .trim();
  }

  return source.replace(/\s+/g, ' ').trim();
}

function sanitizeFileStem(value) {
  return String(value ?? '')
    .trim()
    .replace(/[^\p{L}\p{N}._-]+/gu, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '') || 'output';
}

function cloneWithoutSelectors(element, selectors) {
  const clone = element.cloneNode(true);

  for (const selector of selectors) {
    clone.querySelectorAll(selector).forEach((node) => node.remove());
  }

  return clone;
}

function collectNodeText(node) {
  if (!node) {
    return '';
  }

  if (node.nodeType === node.TEXT_NODE) {
    return node.nodeValue ?? '';
  }

  if (node.nodeType !== node.ELEMENT_NODE) {
    return '';
  }

  if (node.tagName === 'BR') {
    return '\n';
  }

  if (node.tagName === 'SUP') {
    const value = normalizeWhitespace(Array.from(node.childNodes).map((child) => collectNodeText(child)).join(''));
    return value ? `^${value}` : '';
  }

  if (node.tagName === 'SUB') {
    const value = normalizeWhitespace(Array.from(node.childNodes).map((child) => collectNodeText(child)).join(''));
    return value ? `_${value}` : '';
  }

  if (node.tagName === 'IMG') {
    return '';
  }

  return Array.from(node.childNodes)
    .map((child) => collectNodeText(child))
    .join('');
}

function elementToPlainText(element, selectorsToDrop = []) {
  const clone = cloneWithoutSelectors(element, selectorsToDrop);
  clone.querySelectorAll('.MathJye[mathtag="math"]').forEach((node) => {
    const latex = mathNodeToLatex(node);
    node.replaceWith(clone.ownerDocument.createTextNode(latex));
  });
  return normalizeWhitespace(collectNodeText(clone), { preserveLineBreaks: true });
}

function normalizeLatexSpacing(value) {
  return String(value ?? '')
    .replace(/\s+/g, ' ')
    .replace(/\s+([,.;:!?])/g, '$1')
    .replace(/([(])\s+/g, '$1')
    .replace(/\s+([)\]])/g, '$1')
    .replace(/\{\s+/g, '{')
    .replace(/\s+\}/g, '}')
    .trim();
}

function stripOuterBraces(value) {
  if (value.startsWith('{') && value.endsWith('}')) {
    return value.slice(1, -1);
  }

  return value;
}

function wrapScript(value) {
  const normalized = normalizeLatexSpacing(value);
  return `{${stripOuterBraces(normalized)}}`;
}

function normalizeMathToken(value) {
  let normalized = normalizeWhitespace(value);

  if (!normalized) {
    return '';
  }

  if (OPERATOR_LATEX_MAP.has(normalized)) {
    return OPERATOR_LATEX_MAP.get(normalized);
  }

  normalized = normalized.replaceAll('π', '\\pi ');
  normalized = normalized.replaceAll('∞', '\\infty ');

  for (const prefix of FUNCTION_PREFIXES) {
    if (normalized === prefix) {
      return `\\${prefix} `;
    }

    if (normalized.startsWith(prefix) && normalized.length > prefix.length) {
      normalized = `\\${prefix} ${normalized.slice(prefix.length)}`;
      break;
    }
  }

  return normalized;
}

function mathNodeToLatex(node) {
  if (!node) {
    return '';
  }

  if (node.nodeType === node.TEXT_NODE) {
    return normalizeMathToken(node.nodeValue);
  }

  if (node.nodeType !== node.ELEMENT_NODE) {
    return '';
  }

  const classNames = new Set(String(node.className || '').split(/\s+/).filter(Boolean));

  if (classNames.has('mfrac')) {
    const numerator = mathNodesToLatex(node.querySelector('.fracZi')?.childNodes ?? []);
    const denominator = mathNodesToLatex(node.querySelector('.fracMu')?.childNodes ?? []);
    return `\\frac{${stripOuterBraces(numerator)}}{${stripOuterBraces(denominator)}}`;
  }

  if (classNames.has('msqrt')) {
    const radicand = mathNodesToLatex(node.querySelector('.msqrtBox')?.childNodes ?? []);
    return `\\sqrt{${stripOuterBraces(radicand)}}`;
  }

  if (classNames.has('msubsup')) {
    const base = mathNodesToLatex(node.querySelector('.msubsupCont')?.childNodes ?? []);
    const subscript = mathNodesToLatex(node.querySelector('.msub')?.childNodes ?? []);
    const superscript = mathNodesToLatex(node.querySelector('.msup')?.childNodes ?? []);

    if (subscript && superscript) {
      return `${normalizeLatexSpacing(base)}_${wrapScript(subscript)}^${wrapScript(superscript)}`;
    }

    if (subscript) {
      return `${normalizeLatexSpacing(base)}_${wrapScript(subscript)}`;
    }

    if (superscript) {
      return `${normalizeLatexSpacing(base)}^${wrapScript(superscript)}`;
    }

    return normalizeLatexSpacing(base);
  }

  if (classNames.has('mover')) {
    const base = mathNodesToLatex(node.querySelector('.base')?.childNodes ?? []);

    if (node.querySelector('.stretchArrow')) {
      return `\\overrightarrow{${stripOuterBraces(base)}}`;
    }

    return normalizeLatexSpacing(base);
  }

  if (
    classNames.has('mrow') ||
    classNames.has('base') ||
    classNames.has('baseCont') ||
    classNames.has('msub') ||
    classNames.has('msup') ||
    classNames.has('fracZi') ||
    classNames.has('fracMu') ||
    classNames.has('msqrtBox')
  ) {
    return mathNodesToLatex(node.childNodes);
  }

  if (classNames.has('math-letter') || classNames.has('mo')) {
    return normalizeMathToken(node.textContent);
  }

  return mathNodesToLatex(node.childNodes);
}

function mathNodesToLatex(nodes) {
  return normalizeLatexSpacing(
    Array.from(nodes ?? [])
      .map((node) => mathNodeToLatex(node))
      .join(''),
  );
}

export function mathJyeHtmlToLatex(mathHtml) {
  const dom = new JSDOM(`<body>${mathHtml}</body>`);
  const mathNode = dom.window.document.body.firstElementChild;
  return mathNode ? mathNodeToLatex(mathNode) : '';
}

function buildOptionRecord(labelNode) {
  const rawText = elementToPlainText(labelNode);
  const optionMatch = rawText.match(/^([A-Z])[．.]\s*(.*)$/);
  const optionLabel = optionMatch?.[1] ?? null;
  const optionText = optionMatch?.[2] ?? rawText;

  return {
    label: optionLabel,
    text_plain: optionText,
    html_raw: labelNode.innerHTML,
  };
}

function extractQuestionRecord(section, questionType, pageUrl) {
  const headerNode = section.querySelector('.pt1 h2');
  const questionNoText = normalizeWhitespace(headerNode?.querySelector('.qseq')?.textContent ?? '');
  const questionNo = Number.parseInt(questionNoText.replace(/[^\d]/g, ''), 10);
  const mathBlocks = Array.from(section.querySelectorAll('.MathJye[mathtag="math"]'));
  const imageUrls = Array.from(section.querySelectorAll('img'))
    .map((node) => node.getAttribute('src'))
    .filter(Boolean)
    .map((src) => new URL(src, pageUrl).href);
  const options = Array.from(section.querySelectorAll('.pt2 .selectoption label')).map((labelNode) => buildOptionRecord(labelNode));

  return {
    question_no: Number.isFinite(questionNo) ? questionNo : null,
    question_type: questionType,
    html_raw: section.outerHTML,
    math_blocks_raw: mathBlocks.map((node) => node.outerHTML),
    image_urls: imageUrls,
    image_local_paths: [],
    text_plain: headerNode ? elementToPlainText(headerNode, ['.qseq', 'img']) : '',
    options,
    latex_segments: mathBlocks
      .map((node, index) => ({
        index,
        latex: mathNodeToLatex(node),
      }))
      .filter((segment) => segment.latex),
  };
}

export function parseJyeooExamHtml(html, pageUrl) {
  const dom = new JSDOM(html);
  const { document } = dom.window;
  const paperTitle = normalizeWhitespace(document.querySelector('title')?.textContent ?? '').replace(/\s*-\s*菁优网\s*$/, '');
  const questions = [];

  for (const list of Array.from(document.querySelectorAll('.ques-list.list-box'))) {
    let header = list.previousElementSibling;

    while (header && header.tagName !== 'H3') {
      header = header.previousElementSibling;
    }

    const questionType = normalizeWhitespace(header?.textContent ?? '');

    for (const item of Array.from(list.children)) {
      if (!(item instanceof dom.window.HTMLElement) || !item.matches('li.QUES_LI')) {
        continue;
      }

      const section = item.querySelector('section.quesborder');

      if (!section) {
        continue;
      }

      questions.push(extractQuestionRecord(section, questionType, pageUrl));
    }
  }

  return {
    source_url: pageUrl,
    fetched_at: new Date().toISOString(),
    paper_title: paperTitle,
    question_count: questions.length,
    questions,
  };
}

function inferExtension(url, contentType) {
  const pathname = new URL(url).pathname;
  const extFromPath = extname(pathname);

  if (extFromPath) {
    return extFromPath;
  }

  if (contentType?.includes('png')) {
    return '.png';
  }

  if (contentType?.includes('jpeg')) {
    return '.jpg';
  }

  if (contentType?.includes('svg')) {
    return '.svg';
  }

  return '.bin';
}

async function downloadQuestionImages(questions, assetDirPath, fetchImpl) {
  if (!questions.some((question) => question.image_urls.length > 0)) {
    return;
  }

  await mkdir(assetDirPath, { recursive: true });
  let imageCounter = 0;

  for (const question of questions) {
    const localPaths = [];

    for (const imageUrl of question.image_urls) {
      const response = await fetchImpl(imageUrl, {
        headers: {
          'user-agent': DEFAULT_USER_AGENT,
          referer: 'https://www.jyeoo.com/',
        },
      });

      if (!response.ok) {
        continue;
      }

      const extension = inferExtension(imageUrl, response.headers.get('content-type'));
      const fileName = `q${String(question.question_no ?? 'unknown').padStart(3, '0')}-${String(imageCounter + 1).padStart(2, '0')}${extension}`;
      const absolutePath = resolve(assetDirPath, fileName);
      const buffer = Buffer.from(await response.arrayBuffer());
      await writeFile(absolutePath, buffer);
      localPaths.push(absolutePath);
      imageCounter += 1;
    }

    question.image_local_paths = localPaths;
  }
}

async function fetchExamHtml(url, fetchImpl) {
  const response = await fetchImpl(url, {
    headers: {
      'user-agent': DEFAULT_USER_AGENT,
      accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
  }

  return await response.text();
}

export async function scrapeJyeooPaper({
  url,
  outputPath,
  fetchImpl = fetch,
} = {}) {
  if (!url) {
    throw new Error('scrapeJyeooPaper requires a url');
  }

  const html = await fetchExamHtml(url, fetchImpl);
  const result = parseJyeooExamHtml(html, url);

  if (outputPath) {
    const absoluteOutputPath = resolve(outputPath);
    const outputStem = sanitizeFileStem(basename(absoluteOutputPath, extname(absoluteOutputPath)));
    const assetDirPath = resolve(dirname(absoluteOutputPath), `${outputStem}-assets`);
    await mkdir(dirname(absoluteOutputPath), { recursive: true });
    await downloadQuestionImages(result.questions, assetDirPath, fetchImpl);
    await writeFile(absoluteOutputPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  }

  return result;
}

async function runCli() {
  const [, , url, outputPath] = process.argv;

  if (!url) {
    console.error('Usage: node frontend/scripts/scrapeJyeooPaper.mjs <url> [outputPath]');
    process.exitCode = 1;
    return;
  }

  const result = await scrapeJyeooPaper({
    url,
    outputPath,
  });

  console.log(
    JSON.stringify(
      {
        paper_title: result.paper_title,
        question_count: result.question_count,
        output_path: outputPath ? resolve(outputPath) : null,
      },
      null,
      2,
    ),
  );
}

const currentModulePath = fileURLToPath(import.meta.url);

if (process.argv[1] && resolve(process.argv[1]) === currentModulePath) {
  runCli().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
