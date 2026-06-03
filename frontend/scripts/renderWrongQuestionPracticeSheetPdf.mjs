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
const LINUX_CHROMIUM_STABILITY_ARGS = ['--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox'];

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function buildQuestionBlock(item) {
  const preview = buildWrongQuestionLatexPreviewModel(formatQuestionTextForPractice(item.question_text_snapshot || ''));
  const questionTextBlock = preview.html
    ? `
      <div class="question-latex-card">
        <div class="xr-latex-preview question-latex-preview-frame">
          ${preview.html}
        </div>
      </div>
    `
    : '';

  if (item.image_data_url && item.diagram_type) {
    return `
      ${questionTextBlock}
      <div class="geometry-card">
        <div class="geometry-title">生成图像</div>
        <img src="${item.image_data_url}" alt="生成图像" class="geometry-image" />
      </div>
    `;
  }

  if (item.is_geometry) {
    if (item.image_data_url) {
      return `
        ${questionTextBlock}
        <div class="geometry-card">
          <div class="geometry-title">几何原题图片</div>
          <img src="${item.image_data_url}" alt="几何原题图片" class="geometry-image" />
        </div>
      `;
    }

    return `
      ${questionTextBlock}
      <div class="geometry-card">
        <div class="geometry-title">几何原题图片</div>
        <div class="geometry-placeholder">图片暂时无法载入，已保留原图记录。</div>
      </div>
    `;
  }

  return `
    <div class="question-latex-card">
      <div class="xr-latex-preview question-latex-preview-frame">
        ${preview.html || '<span class="question-empty xr-latex-empty">暂无题目文本</span>'}
      </div>
    </div>
  `;
}

function buildLatexTextBlock(value) {
  const preview = buildWrongQuestionLatexPreviewModel(value || '');
  return preview.html || escapeHtml(value || '');
}

function normalizePossiblyJsonStringList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || '').trim()).filter(Boolean);
  }
  const text = String(value ?? '').trim();
  if (!text) {
    return [];
  }
  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed.map((item) => String(item || '').trim()).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function normalizePromptText(prompt) {
  return String(prompt ?? '')
    .replaceAll('\\r\\n', '\n')
    .replaceAll('\\r', '\n')
    .replaceAll('\\n', '\n')
    .replaceAll('\r\n', '\n')
    .replaceAll('\r', '\n');
}

function formatQuestionTextForPractice(value) {
  const text = normalizePromptText(value);
  const hasCompactChoices =
    /(?:^|\s)A[.．、]\s*\S+[\s\S]*\sB[.．、]\s*\S+[\s\S]*\sC[.．、]\s*\S+[\s\S]*\sD[.．、]\s*\S+/.test(text);

  if (!hasCompactChoices) {
    return text;
  }

  return text
    .replace(/([^\n])\s+(A[.．、]\s*)/g, '$1\n$2')
    .replace(/[ \t]+(?=[BCD][.．、]\s*)/g, '\n')
    .replace(/(^|\n)([ABCD])[.．、]\s*/g, '$1$2. ');
}

function stripPromptHeading(value) {
  return String(value ?? '').replace(/^\s*小标题\s*[:：]\s*/, '').trim();
}

function extractWritingPromptBody(prompt) {
  const normalized = normalizePromptText(prompt).trim();
  const lines = normalized
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  const bodyLines = lines.length >= 2 ? lines.slice(1) : lines;
  return bodyLines
    .map((line) => stripPromptHeading(line))
    .filter(Boolean)
    .join('\n')
    .trim();
}

function renderPromptHtml(prompt) {
  return buildLatexTextBlock(normalizePromptText(prompt))
    .replace(/[_＿]{4,}/g, '<span class="blank-gap"></span>')
    .replaceAll('\n', '<br />');
}

function normalizeStructuredContent(item) {
  const source = item && typeof item === 'object' ? item : {};
  const structured = source.structured_content && typeof source.structured_content === 'object'
    ? source.structured_content
    : (source.structuredContent && typeof source.structuredContent === 'object' ? source.structuredContent : {});
  const blankReviewBlocks = Array.isArray(structured.blank_review_blocks)
    ? structured.blank_review_blocks
    : (Array.isArray(structured.blankReviewBlocks) ? structured.blankReviewBlocks : []);

  return {
    mistakeFocus: String(structured.mistake_focus ?? structured.mistakeFocus ?? '').trim(),
    reviewGoal: String(structured.review_goal ?? structured.reviewGoal ?? '').trim(),
    methodHintLines: Array.isArray(structured.method_hint_lines)
      ? structured.method_hint_lines.map((line) => String(line || '').trim()).filter(Boolean)
      : (Array.isArray(structured.methodHintLines)
        ? structured.methodHintLines.map((line) => String(line || '').trim()).filter(Boolean)
        : []),
    blankReviewBlocks: blankReviewBlocks
      .map((block) => {
        const sourceBlock = block && typeof block === 'object' ? block : {};
        const lines = Array.isArray(sourceBlock.lines)
          ? sourceBlock.lines.map((line) => String(line || '').trim()).filter(Boolean)
          : [];
        return {
          title: String(sourceBlock.title || '').trim(),
          lines,
        };
      })
      .filter((block) => block.title || block.lines.length > 0),
    teacherFeedback: String(structured.teacher_feedback ?? structured.teacherFeedback ?? '').trim(),
    confirmationReasons: normalizePossiblyJsonStringList(
      structured.confirmation_reasons
      ?? structured.confirmationReasons
      ?? source.confirmation_reasons
      ?? source.confirmation_reasons_json
      ?? source.confirmationReasons
      ?? source.confirmationReasonsJson,
    ),
  };
}

function buildLegacyWritingBlocks(reasonPrompt, improvementPrompt) {
  const sections = [
    extractWritingPromptBody(reasonPrompt),
    extractWritingPromptBody(improvementPrompt),
  ].filter(Boolean);

  return sections.map((section) => ({
    title: '',
    contentHtml: renderPromptHtml(section),
    kind: 'legacy',
  }));
}

function buildMethodHintSection(item) {
  const structured = normalizeStructuredContent(item);
  const hintLines = structured.methodHintLines;
  if (hintLines.length === 0) {
    return '';
  }
  return `
    <section class="method-hint-card">
      <div class="section-title">方法提醒</div>
      <div class="method-hint-list">
        ${hintLines.map((line) => `<div class="method-hint-line">${buildLatexTextBlock(line)}</div>`).join('')}
      </div>
    </section>
  `;
}

function buildReviewMeta(item) {
  const structured = normalizeStructuredContent(item);
  const chips = [
    structured.mistakeFocus ? `错因定位：${structured.mistakeFocus}` : '',
    structured.reviewGoal ? `本次目标：${structured.reviewGoal}` : '',
  ].filter(Boolean);
  if (chips.length === 0) {
    return '';
  }
  return `
    <div class="review-meta-row">
      ${chips.map((chip) => `<span class="review-meta-chip">${escapeHtml(chip)}</span>`).join('')}
    </div>
  `;
}

function buildWritingSection(item, title = '挖空复盘') {
  const structured = normalizeStructuredContent(item);
  const blocks = structured.blankReviewBlocks.length > 0
    ? structured.blankReviewBlocks.map((block) => ({
      title: block.title,
      contentHtml: block.lines.map((line) => renderPromptHtml(line)).join('<br />'),
      kind: 'structured',
    }))
    : buildLegacyWritingBlocks(item.reason_blank_prompt || '', item.improvement_summary_prompt || '');

  if (blocks.length === 0) {
    return '';
  }

  return `
    <section class="writing-card">
      ${title ? `<div class="section-title">${escapeHtml(title)}</div>` : ''}
      ${buildReviewMeta(item)}
      ${blocks
        .map(
          (block) => `
            <div class="writing-prompt-block">
              ${block.title ? `<div class="writing-prompt-title">${escapeHtml(block.title)}</div>` : ''}
              <div class="writing-prompt">${block.contentHtml}</div>
            </div>
          `,
        )
        .join('')}
    </section>
  `;
}

function buildTeacherConfirmationSection(item) {
  const structured = normalizeStructuredContent(item);
  const reasons = structured.confirmationReasons;
  if (reasons.length === 0) {
    return '';
  }
  return `
    <section class="confirmation-card">
      <div class="section-title">需老师确认</div>
      <div class="confirmation-copy">当前识别或归档信息仍需老师复核。</div>
      <div class="confirmation-reasons">
        ${reasons.map((reason) => `<span class="confirmation-chip">${escapeHtml(reason)}</span>`).join('')}
      </div>
    </section>
  `;
}

function buildRedoWorkArea(label = '重做这题') {
  return `
    <section class="redo-work-area">
      <div class="section-title">订正区</div>
      <div class="redo-work-label">${escapeHtml(label)}</div>
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
      <div class="record-label">原题 / 原图</div>
      ${buildQuestionBlock(item)}
      ${buildMethodHintSection(item)}
      ${buildWritingSection(item)}
      ${buildTeacherConfirmationSection(item)}
      ${buildRedoWorkArea()}
    </section>
  `;
}

function buildScheduledItemMarkup(item, label) {
  const trainingGoal = String(item.trainingGoal || '').trim();
  const writingSection = buildWritingSection(item, '挖空复盘');
  const redoLabel = item.itemType === 'variant' ? '重做变式' : '重做原题';
  return `
    <section class="record-page">
      <div class="record-header">
        <div class="record-index">${escapeHtml(label)}</div>
        <div class="record-type">${escapeHtml(item.itemType === 'variant' ? '变式题' : '原错题')}</div>
      </div>
      ${trainingGoal ? `<div class="pack-goal">训练目标：${escapeHtml(trainingGoal)}</div>` : ''}
      <div class="record-label">原题 / 原图</div>
      ${buildQuestionBlock(item)}
      ${buildMethodHintSection(item)}
      ${writingSection}
      ${buildTeacherConfirmationSection(item)}
      ${buildRedoWorkArea(redoLabel)}
    </section>
  `;
}

function buildAnswerItemMarkup(item, index) {
  const keySteps = Array.isArray(item.keySteps) ? item.keySteps.filter((step) => String(step || '').trim()) : [];
  const answer = String(item.answer || '').trim();
  const pitfallReminder = String(item.pitfallReminder || '').trim();

  return `
    <section class="answer-card">
      <div class="answer-title">第 ${escapeHtml(index)} 题</div>
      ${answer ? `<div class="answer-line"><span>答案</span><div class="answer-latex xr-latex-preview">${buildLatexTextBlock(answer)}</div></div>` : ''}
      ${
        keySteps.length > 0
          ? `
            <div class="answer-line">
              <span>关键步骤</span>
              <ol>
                ${keySteps.map((step) => `<li><div class="answer-latex xr-latex-preview">${buildLatexTextBlock(step)}</div></li>`).join('')}
              </ol>
            </div>
          `
          : ''
      }
      ${pitfallReminder ? `<div class="answer-line"><span>易错提醒</span><div class="answer-latex xr-latex-preview">${buildLatexTextBlock(pitfallReminder)}</div></div>` : ''}
    </section>
  `;
}

function buildScheduledBody(schedule, answerItems) {
  let questionIndex = 0;
  const dailyMarkup = schedule
    .map((day) => {
      const dayItems = Array.isArray(day.items) ? day.items : [];
      return dayItems
        .map((item) => {
          questionIndex += 1;
          const label = `第 ${day.dayIndex || ''} 天${day.date ? `｜${day.date}` : ''}｜第 ${questionIndex} 题`;
          return buildScheduledItemMarkup(item, label);
        })
        .join('');
    })
    .join('');

  const answers = answerItems.length > 0
    ? `
      <section class="answer-section">
        <h1>答案与关键步骤</h1>
        ${answerItems.map((item, index) => buildAnswerItemMarkup(item, index + 1)).join('')}
      </section>
    `
    : '';

  return `${dailyMarkup}${answers}`;
}

export async function buildDocumentMarkup(payload) {
  const katexCss = await readFile(katexCssPath, 'utf8');
  const studentName = escapeHtml(payload.studentName || '');
  const className = escapeHtml(payload.className || '');
  const teacherName = escapeHtml(payload.teacherName || '');
  const title = escapeHtml(payload.title || `${studentName} 错题练习`);
  const items = Array.isArray(payload.items) ? payload.items : [];
  const schedule = Array.isArray(payload.schedule) ? payload.schedule : [];
  const answerItems = Array.isArray(payload.answerItems) ? payload.answerItems : items;
  const packMeta = payload.packMeta && typeof payload.packMeta === 'object' ? payload.packMeta : {};
  const scheduledQuestionCount = schedule.reduce(
    (count, day) => count + (Array.isArray(day.items) ? day.items.length : 0),
    0,
  );
  const hasSchedule = schedule.length > 0;

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

          .record-type {
            font-size: 12px;
            font-weight: 700;
            color: #475569;
          }

          .record-label {
            margin-bottom: 10px;
            font-size: 13px;
            font-weight: 700;
            color: #334155;
          }

          .pack-goal {
            margin: 0 0 12px;
            padding: 10px 12px;
            border: 1px solid #dbeafe;
            border-radius: 10px;
            background: #f8fbff;
            color: #334155;
            font-size: 13px;
            line-height: 1.6;
          }

          .geometry-card,
          .writing-card,
          .method-hint-card,
          .confirmation-card {
            border: 1px solid #dbe2ea;
            border-radius: 10px;
            padding: 16px;
            background: #ffffff;
          }

          .question-latex-card {
            border: 1px solid #dbeafe;
            border-radius: 18px;
            padding: 16px;
            background: #f4fbff;
          }

          .question-latex-preview-frame {
            border: 1px solid #dbeafe;
            border-radius: 18px;
            background: #ffffff;
            padding: 14px 16px;
          }

          .writing-card {
            margin-top: 14px;
            min-height: 82mm;
            padding-bottom: 22px;
          }

          .section-title {
            margin-bottom: 12px;
            font-size: 13px;
            font-weight: 700;
            color: #334155;
          }

          .method-hint-card,
          .confirmation-card {
            margin-top: 14px;
          }

          .method-hint-line {
            font-size: 14px;
            line-height: 1.8;
            color: #334155;
          }

          .method-hint-line + .method-hint-line {
            margin-top: 8px;
          }

          .review-meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 14px;
          }

          .review-meta-chip,
          .confirmation-chip {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 999px;
            background: #f1f5f9;
            color: #475569;
            font-size: 12px;
            line-height: 1.5;
          }

          .writing-prompt-block + .writing-prompt-block {
            margin-top: 18px;
          }

          .writing-prompt-title {
            margin-bottom: 8px;
            font-size: 13px;
            font-weight: 700;
            color: #0f172a;
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
            min-width: 13em;
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

          .redo-question-label {
            margin-top: 18px;
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

          .confirmation-copy {
            font-size: 13px;
            line-height: 1.7;
            color: #475569;
          }

          .confirmation-reasons {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
          }

          .xr-latex-preview {
            font-size: 16px;
            line-height: 1.8;
            word-break: break-word;
          }

          .xr-latex-preview .katex {
            font-size: 1.05em;
          }

          .xr-latex-preview .xr-latex-display {
            margin: 14px 0;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 4px 0;
          }

          .xr-latex-preview .xr-latex-error-source {
            color: #b91c1c;
            background: #fee2e2;
            border-radius: 6px;
            padding: 2px 6px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          }

          .xr-latex-preview .xr-latex-empty {
            color: #64748b;
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

          .answer-section {
            page-break-before: always;
          }

          .answer-section h1 {
            margin: 0 0 16px;
            font-size: 22px;
            color: #0f172a;
          }

          .answer-card {
            break-inside: avoid;
            margin-bottom: 14px;
            padding: 14px;
            border: 1px solid #dbe2ea;
            border-radius: 10px;
            background: #ffffff;
          }

          .answer-title {
            margin-bottom: 8px;
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
          }

          .answer-line {
            margin-top: 8px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
            color: #334155;
            font-size: 13px;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: break-word;
          }

          .answer-line span {
            display: inline-block;
            flex: 0 0 auto;
            min-width: 4.5em;
            color: #64748b;
            font-weight: 700;
          }

          .answer-line ol {
            margin: 6px 0 0 5.2em;
            padding-left: 18px;
            white-space: normal;
          }

          .answer-latex {
            flex: 1;
            min-width: 0;
          }

          .answer-latex p {
            margin: 0;
          }
        </style>
      </head>
      <body>
        <section class="cover">
          <div class="cover-title">${title}</div>
          <div class="cover-meta">学生：${studentName}</div>
          <div class="cover-meta">班级：${className}</div>
          <div class="cover-meta">老师：${teacherName}</div>
          ${
            hasSchedule
              ? `
                <div class="cover-meta">目标：${escapeHtml(packMeta.target || '')}</div>
                <div class="cover-meta">题量档位：${escapeHtml(packMeta.volume || '')}</div>
                <div class="cover-meta">生成日期：${escapeHtml(packMeta.generatedDate || '')}</div>
              `
              : ''
          }
          <div class="cover-meta">题目数量：${hasSchedule ? scheduledQuestionCount : items.length}</div>
        </section>
        ${hasSchedule ? buildScheduledBody(schedule, answerItems) : items.map((item) => buildItemMarkup(item)).join('')}
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
  const args = platform === 'linux' ? LINUX_CHROMIUM_STABILITY_ARGS : undefined;
  const explicitExecutablePath = String(
    env.XR_PLAYWRIGHT_EXECUTABLE_PATH || env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || '',
  ).trim();

  if (explicitExecutablePath) {
    return args ? { executablePath: explicitExecutablePath, args } : { executablePath: explicitExecutablePath };
  }

  const candidates = COMMON_CHROMIUM_EXECUTABLE_PATHS[platform] || [];
  for (const candidate of candidates) {
    if (await pathExists(candidate)) {
      return args ? { executablePath: candidate, args } : { executablePath: candidate };
    }
  }

  return args ? { args } : undefined;
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
