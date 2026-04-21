import React from 'react';
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  ChevronDown,
  Filter,
  GripVertical,
  Sparkles,
  Trash2,
  Users,
} from 'lucide-react';

import {
  COURSE_CALENDAR_TIME_BLOCKS,
  assignScheduleCardsToTimeBlocks,
  buildClassStatusRailData,
  getWeekDates,
  getVisibleWeekLabel,
  joinClassesAndSchedules,
  summarizeTeacherLoad,
  type CourseCalendarClassRecord,
  type CourseCalendarScheduleRecord,
  type CourseCalendarTimeBlock,
  type JoinedCourseCalendarSchedule,
} from './courseCalendarData';

export interface CourseCalendarPageProps {
  anchorDate: string;
  classes: CourseCalendarClassRecord[];
  schedules: CourseCalendarScheduleRecord[];
  onPreviousWeek: () => void;
  onNextWeek: () => void;
  onScheduleClass: (classId: number, date: string, timeBlock: CourseCalendarTimeBlock) => void;
  onDeleteSchedule: (scheduleId: number) => void;
}

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

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
      拖动班级到时间板块
    </div>
  );
}

interface ScheduleCardProps {
  schedule: JoinedCourseCalendarSchedule;
  onDeleteSchedule: (scheduleId: number) => void;
}

function ScheduleCard({ schedule, onDeleteSchedule }: ScheduleCardProps): React.JSX.Element {
  return (
    <div className="rounded-2xl border border-sky-100 bg-white/92 px-3 py-2.5 shadow-[0_10px_30px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-800/90 dark:shadow-[0_16px_32px_rgba(2,6,23,0.28)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900 dark:text-white">
            {schedule.className}
          </p>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            {[schedule.grade, schedule.subject].filter(Boolean).join(' · ') || '未设置科目'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDeleteSchedule(schedule.id)}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-sky-100 bg-sky-50 text-slate-500 transition hover:bg-rose-50 hover:text-rose-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-rose-500/10 dark:hover:text-rose-300"
          aria-label="删除排课"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
        <span>{schedule.teacherName || '未分配教师'}</span>
        <span>{schedule.timeBlock}</span>
      </div>
    </div>
  );
}

export function CourseCalendarPage({
  anchorDate,
  classes,
  schedules,
  onPreviousWeek,
  onNextWeek,
  onScheduleClass,
  onDeleteSchedule,
}: CourseCalendarPageProps): React.JSX.Element {
  const weekDates = getWeekDates(anchorDate);
  const weekDateSet = new Set(weekDates);
  const joinedSchedules = joinClassesAndSchedules(classes, schedules);
  const weekSchedules = joinedSchedules.filter((schedule) => weekDateSet.has(schedule.date));
  const teacherLoad = summarizeTeacherLoad(weekSchedules);
  const classStatus = buildClassStatusRailData(classes, schedules);
  const teacherOptions = getTeacherOptions(classes);
  const classOptions = getClassOptions(classes);

  const dailyBuckets = weekDates.map((date) => ({
    date,
    blocks: assignScheduleCardsToTimeBlocks(weekSchedules.filter((schedule) => schedule.date === date)),
  }));

  const handleDragStart = (event: React.DragEvent<HTMLDivElement>, classId: number) => {
    event.dataTransfer.setData('application/x-course-class-id', String(classId));
    event.dataTransfer.setData('text/plain', String(classId));
    event.dataTransfer.effectAllowed = 'copy';
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>, date: string, timeBlock: CourseCalendarTimeBlock) => {
    event.preventDefault();
    const rawClassId = event.dataTransfer.getData('application/x-course-class-id') || event.dataTransfer.getData('text/plain');
    const classId = Number(rawClassId);
    if (!Number.isInteger(classId) || classId <= 0) {
      return;
    }
    onScheduleClass(classId, date, timeBlock);
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
                    将被分配的班级拖动到六个工作时间板块，快速完成本周排课。
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <div className="inline-flex items-center gap-2 rounded-2xl border border-sky-200 bg-white px-2 py-2 shadow-sm dark:border-white/10 dark:bg-white/5">
                  <button
                    type="button"
                    onClick={onPreviousWeek}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-sky-100 bg-sky-50 text-sky-700 transition hover:bg-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-sky-300 dark:hover:bg-white/10"
                    aria-label="查看上周"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                  <div className="min-w-44 px-2 text-center">
                    <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-500 dark:text-sky-300">
                      本周
                    </p>
                    <p className="mt-1 text-sm font-bold text-slate-900 dark:text-white">
                      {getVisibleWeekLabel(anchorDate)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={onNextWeek}
                    className="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-sky-100 bg-sky-50 text-sky-700 transition hover:bg-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-sky-300 dark:hover:bg-white/10"
                    aria-label="查看下周"
                  >
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="relative">
                    <span className="pointer-events-none absolute left-4 top-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                      <Users className="h-3.5 w-3.5" />
                      老师
                    </span>
                    <select className="h-14 w-full appearance-none rounded-2xl border border-sky-200 bg-white px-4 pt-5 text-sm font-medium text-slate-700 shadow-sm outline-none transition [color-scheme:light] focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark] dark:focus:border-sky-500 dark:focus:ring-sky-500/15">
                      <option>全部老师</option>
                      {teacherOptions.map((teacherName) => (
                        <option key={teacherName}>{teacherName}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-4 top-5 h-4 w-4 text-slate-400 dark:text-slate-500" />
                  </label>
                  <label className="relative">
                    <span className="pointer-events-none absolute left-4 top-3 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">
                      <Filter className="h-3.5 w-3.5" />
                      班级
                    </span>
                    <select className="h-14 w-full appearance-none rounded-2xl border border-sky-200 bg-white px-4 pt-5 text-sm font-medium text-slate-700 shadow-sm outline-none transition [color-scheme:light] focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:[color-scheme:dark] dark:focus:border-sky-500 dark:focus:ring-sky-500/15">
                      <option>全部班级</option>
                      {classOptions.map((courseClass) => (
                        <option key={courseClass.id}>{courseClass.name}</option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-4 top-5 h-4 w-4 text-slate-400 dark:text-slate-500" />
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-5 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_360px] xl:px-6 xl:py-6">
            <div className="space-y-5">
              <div className="rounded-[1.75rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.95)_0%,rgba(239,248,255,0.9)_100%)] p-4 shadow-[0_18px_48px_rgba(47,128,237,0.05)] md:p-5 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(15,23,42,0.72)_100%)] dark:shadow-[0_20px_50px_rgba(2,6,23,0.35)]">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <CalendarDays className="h-5 w-5 text-sky-600 dark:text-sky-300" />
                    <span className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      周视图
                    </span>
                  </div>
                  <span className="rounded-full border border-cyan-100 bg-cyan-50 px-3 py-1 text-xs font-semibold text-cyan-700 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-300">
                    六段工作时间
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <div className="min-w-[1180px]">
                    <div className="grid grid-cols-[128px_repeat(7,minmax(132px,1fr))] gap-3 pb-3">
                      <div className="rounded-2xl border border-sky-100 bg-white/90 px-4 py-4 text-sm font-bold text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                        时间板块
                      </div>
                      {weekDates.map((date, index) => (
                        <div
                          key={date}
                          className={cn(
                            'rounded-2xl border px-4 py-4 shadow-sm',
                            index === 0
                              ? 'border-sky-200 bg-sky-50/80 dark:border-sky-500/30 dark:bg-sky-500/10'
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

                    <div className="space-y-3">
                      {COURSE_CALENDAR_TIME_BLOCKS.map((timeBlock) => (
                        <div
                          key={timeBlock}
                          className="grid grid-cols-[128px_repeat(7,minmax(132px,1fr))] gap-3"
                        >
                          <div className="rounded-3xl border border-sky-100 bg-white/92 px-4 py-5 dark:border-white/10 dark:bg-white/5">
                            <p className="text-base font-black text-slate-900 dark:text-white">{timeBlock}</p>
                            <p className="mt-1 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500">
                              time block
                            </p>
                          </div>

                          {dailyBuckets.map(({ date, blocks }) => {
                            const blockCards = blocks[timeBlock];
                            return (
                              <div
                                key={`${date}-${timeBlock}`}
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={(event) => handleDrop(event, date, timeBlock)}
                                className={cn(
                                  'min-h-[132px] rounded-3xl border px-3 py-3 transition',
                                  date === anchorDate
                                    ? 'border-sky-200 bg-sky-50/60 dark:border-sky-500/30 dark:bg-sky-500/10'
                                    : 'border-sky-100 bg-white/92 dark:border-white/10 dark:bg-white/5',
                                )}
                              >
                                <div className="space-y-2">
                                  {blockCards.length > 0 ? (
                                    blockCards.map((schedule) => (
                                      <React.Fragment key={schedule.id}>
                                        <ScheduleCard
                                          schedule={schedule}
                                          onDeleteSchedule={onDeleteSchedule}
                                        />
                                      </React.Fragment>
                                    ))
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
              </div>
            </div>

            <aside className="space-y-5">
              <section className="rounded-[1.75rem] border border-sky-100 bg-white/92 p-5 shadow-[0_18px_48px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-white/5 dark:shadow-[0_20px_45px_rgba(2,6,23,0.32)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      可排班级
                    </p>
                    <h2 className="mt-1 text-xl font-black text-slate-900 dark:text-white">可排班级</h2>
                  </div>
                  <GripVertical className="h-5 w-5 text-sky-500 dark:text-sky-300" />
                </div>
                <div className="mt-4 space-y-3">
                  {classOptions.length > 0 ? (
                    classOptions.map((courseClass) => (
                      <div
                        key={courseClass.id}
                        draggable
                        onDragStart={(event) => handleDragStart(event, courseClass.id)}
                        className="cursor-grab rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(240,248,255,0.88)_100%)] p-4 active:cursor-grabbing dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.82)_0%,rgba(30,41,59,0.55)_100%)]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-white">{courseClass.name}</p>
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                              {[courseClass.grade, courseClass.subject].filter(Boolean).join(' · ') || '未设置科目'}
                            </p>
                          </div>
                          <GripVertical className="h-4 w-4 shrink-0 text-sky-400 dark:text-sky-300" />
                        </div>
                        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
                          {courseClass.teacher_name || '未分配教师'}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-sky-100 bg-sky-50/50 p-5 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                      暂无可排班级
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-[1.75rem] border border-sky-100 bg-white/92 p-5 shadow-[0_18px_48px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-white/5 dark:shadow-[0_20px_45px_rgba(2,6,23,0.32)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      本周老师负载
                    </p>
                    <h2 className="mt-1 text-xl font-black text-slate-900 dark:text-white">本周老师负载</h2>
                  </div>
                  <Users className="h-5 w-5 text-sky-500 dark:text-sky-300" />
                </div>
                <div className="mt-4 space-y-3">
                  {teacherLoad.length > 0 ? (
                    teacherLoad.map((item) => (
                      <div
                        key={item.teacherName}
                        className="rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(240,248,255,0.88)_100%)] p-4 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.82)_0%,rgba(30,41,59,0.55)_100%)]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-white">{item.teacherName}</p>
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{item.label}</p>
                          </div>
                          <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-bold text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                            {item.count}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                          <span className="rounded-full border border-sky-100 bg-white px-2 py-1 dark:border-white/10 dark:bg-white/5">
                            班级 {item.classCount}
                          </span>
                          <span className="rounded-full border border-sky-100 bg-white px-2 py-1 dark:border-white/10 dark:bg-white/5">
                            排课 {item.scheduleCount}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-sky-100 bg-sky-50/50 p-5 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                      本周暂无老师负载数据
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-[1.75rem] border border-sky-100 bg-white/92 p-5 shadow-[0_18px_48px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-white/5 dark:shadow-[0_20px_45px_rgba(2,6,23,0.32)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-500 dark:text-sky-300">
                      班级状态
                    </p>
                    <h2 className="mt-1 text-xl font-black text-slate-900 dark:text-white">班级状态</h2>
                  </div>
                  <CalendarDays className="h-5 w-5 text-sky-500 dark:text-sky-300" />
                </div>
                <div className="mt-4 space-y-3">
                  {classStatus.length > 0 ? (
                    classStatus.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(239,248,255,0.9)_100%)] p-4 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.82)_0%,rgba(30,41,59,0.55)_100%)]"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold text-slate-900 dark:text-white">{item.name}</p>
                            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                              {[item.grade, item.subject].filter(Boolean).join(' · ') || '未设置科目'}
                            </p>
                          </div>
                          <span
                            className={cn(
                              'rounded-full px-2.5 py-1 text-xs font-bold',
                              item.statusLabel === '已排课'
                                ? 'bg-cyan-50 text-cyan-700 dark:bg-cyan-500/15 dark:text-cyan-300'
                                : 'bg-slate-100 text-slate-600 dark:bg-white/10 dark:text-slate-300',
                            )}
                          >
                            {item.statusLabel}
                          </span>
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
                          <span>{item.teacherName || '未分配教师'}</span>
                          <span>排课 {item.scheduleCount}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-sky-100 bg-sky-50/50 p-5 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                      暂无班级状态
                    </div>
                  )}
                </div>
              </section>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
