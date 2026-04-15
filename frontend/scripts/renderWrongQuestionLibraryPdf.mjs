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

function buildQuestionBlock(record) {
  if (record.is_geometry) {
    if (record.image_data_url) {
      return `
        <div class="geometry-card">
          <div class="geometry-title">几何原题图片</div>
          <img src="${record.image_data_url}" alt="几何原题图片" class="geometry-image" />
          <div class="geometry-caption">保留原图入库，便于按图复盘几何关系。</div>
        </div>
      `;
    }

    return `
      <div class="geometry-card">
        <div class="geometry-title">几何原题图片</div>
        <div class="geometry-placeholder">图片暂时无法载入，已保留原图记录。</div>
        <div class="geometry-caption">保留原图入库，便于按图复盘几何关系。</div>
      </div>
    `;
  }

  const preview = buildWrongQuestionLatexPreviewModel(record.question_text || '');
  return `
    <div class="question-text-block">
      <div class="question-text-preview">${preview.html || '<span class="question-empty">暂无题目文本</span>'}</div>
      ${buildErrorList(preview.errors)}
    </div>
  `;
}

function buildReasonCards(record) {
  const cards = [];
  const childReasonText = String(record.child_reason_text || '').trim();
  const causeNote = String(record.cause_note || '').trim();

  if (childReasonText) {
    cards.push(`
      <div class="reason-card">
        <div class="reason-label">孩子自述错因</div>
        <div class="reason-value">${escapeHtml(childReasonText)}</div>
      </div>
    `);
  }

  if (causeNote) {
    cards.push(`
      <div class="reason-card">
        <div class="reason-label">补充备注</div>
        <div class="reason-value">${escapeHtml(causeNote)}</div>
      </div>
    `);
  }

  if (cards.length === 0) {
    return '';
  }

  return `<div class="reason-grid">${cards.join('')}</div>`;
}

function buildRecordMarkup(record, index) {
  return `
    <section class="record-page">
      <div class="record-header">
        <div class="record-index">第 ${index + 1} 题</div>
        <div class="record-time">上传时间：${escapeHtml(record.created_at || '')}</div>
      </div>
      <div class="record-label">题目内容</div>
      ${buildQuestionBlock(record)}
      ${buildReasonCards(record)}
    </section>
  `;
}

export async function buildDocumentMarkup(payload) {
  const katexCss = await readFile(katexCssPath, 'utf8');
  const teacherTitle = escapeHtml(payload.teacherTitle || '未分配老师');
  const studentName = escapeHtml(payload.studentName || '');
  const className = escapeHtml(payload.className || '');
  const records = Array.isArray(payload.records) ? payload.records : [];

  return `
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>${studentName} 错题库</title>
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
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 2px solid #bfdbfe;
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

          .record-time {
            font-size: 12px;
            color: #64748b;
          }

          .record-label {
            margin-bottom: 10px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #475569;
          }

          .question-text-block,
          .geometry-card {
            border: 1px solid #dbeafe;
            background: #f8fbff;
            border-radius: 16px;
            padding: 16px;
          }

          .reason-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 12px;
          }

          .reason-card {
            border: 1px solid #dbeafe;
            background: #ffffff;
            border-radius: 14px;
            padding: 14px;
          }

          .reason-label {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: #64748b;
          }

          .reason-value {
            margin-top: 8px;
            font-size: 14px;
            line-height: 1.75;
            color: #334155;
            white-space: pre-wrap;
            word-break: break-word;
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

          .geometry-caption {
            margin-top: 12px;
            font-size: 12px;
            color: #64748b;
          }

          @media (max-width: 760px) {
            .reason-grid {
              grid-template-columns: 1fr;
            }
          }
        </style>
      </head>
      <body>
        <section class="cover">
          <div class="cover-title">${studentName} 错题库｜任课老师：${teacherTitle}</div>
          <div class="cover-meta">班级：${className}</div>
          <div class="cover-meta">错题总数：${records.length}</div>
        </section>
        ${records.map((record, index) => buildRecordMarkup(record, index)).join('')}
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
    throw new Error('Usage: node renderWrongQuestionLibraryPdf.mjs <input-json> <output-pdf>');
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

if (process.argv[1] && resolve(process.argv[1]) === currentFilePath) {
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(async (error) => {
    console.error(error instanceof Error ? error.stack || error.message : String(error));
    process.exitCode = 1;
  });
}
}
