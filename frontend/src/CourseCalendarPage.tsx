import React from 'react';
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  ChevronDown,
  Clock,
  Filter,
  GripVertical,
  Plus,
  Sparkles,
  Trash2,
  Users,
} from 'lucide-react';

import {
  COURSE_CALENDAR_TIME_BLOCKS,
  assignScheduleCardsToTimeBlocks,
  buildCourseScheduleTimeRange,
  getCalendarPageDates,
  getCalendarPageRangeLabel,
  joinClassesAndSchedules,
  type CourseCalendarClassRecord,
  type CourseCalendarCustomItemRecord,
  type CourseCalendarCustomScheduleRecord,
  type CourseCalendarScheduleRecord,
  type CourseCalendarTimeBlock,
  type JoinedCourseCalendarSchedule,
} from './courseCalendarData';

export interface CourseCalendarPageProps {
  anchorDate: string;
  today: string;
  currentUserRole: 'super_owner' | 'owner' | 'admin' | 'member';
  classes: CourseCalendarClassRecord[];
  schedules: CourseCalendarScheduleRecord[];
  customItems: CourseCalendarCustomItemRecord[];
  customSchedules: CourseCalendarCustomScheduleRecord[];
  visibleDayCount: number;
  onVisibleDayCountChange: (dayCount: number) => void;
  onPreviousPage: (dayCount: number) => void;
  onNextPage: (dayCount: number) => void;
  onScheduleClass: (classId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes?: number) => void;
  onScheduleCustomItem: (customItemId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes?: number) => void;
  onCreateCustomItem: (item: { title: string; time_range: string; note: string; visibility: 'private' | 'organization' }) => void;
  onDeleteSchedule: (scheduleId: number) => void;
  onDeleteCustomSchedule: (scheduleId: number) => void;
}

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const TIME_ADJUSTMENT_PRESETS = [
  { label: '提前 15 分钟', minutes: -15 },
  { label: '提前半小时', minutes: -30 },
  { label: '晚 15 分钟', minutes: 15 },
  { label: '晚半小时', minutes: 30 },
] as const;

type CustomOffsetDirection = 'early' | 'late';

interface PendingDrop {
  itemType: 'class' | 'custom';
  itemId: number;
  date: string;
  timeBlock: CourseCalendarTimeBlock;
}

interface JoinedCustomSchedule {
  id: number;
  customItemId: number;
  title: string;
  timeRange: string;
  note: string;
  date: string;
  timeBlock: CourseCalendarTimeBlock;
  startOffsetMinutes: number;
  startText: string;
  displayRange: string;
}

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function parseIsoDate(dateString: string): Date {
  const [year, month, day] = dateString.split('-').map((value) => Number(value));
  return new Date(Date.UTC(year, month - 1, day));
}

function formatDayLabel(dateString: string): string {
  const [, month, day] = dateString.split('-');
  return `${month}.${day}`;
}

function formatWeekdayLabel(dateString: string): string {
  const date = parseIsoDate(dateString);
  const dayIndex = (date.getUTCDay() + 6) % 7;
  return WEEKDAY_LABELS[dayIndex];
}

function normalizeTimeBlock(timeBlock: string): CourseCalendarTimeBlock {
  return COURSE_CALENDAR_TIME_BLOCKS.includes(timeBlock as CourseCalendarTimeBlock)
    ? timeBlock as CourseCalendarTimeBlock
    : COURSE_CALENDAR_TIME_BLOCKS[0];
}

function buildJoinedCustomSchedules(customSchedules: CourseCalendarCustomScheduleRecord[]): JoinedCustomSchedule[] {
  return customSchedules.map((schedule) => {
    const timeBlock = normalizeTimeBlock(schedule.time_block);
    const startOffsetMinutes = typeof schedule.start_offset_minutes === 'number' ? schedule.start_offset_minutes : 0;
    const timeRange = buildCourseScheduleTimeRange(timeBlock, startOffsetMinutes);
    return {
      id: schedule.id,
      customItemId: schedule.custom_item_id,
      title: schedule.title,
      timeRange: schedule.time_range,
      note: schedule.note,
      date: schedule.date,
      timeBlock,
      startOffsetMinutes,
      startText: timeRange.startText,
      displayRange: timeRange.displayRange,
    };
  });
}

function getTeacherOptions(classes: CourseCalendarClassRecord[]): string[] {
  return Array.from(
    new Set(classes.map((courseClass) => courseClass.teacher_name?.trim()).filter(Boolean)),
  ) as string[];
}

function getClassOptions(classes: CourseCalendarClassRecord[]): CourseCalendarClassRecord[] {
  return [...classes].sort((a, b) => a.id - b.id);
}

function EmptyDropZone(): React.JSX.Element {
  return (
    <div className="rounded-2xl border border-dashed border-sky-100 bg-white/55 px-3 py-5 text-center text-xs font-medium text-slate-400 dark:border-white/10 dark:bg-white/5 dark:text-slate-500">
      拖动课程到此
    </div>
  );
}

interface ScheduleCardProps {
  schedule: JoinedCourseCalendarSchedule;
  onDeleteSchedule: (scheduleId: number) => void;
}

function ScheduleCard({ schedule, onDeleteSchedule }: ScheduleCardProps): React.JSX.Element {
  return (
    <div className="rounded-xl border border-sky-100 bg-white/92 px-2.5 py-2.5 shadow-[0_10px_30px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-800/90 dark:shadow-[0_16px_32px_rgba(2,6,23,0.28)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold leading-snug text-slate-900 dark:text-white">
            {schedule.className}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            {[schedule.grade, schedule.subject].filter(Boolean).join(' · ') || '未设置科目'}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-1">
          <div className="rounded-xl border border-cyan-100 bg-cyan-50 px-2 py-1 text-right text-cyan-700 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-200">
            <p className="text-[11px] font-black leading-none">{schedule.startText}</p>
            <p className="mt-1 text-[10px] font-semibold leading-none">{schedule.displayRange}</p>
          </div>
          <button
            type="button"
            onClick={() => onDeleteSchedule(schedule.id)}
            className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-sky-100 bg-sky-50 text-slate-500 transition hover:bg-rose-50 hover:text-rose-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
            aria-label="删除排课"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>{schedule.teacherName || '未分配教师'}</span>
        <span>{schedule.timeBlock}</span>
      </div>
    </div>
  );
}

interface CustomScheduleCardProps {
  schedule: JoinedCustomSchedule;
  onOpenNote: (schedule: JoinedCustomSchedule) => void;
  onDeleteSchedule: (scheduleId: number) => void;
}

function CustomScheduleCard({ schedule, onOpenNote, onDeleteSchedule }: CustomScheduleCardProps): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onOpenNote(schedule)}
      className="w-full rounded-xl border border-amber-100 bg-amber-50/70 px-2.5 py-2.5 text-left shadow-[0_10px_30px_rgba(245,158,11,0.08)] transition hover:bg-amber-50 dark:border-amber-400/20 dark:bg-amber-500/10 dark:shadow-[0_16px_32px_rgba(2,6,23,0.28)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold leading-snug text-slate-900 dark:text-white">
            {schedule.title}
          </p>
          <p className="mt-0.5 text-xs text-amber-700 dark:text-amber-200">{schedule.timeRange}</p>
        </div>
        <span className="rounded-xl border border-amber-200 bg-white/75 px-2 py-1 text-[10px] font-bold text-amber-700 dark:border-amber-400/20 dark:bg-white/10 dark:text-amber-200">
          事项
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>{schedule.displayRange}</span>
        <span
          role="button"
          tabIndex={0}
          onClick={(event) => {
            event.stopPropagation();
            onDeleteSchedule(schedule.id);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              event.stopPropagation();
              onDeleteSchedule(schedule.id);
            }
          }}
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-amber-100 bg-white text-slate-500 transition hover:bg-rose-50 hover:text-rose-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
          aria-label="删除事项排期"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </span>
      </div>
    </button>
  );
}

export function CourseCalendarPage({
  anchorDate,
  today,
  currentUserRole,
  classes,
  schedules,
  customItems,
  customSchedules,
  visibleDayCount,
  onVisibleDayCountChange,
  onPreviousPage,
  onNextPage,
  onScheduleClass,
  onScheduleCustomItem,
  onCreateCustomItem,
  onDeleteSchedule,
  onDeleteCustomSchedule,
}: CourseCalendarPageProps): React.JSX.Element {
  const normalizedVisibleDayCount = Math.max(1, Math.min(14, Math.trunc(visibleDayCount) || 6));
  const visibleDates = getCalendarPageDates(anchorDate, normalizedVisibleDayCount);
  const visibleDateSet = new Set(visibleDates);
  const joinedSchedules = joinClassesAndSchedules(classes, schedules);
  const visibleSchedules = joinedSchedules.filter((schedule) => visibleDateSet.has(schedule.date));
  const joinedCustomSchedules = buildJoinedCustomSchedules(customSchedules);
  const visibleCustomSchedules = joinedCustomSchedules.filter((schedule) => visibleDateSet.has(schedule.date));
  const teacherOptions = getTeacherOptions(classes);
  const subjectOptions = Array.from(new Set(classes.map((courseClass) => courseClass.subject?.trim()).filter(Boolean))) as string[];
  const [teacherFilter, setTeacherFilter] = React.useState('');
  const [subjectFilter, setSubjectFilter] = React.useState('');
  const canFilterCourses = currentUserRole !== 'member';
  const classOptions = getClassOptions(classes).filter((courseClass) => {
    if (canFilterCourses && teacherFilter && courseClass.teacher_name !== teacherFilter) {
      return false;
    }
    if (canFilterCourses && subjectFilter && courseClass.subject !== subjectFilter) {
      return false;
    }
    return true;
  });
  const [pendingDrop, setPendingDrop] = React.useState<PendingDrop | null>(null);
  const [selectedOffsetMinutes, setSelectedOffsetMinutes] = React.useState(0);
  const [customOffsetDirection, setCustomOffsetDirection] = React.useState<CustomOffsetDirection>('late');
  const [customOffsetMinutes, setCustomOffsetMinutes] = React.useState('');
  const [customTitle, setCustomTitle] = React.useState('');
  const [customTimeRange, setCustomTimeRange] = React.useState('');
  const [customNote, setCustomNote] = React.useState('');
  const [customVisibility, setCustomVisibility] = React.useState<'private' | 'organization'>('private');
  const [openedCustomSchedule, setOpenedCustomSchedule] = React.useState<JoinedCustomSchedule | null>(null);
  const pendingDropClass = pendingDrop?.itemType === 'class'
    ? classes.find((courseClass) => courseClass.id === pendingDrop.itemId)
    : undefined;
  const pendingDropCustomItem = pendingDrop?.itemType === 'custom'
    ? customItems.find((item) => item.id === pendingDrop.itemId)
    : undefined;
  const pendingTimeRange = pendingDrop
    ? buildCourseScheduleTimeRange(pendingDrop.timeBlock, selectedOffsetMinutes)
    : null;

  const dailyBuckets = visibleDates.map((date) => ({
    date,
    blocks: assignScheduleCardsToTimeBlocks(visibleSchedules.filter((schedule) => schedule.date === date)),
    customBlocks: COURSE_CALENDAR_TIME_BLOCKS.reduce((result, timeBlock) => {
      result[timeBlock] = visibleCustomSchedules.filter((schedule) => schedule.date === date && schedule.timeBlock === timeBlock);
      return result;
    }, {} as Record<CourseCalendarTimeBlock, JoinedCustomSchedule[]>),
  }));

  const handleClassDragStart = (event: React.DragEvent<HTMLDivElement>, classId: number) => {
    event.dataTransfer.setData('application/x-course-class-id', String(classId));
    event.dataTransfer.setData('text/plain', String(classId));
    event.dataTransfer.effectAllowed = 'copy';
  };

  const handleCustomItemDragStart = (event: React.DragEvent<HTMLDivElement>, customItemId: number) => {
    event.dataTransfer.setData('application/x-course-custom-item-id', String(customItemId));
    event.dataTransfer.setData('text/plain', String(customItemId));
    event.dataTransfer.effectAllowed = 'copy';
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>, date: string, timeBlock: CourseCalendarTimeBlock) => {
    event.preventDefault();
    const rawCustomItemId = event.dataTransfer.getData('application/x-course-custom-item-id');
    if (rawCustomItemId) {
      const customItemId = Number(rawCustomItemId);
      if (Number.isInteger(customItemId) && customItemId > 0) {
        setPendingDrop({ itemType: 'custom', itemId: customItemId, date, timeBlock });
        setSelectedOffsetMinutes(0);
        setCustomOffsetDirection('late');
        setCustomOffsetMinutes('');
      }
      return;
    }
    const rawClassId = event.dataTransfer.getData('application/x-course-class-id') || event.dataTransfer.getData('text/plain');
    const classId = Number(rawClassId);
    if (Number.isInteger(classId) && classId > 0) {
      setPendingDrop({ itemType: 'class', itemId: classId, date, timeBlock });
      setSelectedOffsetMinutes(0);
      setCustomOffsetDirection('late');
      setCustomOffsetMinutes('');
    }
  };

  const handleCustomOffsetChange = (direction: CustomOffsetDirection, rawMinutes: string) => {
    const numericMinutes = Math.max(0, Math.min(120, Math.trunc(Number(rawMinutes) || 0)));
    setCustomOffsetDirection(direction);
    setCustomOffsetMinutes(rawMinutes);
    setSelectedOffsetMinutes(direction === 'early' ? -numericMinutes : numericMinutes);
  };

  const handleConfirmAdjustedSchedule = () => {
    if (!pendingDrop) {
      return;
    }
    if (pendingDrop.itemType === 'class') {
      onScheduleClass(pendingDrop.itemId, pendingDrop.date, pendingDrop.timeBlock, selectedOffsetMinutes);
    } else {
      onScheduleCustomItem(pendingDrop.itemId, pendingDrop.date, pendingDrop.timeBlock, selectedOffsetMinutes);
    }
    setPendingDrop(null);
  };

  const handleCreateCustomItem = () => {
    const title = customTitle.trim();
    const timeRange = customTimeRange.trim();
    const note = customNote.trim();
    if (!title || !timeRange) {
      return;
    }
    onCreateCustomItem({ title, time_range: timeRange, note, visibility: customVisibility });
    setCustomTitle('');
    setCustomTimeRange('');
    setCustomNote('');
    setCustomVisibility('private');
  };

  return (
    <div className="min-h-full bg-[radial-gradient(circle_at_top_left,rgba(34,199,232,0.15),transparent_26%),radial-gradient(circle_at_90%_10%,rgba(47,128,237,0.14),transparent_24%),linear-gradient(180deg,#F7FBFF_0%,#EEF7FF_100%)] px-4 py-5 text-slate-900 md:px-6 md:py-6 dark:bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.12),transparent_24%),radial-gradient(circle_at_85%_15%,rgba(59,130,246,0.14),transparent_22%),linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className="mx-auto max-w-[1600px]">
        <div className="overflow-hidden rounded-[2rem] border border-sky-100/90 bg-white/82 shadow-[0_28px_90px_rgba(47,128,237,0.1)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-900/78 dark:shadow-[0_30px_80px_rgba(2,6,23,0.42)]">
          <div className="border-b border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(239,248,255,0.92)_100%)] px-5 py-5 md:px-7 md:py-6 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.82)_100%)]">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white px-3 py-1 text-[11px] font-bold uppercase tracking-[0.32em] text-sky-600 dark:border-sky-500/30 dark:bg-white/5 dark:text-sky-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  Starain
                </div>
                <div>
                  <h1 className="text-3xl font-black tracking-tight text-slate-900 md:text-4xl dark:text-white">
                    课程日历
                  </h1>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500 md:text-base dark:text-slate-300">
                    将绑定班级或自定义事项拖动到时间板块，快速完成当前页排课。
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-sky-200 bg-white px-2 py-2 shadow-sm dark:border-white/10 dark:bg-white/5">
                  <button
                    type="button"
                    onClick={() => onPreviousPage(normalizedVisibleDayCount)}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-sky-100 bg-sky-50 text-sky-700 transition hover:bg-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-sky-300 dark:hover:bg-white/10"
                    aria-label="查看上一页"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                  <div className="min-w-44 px-2 text-center">
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-500 dark:text-sky-300">
                      第 1 页
                    </p>
                    <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                      {getCalendarPageRangeLabel(anchorDate, normalizedVisibleDayCount)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onNextPage(normalizedVisibleDayCount)}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-sky-100 bg-sky-50 text-sky-700 transition hover:bg-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-sky-300 dark:hover:bg-white/10"
                    aria-label="查看下一页"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>

                <label className="relative">
                  <span className="pointer-events-none absolute left-4 top-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                    天数
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={14}
                    value={normalizedVisibleDayCount}
                    onChange={(event) => onVisibleDayCountChange(Math.max(1, Math.min(14, Math.trunc(Number(event.target.value) || 6))))}
                    className="h-14 w-28 rounded-2xl border border-sky-200 bg-white px-4 pt-5 text-sm font-medium text-slate-700 shadow-sm outline-none transition [color-scheme:light] focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark] dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                  />
                </label>

                {canFilterCourses && (
                  <div className="grid gap-3 sm:grid-cols-2">
                  <label className="relative">
                    <span className="pointer-events-none absolute left-4 top-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                      <Users className="h-3.5 w-3.5" />
                      老师
                    </span>
                    <select
                      value={teacherFilter}
                      onChange={(event) => setTeacherFilter(event.target.value)}
                      className="h-14 w-full appearance-none rounded-2xl border border-sky-200 bg-white px-4 pt-5 text-sm font-medium text-slate-700 shadow-sm outline-none transition [color-scheme:light] focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark] dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                    >
                      <option value="">全部老师</option>
                      {teacherOptions.map((teacherName) => (
                        <option key={teacherName} value={teacherName}>{teacherName}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-4 top-5 h-4 w-4 text-slate-400 dark:text-slate-500" />
                  </label>
                  <label className="relative">
                    <span className="pointer-events-none absolute left-4 top-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                      <Filter className="h-3.5 w-3.5" />
                      学科
                    </span>
                    <select
                      value={subjectFilter}
                      onChange={(event) => setSubjectFilter(event.target.value)}
                      className="h-14 w-full appearance-none rounded-2xl border border-sky-200 bg-white px-4 pt-5 text-sm font-medium text-slate-700 shadow-sm outline-none transition [color-scheme:light] focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark] dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                    >
                      <option value="">全部学科</option>
                      {subjectOptions.map((subject) => (
                        <option key={subject} value={subject}>{subject}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-4 top-5 h-4 w-4 text-slate-400 dark:text-slate-500" />
                  </label>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-5 px-4 py-5 md:px-5 xl:px-6 xl:py-6">
            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
              <div className="rounded-[1.75rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.95)_0%,rgba(239,248,255,0.9)_100%)] p-4 shadow-[0_18px_48px_rgba(47,128,237,0.05)] md:p-5 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(15,23,42,0.72)_100%)] dark:shadow-[0_20px_50px_rgba(2,6,23,0.35)]">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <CalendarDays className="h-5 w-5 text-sky-600 dark:text-sky-300" />
                    <span className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      周视图
                    </span>
                  </div>
                  <span className="rounded-full border border-cyan-100 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300">
                    {normalizedVisibleDayCount} 天 · 六段工作时间
                  </span>
                </div>

                <div className="hidden lg:block">
                  <div className="min-w-0">
                    <div
                      className="grid gap-2 pb-2"
                      style={{ gridTemplateColumns: `82px repeat(${normalizedVisibleDayCount}, minmax(0, 1fr))` }}
                    >
                      <div className="rounded-xl border border-sky-100 bg-white/90 px-3 py-3 text-xs font-bold text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                        时间板块
                      </div>
                      {visibleDates.map((date) => (
                        <div
                          key={date}
                          className={cn(
                            'rounded-xl border px-3 py-3 shadow-sm',
                            date === today
                              ? 'border-cyan-300 bg-cyan-50 shadow-[0_10px_28px_rgba(6,182,212,0.14)] dark:border-cyan-400/40 dark:bg-cyan-500/15'
                              : 'border-sky-100 bg-white/88 dark:border-white/10 dark:bg-white/5',
                          )}
                        >
                          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500 dark:text-sky-300">
                            {formatWeekdayLabel(date)}
                          </p>
                          <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">{formatDayLabel(date)}</p>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      {COURSE_CALENDAR_TIME_BLOCKS.map((timeBlock) => (
                        <div
                          key={timeBlock}
                          className="grid gap-2"
                          style={{ gridTemplateColumns: `82px repeat(${normalizedVisibleDayCount}, minmax(0, 1fr))` }}
                        >
                          <div className="rounded-xl border border-sky-100 bg-white/92 px-2.5 py-3 dark:border-white/10 dark:bg-white/5">
                            <p className="text-sm font-black leading-tight text-slate-900 dark:text-white">{timeBlock}</p>
                            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-slate-500">
                              block
                            </p>
                          </div>

                          {dailyBuckets.map(({ date, blocks, customBlocks }) => {
                            const blockCards = blocks[timeBlock];
                            const customBlockCards = customBlocks[timeBlock];
                            return (
                              <div
                                key={`${date}-${timeBlock}`}
                                data-calendar-slot={`${date}-${timeBlock}`}
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={(event) => handleDrop(event, date, timeBlock)}
                                className={cn(
                                  'min-h-[108px] rounded-xl border px-2 py-2 transition',
                                  date === today
                                    ? 'border-cyan-300 bg-cyan-50/70 dark:border-cyan-400/40 dark:bg-cyan-500/15'
                                    : 'border-sky-100 bg-white/92 dark:border-white/10 dark:bg-white/5',
                                )}
                              >
                                <div className="space-y-2">
                                  {blockCards.length + customBlockCards.length > 0 ? (
                                    <>
                                      {blockCards.map((schedule) => (
                                        <ScheduleCard
                                          key={schedule.id}
                                          schedule={schedule}
                                          onDeleteSchedule={onDeleteSchedule}
                                        />
                                      ))}
                                      {customBlockCards.map((schedule) => (
                                        <CustomScheduleCard
                                          key={`custom-${schedule.id}`}
                                          schedule={schedule}
                                          onOpenNote={setOpenedCustomSchedule}
                                          onDeleteSchedule={onDeleteCustomSchedule}
                                        />
                                      ))}
                                    </>
                                  ) : (
                                    <EmptyDropZone />
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-4 lg:hidden">
                  {dailyBuckets.map(({ date, blocks, customBlocks }) => (
                    <section
                      key={date}
                      className="rounded-2xl border border-sky-100 bg-white/88 p-3 dark:border-white/10 dark:bg-white/5"
                    >
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500 dark:text-sky-300">
                            {formatWeekdayLabel(date)}
                          </p>
                          <p className="mt-1 text-lg font-black text-slate-900 dark:text-white">{formatDayLabel(date)}</p>
                        </div>
                        <span className="rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-200">
                          6 个时段
                        </span>
                      </div>
                      <div className="space-y-2">
                        {COURSE_CALENDAR_TIME_BLOCKS.map((timeBlock) => {
                          const blockCards = blocks[timeBlock];
                          const customBlockCards = customBlocks[timeBlock];
                          return (
                            <div
                              key={`${date}-${timeBlock}`}
                              data-calendar-slot={`${date}-${timeBlock}`}
                              onDragOver={(event) => event.preventDefault()}
                              onDrop={(event) => handleDrop(event, date, timeBlock)}
                              className={cn(
                                'rounded-xl border px-3 py-3 transition',
                                date === today
                                  ? 'border-cyan-300 bg-cyan-50/70 dark:border-cyan-400/40 dark:bg-cyan-500/15'
                                  : 'border-sky-100 bg-white/92 dark:border-white/10 dark:bg-white/5',
                              )}
                            >
                              <div className="mb-2 flex items-center justify-between gap-2">
                                <p className="text-sm font-black text-slate-900 dark:text-white">{timeBlock}</p>
                                <p className="text-[11px] font-semibold text-slate-400 dark:text-slate-500">拖入排课</p>
                              </div>
                              <div className="space-y-2">
                                {blockCards.length + customBlockCards.length > 0 ? (
                                  <>
                                    {blockCards.map((schedule) => (
                                      <ScheduleCard
                                        key={schedule.id}
                                        schedule={schedule}
                                        onDeleteSchedule={onDeleteSchedule}
                                      />
                                    ))}
                                    {customBlockCards.map((schedule) => (
                                      <CustomScheduleCard
                                        key={`custom-${schedule.id}`}
                                        schedule={schedule}
                                        onOpenNote={setOpenedCustomSchedule}
                                        onDeleteSchedule={onDeleteCustomSchedule}
                                      />
                                    ))}
                                  </>
                                ) : (
                                  <EmptyDropZone />
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </section>
                  ))}
                </div>
              </div>
            </div>

            <aside className="space-y-5">
              <section className="rounded-[1.75rem] border border-sky-100 bg-white/92 p-4 shadow-[0_18px_48px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-white/5 dark:shadow-[0_20px_45px_rgba(2,6,23,0.32)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      课程卡片
                    </p>
                    <h2 className="mt-1 text-lg font-black text-slate-900 dark:text-white">拖拽排课</h2>
                  </div>
                  <GripVertical className="h-5 w-5 text-sky-500 dark:text-sky-300" />
                </div>
                <div className="mt-4 max-h-[46vh] space-y-3 overflow-y-auto pr-1">
                  {classOptions.length > 0 ? (
                    classOptions.map((courseClass) => (
                      <div
                        key={courseClass.id}
                        data-course-class-id={courseClass.id}
                        draggable
                        onDragStart={(event) => handleClassDragStart(event, courseClass.id)}
                        className="cursor-grab rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(240,248,255,0.88)_100%)] p-3 active:cursor-grabbing dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.82)_0%,rgba(30,41,59,0.55)_100%)]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-white">{courseClass.name}</p>
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                              {COURSE_CALENDAR_TIME_BLOCKS[0]}
                            </p>
                          </div>
                          <GripVertical className="h-4 w-4 shrink-0 text-sky-400 dark:text-sky-300" />
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-sky-100 bg-sky-50/50 p-5 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                      暂无可拖拽课程
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-[1.75rem] border border-amber-100 bg-white/92 p-4 shadow-[0_18px_48px_rgba(245,158,11,0.06)] dark:border-amber-400/20 dark:bg-white/5">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-amber-600 dark:text-amber-200">
                      自定义事项
                    </p>
                    <h2 className="mt-1 text-lg font-black text-slate-900 dark:text-white">自己生成卡片</h2>
                  </div>
                  <Plus className="h-5 w-5 text-amber-500 dark:text-amber-200" />
                </div>
                <div className="mt-4 space-y-3">
                  <input
                    value={customTitle}
                    onChange={(event) => setCustomTitle(event.target.value)}
                    placeholder="事项名称"
                    className="h-11 w-full rounded-xl border border-amber-100 bg-white px-3 text-sm text-slate-700 outline-none focus:border-amber-300 focus:ring-4 focus:ring-amber-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                  <input
                    value={customTimeRange}
                    onChange={(event) => setCustomTimeRange(event.target.value)}
                    placeholder="时间段"
                    className="h-11 w-full rounded-xl border border-amber-100 bg-white px-3 text-sm text-slate-700 outline-none focus:border-amber-300 focus:ring-4 focus:ring-amber-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                  <textarea
                    value={customNote}
                    onChange={(event) => setCustomNote(event.target.value)}
                    placeholder="备注"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-amber-100 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-amber-300 focus:ring-4 focus:ring-amber-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500"
                  />
                  {currentUserRole !== 'member' && (
                    <label className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-300">
                      <input
                        type="checkbox"
                        checked={customVisibility === 'organization'}
                        onChange={(event) => setCustomVisibility(event.target.checked ? 'organization' : 'private')}
                        className="h-4 w-4 rounded border-amber-200 text-amber-500 focus:ring-amber-200"
                      />
                      发布给本机构成员
                    </label>
                  )}
                  <button
                    type="button"
                    onClick={handleCreateCustomItem}
                    className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-amber-500 px-4 text-sm font-bold text-white transition hover:bg-amber-600"
                  >
                    <Plus className="h-4 w-4" />
                    生成事项卡片
                  </button>
                </div>

                <div className="mt-4 space-y-3">
                  {customItems.length > 0 ? (
                    customItems.map((item) => (
                      <div
                        key={item.id}
                        data-course-custom-item-id={item.id}
                        draggable
                        onDragStart={(event) => handleCustomItemDragStart(event, item.id)}
                        className="cursor-grab rounded-2xl border border-amber-100 bg-amber-50/70 p-3 active:cursor-grabbing dark:border-amber-400/20 dark:bg-amber-500/10"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-white">{item.title}</p>
                            <p className="mt-1 text-xs text-amber-700 dark:text-amber-200">{item.time_range}</p>
                          </div>
                          <span className="rounded-full bg-white/75 px-2.5 py-1 text-[10px] font-bold text-amber-700 dark:bg-white/10 dark:text-amber-200">
                            {item.visibility === 'organization' ? '已发布' : '私有'}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-amber-100 bg-amber-50/40 p-5 text-sm text-slate-500 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-slate-400">
                      暂无自定义事项
                    </div>
                  )}
                </div>
              </section>
            </aside>
          </div>
        </div>
      </div>
      {openedCustomSchedule && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-3xl border border-amber-100 bg-white p-5 shadow-[0_30px_90px_rgba(15,23,42,0.22)] dark:border-amber-400/20 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-600 dark:text-amber-200">事项备注</p>
                <h2 className="mt-1 text-xl font-black text-slate-900 dark:text-white">{openedCustomSchedule.title}</h2>
                <p className="mt-2 text-sm text-amber-700 dark:text-amber-200">{openedCustomSchedule.timeRange}</p>
              </div>
              <Clock className="h-6 w-6 shrink-0 text-amber-500 dark:text-amber-200" />
            </div>
            <div className="mt-5 rounded-2xl border border-amber-100 bg-amber-50/60 p-4 text-sm leading-6 text-slate-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-slate-200">
              {openedCustomSchedule.note || '暂无备注'}
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setOpenedCustomSchedule(null)}
                className="inline-flex h-11 items-center justify-center rounded-xl bg-amber-500 px-5 text-sm font-bold text-white transition hover:bg-amber-600"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
      {pendingDrop && pendingTimeRange && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-3xl border border-sky-100 bg-white p-5 shadow-[0_30px_90px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">微调启动时间</p>
                <h2 className="mt-1 text-xl font-black text-slate-900 dark:text-white">
                  {pendingDropClass?.name || pendingDropCustomItem?.title || '待排事项'}
                </h2>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                  基础时段 {pendingDrop.timeBlock}，当前实际时间 {pendingTimeRange.displayRange}
                </p>
              </div>
              <Clock className="h-6 w-6 shrink-0 text-sky-500 dark:text-sky-300" />
            </div>

            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              {TIME_ADJUSTMENT_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setSelectedOffsetMinutes(preset.minutes)}
                  className={cn(
                    'rounded-2xl border px-4 py-3 text-left text-sm font-semibold transition',
                    selectedOffsetMinutes === preset.minutes
                      ? 'border-sky-300 bg-sky-50 text-sky-700 ring-4 ring-sky-100 dark:border-sky-500/50 dark:bg-sky-500/15 dark:text-sky-200 dark:ring-sky-500/15'
                      : 'border-sky-100 bg-white text-slate-600 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <div className="mt-4 rounded-2xl border border-sky-100 bg-sky-50/60 p-4 dark:border-white/10 dark:bg-white/5">
              <p className="text-sm font-bold text-slate-900 dark:text-white">自定义微调</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-[128px_minmax(0,1fr)]">
                <select
                  value={customOffsetDirection}
                  onChange={(event) => handleCustomOffsetChange(event.target.value as CustomOffsetDirection, customOffsetMinutes)}
                  className="h-11 rounded-xl border border-sky-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                >
                  <option value="early">提前</option>
                  <option value="late">延后</option>
                </select>
                <input
                  type="number"
                  min={0}
                  max={120}
                  step={1}
                  value={customOffsetMinutes}
                  onChange={(event) => handleCustomOffsetChange(customOffsetDirection, event.target.value)}
                  placeholder="输入分钟数"
                  className="h-11 rounded-xl border border-sky-200 bg-white px-3 text-sm font-medium text-slate-700 outline-none focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:ring-sky-500/15"
                />
              </div>
            </div>

            <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setPendingDrop(null)}
                className="inline-flex h-11 items-center justify-center rounded-xl border border-sky-100 bg-white px-5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleConfirmAdjustedSchedule}
                className="inline-flex h-11 items-center justify-center rounded-xl bg-sky-600 px-5 text-sm font-bold text-white shadow-[0_12px_30px_rgba(14,165,233,0.22)] transition hover:bg-sky-700"
              >
                按 {pendingTimeRange.startText} 排课
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
