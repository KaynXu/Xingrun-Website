import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpenCheck,
  CalendarDays,
  ChevronRight,
  Clock3,
  Download,
  ExternalLink,
  FileText,
  KeyRound,
  Loader2,
  LogOut,
  RefreshCw,
  UserRound,
  Users,
} from 'lucide-react';

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

type StudentAccount = {
  id: number;
  username: string;
  organization_id: number;
  organization_name?: string;
  student: StudentReviewTaskStudent;
  created_at?: string;
  last_login?: string | null;
};

type StudentClassInvitePreview = {
  class: {
    id: number;
    name: string;
    subject: string;
    grade: string;
    organization_id: number;
  };
  students: Array<{
    id: number;
    name: string;
    organization_id?: number;
  }>;
};

type StudentAuthResponse = {
  token: string;
  account: StudentAccount;
};

type StudentReviewTasksResponse = {
  date: string;
  student: StudentReviewTaskStudent;
  tasks: StudentReviewTask[];
};

type BuildAuthedPath = (path: string) => string;

type StudentTodayTasksContentProps = {
  today: string;
  student: StudentReviewTaskStudent | null;
  loading: boolean;
  taskLoading: boolean;
  error: string;
  tasks: StudentReviewTask[];
  activeTask: StudentReviewTask | null;
  onTaskSelect: (task: StudentReviewTask) => void;
  buildAuthedPath: BuildAuthedPath;
  onLogout?: () => void;
};

const STUDENT_TOKEN_KEY = 'xr_student_token';

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function getStoredStudentToken(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return window.localStorage.getItem(STUDENT_TOKEN_KEY) || '';
}

function saveStoredStudentToken(token: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  if (token) {
    window.localStorage.setItem(STUDENT_TOKEN_KEY, token);
  } else {
    window.localStorage.removeItem(STUDENT_TOKEN_KEY);
  }
}

async function studentApiFetch<T>(path: string, token = '', options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('X-Student-Auth-Token', token);
  }
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = typeof data?.error === 'string' && data.error ? data.error : `请求失败: ${response.status}`;
    throw new Error(message);
  }
  return data as T;
}

export function buildStudentTaskPdfPreviewPath(task: StudentReviewTask, buildAuthedPath: BuildAuthedPath): string {
  const authedPath = buildAuthedPath(task.pdf_url);
  if (!task.pdf_page) {
    return authedPath;
  }
  const [pathWithoutFragment] = authedPath.split('#');
  return `${pathWithoutFragment}#page=${task.pdf_page}`;
}

function buildStudentAuthedPath(path: string, token: string): string {
  if (!token) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}token=${encodeURIComponent(token)}`;
}

function getClassSummary(student: StudentReviewTaskStudent | null): string {
  if (!student?.class_names?.length) {
    return '未绑定班级';
  }
  return student.class_names.slice(0, 2).join(' / ');
}

function getTaskStepText(task: StudentReviewTask): string {
  return task.steps.find((step) => step.trim()) || task.review_label || '按老师安排完成今天的复习';
}

function StudentBrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cx('flex items-center gap-3 rounded-2xl border border-sky-100 bg-white/85 px-3 py-2 shadow-sm', compact && 'gap-2 px-2.5 py-2')}>
      <img src="/logo.png" alt="Starain logo" className={cx('shrink-0 object-contain', compact ? 'h-9 w-9' : 'h-10 w-10')} />
      <div className={cx('min-w-0', compact && 'hidden sm:block')}>
        <p className="truncate text-sm font-bold leading-5 text-slate-950">Starain</p>
        <p className="truncate text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-sky-600">学生复习</p>
      </div>
    </div>
  );
}

export function StudentTodayTasksContent({
  today,
  student,
  loading,
  taskLoading,
  error,
  tasks,
  activeTask,
  onTaskSelect,
  buildAuthedPath,
  onLogout,
}: StudentTodayTasksContentProps) {
  const previewPath = activeTask && activeTask.pdf_available
    ? buildStudentTaskPdfPreviewPath(activeTask, buildAuthedPath)
    : '';
  const studentName = student?.name || '同学';
  const classSummary = getClassSummary(student);
  const taskCount = tasks.length;
  const activeTaskIndex = activeTask ? tasks.findIndex((task) => task.lesson_id === activeTask.lesson_id) : -1;
  const taskPosition = activeTaskIndex >= 0 ? activeTaskIndex + 1 : taskCount ? 1 : 0;
  const progressPercent = taskCount ? Math.max(8, (taskPosition / taskCount) * 100) : 0;
  const activeTaskStep = activeTask ? getTaskStepText(activeTask) : '';
  const activeDownloadPath = activeTask ? buildAuthedPath(activeTask.pdf_download_url || activeTask.pdf_url) : '';
  const activeOpenPath = activeTask ? buildAuthedPath(activeTask.pdf_url) : '';

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6fbff_0%,#eef7ff_54%,#f8fbff_100%)] text-slate-950">
      <div className="mx-auto flex max-w-[92rem] flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-sky-100/80 pb-5 sm:flex-row sm:items-center">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
              <UserRound size={23} />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-bold text-slate-950 sm:text-3xl">你好, {studentName}</h1>
              <p className="mt-1 text-sm font-medium text-slate-500">今日复习安排</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 sm:ml-auto sm:justify-end">
            <div className="inline-flex h-11 items-center gap-2 rounded-2xl border border-sky-100 bg-white/80 px-3 text-sm font-semibold text-slate-600 shadow-sm">
              <CalendarDays size={17} className="text-slate-500" />
              <span>{today}</span>
            </div>
            {onLogout && (
              <button
                type="button"
                onClick={onLogout}
                title="退出登录"
                className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-sky-100 bg-white/80 text-slate-500 shadow-sm transition hover:border-sky-200 hover:text-sky-700"
              >
                <LogOut size={18} />
              </button>
            )}
            <StudentBrandMark compact />
          </div>
        </header>

        {error && (
          <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <section className="rounded-xl border border-sky-100 bg-white/90 p-5 shadow-sm">
          <div className="grid gap-5 md:grid-cols-[14rem_minmax(0,1fr)] md:items-center">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-600">
                <BookOpenCheck size={23} />
              </div>
              <div>
                <p className="text-xl font-bold text-slate-950">今日复习</p>
                <p className="mt-1 text-sm font-medium text-slate-500">{classSummary}</p>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-500">
                <span>{taskCount ? `今天要完成 ${taskCount} 个任务` : '今天没有任务'}</span>
                <span>{taskCount ? `任务 ${taskPosition}/${taskCount}` : '任务 0/0'}</span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          </div>
        </section>

        <section className="grid min-h-[40rem] gap-5 xl:grid-cols-[minmax(22rem,34rem)_minmax(0,1fr)]">
          <aside className="flex min-h-[40rem] flex-col rounded-xl border border-sky-100 bg-white/95 p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3 px-1">
              <div className="flex items-center gap-2">
                <CalendarDays size={21} className="text-sky-600" />
                <p className="text-xl font-bold text-slate-950">今天要做</p>
              </div>
              {taskLoading && <Loader2 size={18} className="animate-spin text-sky-500" />}
            </div>

            <div className="mt-5 flex-1 space-y-4">
              {loading || taskLoading ? (
                <div className="flex min-h-64 items-center justify-center rounded-2xl border border-dashed border-sky-200 bg-sky-50/60 text-sm font-semibold text-slate-500">
                  <Loader2 size={18} className="mr-2 animate-spin text-sky-500" />
                  正在加载今日任务
                </div>
              ) : tasks.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-dashed border-sky-200 bg-sky-50/60 px-6 text-center">
                  <BookOpenCheck size={34} className="text-emerald-500" />
                  <p className="mt-4 text-base font-semibold text-slate-800">今天暂无复习任务</p>
                  <p className="mt-2 text-sm text-slate-500">可以先整理错题和课堂笔记</p>
                </div>
              ) : (
                tasks.map((task, index) => {
                  const active = activeTask?.lesson_id === task.lesson_id;
                  const stepText = getTaskStepText(task);
                  return (
                    <button
                      key={`${task.lesson_id}-${task.review_label}`}
                      type="button"
                      aria-pressed={active}
                      onClick={() => onTaskSelect(task)}
                      className={cx(
                        'group w-full rounded-xl border border-l-4 p-4 text-left shadow-sm transition',
                        active
                          ? 'border-sky-100 border-l-emerald-500 bg-white'
                          : 'border-sky-100 border-l-transparent bg-white hover:border-sky-300 hover:border-l-sky-300',
                      )}
                    >
                      <div className="grid grid-cols-[3rem_minmax(0,1fr)] gap-4">
                        <div
                          className={cx(
                            'flex h-full items-center justify-center rounded-lg border-r border-slate-200 pr-3',
                            active && 'bg-emerald-50',
                          )}
                        >
                          <span
                            className={cx(
                              'flex h-8 w-8 items-center justify-center rounded-lg border text-sm font-bold',
                              active
                                ? 'border-emerald-500 bg-emerald-500 text-white'
                                : 'border-slate-300 bg-white text-slate-500 group-hover:border-sky-400 group-hover:text-sky-600',
                            )}
                          >
                            {index + 1}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <span className="inline-flex rounded-md bg-sky-50 px-2 py-1 text-xs font-bold text-sky-700">{task.lesson_subject || '复习'}</span>
                              <p className="mt-2 text-lg font-bold leading-snug text-slate-950">{task.lesson_topic || '未命名课程'}</p>
                            </div>
                            <span className={cx('shrink-0 rounded-lg border px-3 py-1 text-xs font-bold', active ? 'border-emerald-200 bg-white text-emerald-700' : 'border-sky-200 bg-white text-sky-700')}>
                              {active ? '预览中' : '打开'}
                            </span>
                          </div>
                          <p className="mt-2 truncate text-sm font-medium text-slate-500">{task.review_label}</p>
                          <div className="mt-3 flex flex-wrap gap-3 text-sm font-medium text-slate-500">
                            <span className="inline-flex items-center gap-1.5">
                              <Clock3 size={15} />
                              {task.estimated_time}
                            </span>
                            {task.pdf_page && (
                              <span className="inline-flex items-center gap-1.5">
                                <FileText size={15} />
                                第 {task.pdf_page} 页
                              </span>
                            )}
                          </div>
                          <p className="mt-3 line-clamp-2 border-t border-slate-100 pt-3 text-sm font-medium text-slate-600">{stepText}</p>
                        </div>
                      </div>
                    </button>
                  );
                })
              )}
            </div>

            <div className="mt-5 flex items-center gap-2 rounded-xl bg-sky-50 px-4 py-3 text-sm font-semibold text-slate-500">
              <BookOpenCheck size={18} className="text-sky-600" />
              <span>任务按复习计划顺序排列</span>
            </div>
          </aside>

          <div className="min-h-[40rem] overflow-hidden rounded-xl border border-sky-100 bg-white shadow-sm">
            <div className="flex min-h-16 flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
              <div className="mr-auto flex min-w-0 items-center gap-2">
                <FileText size={21} className="text-slate-700" />
                <div className="min-w-0">
                  <p className="truncate text-base font-bold text-slate-950">PDF预览</p>
                  <p className="truncate text-xs font-semibold text-slate-500">{activeTask?.pdf_filename || activeTask?.lesson_topic || '今日复习资料'}</p>
                </div>
              </div>
              {activeTask?.pdf_page && (
                <span className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-bold text-slate-700">第 {activeTask.pdf_page} 页</span>
              )}
              <span className="rounded-xl bg-slate-100 px-3 py-2 text-sm font-bold text-slate-700">自动缩放</span>
              {activeTask && activeDownloadPath && (
                <a
                  href={activeDownloadPath}
                  title="下载PDF"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition hover:bg-sky-50 hover:text-sky-700"
                >
                  <Download size={19} />
                  <span className="sr-only">下载PDF</span>
                </a>
              )}
              {activeTask && activeOpenPath && (
                <a
                  href={activeOpenPath}
                  target="_blank"
                  rel="noreferrer"
                  title="打开PDF"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 transition hover:bg-sky-50 hover:text-sky-700"
                >
                  <ExternalLink size={19} />
                  <span className="sr-only">打开PDF</span>
                </a>
              )}
            </div>
            {activeTask && previewPath ? (
              <iframe title={`${activeTask.lesson_topic} PDF`} src={previewPath} className="h-full min-h-[calc(40rem-4rem)] w-full border-0 bg-slate-100" />
            ) : (
              <div className="flex h-full min-h-[calc(40rem-4rem)] flex-col items-center justify-center bg-slate-50 px-6 text-center">
                <FileText size={42} className="text-slate-400" />
                <p className="mt-4 text-base font-semibold text-slate-700">选择一个任务后预览资料</p>
                <p className="mt-2 text-sm text-slate-500">如果 PDF 还没生成, 可以先看任务说明</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export function StudentPortalPage({ today }: { today: string }) {
  const [token, setToken] = useState(getStoredStudentToken);
  const [account, setAccount] = useState<StudentAccount | null>(null);
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [invitePreview, setInvitePreview] = useState<StudentClassInvitePreview | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [authLoading, setAuthLoading] = useState(Boolean(token));
  const [inviteLoading, setInviteLoading] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [taskError, setTaskError] = useState('');
  const [tasks, setTasks] = useState<StudentReviewTask[]>([]);
  const [activeLessonId, setActiveLessonId] = useState<number | null>(null);

  const activeTask = useMemo(
    () => tasks.find((task) => task.lesson_id === activeLessonId) ?? tasks[0] ?? null,
    [activeLessonId, tasks],
  );

  const authedPath = useMemo(() => (path: string) => buildStudentAuthedPath(path, token), [token]);

  useEffect(() => {
    if (!token) {
      setAuthLoading(false);
      return;
    }
    let cancelled = false;
    setAuthLoading(true);
    setAuthError('');
    studentApiFetch<{ account: StudentAccount }>('/api/student/me', token)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setAccount(payload.account);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        saveStoredStudentToken('');
        setToken('');
        setAccount(null);
      })
      .finally(() => {
        if (!cancelled) {
          setAuthLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!account || !token) {
      setTasks([]);
      setActiveLessonId(null);
      return;
    }
    let cancelled = false;
    setTaskLoading(true);
    setTaskError('');
    studentApiFetch<StudentReviewTasksResponse>(`/api/student/review-tasks?date=${encodeURIComponent(today)}`, token)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        const nextTasks = Array.isArray(payload.tasks) ? payload.tasks : [];
        setTasks(nextTasks);
        setActiveLessonId(nextTasks[0]?.lesson_id ?? null);
        if (payload.student) {
          setAccount((current) => current ? { ...current, student: payload.student } : current);
        }
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setTasks([]);
        setActiveLessonId(null);
        setTaskError(err instanceof Error ? err.message : '今日任务加载失败');
      })
      .finally(() => {
        if (!cancelled) {
          setTaskLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [account?.id, today, token]);

  const handleAuthSuccess = (payload: StudentAuthResponse) => {
    saveStoredStudentToken(payload.token);
    setToken(payload.token);
    setAccount(payload.account);
    setAuthError('');
  };

  const handleLogin = async (event: FormEvent) => {
    event.preventDefault();
    setAuthLoading(true);
    setAuthError('');
    try {
      const payload = await studentApiFetch<StudentAuthResponse>('/api/student/login', '', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      handleAuthSuccess(payload);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleInvitePreview = async () => {
    setInviteLoading(true);
    setAuthError('');
    try {
      const payload = await studentApiFetch<StudentClassInvitePreview>(`/api/student/class-invite/${encodeURIComponent(inviteCode.trim())}`);
      setInvitePreview(payload);
      setSelectedStudentId(payload.students[0]?.id ?? null);
    } catch (err) {
      setInvitePreview(null);
      setSelectedStudentId(null);
      setAuthError(err instanceof Error ? err.message : '班级邀请码无效');
    } finally {
      setInviteLoading(false);
    }
  };

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedStudentId) {
      setAuthError('请选择学生');
      return;
    }
    setAuthLoading(true);
    setAuthError('');
    try {
      const payload = await studentApiFetch<StudentAuthResponse>('/api/student/register', '', {
        method: 'POST',
        body: JSON.stringify({
          invite_code: inviteCode.trim(),
          student_id: selectedStudentId,
          username,
          password,
        }),
      });
      handleAuthSuccess(payload);
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : '注册失败');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    saveStoredStudentToken('');
    setToken('');
    setAccount(null);
    setTasks([]);
    setActiveLessonId(null);
    setPassword('');
  };

  if (account || authLoading && token) {
    return (
      <StudentTodayTasksContent
        today={today}
        student={account?.student ?? null}
        loading={authLoading}
        taskLoading={taskLoading}
        error={taskError}
        tasks={tasks}
        activeTask={activeTask}
        onTaskSelect={(task) => setActiveLessonId(task.lesson_id)}
        buildAuthedPath={authedPath}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f6fbff_0%,#eef7ff_58%,#f8fbff_100%)] text-slate-950">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex justify-end">
          <StudentBrandMark />
        </header>
        <main className="grid flex-1 place-items-center py-8">
          <section className="w-full max-w-xl rounded-2xl border border-sky-100 bg-white/95 p-5 shadow-[0_24px_80px_rgba(47,128,237,0.12)] md:p-8">
            <div className="mb-7">
              <p className="text-sm font-bold text-sky-600">学生端</p>
              <h1 className="mt-2 text-3xl font-bold text-slate-950">学生端登录</h1>
              <p className="mt-3 text-sm font-medium text-slate-500">今天打开复习计划, 按顺序完成任务.</p>
          </div>

            <div className="flex rounded-2xl bg-slate-100 p-1 text-sm font-semibold dark:bg-white/8">
              <button
                type="button"
                onClick={() => setMode('login')}
                className={cx('flex-1 rounded-xl px-4 py-2.5 transition', mode === 'login' ? 'bg-white text-slate-950 shadow-sm dark:bg-slate-950 dark:text-white' : 'text-slate-500 dark:text-slate-300')}
              >
                登录
              </button>
              <button
                type="button"
                onClick={() => setMode('register')}
                className={cx('flex-1 rounded-xl px-4 py-2.5 transition', mode === 'register' ? 'bg-white text-slate-950 shadow-sm dark:bg-slate-950 dark:text-white' : 'text-slate-500 dark:text-slate-300')}
              >
                注册
              </button>
            </div>

            {authError && (
              <div className="mt-5 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-200">
                <AlertCircle size={16} />
                <span>{authError}</span>
              </div>
            )}

            {mode === 'login' ? (
              <form onSubmit={handleLogin} className="mt-7 space-y-4">
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">学生账号</span>
                  <input
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">密码</span>
                  <input
                    type="password"
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                  />
                </label>
                <button
                  type="submit"
                  disabled={authLoading}
                  className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
                >
                  {authLoading ? <Loader2 size={17} className="animate-spin" /> : <KeyRound size={17} />}
                  登录学生端
                </button>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="mt-7 space-y-4">
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
                  <label className="block">
                    <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">班级邀请码</span>
                    <input
                      className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold uppercase tracking-widest text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                      value={inviteCode}
                      onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                    />
                  </label>
                  <button
                    type="button"
                    onClick={handleInvitePreview}
                    disabled={inviteLoading || !inviteCode.trim()}
                    className="mt-6 inline-flex h-12 items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10 sm:mt-[1.625rem]"
                  >
                    {inviteLoading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
                    查看班级
                  </button>
                </div>

                {invitePreview && (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-400/20 dark:bg-emerald-500/10">
                    <div className="flex items-center gap-2 text-sm font-bold text-emerald-800 dark:text-emerald-100">
                      <Users size={16} />
                      {invitePreview.class.name}
                    </div>
                    <label className="mt-4 block">
                      <span className="mb-2 block text-xs font-semibold text-emerald-700 dark:text-emerald-200">绑定学生</span>
                      <select
                        className="h-12 w-full rounded-2xl border border-emerald-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-emerald-400 focus:ring-4 focus:ring-emerald-100 dark:border-emerald-400/20 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-emerald-400/15"
                        value={selectedStudentId ?? ''}
                        onChange={(event) => setSelectedStudentId(Number(event.target.value) || null)}
                      >
                        {invitePreview.students.map((student) => (
                          <option key={student.id} value={student.id}>{student.name}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}

                <label className="block">
                  <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">学生账号</span>
                  <input
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    autoComplete="username"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-xs font-semibold text-slate-500 dark:text-slate-300">密码</span>
                  <input
                    type="password"
                    className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/15"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                  />
                </label>
                <button
                  type="submit"
                  disabled={authLoading || !invitePreview}
                  className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-4 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
                >
                  {authLoading ? <Loader2 size={17} className="animate-spin" /> : <ChevronRight size={17} />}
                  创建学生账号
                </button>
              </form>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}
