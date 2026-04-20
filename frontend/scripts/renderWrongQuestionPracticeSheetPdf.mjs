import { constants as fsConstants } from 'node:fs';
import { access, mkdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { chromium } from 'playwright';

import { buildWrongQuestionLatexPreviewModel } from '../src/wrongQuestionLatex.js';

const currentFilePath = fileURLToPath(import.meta.url);
const currentDir = dirname(currentFilePath);
const katexCssPath = resolve(currentDir, '../node_modules/katex/dist/katex.min.css');
const COMMON_CHROMIUM_EXECUTABLE_PATHS = {
  darwin: [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ],
  linux: [
    '/snap/bin/chromium',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/google-chrome',
  ],
  win32: [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Chromium\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  ],
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function buildErrorList(errors) {
  if (!Array.isArray(errors) || errors.length === 0) {
    return '';
  }

  return `
    <div class="latex-error-box">
      <div class="latex-error-title">检测到公式渲染失败，已保留原文</div>
      <ul>
        ${errors.map((error) => `<li>${escapeHtml(error.message || '公式渲染失败')}：${escapeHtml(error.source || '')}</li>`).join('')}
      </ul>
    </div>
  `;
}

function buildQuestionBlock(item) {
  if (item.is_geometry) {
    if (item.image_data_url) {
      return `
        <div class="geometry-card">
          <div class="geometry-title">几何原题图片</div>
          <img src="${item.image_data_url}" alt="几何原题图片" class="geometry-image" />
        </div>
      `;
    }

    return `
      <div class="geometry-card">
        <div class="geometry-title">几何原题图片</div>
        <div class="geometry-placeholder">图片暂时无法载入，已保留原图记录。</div>
      </div>
    `;
  }

  const preview = buildWrongQuestionLatexPreviewModel(item.question_text_snapshot || '');
  return `
    <div class="question-text-block">
      <div class="question-text-preview">${preview.html || '<span class="question-empty">暂无题目文本</span>'}</div>
      ${buildErrorList(preview.errors)}
    </div>
  `;
}

function splitWritingSection(prompt, fallbackLabel) {
  const normalized = String(prompt ?? '').replaceAll('\r\n', '\n').replaceAll('\r', '\n').trim();
  const lines = normalized
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length >= 2) {
    return {
      label: lines[0],
      prompt: lines.slice(1).join('\n'),
    };
  }

  return {
    label: fallbackLabel,
    prompt: lines[0] || '',
  };
}

function renderPromptHtml(prompt) {
  return escapeHtml(String(prompt ?? ''))
    .replace(/[_＿]{4,}/g, '<span class="blank-gap"></span>')
    .replaceAll('\n', '<br />');
}

function buildWritingSection(prompt, fallbackLabel) {
  const section = splitWritingSection(prompt, fallbackLabel);
  return `
    <section class="writing-card">
      <div class="writing-label">${escapeHtml(section.label)}</div>
      <div class="writing-prompt">${renderPromptHtml(section.prompt)}</div>
    </section>
  `;
}

function buildRedoWorkArea() {
  return `
    <section class="redo-work-area">
      <div class="redo-work-label">重做这题（可选）</div>
      <div class="redo-lines">
        ${Array.from({ length: 12 }, () => '<div class="redo-line"></div>').join('')}
      </div>
    </section>
  `;
}

function buildItemMarkup(item) {
  return `
    <section class="record-page">
      <div class="record-header">
        <div class="record-index">第 ${escapeHtml(item.question_order || '')} 题</div>
      </div>
      <div class="record-label">题目内容</div>
      ${buildQuestionBlock(item)}

      ${buildWritingSection(item.reason_blank_prompt || '', '先梳理错因')}
      ${buildWritingSection(item.improvement_summary_prompt || '', '再写你的想法')}
      ${buildRedoWorkArea()}
    </section>
  `;
}

export async function buildDocumentMarkup(payload) {
  const katexCss = await readFile(katexCssPath, 'utf8');
  const studentName = escapeHtml(payload.studentName || '');
  const className = escapeHtml(payload.className || '');
  const teacherName = escapeHtml(payload.teacherName || '');
  const title = escapeHtml(payload.title || `${studentName} 错题练习`);
  const items = Array.isArray(payload.items) ? payload.items : [];

  return `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>${title}</title>
        <style>
          ${katexCss}

          @page {
            size: A4;
            margin: 16mm 14mm;
          }

          * {
            box-sizing: border-box;
          }

          body {
            margin: 0;
            color: #1f2937;
            font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: #ffffff;
          }

          .cover {
            margin-bottom: 16px;
            padding-bottom: 14px;
            border-bottom: 2px solid #c7d2fe;
            text-align: center;
          }

          .cover-title {
            font-size: 24px;
            font-weight: 700;
            color: #0f172a;
          }

          .cover-meta {
            margin-top: 8px;
            color: #475569;
            font-size: 13px;
          }

          .record-page {
            page-break-before: always;
            min-height: 265mm;
            display: flex;
            flex-direction: column;
          }

          .record-page:first-of-type {
            page-break-before: auto;
          }

          .record-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
          }

          .record-index {
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
          }

          .record-label,
          .writing-label {
            margin-bottom: 10px;
            font-size: 13px;
            font-weight: 700;
            color: #334155;
          }

          .question-text-block,
          .geometry-card,
          .writing-card {
            border: 1px solid #dbe2ea;
            border-radius: 10px;
            padding: 16px;
            background: #ffffff;
          }

          .writing-card {
            margin-top: 14px;
          }

          .writing-prompt {
            font-size: 14px;
            line-height: 1.8;
            color: #334155;
            white-space: pre-wrap;
            word-break: break-word;
          }

          .blank-gap {
            display: inline-block;
            min-width: 10.5em;
            height: 1.2em;
            margin: 0 0.2em;
            vertical-align: -0.2em;
            border-bottom: 1.5px solid #334155;
          }

          .redo-work-area {
            flex: 1;
            min-height: 88mm;
            margin-top: 18px;
            display: flex;
            flex-direction: column;
          }

          .redo-work-label {
            margin-bottom: 10px;
            font-size: 12px;
            font-weight: 700;
            color: #64748b;
          }

          .redo-lines {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
          }

          .redo-line {
            min-height: 16px;
            border-bottom: 1px solid #cbd5e1;
          }

          .question-empty,
          .geometry-placeholder {
            color: #64748b;
            font-size: 14px;
          }

          .question-text-preview {
            font-size: 16px;
            line-height: 1.8;
            word-break: break-word;
          }

          .question-text-preview .katex {
            font-size: 1.05em;
          }

          .question-text-preview .xr-latex-display {
            margin: 14px 0;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 4px 0;
          }

          .question-text-preview .xr-latex-error-source {
            color: #b91c1c;
            background: #fee2e2;
            border-radius: 6px;
            padding: 2px 6px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          }

          .latex-error-box {
            margin-top: 14px;
            padding: 10px 12px;
            border: 1px solid #fecaca;
            border-radius: 12px;
            background: #fff1f2;
            color: #9f1239;
            font-size: 12px;
            line-height: 1.6;
          }

          .latex-error-title {
            font-weight: 700;
            margin-bottom: 4px;
          }

          .latex-error-box ul {
            margin: 0;
            padding-left: 18px;
          }

          .geometry-title {
            margin-bottom: 12px;
            font-size: 14px;
            font-weight: 700;
            color: #0f172a;
          }

          .geometry-image {
            display: block;
            max-width: 100%;
            max-height: 220mm;
            margin: 0 auto;
            object-fit: contain;
            border-radius: 12px;
            background: #ffffff;
          }
        </style>
      </head>
      <body>
        <section class="cover">
          <div class="cover-title">${title}</div>
          <div class="cover-meta">学生：${studentName}</div>
          <div class="cover-meta">班级：${className}</div>
          <div class="cover-meta">老师：${teacherName}</div>
          <div class="cover-meta">题目数量：${items.length}</div>
        </section>
        ${items.map((item) => buildItemMarkup(item)).join('')}
      </body>
    </html>
  `;
}

export async function resolveChromiumLaunchOptions({
  env = process.env,
  platform = process.platform,
  pathExists = async (candidate) => {
    try {
      await access(candidate, fsConstants.X_OK);
      return true;
    } catch {
      return false;
    }
  },
} = {}) {
  const explicitExecutablePath = String(
    env.XR_PLAYWRIGHT_EXECUTABLE_PATH || env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '',
  ).trim();

  if (explicitExecutablePath) {
    return { executablePath: explicitExecutablePath };
  }

  const candidates = COMMON_CHROMIUM_EXECUTABLE_PATHS[platform] || [];
  for (const candidate of candidates) {
    if (await pathExists(candidate)) {
      return { executablePath: candidate };
    }
  }

  return undefined;
}

async function main() {
  const [, , inputPath, outputPath] = process.argv;

  if (!inputPath || !outputPath) {
    throw new Error('Usage: node renderWrongQuestionPracticeSheetPdf.mjs <input-json> <output-pdf>');
  }

  const payload = JSON.parse(await readFile(inputPath, 'utf8'));
  const documentMarkup = await buildDocumentMarkup(payload);
  const browser = await chromium.launch(await resolveChromiumLaunchOptions());

  try {
    const page = await browser.newPage();
    await page.setContent(documentMarkup, { waitUntil: 'load' });
    await page.emulateMedia({ media: 'screen' });
    await mkdir(dirname(outputPath), { recursive: true });
    await page.pdf({
      path: outputPath,
      format: 'A4',
      printBackground: true,
      preferCSSPageSize: true,
      margin: {
        top: '0mm',
        right: '0mm',
        bottom: '0mm',
        left: '0mm',
      },
    });
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(async (error) => {
    console.error(error instanceof Error ? error.stack || error.message : String(error));
    process.exitCode = 1;
  });
}
