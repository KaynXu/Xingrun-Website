export const COURSE_CALENDAR_TIME_BLOCKS = [
  '08:00-10:00',
  '10:00-12:00',
  '14:00-16:00',
  '16:00-18:00',
  '18:00-20:00',
  '20:00-22:00',
] as const;

export type CourseCalendarTimeBlock = (typeof COURSE_CALENDAR_TIME_BLOCKS)[number];

const LEGACY_COURSE_CALENDAR_TIME_BLOCKS: Record<string, CourseCalendarTimeBlock> = {
  '13:00-15:00': '14:00-16:00',
  '15:00-17:00': '16:00-18:00',
  '17:00-19:00': '18:00-20:00',
  '19:00-21:00': '20:00-22:00',
};

export interface CourseCalendarClassRecord {
  id: number;
  name: string;
  subject?: string;
  grade?: string;
  teacher_name?: string;
  teacher_email?: string;
  lesson_count?: number;
}

export interface CourseCalendarScheduleRecord {
  id: number;
  class_id: number;
  date: string;
  time_block: CourseCalendarTimeBlock | string;
  created_by?: number | null;
  created_at?: string;
  start_offset_minutes?: number;
  class_name?: string;
  subject?: string;
  grade?: string;
  teacher_name?: string;
  teacher_email?: string;
}

export interface CourseCalendarCustomItemRecord {
  id: number;
  title: string;
  time_range: string;
  note: string;
  visibility: 'private' | 'organization';
  can_delete?: boolean;
  created_by?: number | null;
  created_at?: string;
}

export interface CourseCalendarCustomScheduleRecord {
  id: number;
  custom_item_id: number;
  date: string;
  time_block: CourseCalendarTimeBlock | string;
  start_offset_minutes?: number;
  title: string;
  time_range: string;
  note: string;
  visibility?: 'private' | 'organization';
  created_by?: number | null;
  created_at?: string;
}

export interface JoinedCourseCalendarSchedule {
  id: number;
  classId: number;
  className: string;
  subject: string;
  grade: string;
  teacherName: string;
  teacherEmail: string;
  scheduleCount: number;
  date: string;
  timeBlock: CourseCalendarTimeBlock;
  startOffsetMinutes: number;
  startLabel: string;
  endLabel: string;
  displayRange: string;
  startText: string;
}

export type CourseCalendarTimeBlockBuckets = Record<CourseCalendarTimeBlock, JoinedCourseCalendarSchedule[]>;

export interface TeacherLoadSummary {
  teacherName: string;
  count: number;
  classCount: number;
  scheduleCount: number;
  label: string;
}

export interface PendingRecordSummary {
  label: string;
  count: number;
  lessonIds: number[];
}

export interface ClassStatusRailItem {
  id: number;
  name: string;
  subject: string;
  grade: string;
  teacherName: string;
  teacherEmail: string;
  scheduleCount: number;
  statusLabel: string;
}

function parseIsoDate(dateString: string): Date {
  const [year, month, day] = dateString.split('-').map((value) => Number(value));
  return new Date(Date.UTC(year, month - 1, day));
}

function formatIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function formatWeekLabelDate(date: Date): string {
  return formatIsoDate(date).replace(/-/g, '.');
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date.getTime());
  next.setUTCDate(next.getUTCDate() + days);
  return next;
}

function startOfIsoWeek(date: Date): Date {
  const offset = (date.getUTCDay() + 6) % 7;
  return addDays(date, -offset);
}

function normalizeTimeBlock(timeBlock?: string): CourseCalendarTimeBlock {
  const normalized = (timeBlock ?? '').trim();
  if (COURSE_CALENDAR_TIME_BLOCKS.includes(normalized as CourseCalendarTimeBlock)) {
    return normalized as CourseCalendarTimeBlock;
  }
  return LEGACY_COURSE_CALENDAR_TIME_BLOCKS[normalized] ?? COURSE_CALENDAR_TIME_BLOCKS[0];
}

function normalizeStartOffsetMinutes(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.trunc(value) : 0;
}

function parseClockMinutes(value: string): number {
  const [hour, minute] = value.split(':').map((part) => Number(part));
  return hour * 60 + minute;
}

function formatClockMinutes(value: number): string {
  const normalized = ((value % 1440) + 1440) % 1440;
  const hour = Math.floor(normalized / 60);
  const minute = normalized % 60;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
}

export function buildCourseScheduleTimeRange(timeBlock: string, startOffsetMinutes = 0) {
  const normalizedTimeBlock = normalizeTimeBlock(timeBlock);
  const [baseStart, baseEnd] = normalizedTimeBlock.split('-');
  const normalizedOffset = normalizeStartOffsetMinutes(startOffsetMinutes);
  const startLabel = formatClockMinutes(parseClockMinutes(baseStart) + normalizedOffset);
  const endLabel = formatClockMinutes(parseClockMinutes(baseEnd) + normalizedOffset);

  return {
    startLabel,
    endLabel,
    displayRange: `${startLabel}-${endLabel}`,
    startText: `${startLabel} 开始`,
  };
}

function countSchedulesByClassId(schedules: CourseCalendarScheduleRecord[]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const schedule of schedules) {
    counts.set(schedule.class_id, (counts.get(schedule.class_id) ?? 0) + 1);
  }
  return counts;
}

function sortByBlockAndDate(a: JoinedCourseCalendarSchedule, b: JoinedCourseCalendarSchedule): number {
  const dateCompare = a.date.localeCompare(b.date);
  if (dateCompare !== 0) {
    return dateCompare;
  }

  const blockCompare = COURSE_CALENDAR_TIME_BLOCKS.indexOf(a.timeBlock) - COURSE_CALENDAR_TIME_BLOCKS.indexOf(b.timeBlock);
  if (blockCompare !== 0) {
    return blockCompare;
  }

  return a.id - b.id;
}

export function getWeekDates(anchorDate: string): string[] {
  const weekStart = startOfIsoWeek(parseIsoDate(anchorDate));
  return Array.from({ length: 7 }, (_, index) => formatIsoDate(addDays(weekStart, index)));
}

export function getCurrentWeekTuesday(dateString: string): string {
  return formatIsoDate(addDays(startOfIsoWeek(parseIsoDate(dateString)), 1));
}

export function getCalendarPageDates(anchorDate: string, visibleDayCount: number): string[] {
  const pageStart = parseIsoDate(anchorDate);
  const normalizedCount = Math.max(1, Math.min(14, Math.trunc(visibleDayCount) || 6));
  return Array.from({ length: normalizedCount }, (_, index) => formatIsoDate(addDays(pageStart, index)));
}

export function getCalendarPageRangeLabel(anchorDate: string, visibleDayCount: number): string {
  const dates = getCalendarPageDates(anchorDate, visibleDayCount);
  return `${formatWeekLabelDate(parseIsoDate(dates[0]))} - ${formatWeekLabelDate(parseIsoDate(dates[dates.length - 1]))}`;
}

export function getWeekRangeLabel(anchorDate: string): string {
  const weekDates = getWeekDates(anchorDate);
  return `${formatWeekLabelDate(parseIsoDate(weekDates[0]))} - ${formatWeekLabelDate(parseIsoDate(weekDates[6]))}`;
}

export function getVisibleWeekLabel(anchorDate: string): string {
  return getWeekRangeLabel(anchorDate);
}

export function joinClassesAndSchedules(
  classes: CourseCalendarClassRecord[],
  schedules: CourseCalendarScheduleRecord[],
): JoinedCourseCalendarSchedule[] {
  const classById = new Map<number, CourseCalendarClassRecord>();
  for (const courseClass of classes) {
    classById.set(courseClass.id, courseClass);
  }

  const scheduleCounts = countSchedulesByClassId(schedules);

  return schedules
    .map((schedule) => {
      const courseClass = classById.get(schedule.class_id);

      const startOffsetMinutes = normalizeStartOffsetMinutes(schedule.start_offset_minutes);
      const timeRange = buildCourseScheduleTimeRange(schedule.time_block, startOffsetMinutes);

      return {
        id: schedule.id,
        classId: schedule.class_id,
        className: courseClass?.name ?? schedule.class_name ?? '',
        subject: courseClass?.subject ?? schedule.subject ?? '',
        grade: courseClass?.grade ?? schedule.grade ?? '',
        teacherName: courseClass?.teacher_name ?? schedule.teacher_name ?? '',
        teacherEmail: courseClass?.teacher_email ?? schedule.teacher_email ?? '',
        scheduleCount: scheduleCounts.get(schedule.class_id) ?? 0,
        date: schedule.date,
        timeBlock: normalizeTimeBlock(schedule.time_block),
        startOffsetMinutes,
        ...timeRange,
      };
    })
    .sort(sortByBlockAndDate);
}

export function assignScheduleCardsToTimeBlocks(
  scheduleCards: JoinedCourseCalendarSchedule[],
): CourseCalendarTimeBlockBuckets {
  const buckets = Object.fromEntries(
    COURSE_CALENDAR_TIME_BLOCKS.map((timeBlock) => [timeBlock, []]),
  ) as CourseCalendarTimeBlockBuckets;

  for (const card of scheduleCards) {
    buckets[card.timeBlock].push(card);
  }

  for (const timeBlock of COURSE_CALENDAR_TIME_BLOCKS) {
    buckets[timeBlock].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  }

  return buckets;
}

export function summarizeTeacherLoad(
  scheduleCards: JoinedCourseCalendarSchedule[],
): TeacherLoadSummary[] {
  const summary = new Map<string, TeacherLoadSummary>();
  const classIdsByTeacher = new Map<string, Set<number>>();

  for (const scheduleCard of scheduleCards) {
    const teacherName = scheduleCard.teacherName.trim() || '未分配教师';
    const classIds = classIdsByTeacher.get(teacherName) ?? new Set<number>();
    classIds.add(scheduleCard.classId);
    classIdsByTeacher.set(teacherName, classIds);

    const existing = summary.get(teacherName);
    if (existing) {
      existing.count += 1;
      existing.scheduleCount += 1;
      existing.classCount = classIds.size;
      existing.label = `${teacherName} · ${existing.count}`;
      continue;
    }

    summary.set(teacherName, {
      teacherName,
      count: 1,
      classCount: classIds.size,
      scheduleCount: 1,
      label: `${teacherName} · 1`,
    });
  }

  return [...summary.values()].sort((a, b) => a.teacherName.localeCompare(b.teacherName, 'zh-Hans-CN'));
}

export function summarizePendingRecords(
  _schedules: CourseCalendarScheduleRecord[],
): PendingRecordSummary[] {
  return [];
}

export function buildClassStatusRailData(
  classes: CourseCalendarClassRecord[],
  schedules: CourseCalendarScheduleRecord[] = [],
): ClassStatusRailItem[] {
  const scheduleCounts = countSchedulesByClassId(schedules);

  return classes
    .map((courseClass) => {
      const scheduleCount = scheduleCounts.get(courseClass.id) ?? 0;

      return {
        id: courseClass.id,
        name: courseClass.name,
        subject: courseClass.subject ?? '',
        grade: courseClass.grade ?? '',
        teacherName: courseClass.teacher_name ?? '',
        teacherEmail: courseClass.teacher_email ?? '',
        scheduleCount,
        statusLabel: scheduleCount > 0 ? '已排课' : '待安排',
      };
    })
    .sort((a, b) => a.id - b.id);
}
