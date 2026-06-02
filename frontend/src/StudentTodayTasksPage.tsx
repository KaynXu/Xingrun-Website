import React, { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  BookOpenCheck,
  ChevronRight,
  FileText,
  KeyRound,
  Loader2,
  RefreshCw,
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

export function StudentTodayTasksContent({
  today: _today,
  student: _student,
  loading,
  taskLoading,
  error,
  tasks,
  activeTask,
  onTaskSelect,
  buildAuthedPath,
  onLogout: _onLogout,
}: StudentTodayTasksContentProps) {
  const previewPath = activeTask && activeTask.pdf_available
    ? buildStudentTaskPdfPreviewPath(activeTask, buildAuthedPath)
    : '';

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-5 text-slate-950 dark:bg-slate-950 dark:text-slate-50 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <header className="px-1">
          <h1 className="text-4xl font-bold tracking-tight text-slate-950 dark:text-white">今日复习</h1>
        </header>

        {error && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-200">
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <section className="grid min-h-[38rem] gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <div className="border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-slate-900">
            <div className="flex items-center justify-between gap-3">
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">今日任务</p>
              {taskLoading && <Loader2 size={18} className="animate-spin text-sky-500" />}
            </div>

            <div className="mt-3 space-y-3">
              {loading || taskLoading ? (
                <div className="flex min-h-64 items-center justify-center border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                  正在加载今日任务
                </div>
              ) : tasks.length === 0 ? (
                <div className="flex min-h-64 flex-col items-center justify-center border border-dashed border-slate-200 bg-slate-50 px-6 text-center dark:border-white/10 dark:bg-white/5">
                  <BookOpenCheck size={34} className="text-emerald-500" />
                  <p className="mt-4 text-base font-semibold text-slate-800 dark:text-slate-100">今天暂无复习任务</p>
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
                        'w-full border p-4 text-left transition',
                        active
                          ? 'border-sky-300 bg-sky-50 dark:border-sky-400/40 dark:bg-sky-500/10'
                          : 'border-slate-200 bg-white hover:border-sky-200 hover:bg-sky-50/70 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/8',
                      )}
                    >
                      <p className="truncate text-base font-bold text-slate-900 dark:text-slate-100">{task.lesson_topic || '未命名课程'}</p>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="min-h-[38rem] overflow-hidden border border-slate-200 bg-white dark:border-white/10 dark:bg-slate-900">
            {activeTask && previewPath ? (
              <iframe title={`${activeTask.lesson_topic} PDF`} src={previewPath} className="h-full min-h-[38rem] w-full border-0" />
            ) : (
              <div className="flex h-full min-h-[38rem] items-center justify-center bg-slate-100 dark:bg-slate-950">
                <FileText size={38} className="text-slate-400" />
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
    <div className="min-h-screen bg-slate-50 px-4 py-6 text-slate-950 dark:bg-slate-950 dark:text-slate-50 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] max-w-xl items-center justify-center">
        <section className="w-full rounded-3xl border border-slate-200 bg-white p-5 shadow-[0_24px_80px_rgba(15,23,42,0.10)] dark:border-white/10 dark:bg-slate-900 md:p-8">
          <div className="mb-7">
            <p className="text-sm font-semibold text-sky-600 dark:text-sky-300">学生端</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">学生端登录</h1>
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
      </div>
    </div>
  );
}
