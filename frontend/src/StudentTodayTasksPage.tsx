import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, BookOpenCheck, CalendarDays, Download, FileText, Loader2, UserRound } from 'lucide-react';

export type StudentReviewTask = {
  lesson_id: number;
  lesson_date: string;
  lesson_subject: string;
  lesson_topic: string;
  class_id?: number | null;
  class_name: string;
  review_label: string;
  estimated_time: string;
  steps: string[];
  pdf_url: string;
  pdf_download_url: string;
  pdf_filename: string;
  pdf_available: boolean;
  pdf_page: number | null;
  pdf_page_estimated: boolean;
};

export type StudentReviewTaskStudent = {
  id: number;
  name: string;
  organization_id?: number;
  class_names: string[];
  class_count?: number;
};

type ApiFetch = <T = unknown>(path: string, options?: RequestInit) => Promise<T>;
type BuildAuthedPath = (path: string) => string;

type StudentReviewTasksResponse = {
  date: string;
  student: StudentReviewTaskStudent;
  tasks: StudentReviewTask[];
};

type StudentReviewTaskStudentsResponse = {
  items: StudentReviewTaskStudent[];
};

type StudentTodayTasksPageProps = {
  today: string;
  apiFetch: ApiFetch;
  buildAuthedPath: BuildAuthedPath;
};

type StudentTodayTasksContentProps = {
  today: string;
  selectedStudentName: string;
  students: StudentReviewTaskStudent[];
  selectedStudentId: number | null;
  loading: boolean;
  taskLoading: boolean;
  error: string;
  tasks: StudentReviewTask[];
  activeTask: StudentReviewTask | null;
  onStudentChange: (studentId: number) => void;
  onTaskSelect: (task: StudentReviewTask) => void;
  buildAuthedPath: BuildAuthedPath;
};

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

export function buildStudentTaskPdfPreviewPath(task: StudentReviewTask, buildAuthedPath: BuildAuthedPath): string {
  const authedPath = buildAuthedPath(task.pdf_url);
  if (!task.pdf_page) {
    return authedPath;
  }
  const [pathWithoutFragment] = authedPath.split('#');
  return `${pathWithoutFragment}#page=${task.pdf_page}`;
}

function summarizeClasses(student: StudentReviewTaskStudent | undefined): string {
  if (!student?.class_names?.length) {
    return '未绑定班级';
  }
  return student.class_names.join(' / ');
}

export function StudentTodayTasksContent({
  today,
  selectedStudentName,
  students,
  selectedStudentId,
  loading,
  taskLoading,
  error,
  tasks,
  activeTask,
  onStudentChange,
  onTaskSelect,
  buildAuthedPath,
}: StudentTodayTasksContentProps) {
  const selectedStudent = students.find((student) => student.id === selectedStudentId);
  const previewPath = activeTask && activeTask.pdf_available
    ? buildStudentTaskPdfPreviewPath(activeTask, buildAuthedPath)
    : '';
  const downloadPath = activeTask?.pdf_download_url ? buildAuthedPath(activeTask.pdf_download_url) : '';

  return (
    <div className="px-6 py-6 md:px-8 md:py-8 xl:px-10 xl:py-10">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="overflow-hidden rounded-[1.75rem] border border-sky-100/90 bg-[linear-gradient(135deg,rgba(255,255,255,0.98)_0%,rgba(236,248,255,0.96)_46%,rgba(220,246,255,0.9)_100%)] p-6 shadow-[0_22px_54px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[linear-gradient(135deg,rgba(15,23,42,0.98)_0%,rgba(12,30,48,0.94)_54%,rgba(8,47,73,0.9)_100%)] dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)] md:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 shadow-sm dark:border-white/10 dark:bg-white/8 dark:text-sky-200">
                <CalendarDays size={14} />
                {today}
              </div>
              <div>
                <p className="text-sm font-semibold text-sky-600 dark:text-sky-300">学生端</p>
                <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white md:text-4xl">今日复习</h2>
              </div>
              <p className="max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-300">
                {selectedStudentName ? `${selectedStudentName} 今天需要完成 ${tasks.length} 项复习任务` : '选择学生后查看今日复习任务'}
              </p>
            </div>

            <div className="grid gap-3 sm:min-w-[24rem] sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
              <label className="block">
                <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">学生</span>
                <select
                  className="h-12 w-full rounded-2xl border border-sky-200 bg-white/92 px-4 text-sm font-semibold text-slate-800 shadow-sm outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950/80 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                  value={selectedStudentId ?? ''}
                  onChange={(event) => onStudentChange(Number(event.target.value))}
                  disabled={loading || students.length === 0}
                  aria-label="选择学生"
                >
                  {students.length === 0 ? (
                    <option value="">暂无学生</option>
                  ) : (
                    students.map((student) => (
                      <option key={student.id} value={student.id}>
                        {student.name}
                      </option>
                    ))
                  )}
                </select>
              </label>
              <div className="rounded-2xl border border-sky-100 bg-white/75 px-4 py-3 text-sm shadow-sm dark:border-white/10 dark:bg-white/8">
                <p className="text-xs font-semibold text-slate-400 dark:text-slate-400">班级</p>
                <p className="mt-1 max-w-[16rem] truncate font-semibold text-slate-800 dark:text-slate-100">{summarizeClasses(selectedStudent)}</p>
              </div>
            </div>
          </div>
        </section>

        {error && (
          <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-200">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <section className="grid min-h-[34rem] gap-5 xl:grid-cols-[minmax(320px,0.82fr)_minmax(0,1.18fr)]">
          <div className="rounded-[1.75rem] border border-sky-100/90 bg-white/88 p-4 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-950/78 dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)]">
            <div className="flex items-center justify-between gap-3 px-2 py-2">
              <div>
                <p className="text-lg font-bold text-slate-900 dark:text-slate-100">今日任务</p>
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{tasks.length} 项</p>
              </div>
              {taskLoading && <Loader2 size={18} className="animate-spin text-sky-500" />}
            </div>

            <div className="mt-3 space-y-3">
              {loading || taskLoading ? (
                <div className="flex min-h-64 items-center justify-center rounded-3xl border border-dashed border-sky-200 bg-sky-50/50 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                  正在加载今日任务
                </div>
              ) : tasks.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center rounded-3xl border border-dashed border-sky-200 bg-sky-50/50 px-6 text-center dark:border-white/10 dark:bg-white/5">
                  <BookOpenCheck size={34} className="text-sky-500" />
                  <p className="mt-4 text-base font-semibold text-slate-800 dark:text-slate-100">今天暂无复习任务</p>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">系统只展示今天需要完成的内容</p>
                </div>
              ) : (
                tasks.map((task) => {
                  const active = activeTask?.lesson_id === task.lesson_id;
                  return (
                    <button
                      key={`${task.lesson_id}-${task.review_label}`}
                      type="button"
                      onClick={() => onTaskSelect(task)}
                      className={cx(
                        'w-full rounded-3xl border p-4 text-left transition',
                        active
                          ? 'border-sky-300 bg-sky-50 shadow-[0_16px_34px_rgba(14,165,233,0.14)] dark:border-sky-400/40 dark:bg-sky-500/10'
                          : 'border-sky-100 bg-white hover:border-sky-200 hover:bg-sky-50/70 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/8',
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-base font-bold text-slate-900 dark:text-slate-100">{task.lesson_topic || '未命名课程'}</p>
                          <p className="mt-1 truncate text-xs font-medium text-slate-500 dark:text-slate-400">{task.class_name} / {task.lesson_subject}</p>
                        </div>
                        <span className="shrink-0 rounded-full bg-white px-3 py-1 text-xs font-semibold text-sky-700 shadow-sm dark:bg-white/10 dark:text-sky-200">
                          {task.estimated_time || '今日'}
                        </span>
                      </div>
                      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400">
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 dark:bg-white/8">
                          <FileText size={13} />
                          {task.pdf_page ? `PDF 第 ${task.pdf_page} 页${task.pdf_page_estimated ? ' 估算' : ''}` : 'PDF'}
                        </span>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 dark:bg-white/8">{task.review_label}</span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-sky-100/90 bg-white/88 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-950/78 dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)]">
            {activeTask ? (
              <div className="flex h-full min-h-[34rem] flex-col">
                <div className="flex flex-col gap-4 border-b border-sky-100 px-5 py-4 dark:border-white/10 md:flex-row md:items-center md:justify-between">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-sky-600 dark:text-sky-300">{activeTask.review_label}</p>
                    <h3 className="mt-1 truncate text-xl font-bold text-slate-900 dark:text-slate-100">{activeTask.lesson_topic || '今日复习资料'}</h3>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      {activeTask.pdf_page ? `PDF 第 ${activeTask.pdf_page} 页${activeTask.pdf_page_estimated ? ' 估算' : ''}` : activeTask.pdf_filename || 'PDF 资料'}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {downloadPath && (
                      <a
                        href={downloadPath}
                        className="inline-flex items-center justify-center gap-2 rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10"
                      >
                        <Download size={16} />
                        下载
                      </a>
                    )}
                  </div>
                </div>

                <div className="grid flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_20rem]">
                  <div className="min-h-[28rem] bg-slate-100 dark:bg-slate-900/70">
                    {previewPath ? (
                      <iframe title={`${activeTask.lesson_topic} PDF`} src={previewPath} className="h-full min-h-[28rem] w-full border-0" />
                    ) : (
                      <div className="flex h-full min-h-[28rem] flex-col items-center justify-center px-6 text-center">
                        <FileText size={38} className="text-slate-400" />
                        <p className="mt-4 text-base font-semibold text-slate-800 dark:text-slate-100">PDF 资料待同步</p>
                        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{activeTask.pdf_filename || '生成完成后这里会显示预览'}</p>
                      </div>
                    )}
                  </div>

                  <aside className="border-t border-sky-100 p-5 dark:border-white/10 lg:border-l lg:border-t-0">
                    <div className="flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
                      <BookOpenCheck size={17} className="text-sky-500" />
                      完成清单
                    </div>
                    <ol className="mt-4 space-y-3">
                      {activeTask.steps.map((step, index) => (
                        <li key={`${activeTask.lesson_id}-${index}`} className="flex gap-3 rounded-2xl bg-sky-50/70 p-3 text-sm leading-relaxed text-slate-600 dark:bg-white/5 dark:text-slate-300">
                          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-600 text-xs font-bold text-white">{index + 1}</span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                  </aside>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[34rem] flex-col items-center justify-center px-8 text-center">
                <UserRound size={38} className="text-sky-500" />
                <p className="mt-4 text-lg font-bold text-slate-900 dark:text-slate-100">选择学生查看今日任务</p>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">今日任务会自动显示对应 PDF 页面</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export function StudentTodayTasksPage({ today, apiFetch, buildAuthedPath }: StudentTodayTasksPageProps) {
  const [students, setStudents] = useState<StudentReviewTaskStudent[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [selectedStudentName, setSelectedStudentName] = useState('');
  const [tasks, setTasks] = useState<StudentReviewTask[]>([]);
  const [activeLessonId, setActiveLessonId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [taskLoading, setTaskLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    apiFetch<StudentReviewTaskStudentsResponse>('/api/student-review-tasks/students')
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const items = Array.isArray(payload.items) ? payload.items : [];
        setStudents(items);
        setSelectedStudentId((current) => current ?? items[0]?.id ?? null);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : '学生列表加载失败');
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch]);

  useEffect(() => {
    if (!selectedStudentId) {
      setTasks([]);
      setSelectedStudentName('');
      setActiveLessonId(null);
      return;
    }

    let cancelled = false;
    setTaskLoading(true);
    setError('');
    apiFetch<StudentReviewTasksResponse>(`/api/student-review-tasks?student_id=${selectedStudentId}&date=${encodeURIComponent(today)}`)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const nextTasks = Array.isArray(payload.tasks) ? payload.tasks : [];
        setTasks(nextTasks);
        setSelectedStudentName(payload.student?.name || students.find((student) => student.id === selectedStudentId)?.name || '');
        setActiveLessonId(nextTasks[0]?.lesson_id ?? null);
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setTasks([]);
        setActiveLessonId(null);
        setError(err instanceof Error ? err.message : '今日任务加载失败');
      })
      .finally(() => {
        if (!cancelled) {
          setTaskLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiFetch, selectedStudentId, students, today]);

  const activeTask = useMemo(
    () => tasks.find((task) => task.lesson_id === activeLessonId) ?? tasks[0] ?? null,
    [activeLessonId, tasks],
  );

  return (
    <StudentTodayTasksContent
      today={today}
      selectedStudentName={selectedStudentName}
      students={students}
      selectedStudentId={selectedStudentId}
      loading={loading}
      taskLoading={taskLoading}
      error={error}
      tasks={tasks}
      activeTask={activeTask}
      onStudentChange={(studentId) => setSelectedStudentId(studentId || null)}
      onTaskSelect={(task) => setActiveLessonId(task.lesson_id)}
      buildAuthedPath={buildAuthedPath}
    />
  );
}
