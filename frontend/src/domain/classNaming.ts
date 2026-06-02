export const academicStageOptions = ['小奥', '初中', '高中'] as const;
export const bridgeStageOptions = ['小学', '初中', '高中'] as const;

export type AcademicStage = typeof academicStageOptions[number];
export type BridgeStage = typeof bridgeStageOptions[number];

export const academicGradeGroups: Record<AcademicStage, string[]> = {
  小奥: ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级'],
  初中: ['七年级', '八年级', '九年级'],
  高中: ['高一', '高二', '高三'],
};

export const academicGradeOptions = [
  ...academicGradeGroups.小奥,
  ...academicGradeGroups.初中,
  ...academicGradeGroups.高中,
];

const gradeAliasMap: Record<string, string> = {
  '1年级': '一年级',
  '2年级': '二年级',
  '3年级': '三年级',
  '4年级': '四年级',
  '5年级': '五年级',
  '6年级': '六年级',
  '7年级': '七年级',
  '8年级': '八年级',
  '9年级': '九年级',
  一年级: '一年级',
  二年级: '二年级',
  三年级: '三年级',
  四年级: '四年级',
  五年级: '五年级',
  六年级: '六年级',
  七年级: '七年级',
  八年级: '八年级',
  九年级: '九年级',
  初一: '七年级',
  初二: '八年级',
  初三: '九年级',
  高一: '高一',
  高二: '高二',
  高三: '高三',
};

const classGradeAliases: Array<[string, string]> = [
  ['一年级', '一年级'],
  ['二年级', '二年级'],
  ['三年级', '三年级'],
  ['四年级', '四年级'],
  ['五年级', '五年级'],
  ['六年级', '六年级'],
  ['七年级', '七年级'],
  ['八年级', '八年级'],
  ['九年级', '九年级'],
  ['初一', '七年级'],
  ['初二', '八年级'],
  ['初三', '九年级'],
  ['高一', '高一'],
  ['高二', '高二'],
  ['高三', '高三'],
];

export interface ClassDisplayNameInput {
  subject?: string;
  class_type?: string;
  stage?: string;
  current_grade: string;
  grade: string;
  class_number: string;
  cohort_year: string | number;
  show_cohort_year: boolean;
  is_bridge: boolean;
  bridge_target?: string;
  selected_student_names?: string[];
}

export interface ClassDisplayNameSource {
  name?: string | null;
  subject?: string | null;
  class_type?: string | null;
  stage?: string | null;
  current_grade?: string | null;
  grade?: string | null;
  class_number?: string | number | null;
  cohort_year?: string | number | null;
  is_bridge?: boolean | number | null;
  bridge_target?: string | null;
}

export interface FormatClassDisplayNameOptions {
  showCohortYear?: boolean;
}

export function normalizeAcademicGradeLabel(value: string): string {
  const normalized = value.trim();
  return gradeAliasMap[normalized] || normalized;
}

export function getAcademicStageFromGrade(value: string): AcademicStage | '' {
  const grade = normalizeAcademicGradeLabel(value);
  if (academicGradeGroups.小奥.includes(grade)) return '小奥';
  if (academicGradeGroups.初中.includes(grade)) return '初中';
  if (academicGradeGroups.高中.includes(grade)) return '高中';
  return '';
}

export function normalizeBridgeStage(value: string): BridgeStage | '' {
  const normalized = value.trim();
  if (normalized === '小学' || normalized === '小奥' || normalized === '小') return '小学';
  if (normalized === '初中' || normalized === '初') return '初中';
  if (normalized === '高中' || normalized === '高') return '高中';
  return '';
}

function getBridgeStageShortLabel(stage: string): string {
  const normalized = normalizeBridgeStage(stage);
  if (normalized === '小学') return '小';
  if (normalized === '初中') return '初';
  if (normalized === '高中') return '高';
  return '';
}

function getNextBridgeStage(stage: string): BridgeStage {
  const normalized = normalizeBridgeStage(stage);
  if (normalized === '初中') return '高中';
  if (normalized === '高中') return '高中';
  return '初中';
}

export function serializeBridgeTarget(fromStage: string, toStage: string): string {
  const normalizedFrom = normalizeBridgeStage(fromStage) || '小学';
  const normalizedTo = normalizeBridgeStage(toStage) || getNextBridgeStage(normalizedFrom);
  return `${normalizedFrom}衔接${normalizedTo}`;
}

export function parseBridgeTarget(
  bridgeTarget: string | null | undefined,
  fallbackStage: string,
): { fromStage: BridgeStage; toStage: BridgeStage } {
  const normalizedFallback = normalizeBridgeStage(fallbackStage) || '小学';
  const raw = (bridgeTarget || '').trim();
  if (!raw || raw === '默认下一学段') {
    return {
      fromStage: normalizedFallback,
      toStage: getNextBridgeStage(normalizedFallback),
    };
  }
  const compact = raw.replace(/\s+/g, '');
  const longMatch = compact.match(/^(小学|小奥|小|初中|初|高中|高)衔接(小学|小奥|小|初中|初|高中|高)$/);
  if (longMatch) {
    return {
      fromStage: normalizeBridgeStage(longMatch[1]) || normalizedFallback,
      toStage: normalizeBridgeStage(longMatch[2]) || getNextBridgeStage(normalizedFallback),
    };
  }
  const shortMatch = compact.match(/^(小|初|高)衔(小|初|高)$/);
  if (shortMatch) {
    return {
      fromStage: normalizeBridgeStage(shortMatch[1]) || normalizedFallback,
      toStage: normalizeBridgeStage(shortMatch[2]) || getNextBridgeStage(normalizedFallback),
    };
  }
  if (compact === '初中衔接') {
    return { fromStage: normalizedFallback, toStage: '初中' };
  }
  if (compact === '高中衔接') {
    return { fromStage: normalizedFallback, toStage: '高中' };
  }
  return {
    fromStage: normalizedFallback,
    toStage: getNextBridgeStage(normalizedFallback),
  };
}

export function getBridgeShortLabel(bridgeTarget: string | null | undefined, fallbackStage: string): string {
  const { fromStage, toStage } = parseBridgeTarget(bridgeTarget, fallbackStage);
  const fromLabel = getBridgeStageShortLabel(fromStage);
  const toLabel = getBridgeStageShortLabel(toStage);
  return fromLabel && toLabel ? `${fromLabel}衔${toLabel}` : '衔接';
}

export function isReverseBridgeTarget(bridgeTarget: string | null | undefined, fallbackStage: string): boolean {
  const { fromStage, toStage } = parseBridgeTarget(bridgeTarget, fallbackStage);
  const rank: Record<BridgeStage, number> = { 小学: 1, 初中: 2, 高中: 3 };
  return rank[toStage] < rank[fromStage];
}

export function getAcademicGradeRank(value: string): number {
  const grade = normalizeAcademicGradeLabel(value);
  const index = academicGradeOptions.indexOf(grade);
  return index === -1 ? 999 : index;
}

export function getAcademicGradeRankFromText(value: string): number {
  const label = value.trim();
  const gradeRanks: Array<[RegExp, number]> = [
    [/高三|高中三|高 3|高3/, 11],
    [/高二|高中二|高 2|高2/, 10],
    [/高一|高中一|高 1|高1/, 9],
    [/初三|初中三|初 3|初3|九年级|9年级/, 8],
    [/初二|初中二|初 2|初2|八年级|8年级/, 7],
    [/初一|初中一|初 1|初1|七年级|7年级/, 6],
    [/六年级|6年级|小六/, 5],
    [/五年级|5年级|小五/, 4],
    [/四年级|4年级|小四/, 3],
    [/三年级|3年级|小三/, 2],
    [/二年级|2年级|小二/, 1],
    [/一年级|1年级|小一/, 0],
  ];
  return gradeRanks.find(([pattern]) => pattern.test(label))?.[1] ?? 999;
}

export function getCurrentSchoolYearStart(date = new Date()): number {
  const month = date.getMonth() + 1;
  const day = date.getDate();
  return month > 6 || (month === 6 && day >= 30) ? date.getFullYear() : date.getFullYear() - 1;
}

export function inferAcademicCohortYear(grade: string, date = new Date()): number {
  const normalizedGrade = normalizeAcademicGradeLabel(grade);
  const stage = getAcademicStageFromGrade(normalizedGrade);
  const stageGrades = stage ? academicGradeGroups[stage] : [];
  const stageOffset = stageGrades.indexOf(normalizedGrade);
  return getCurrentSchoolYearStart(date) - Math.max(0, stageOffset);
}

export function inferAcademicCohortYearForStage(grade: string, stage: string, date = new Date()): number {
  const gradeRank = getAcademicGradeRank(grade);
  const normalizedStage = normalizeBridgeStage(stage);
  const stageFirstRank = normalizedStage === '高中' ? 9 : normalizedStage === '初中' ? 6 : 0;
  if (gradeRank === 999) {
    return inferAcademicCohortYear(grade, date);
  }
  return getCurrentSchoolYearStart(date) - (gradeRank - stageFirstRank);
}

function getCohortStageForDisplay(form: Pick<ClassDisplayNameInput, 'is_bridge' | 'bridge_target' | 'stage' | 'current_grade' | 'grade'>): BridgeStage {
  if (form.is_bridge) {
    return parseBridgeTarget(form.bridge_target, form.stage || form.current_grade || form.grade).toStage;
  }
  return normalizeBridgeStage(form.stage || getAcademicStageFromGrade(form.current_grade || form.grade)) || '小学';
}

export function buildGroupClassDisplayName(form: ClassDisplayNameInput): string {
  const grade = normalizeAcademicGradeLabel(form.current_grade || form.grade);
  const subject = (form.subject || '').trim();
  const cohortStage = getCohortStageForDisplay({ ...form, current_grade: grade });
  const cohortStageLabel = getBridgeStageShortLabel(cohortStage);
  const bridgeSuffix = form.is_bridge ? `·${getBridgeShortLabel(form.bridge_target, form.stage || grade)}` : '';
  const classNumber = String(form.class_number).trim();
  if (!grade || !classNumber) {
    return '';
  }
  const cohortYear = Number(form.cohort_year) || inferAcademicCohortYearForStage(grade, cohortStage);
  const cohortPrefix = form.show_cohort_year && cohortYear ? `${cohortStageLabel}${cohortYear}级·` : '';
  const subjectPrefix = subject ? `${subject}·` : '';
  return `${subjectPrefix}${cohortPrefix}${grade}·${classNumber}班${bridgeSuffix}`;
}

export function buildSmallClassDisplayName(form: ClassDisplayNameInput): string {
  const grade = normalizeAcademicGradeLabel(form.current_grade || form.grade);
  const subject = (form.subject || '').trim();
  const classType = (form.class_type || '').trim();
  const studentNames = (form.selected_student_names || []).map((item) => item.trim()).filter(Boolean);
  if (!classType || classType === 'group' || !grade || !studentNames.length) {
    return '';
  }
  const cohortStage = getCohortStageForDisplay({ ...form, current_grade: grade });
  const cohortStageLabel = getBridgeStageShortLabel(cohortStage);
  const bridgeSuffix = form.is_bridge ? `·${getBridgeShortLabel(form.bridge_target, form.stage || grade)}` : '';
  const namePart = classType === '1v1'
    ? studentNames[0]
    : studentNames.map((item) => item.slice(0, 1)).join('');
  const cohortYear = Number(form.cohort_year) || inferAcademicCohortYearForStage(grade, cohortStage);
  const cohortPart = form.show_cohort_year && cohortYear ? `·${cohortStageLabel}${cohortYear}级` : '';
  const subjectPrefix = subject ? `${subject}·` : '';
  return `${subjectPrefix}${classType}${cohortPart}·${grade}·${namePart}${bridgeSuffix}`;
}

export function buildClassDisplayName(form: ClassDisplayNameInput): string {
  const classType = (form.class_type || 'group').trim() || 'group';
  if (classType !== 'group') {
    return buildSmallClassDisplayName(form);
  }
  return buildGroupClassDisplayName(form);
}

function stripCohortYearFromSavedName(value: string): string {
  return value.replace(/·[小初高]\d{4}级(?=·)/g, '');
}

export function formatClassDisplayName(
  source: ClassDisplayNameSource | null | undefined,
  options: FormatClassDisplayNameOptions = {},
): string {
  if (!source) {
    return '';
  }
  const displayName = buildClassDisplayName({
    subject: source.subject || '',
    class_type: source.class_type || 'group',
    stage: source.stage || '',
    grade: source.grade || '',
    current_grade: source.current_grade || source.grade || '',
    class_number: source.class_number == null ? '' : String(source.class_number),
    cohort_year: source.cohort_year == null ? '' : source.cohort_year,
    show_cohort_year: Boolean(options.showCohortYear),
    is_bridge: Boolean(source.is_bridge),
    bridge_target: source.bridge_target || '',
  });
  const savedName = source.name?.trim() ?? '';
  if (displayName) {
    return displayName;
  }
  return options.showCohortYear ? savedName : stripCohortYearFromSavedName(savedName);
}

export function normalizeClassNameInput(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }

  const normalized = trimmed
    .replace(/\s+/g, '')
    .replace(/^6年级/, '六年级')
    .replace(/^9年级/, '九年级')
    .replace(/^8年级/, '八年级')
    .replace(/^7年级/, '七年级')
    .replace(/^5年级/, '五年级')
    .replace(/^4年级/, '四年级')
    .replace(/^3年级/, '三年级')
    .replace(/^2年级/, '二年级')
    .replace(/^1年级/, '一年级')
    .replace(/^六年(?=\d+班$)/, '六年级')
    .replace(/^九年(?=\d+班$)/, '九年级')
    .replace(/^八年(?=\d+班$)/, '八年级')
    .replace(/^七年(?=\d+班$)/, '七年级')
    .replace(/^五年(?=\d+班$)/, '五年级')
    .replace(/^四年(?=\d+班$)/, '四年级')
    .replace(/^三年(?=\d+班$)/, '三年级')
    .replace(/^二年(?=\d+班$)/, '二年级')
    .replace(/^一年(?=\d+班$)/, '一年级')
    .replace(/一班$/, '1班')
    .replace(/二班$/, '2班')
    .replace(/三班$/, '3班')
    .replace(/四班$/, '4班')
    .replace(/五班$/, '5班')
    .replace(/六班$/, '6班');

  const gradePrefix = classGradeAliases.find(([alias]) => normalized.startsWith(alias))?.[1];
  const match = normalized.match(/^(一年级|二年级|三年级|四年级|五年级|六年级|七年级|八年级|九年级|初一|初二|初三|高一|高二|高三)(\d+)班$/);
  if (!match || !gradePrefix) {
    return trimmed;
  }

  return `${gradePrefix} ${match[2]} 班`;
}
