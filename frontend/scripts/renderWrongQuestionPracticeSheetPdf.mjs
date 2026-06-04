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
  const rawText = String(text || '').trim();
  const normalized = rawText.replace(/\s+/g, '').trim();
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
  const genericGuidancePatterns = [
    '认真审题',
    '理解题意',
    '先理解题意',
    '关键步骤',
    '题目条件',
    '注意条件',
    '注意计算细节',
    '检查关键条件',
    '多练类似题目',
  ];
  if (genericGuidancePatterns.some((pattern) => rawText.includes(pattern)) && !containsSpecificMathAnchor(rawText)) {
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

function shortenWrongQuestionText(value, limit = 28) {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(limit - 1, 1)).trimEnd()}…`;
}

function dedupeNonEmptyTexts(values, limit = 4) {
  const deduped = [];
  const seen = new Set();
  for (const value of values) {
    const text = String(value ?? '').trim();
    if (!text || seen.has(text)) {
      continue;
    }
    deduped.push(text);
    seen.add(text);
    if (deduped.length >= limit) {
      break;
    }
  }
  return deduped;
}

function containsSpecificMathAnchor(text) {
  const rawText = String(text ?? '').trim();
  if (!rawText) {
    return false;
  }
  if (/[A-Z]{1,3}|\d|[=<>≤≥⊥∥∠△□○%+\-×÷/\\^]/.test(rawText)) {
    return true;
  }
  const keywords = [
    '垂直',
    '平行',
    '等角',
    '相似',
    '辅助线',
    '面积',
    '角平分线',
    '切线',
    '分母',
    '因式',
    '代换',
    '移项',
    '方程',
    '定义域',
    '单调',
    '交点',
    '极值',
    '导数',
    '积分',
    '受力',
    '守恒',
    '样本空间',
    '条件概率',
    '分布',
    '速度',
    '位移',
  ];
  return keywords.some((keyword) => rawText.includes(keyword));
}

const GENERIC_REASON_TEXTS = new Set(['不会', '不太会', '算错了', '看错了', '粗心了', '做错了', '没做出来']);
const WEAK_TAG_TEXTS = new Set(['未分类', '待补充', '同类题', '同类题经验', '需要确认', '待确认']);

function isWeakWrongQuestionAnchor(text) {
  const normalized = String(text ?? '').trim();
  if (!normalized) {
    return true;
  }
  if (/^[xyzamn]$/.test(normalized)) {
    return true;
  }
  return ['条件', '关系', '目标', '题目条件'].includes(normalized) || WEAK_TAG_TEXTS.has(normalized);
}

function isGenericReasonText(text) {
  const normalized = String(text ?? '').replace(/\s+/g, '').trim();
  if (!normalized) {
    return true;
  }
  return GENERIC_REASON_TEXTS.has(normalized);
}

function defaultTopicPhrase(kind) {
  return {
    geometry: '这类几何题',
    algebra: '这类代数题',
    function: '这类函数题',
    calculus: '这类微积分题',
    mechanics: '这类力学题',
    probability: '这类概率统计题',
    generic: '这类题',
  }[kind] || '这类题';
}

function humanizeWrongQuestionCopy(value) {
  let text = String(value ?? '').trim();
  if (!text) {
    return '';
  }
  text = text.replace(/\s+/g, ' ');
  text = text.replace(/^(?:此外|另外|然而|总的来说|值得注意的是|需要注意的是|可以看到|实际上|当然|希望这对你有帮助[。！]?|请告诉我[。！]?)/, '').trim();
  const replacements = [
    ['这不仅仅是', '这不是'],
    ['本题考察了', '这题要用到'],
    ['我们需要注意', '先看'],
    ['值得注意的是', ''],
    ['需要注意的是', ''],
    ['总的来说', ''],
    ['与此同时', ''],
    ['这题先别急着算，关键是把', '别急着往下算，先把'],
    ['如果一时接不上，就回头问自己：现在缺的是', '要是还连不上，就问自己还差哪一步'],
    ['里的哪一座', '里的哪一步'],
    ['再决定下一步', '再往下做'],
    ['未分类题', '这类题'],
    ['未分类', '这类题'],
    ['待补充', '这一步'],
    ['同类题经验', '这类题'],
    ['同类题', '这类题'],
    ['先先', '先'],
  ];
  for (const [oldValue, newValue] of replacements) {
    text = text.replaceAll(oldValue, newValue);
  }
  text = text.replace(/[，,]{2,}/g, '，').replace(/[。]{2,}/g, '。');
  return text.trim().replace(/^[，；]+|[，；]+$/g, '');
}

function buildQuestionAnalysisText(item) {
  const source = item && typeof item === 'object' ? item : {};
  const questionStructured = normalizeQuestionStructured(source);
  const knowledgeTags = normalizeKnowledgeTags(source);
  const parts = [
    String(source.question_text_snapshot ?? source.question_text ?? '').trim(),
    questionStructured.stem,
    String(source.topic_category_snapshot ?? source.topic_category ?? source.topicCategory ?? '').trim(),
    knowledgeTags.join(' '),
    String(source.standard_solution_snapshot ?? source.standard_solution ?? source.standardSolution ?? '').trim(),
  ].filter(Boolean);
  return parts.join('\n');
}

function inferReflectionQuestionKind(item) {
  const source = item && typeof item === 'object' ? item : {};
  const analysisText = buildQuestionAnalysisText(source);
  if (source.is_geometry) {
    return 'geometry';
  }

  const rules = [
    ['calculus', ['导数', '积分', '极限', '微分', '切线斜率', '变化率', '导函数']],
    ['mechanics', ['受力', '牛顿', '加速度', '位移', '速度变化', '约束条件', '守恒', '动量', '能量']],
    ['probability', ['概率', '统计', '随机', '样本空间', '条件概率', '独立', '分布', '期望', '方差']],
    ['function', ['函数', '定义域', '值域', '图像', '单调', '极值', '零点', '交点', '参数']],
    ['algebra', ['方程', '代数', '因式', '分母', '配方', '代换', '移项', '根式', '整式', '分式', '化简', '求值']],
    ['geometry', ['垂直', '平行', '等角', '相似', '圆', '辅助线', '面积', '角平分线', '切线', '三角形']],
  ];
  for (const [kind, keywords] of rules) {
    if (keywords.some((keyword) => analysisText.includes(keyword))) {
      return kind;
    }
  }
  if (/[A-Z]{1,3}\s*[⊥∥]|∠[A-Z]{1,3}|△[A-Z]{3}/.test(analysisText)) {
    return 'geometry';
  }
  return 'generic';
}

function extractReflectionGoal(item, kind) {
  const questionStructured = normalizeQuestionStructured(item);
  const questionText = firstNonEmptyText(item?.question_text_snapshot, item?.question_text, questionStructured.stem);
  const patterns = [
    /(求证[^。；，,\n]+)/,
    /(证明[^。；，,\n]+)/,
    /(求[^。；，,\n]+)/,
    /(解[^。；，,\n]+)/,
    /(化简[^。；，,\n]+)/,
    /(比较[^。；，,\n]+)/,
    /(判断[^。；，,\n]+)/,
  ];
  for (const pattern of patterns) {
    const match = questionText.match(pattern);
    if (match) {
      return shortenWrongQuestionText(match[1], 22);
    }
  }

  const defaults = {
    geometry: '找到图上能连到目标的关系',
    algebra: '把已知式稳稳变到目标式',
    function: '判断函数关系或参数范围',
    calculus: '判断变化关系或边界条件',
    mechanics: '连起受力、状态和方程',
    probability: '先定事件关系再下手计算',
    generic: '先把已知和目标连起来',
  };
  return defaults[kind] || defaults.generic;
}

function extractReflectionConditions(item, kind) {
  const analysisText = buildQuestionAnalysisText(item);
  const knowledgeTags = normalizeKnowledgeTags(item);
  const matches = [];

  const regexes = [
    /[A-Za-z]{1,3}\s*=\s*[^，。；\n]+/g,
    /[A-Z]{1,3}\s*⊥\s*[A-Z]{1,3}/g,
    /[A-Z]{1,3}\s*∥\s*[A-Z]{1,3}/g,
    /∠[A-Z]{1,3}\s*=\s*∠[A-Z]{1,3}/g,
    /\b\d+°/g,
    /\b[xyzamn]\b/g,
    /f\([^)]*\)/g,
  ];
  for (const regex of regexes) {
    for (const match of analysisText.matchAll(regex)) {
      matches.push(match[0].replaceAll(' ', ''));
    }
  }

  const keywordMap = {
    geometry: ['垂直', '平行', '等角', '相似', '圆', '辅助线', '面积', '角平分线', '切线', '中点'],
    algebra: ['分母', '因式', '代换', '移项', '配方', '未知数', '比例', '同类项', '根式', '方程'],
    function: ['定义域', '图像', '交点', '单调', '极值', '参数', '零点', '自变量', '函数值'],
    calculus: ['导数', '积分', '边界条件', '变化率', '切线', '极值', '单调', '几何意义'],
    mechanics: ['受力', '速度', '加速度', '位移', '方向', '守恒', '约束条件', '平衡', '运动状态'],
    probability: ['事件', '条件概率', '样本空间', '独立', '分布', '频率', '均值', '方差'],
    generic: ['条件', '关系', '目标'],
  };
  for (const keyword of keywordMap[kind] || keywordMap.generic) {
    if (analysisText.includes(keyword)) {
      matches.push(keyword);
    }
  }

  matches.push(...knowledgeTags.filter((tag) => !WEAK_TAG_TEXTS.has(String(tag || '').trim())));
  const topicAnchor = String(item?.topic_category_snapshot ?? item?.topic_category ?? item?.topicCategory ?? '').trim();
  if (topicAnchor && !WEAK_TAG_TEXTS.has(topicAnchor)) {
    matches.push(topicAnchor);
  }

  const filteredMatches = matches.filter((match) => !isWeakWrongQuestionAnchor(match));
  return dedupeNonEmptyTexts(filteredMatches.length > 0 ? filteredMatches : matches, 4);
}

function buildGuidedReflectionAnalysis(item) {
  const source = item && typeof item === 'object' ? item : {};
  const kind = inferReflectionQuestionKind(source);
  const conditions = extractReflectionConditions(source, kind);
  const rawTopicAnchor = firstNonEmptyText(source.topic_category_snapshot, source.topic_category, source.topicCategory);
  const fallbackTopicPhrase = defaultTopicPhrase(kind);
  const topicAnchor = rawTopicAnchor && !WEAK_TAG_TEXTS.has(rawTopicAnchor) ? rawTopicAnchor : fallbackTopicPhrase;
  const reflection = normalizeReflectionSummary(source);
  const focusSource = firstNonEmptyText(
    source.child_reason_transcript_snapshot,
    source.student_transcript,
    source.child_reason_text_snapshot,
    source.student_reason_text,
    source.cause_note_snapshot,
    source.cause_note,
    reflection.unknownStep,
  );
  const primaryCondition = conditions[0] || '';
  const secondaryCondition = conditions[1] || '';
  const conditionPair = primaryCondition && secondaryCondition && primaryCondition !== secondaryCondition
    ? `${primaryCondition} 和 ${secondaryCondition}`
    : primaryCondition;

  const profiles = {
    geometry: {
      reasonTitle: '【图上先找关系】',
      reminderTitle: '【下次先连条件】',
      defaultPair: '图上的已知角和辅助线',
      focusCondition: primaryCondition || '垂直、平行或等角',
      startAction: '先在图上标出已知角、直角或对应边',
      bridgeBucket: '角度、长度、相似还是辅助线',
    },
    algebra: {
      reasonTitle: '【式子先看方向】',
      reminderTitle: '【下次先找变形】',
      defaultPair: '已知式和目标式',
      focusCondition: primaryCondition || '分母、因式或代换条件',
      startAction: '先盯住目标式和已知式差在哪一步',
      bridgeBucket: '移项、去分母、因式还是代换',
    },
    function: {
      reasonTitle: '【先盯定义域和图像】',
      reminderTitle: '【下次先看函数桥】',
      defaultPair: '定义域和图像特征',
      focusCondition: primaryCondition || '定义域、单调或参数条件',
      startAction: '先圈出自变量范围和图像线索',
      bridgeBucket: '定义域、图像、单调还是参数',
    },
    calculus: {
      reasonTitle: '【先看对象和边界】',
      reminderTitle: '【下次先定变化关系】',
      defaultPair: '求导对象和边界条件',
      focusCondition: primaryCondition || '导数、积分或边界条件',
      startAction: '先看要求导还是积分，再圈边界条件',
      bridgeBucket: '变化率、单调、边界还是几何意义',
    },
    mechanics: {
      reasonTitle: '【先画受力和状态】',
      reminderTitle: '【下次先选方程】',
      defaultPair: '受力情况和运动状态',
      focusCondition: primaryCondition || '受力、方向或约束条件',
      startAction: '先分清受力、方向和当前运动状态',
      bridgeBucket: '受力、守恒、位移还是速度关系',
    },
    probability: {
      reasonTitle: '【先定事件和样本】',
      reminderTitle: '【下次先拆事件】',
      defaultPair: '事件定义和样本空间',
      focusCondition: primaryCondition || '事件、条件概率或分布信息',
      startAction: '先把事件和样本空间写清楚',
      bridgeBucket: '事件、独立、条件概率还是分布',
    },
    generic: {
      reasonTitle: '【先把条件连起来】',
      reminderTitle: '【下次先找入口】',
      defaultPair: '题目条件和目标',
      focusCondition: primaryCondition || '关键条件',
      startAction: '先圈出已知和问题在问什么',
      bridgeBucket: '条件、关系、式子还是图形线索',
    },
  };
  const profile = profiles[kind] || profiles.generic;
  const topicPhrase = topicAnchor === fallbackTopicPhrase ? fallbackTopicPhrase : (topicAnchor.endsWith('题') ? topicAnchor : `${topicAnchor}题`);

  return {
    goal: extractReflectionGoal(source, kind),
    topicAnchor,
    topicPhrase,
    focusHint: shortenWrongQuestionText(focusSource, 24),
    conditionPair: conditionPair || profile.defaultPair,
    focusCondition: isWeakWrongQuestionAnchor(primaryCondition) ? profile.focusCondition : primaryCondition,
    startAction: profile.startAction,
    bridgeBucket: profile.bridgeBucket,
    reasonTitle: profile.reasonTitle,
    reminderTitle: profile.reminderTitle,
  };
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

  return hintLines.map((line) => humanizeWrongQuestionCopy(line)).filter(Boolean).slice(0, 3);
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
  return merged.map((line) => humanizeWrongQuestionCopy(line)).filter(Boolean).slice(0, 3);
}

function buildQuestionSummaryText(item) {
  const reflection = normalizeReflectionSummary(item);
  const structured = normalizeStructuredContent(item);
  const questionStructured = normalizeQuestionStructured(item);
  const questionText = normalizePromptText(item.question_text_snapshot || item.question_text || '').trim();
  const studentReason = firstNonEmptyText(
    isGenericReasonText(item.child_reason_transcript_snapshot) ? '' : item.child_reason_transcript_snapshot,
    isGenericReasonText(item.student_transcript) ? '' : item.student_transcript,
    isGenericReasonText(item.child_reason_text_snapshot) ? '' : item.child_reason_text_snapshot,
    isGenericReasonText(item.student_reason_text) ? '' : item.student_reason_text,
  );
  const reasonAnchor = firstNonEmptyText(studentReason, reflection.whyWrong, structured.mistakeFocus);
  const guidanceLines = buildGuidingMethodLines(item);

  if (reasonAnchor && guidanceLines.length > 0) {
    return humanizeWrongQuestionCopy(`先从“${reasonAnchor.replace(/[。！!？?]$/u, '')}”这里倒回来，这题第一手先做：${guidanceLines[0]}`);
  }
  if (guidanceLines.length > 0) {
    return humanizeWrongQuestionCopy(guidanceLines[0]);
  }
  if (reasonAnchor) {
    return humanizeWrongQuestionCopy(`先从“${reasonAnchor.replace(/[。！!？?]$/u, '')}”这里回头看，再想第一步该用什么关系。`);
  }
  if (questionStructured.stem) {
    return humanizeWrongQuestionCopy(`先把题目里“${questionStructured.stem}”这一步重新读清。`);
  }
  if (questionText) {
    return humanizeWrongQuestionCopy('先把题目在问什么、已知什么重新圈出来，再决定第一步从哪里下手。');
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
  const analysis = buildGuidedReflectionAnalysis(item);
  const unknownStep = isWeakWrongQuestionAnchor(reflection.unknownStep) ? '' : reflection.unknownStep;
  const sourceAnchor = firstNonEmptyText(
    isGenericReasonText(item?.child_reason_transcript_snapshot) ? '' : item?.child_reason_transcript_snapshot,
    isGenericReasonText(item?.student_transcript) ? '' : item?.student_transcript,
    isGenericReasonText(item?.child_reason_text_snapshot) ? '' : item?.child_reason_text_snapshot,
    isGenericReasonText(item?.student_reason_text) ? '' : item?.student_reason_text,
    reflection.whyWrong,
    unknownStep,
  );
  const normalizedSourceAnchor = isWeakWrongQuestionAnchor(sourceAnchor) ? '' : sourceAnchor;
  const sourcePrefix = normalizedSourceAnchor ? `先回到“${shortenWrongQuestionText(normalizedSourceAnchor, 22)}”这一步，` : '';
  const bridgeSource = knowledgeTags.filter((tag) => !isWeakWrongQuestionAnchor(tag)).slice(0, 3).join('、') || analysis.bridgeBucket;

  return [
    {
      title: analysis.reasonTitle,
      contentHtml: [
        `${sourcePrefix}像这题，先看 ${analysis.conditionPair}，想想它们能不能连出 ______。`,
        `别急着往下算，先把 ${analysis.focusCondition} 改成能直接用的 ______，再往下做。`,
      ].map((line) => renderPromptHtml(humanizeWrongQuestionCopy(line))).join('<br />'),
      kind: 'reflection',
    },
    {
      title: analysis.reminderTitle,
      contentHtml: [
        reflection.helpPreference
          ? `下次遇到 ${analysis.topicPhrase}，先按“${shortenWrongQuestionText(reflection.helpPreference, 18)}”的顺序，${analysis.startAction}，再找 ______。`
          : `下次遇到 ${analysis.topicPhrase}，我先${analysis.startAction}，先找 ______，再下笔。`,
        `要是还连不上，就问自己：在 ${bridgeSource} 这里，还差哪一步 ______。`,
      ].map((line) => renderPromptHtml(humanizeWrongQuestionCopy(line))).join('<br />'),
      kind: 'reflection',
    },
  ];
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
