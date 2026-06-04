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
  const hasQuestionText = Boolean(preview.html);
  const imageSource = String(item.image_source || item.imageSource || '').trim();
  const surfaceMode = String(item.question_surface_mode || item.questionSurfaceMode || '').trim();
  const questionTextBlock = preview.html
    ? `
      <div class="question-latex-card">
        <div class="xr-latex-preview question-latex-preview-frame">
          ${preview.html}
        </div>
      </div>
    `
    : '';

  const buildImageBlock = (title, extraClass = 'source-image-card') => `
      <div class="geometry-card ${extraClass}">
        <div class="geometry-title">${title}</div>
        <img src="${item.image_data_url}" alt="${title}" class="geometry-image source-image" />
      </div>
    `;

  if (item.image_data_url && item.diagram_type) {
    return `
      ${questionTextBlock}
      <div class="geometry-card generated-diagram-card">
        <div class="geometry-title">生成图像</div>
        <img src="${item.image_data_url}" alt="生成图像" class="geometry-image generated-diagram-image" />
      </div>
    `;
  }

  if (item.image_data_url && surfaceMode === 'image_clean') {
    const imageTitle = item.is_geometry ? '干净几何原题图片' : '干净原题图片';
    return buildImageBlock(imageTitle);
  }

  if (hasQuestionText) {
    return questionTextBlock;
  }

  if (item.image_data_url) {
    const imageTitle = imageSource === 'erased'
      ? (item.is_geometry ? '擦除后几何原题图片' : '擦除后原题图片')
      : (item.is_geometry ? '几何原题图片' : '原题图片');
    return buildImageBlock(imageTitle);
  }

  if (item.is_geometry) {
    return `
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

function normalizePossiblyJsonObject(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value;
  }
  const text = String(value ?? '').trim();
  if (!text) {
    return {};
  }
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
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

function firstNonEmptyText(...values) {
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (text) {
      return text;
    }
  }
  return '';
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
    redoGuidanceLines: Array.isArray(structured.redo_guidance_lines)
      ? structured.redo_guidance_lines.map((line) => String(line || '').trim()).filter(Boolean)
      : (Array.isArray(structured.redoGuidanceLines)
        ? structured.redoGuidanceLines.map((line) => String(line || '').trim()).filter(Boolean)
        : []),
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

function isLowInformationClozeText(text) {
  const normalized = String(text || '').replace(/\s+/g, '').trim();
  if (!normalized) {
    return false;
  }
  const patterns = [
    '我这题错在______',
    '我错在______',
    '下次我要先看______',
    '下次我会先______',
    '我要注意______',
    '这一步需要先看清______',
    '做完后我要检查______',
  ];
  if (patterns.some((pattern) => normalized.includes(pattern))) {
    return true;
  }
  return normalized.includes('______') && normalized.replaceAll('______', '').length <= 8;
}

function hasLowInformationClozeLines(lines) {
  return lines.some((line) => isLowInformationClozeText(line));
}

function normalizeReflectionSummary(item) {
  const source = item && typeof item === 'object' ? item : {};
  const reflection = normalizePossiblyJsonObject(
    source.reflection_summary_snapshot_json
    ?? source.reflectionSummarySnapshot
    ?? source.reflection_summary_snapshot
    ?? source.reflectionSummary,
  );
  return {
    whyWrong: String(reflection.why_wrong ?? reflection.whyWrong ?? '').trim(),
    unknownStep: String(reflection.unknown_step ?? reflection.unknownStep ?? '').trim(),
    helpPreference: String(reflection.help_preference ?? reflection.helpPreference ?? '').trim(),
    summaryText: String(reflection.summary_text ?? reflection.summaryText ?? '').trim(),
  };
}

function normalizeQuestionStructured(item) {
  const source = item && typeof item === 'object' ? item : {};
  const structured = normalizePossiblyJsonObject(
    source.question_structured_snapshot_json
    ?? source.questionStructuredSnapshot
    ?? source.question_structured_snapshot
    ?? source.questionStructured,
  );
  return {
    stem: String(structured.stem ?? '').trim(),
    subject: String(structured.subject ?? '').trim(),
  };
}

function normalizeKnowledgeTags(item) {
  const source = item && typeof item === 'object' ? item : {};
  return normalizePossiblyJsonStringList(
    source.knowledge_tags_snapshot_json
    ?? source.knowledgeTagsSnapshot
    ?? source.knowledge_tags_snapshot
    ?? source.knowledgeTags,
  );
}

function buildReflectionFallbackMethodHints(item) {
  const reflection = normalizeReflectionSummary(item);
  const questionStructured = normalizeQuestionStructured(item);
  const knowledgeTags = normalizeKnowledgeTags(item);
  const hintLines = [];

  if (knowledgeTags.length > 0) {
    hintLines.push(`先回到 ${knowledgeTags.slice(0, 2).join(' / ')} 这组知识点。`);
  } else if (questionStructured.subject) {
    hintLines.push(`先回到这道${questionStructured.subject}题对应的基础规则。`);
  }
  if (reflection.unknownStep) {
    hintLines.push(`先补清：${reflection.unknownStep}`);
  }
  if (reflection.helpPreference) {
    hintLines.push(`这次先按“${reflection.helpPreference}”的方式复盘。`);
  }

  return hintLines.slice(0, 3);
}

function buildGuidingMethodLines(item) {
  const structured = normalizeStructuredContent(item);
  const hintLines = structured.methodHintLines.length > 0
    ? structured.methodHintLines
    : buildReflectionFallbackMethodHints(item);
  const merged = [...hintLines];
  if (structured.teacherFeedback) {
    const duplicated = merged.some((line) => line.includes(structured.teacherFeedback) || structured.teacherFeedback.includes(line));
    if (!duplicated) {
      merged.push(structured.teacherFeedback);
    }
  }
  if (merged.length === 0) {
    merged.push('先把题目里的已知条件和问法分开圈出来，再决定第一步用哪个关系。');
  }
  return merged.slice(0, 3);
}

function buildQuestionSummaryText(item) {
  const reflection = normalizeReflectionSummary(item);
  const structured = normalizeStructuredContent(item);
  const questionStructured = normalizeQuestionStructured(item);
  const questionText = normalizePromptText(item.question_text_snapshot || item.question_text || '').trim();
  const studentReason = firstNonEmptyText(
    item.child_reason_transcript_snapshot,
    item.student_transcript,
    item.child_reason_text_snapshot,
    item.student_reason_text,
  );
  const reasonAnchor = firstNonEmptyText(studentReason, reflection.whyWrong, structured.mistakeFocus);
  const guidanceLines = buildGuidingMethodLines(item);

  if (reasonAnchor && guidanceLines.length > 0) {
    return `先回到“${reasonAnchor.replace(/[。！!？?]$/u, '')}”这个入口，再按这题的起手顺序往下走：${guidanceLines[0]}`;
  }
  if (guidanceLines.length > 0) {
    return guidanceLines[0];
  }
  if (reasonAnchor) {
    return `先回到“${reasonAnchor.replace(/[。！!？?]$/u, '')}”这个卡点，再看题目第一步要用什么关系。`;
  }
  if (questionStructured.stem) {
    return `先把题目里“${questionStructured.stem}”这一步重新读清。`;
  }
  if (questionText) {
    return '先把题目在问什么、已知什么重新圈出来，再决定第一步从哪里下手。';
  }
  return '';
}

function buildQuestionSummarySection(item) {
  const summaryText = buildQuestionSummaryText(item);
  if (!summaryText) {
    return '';
  }
  return `
    <section class="summary-card">
      <div class="section-title">题干摘要</div>
      <div class="summary-copy">${buildLatexTextBlock(summaryText)}</div>
    </section>
  `;
}

function buildLegacyWritingBlocks(reasonPrompt, improvementPrompt) {
  const sections = [
    extractWritingPromptBody(reasonPrompt),
    extractWritingPromptBody(improvementPrompt),
  ].filter(Boolean);

  return sections.map((section) => ({
    title: '',
    rawText: section,
    contentHtml: renderPromptHtml(section),
    kind: 'legacy',
  }));
}

function buildReflectionWritingBlocks(item) {
  const reflection = normalizeReflectionSummary(item);
  const knowledgeTags = normalizeKnowledgeTags(item);
  const questionStructured = normalizeQuestionStructured(item);
  const topic = knowledgeTags.slice(0, 2).join(' / ') || questionStructured.subject || '同类题';
  const blocks = [];

  if (reflection.whyWrong || reflection.unknownStep || questionStructured.stem) {
    const lines = [];
    if (reflection.whyWrong) {
      lines.push(`本题复盘时，先把“${reflection.whyWrong}”对应到 ______。`);
    }
    if (reflection.unknownStep) {
      lines.push(`我卡住的步骤是“${reflection.unknownStep}”，这里要先补清 ______。`);
    } else if (questionStructured.stem) {
      lines.push(`先回到题干“${questionStructured.stem}”，找出最关键的 ______。`);
    }
    blocks.push({
      title: '错因复盘',
      contentHtml: lines.map((line) => renderPromptHtml(line)).join('<br />'),
      kind: 'reflection',
    });
  }

  if (reflection.helpPreference || knowledgeTags.length > 0 || questionStructured.subject) {
    const lines = [];
    if (reflection.helpPreference) {
      lines.push(`下次遇到${topic}题，先按“${reflection.helpPreference}”检查 ______。`);
    } else {
      lines.push(`下次遇到${topic}题，先把题目条件翻译成可用的 ______。`);
    }
    if (knowledgeTags.length > 0) {
      lines.push(`看到 ${knowledgeTags.slice(0, 3).join('、')} 时，先判断它提示的是角度、数量、关系还是 ______。`);
    }
    blocks.push({
      title: '下次提醒',
      contentHtml: lines.map((line) => renderPromptHtml(line)).join('<br />'),
      kind: 'reflection',
    });
  }

  if (blocks.length === 0) {
    blocks.push({
      title: '错因复盘',
      contentHtml: renderPromptHtml('本题信息还不完整，先回到原题确认关键条件和 ______。'),
      kind: 'reflection',
    });
    blocks.push({
      title: '下次提醒',
      contentHtml: renderPromptHtml('下次遇到同类题，先把题目条件翻译成可用的 ______。'),
      kind: 'reflection',
    });
  }

  return blocks;
}

function buildMethodHintSection(item) {
  const hintLines = buildGuidingMethodLines(item);
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

function shouldShowWritingBlockTitle(title) {
  return !['', '错因复盘', '下次提醒'].includes(String(title || '').trim());
}

function buildWritingSection(item, title = '挖空复盘') {
  const structured = normalizeStructuredContent(item);
  let blocks = structured.blankReviewBlocks.length > 0 && !structured.blankReviewBlocks.some((block) => hasLowInformationClozeLines(block.lines))
    ? structured.blankReviewBlocks.map((block) => ({
      title: block.title,
      contentHtml: block.lines.map((line) => renderPromptHtml(line)).join('<br />'),
      kind: 'structured',
    }))
    : buildLegacyWritingBlocks(item.reason_blank_prompt || '', item.improvement_summary_prompt || '');

  if (blocks.some((block) => isLowInformationClozeText(block.contentHtml))) {
    blocks = buildReflectionWritingBlocks(item);
  }
  if (blocks.some((block) => isLowInformationClozeText(block.rawText))) {
    blocks = buildReflectionWritingBlocks(item);
  }

  if (blocks.length === 0) {
    return '';
  }

  return `
    <section class="writing-card">
      ${title ? `<div class="section-title">${escapeHtml(title)}</div>` : ''}
      ${blocks
        .map(
          (block) => `
            <div class="writing-prompt-block">
              ${shouldShowWritingBlockTitle(block.title) ? `<div class="writing-prompt-title">${escapeHtml(block.title)}</div>` : ''}
              <div class="writing-prompt">${block.contentHtml}</div>
            </div>
          `,
        )
        .join('')}
    </section>
  `;
}

function buildRedoWorkArea() {
  return `
    <section class="redo-work-area">
      <div class="section-title">订正区</div>
      <div class="redo-lines">
        ${Array.from({ length: 14 }, () => '<div class="redo-line"></div>').join('')}
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
      ${buildQuestionSummarySection(item)}
      ${buildMethodHintSection(item)}
      ${buildWritingSection(item)}
      ${buildRedoWorkArea()}
    </section>
  `;
}

function buildScheduledItemMarkup(item, label) {
  const trainingGoal = String(item.trainingGoal || '').trim();
  const writingSection = buildWritingSection(item, '挖空复盘');
  return `
    <section class="record-page">
      <div class="record-header">
        <div class="record-index">${escapeHtml(label)}</div>
        <div class="record-type">${escapeHtml(item.itemType === 'variant' ? '变式题' : '原错题')}</div>
      </div>
      ${trainingGoal ? `<div class="pack-goal">训练目标：${escapeHtml(trainingGoal)}</div>` : ''}
      <div class="record-label">原题 / 原图</div>
      ${buildQuestionBlock(item)}
      ${buildQuestionSummarySection(item)}
      ${buildMethodHintSection(item)}
      ${writingSection}
      ${buildRedoWorkArea()}
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
  const title = escapeHtml(payload.title || `${payload.studentName || ''} 错题练习`);
  const items = Array.isArray(payload.items) ? payload.items : [];
  const schedule = Array.isArray(payload.schedule) ? payload.schedule : [];
  const answerItems = Array.isArray(payload.answerItems) ? payload.answerItems : items;
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

          .record-page {
            margin-bottom: 10px;
            padding-bottom: 8px;
          }

          .record-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
          }

          .record-index {
            font-size: 17px;
            font-weight: 700;
            color: #0f172a;
          }

          .record-type {
            font-size: 12px;
            font-weight: 700;
            color: #475569;
          }

          .record-label {
            margin-bottom: 6px;
            font-size: 13px;
            font-weight: 700;
            color: #334155;
          }

          .pack-goal {
            margin: 0 0 10px;
            padding: 10px 12px;
            border: 1px solid #dbeafe;
            border-radius: 10px;
            background: #f8fbff;
            color: #334155;
            font-size: 13px;
            line-height: 1.6;
          }

          .geometry-card,
          .summary-card,
          .writing-card,
          .method-hint-card {
            break-inside: avoid;
            page-break-inside: avoid;
            border: 1px solid #dbe2ea;
            border-radius: 10px;
            padding: 10px 12px;
            background: #ffffff;
          }

          .question-latex-card {
            border: 1px solid #dbe2ea;
            border-radius: 10px;
            padding: 10px 12px;
            background: #ffffff;
          }

          .question-latex-preview-frame {
            border: none;
            border-radius: 0;
            background: #ffffff;
            padding: 0;
          }

          .summary-card {
            margin-top: 6px;
          }

          .summary-copy {
            color: #334155;
            font-size: 13px;
            line-height: 1.92;
          }

          .writing-card {
            margin-top: 6px;
            min-height: 0;
            padding-bottom: 10px;
          }

          .section-title {
            margin-bottom: 8px;
            font-size: 13px;
            font-weight: 700;
            color: #334155;
          }

          .method-hint-card {
            margin-top: 6px;
          }

          .method-hint-line {
            font-size: 14px;
            line-height: 1.98;
            color: #334155;
          }

          .method-hint-line + .method-hint-line {
            margin-top: 4px;
          }

          .writing-prompt-block + .writing-prompt-block {
            margin-top: 8px;
          }

          .writing-prompt-block {
            break-inside: avoid;
            page-break-inside: avoid;
          }

          .writing-prompt-title {
            margin-bottom: 6px;
            font-size: 13px;
            font-weight: 700;
            color: #0f172a;
          }

          .writing-prompt {
            font-size: 14px;
            line-height: 2;
            color: #334155;
            white-space: pre-wrap;
            word-break: break-word;
          }

          .blank-gap {
            display: inline-block;
            min-width: 11.5em;
            height: 1.2em;
            margin: 0 0.2em;
            vertical-align: -0.2em;
            border-bottom: 1.5px solid #334155;
          }

          .redo-work-area {
            break-inside: avoid;
            page-break-inside: avoid;
            min-height: 0;
            margin-top: 8px;
          }

          .redo-lines {
            display: flex;
            flex-direction: column;
            gap: 4px;
          }

          .redo-line {
            min-height: 13px;
            border-bottom: 1px solid #cbd5e1;
          }

          .question-empty,
          .geometry-placeholder {
            color: #64748b;
            font-size: 14px;
          }

          .xr-latex-preview {
            font-size: 15px;
            line-height: 1.96;
            word-break: break-word;
          }

          .xr-latex-preview .katex {
            font-size: 1.05em;
          }

          .xr-latex-preview .xr-latex-display {
            margin: 10px 0;
            overflow-x: auto;
            overflow-y: hidden;
            padding: 2px 0;
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
            margin-bottom: 6px;
            font-size: 13px;
            font-weight: 700;
            color: #0f172a;
          }

          .geometry-image {
            display: block;
            max-width: 100%;
            margin: 0 auto;
            object-fit: contain;
            border-radius: 10px;
            background: #ffffff;
          }

          .source-image {
            max-height: 66mm;
          }

          .generated-diagram-image {
            max-height: 96mm;
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
