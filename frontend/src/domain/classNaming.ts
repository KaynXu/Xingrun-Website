export const academicStageOptions = ['小奥', '初中', '高中'] as const;

export type AcademicStage = typeof academicStageOptions[number];

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
  current_grade: string;
  grade: string;
  class_number: string;
  cohort_year: string | number;
  show_cohort_year: boolean;
  is_bridge: boolean;
}

export interface ClassDisplayNameSource {
  name?: string | null;
  current_grade?: string | null;
  grade?: string | null;
  class_number?: string | number | null;
  cohort_year?: string | number | null;
  is_bridge?: boolean | number | null;
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
  return date.getMonth() + 1 >= 7 ? date.getFullYear() : date.getFullYear() - 1;
}

export function inferAcademicCohortYear(grade: string, date = new Date()): number {
  const normalizedGrade = normalizeAcademicGradeLabel(grade);
  const stage = getAcademicStageFromGrade(normalizedGrade);
  const stageGrades = stage ? academicGradeGroups[stage] : [];
  const stageOffset = stageGrades.indexOf(normalizedGrade);
  return getCurrentSchoolYearStart(date) - Math.max(0, stageOffset);
}

export function buildClassDisplayName(form: ClassDisplayNameInput): string {
  const grade = normalizeAcademicGradeLabel(form.current_grade || form.grade);
  const classNumber = String(form.class_number).trim();
  if (!grade || !classNumber) {
    return '';
  }
  const cohortYear = Number(form.cohort_year) || inferAcademicCohortYear(grade);
  const cohortPrefix = form.show_cohort_year && cohortYear ? `${cohortYear}级·` : '';
  const bridgeSuffix = form.is_bridge ? '·衔接' : '';
  return `${cohortPrefix}${grade}·${classNumber}班${bridgeSuffix}`;
}

export function formatClassDisplayName(
  source: ClassDisplayNameSource | null | undefined,
  options: FormatClassDisplayNameOptions = {},
): string {
  if (!source) {
    return '';
  }
  const displayName = buildClassDisplayName({
    grade: source.grade || '',
    current_grade: source.current_grade || source.grade || '',
    class_number: source.class_number == null ? '' : String(source.class_number),
    cohort_year: source.cohort_year == null ? '' : source.cohort_year,
    show_cohort_year: Boolean(options.showCohortYear),
    is_bridge: Boolean(source.is_bridge),
  });
  return displayName || (source.name?.trim() ?? '');
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
