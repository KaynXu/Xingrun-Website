export type CourseCalendarPeriod = '上午' | '下午' | '晚间';

export interface CourseCalendarClassRecord {
  id: number;
  name: string;
  subject?: string;
  grade?: string;
  teacher_name?: string;
  teacher_email?: string;
  lesson_count?: number;
}

export interface CourseCalendarLessonRecord {
  id: number;
  class_id?: number | null;
  date: string;
  subject?: string;
  grade?: string;
  topic?: string;
  summary?: string;
  weak_points?: string;
  pdf_path?: string;
  created_at?: string;
  session?: CourseCalendarPeriod | string;
  record_status?: string;
}

export interface JoinedCourseCalendarLesson {
  id: number;
  classId: number | null;
  className: string;
  subject: string;
  grade: string;
  teacherName: string;
  teacherEmail: string;
  lessonCount: number;
  date: string;
  title: string;
  summary: string;
  weakPoints: string;
  pdfPath: string;
  period: CourseCalendarPeriod;
  pending: boolean;
}

export interface CourseCalendarPeriodBuckets {
  上午: JoinedCourseCalendarLesson[];
  下午: JoinedCourseCalendarLesson[];
  晚间: JoinedCourseCalendarLesson[];
}

export interface TeacherLoadSummary {
  teacherName: string;
  count: number;
  classCount: number;
  lessonCount: number;
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
  lessonCount: number;
  statusLabel: string;
}

const PERIOD_ORDER: CourseCalendarPeriod[] = ['上午', '下午', '晚间'];

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

function normalizePeriod(period?: string): CourseCalendarPeriod {
  if (period === '上午' || period === '下午' || period === '晚间') {
    return period;
  }
  return '上午';
}

function resolvePeriod(lesson: CourseCalendarLessonRecord): CourseCalendarPeriod {
  if (lesson.session) {
    return normalizePeriod(lesson.session);
  }

  if (lesson.created_at) {
    const timeMatch = lesson.created_at.match(/(?:\s|T)(\d{2}):(\d{2})/);
    if (timeMatch) {
      const hour = Number(timeMatch[1]);
      if (hour < 12) {
        return '上午';
      }
      if (hour < 18) {
        return '下午';
      }
      return '晚间';
    }
  }

  return '上午';
}

function countLessonsByClassId(lessons: CourseCalendarLessonRecord[]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const lesson of lessons) {
    if (typeof lesson.class_id !== 'number') {
      continue;
    }
    counts.set(lesson.class_id, (counts.get(lesson.class_id) ?? 0) + 1);
  }
  return counts;
}

function sortByPeriodAndDate(a: JoinedCourseCalendarLesson, b: JoinedCourseCalendarLesson): number {
  const dateCompare = a.date.localeCompare(b.date);
  if (dateCompare !== 0) {
    return dateCompare;
  }

  const periodCompare = PERIOD_ORDER.indexOf(a.period) - PERIOD_ORDER.indexOf(b.period);
  if (periodCompare !== 0) {
    return periodCompare;
  }

  return a.id - b.id;
}

export function getWeekDates(anchorDate: string): string[] {
  const weekStart = startOfIsoWeek(parseIsoDate(anchorDate));
  return Array.from({ length: 7 }, (_, index) => formatIsoDate(addDays(weekStart, index)));
}

export function getWeekRangeLabel(anchorDate: string): string {
  const weekDates = getWeekDates(anchorDate);
  return `${formatWeekLabelDate(parseIsoDate(weekDates[0]))} - ${formatWeekLabelDate(parseIsoDate(weekDates[6]))}`;
}

export function getVisibleWeekLabel(anchorDate: string): string {
  return getWeekRangeLabel(anchorDate);
}

export function joinClassesAndLessons(
  classes: CourseCalendarClassRecord[],
  lessons: CourseCalendarLessonRecord[],
): JoinedCourseCalendarLesson[] {
  const classById = new Map<number, CourseCalendarClassRecord>();
  for (const courseClass of classes) {
    classById.set(courseClass.id, courseClass);
  }

  const lessonCounts = countLessonsByClassId(lessons);

  return lessons
    .map((lesson) => {
      const courseClass = typeof lesson.class_id === 'number' ? classById.get(lesson.class_id) : undefined;
      const lessonCount = typeof lesson.class_id === 'number'
        ? lessonCounts.get(lesson.class_id) ?? courseClass?.lesson_count ?? 0
        : courseClass?.lesson_count ?? 0;

      return {
        id: lesson.id,
        classId: typeof lesson.class_id === 'number' ? lesson.class_id : null,
        className: courseClass?.name ?? '',
        subject: lesson.subject ?? courseClass?.subject ?? '',
        grade: lesson.grade ?? courseClass?.grade ?? '',
        teacherName: courseClass?.teacher_name ?? '',
        teacherEmail: courseClass?.teacher_email ?? '',
        lessonCount,
        date: lesson.date,
        title: lesson.topic ?? lesson.summary ?? courseClass?.name ?? '课程记录',
        summary: lesson.summary ?? '',
        weakPoints: lesson.weak_points ?? '',
        pdfPath: lesson.pdf_path ?? '',
        period: resolvePeriod(lesson),
        pending: lesson.record_status === 'pending' || (!lesson.pdf_path && !lesson.summary && !lesson.topic),
      };
    })
    .sort(sortByPeriodAndDate);
}

export function assignLessonCardsToPeriods(
  lessonCards: JoinedCourseCalendarLesson[],
): CourseCalendarPeriodBuckets {
  const buckets: CourseCalendarPeriodBuckets = {
    上午: [],
    下午: [],
    晚间: [],
  };

  for (const card of lessonCards) {
    buckets[card.period].push(card);
  }

  for (const period of PERIOD_ORDER) {
    buckets[period].sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  }

  return buckets;
}

export function summarizeTeacherLoad(
  lessonCards: JoinedCourseCalendarLesson[],
): TeacherLoadSummary[] {
  const summary = new Map<string, TeacherLoadSummary>();
  const classIdsByTeacher = new Map<string, Set<number>>();

  for (const lessonCard of lessonCards) {
    const teacherName = lessonCard.teacherName.trim() || '未分配教师';
    const classIds = classIdsByTeacher.get(teacherName) ?? new Set<number>();
    if (lessonCard.classId !== null) {
      classIds.add(lessonCard.classId);
    }
    classIdsByTeacher.set(teacherName, classIds);

    const existing = summary.get(teacherName);
    if (existing) {
      existing.count += 1;
      existing.lessonCount += 1;
      existing.classCount = classIds.size;
      existing.label = `${teacherName} · ${existing.count}`;
      continue;
    }

    summary.set(teacherName, {
      teacherName,
      count: 1,
      classCount: classIds.size,
      lessonCount: 1,
      label: `${teacherName} · 1`,
    });
  }

  return [...summary.values()].sort((a, b) => a.teacherName.localeCompare(b.teacherName, 'zh-Hans-CN'));
}

export function summarizePendingRecords(
  lessons: CourseCalendarLessonRecord[],
): PendingRecordSummary[] {
  const pendingLessons = lessons.filter((lesson) => lesson.record_status === 'pending' || (!lesson.pdf_path && !lesson.summary && !lesson.topic));

  if (pendingLessons.length === 0) {
    return [];
  }

  return [
    {
      label: '待补录',
      count: pendingLessons.length,
      lessonIds: pendingLessons.map((lesson) => lesson.id),
    },
  ];
}

export function buildClassStatusRailData(
  classes: CourseCalendarClassRecord[],
  lessons: CourseCalendarLessonRecord[] = [],
): ClassStatusRailItem[] {
  const lessonCounts = countLessonsByClassId(lessons);

  return classes
    .map((courseClass) => {
      const derivedLessonCount = lessonCounts.get(courseClass.id);
      const lessonCount = derivedLessonCount ?? courseClass.lesson_count ?? 0;

      return {
        id: courseClass.id,
        name: courseClass.name,
        subject: courseClass.subject ?? '',
        grade: courseClass.grade ?? '',
        teacherName: courseClass.teacher_name ?? '',
        teacherEmail: courseClass.teacher_email ?? '',
        lessonCount,
        statusLabel: lessonCount > 0 ? '已排课' : '待安排',
      };
    })
    .sort((a, b) => a.id - b.id);
}
