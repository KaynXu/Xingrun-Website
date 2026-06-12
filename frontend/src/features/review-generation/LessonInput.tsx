import React, { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, CheckCircle2, Cpu, Upload } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import type { ClassItem, CurrentUser } from '../../App';
import { formatClassDisplayName } from '../../domain/classNaming';
import {
  apiFetch,
  buildAuthedPath,
  cn,
  workspaceCardClass,
  workspaceFieldClass,
  workspaceGhostButtonClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
} from '../../workspaceShared';

type Lesson = {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  summary: string;
  weak_points: string;
  pdf_path: string;
  class_id: number | null;
  created_at: string;
  record_status?: string;
  generation_error?: string;
};

type ReviewPlanCreateResponse = {
  id: number;
  success?: boolean;
  status?: string;
  duplicate?: boolean;
};

const gradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '七年级', '八年级', '九年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const academicSubjectOptions = ['数学', '物理', '国际数学'];

function getTodayIsoDate(): string {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 10);
}

function getCurrentClassDisplayName(item: ClassItem | null | undefined, showCohortYear = false): string {
  return formatClassDisplayName(item, { showCohortYear });
}

function syncMemberScopedClassSelection(
  role: CurrentUser['role'],
  classes: ClassItem[],
  selectedClassId: number | null,
): number | null {
  if (role !== 'member') {
    return selectedClassId;
  }

  if (selectedClassId !== null && classes.some((item) => item.id === selectedClassId)) {
    return selectedClassId;
  }

  if (classes.length === 1) {
    return classes[0]?.id ?? null;
  }

  return null;
}

function apiUploadFormWithProgress<T = unknown>(
  path: string,
  body: FormData,
  onProgress: (progress: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', path);
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('xr_token') : null;
    if (token) {
      xhr.setRequestHeader('X-Auth-Token', token);
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) {
        return;
      }
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    };
    xhr.onload = () => {
      if (xhr.status === 401 && typeof window !== 'undefined') {
        window.localStorage.removeItem('xr_token');
        window.location.reload();
      }
      let payload: T & { error?: string };
      try {
        payload = JSON.parse(xhr.responseText || '{}') as T & { error?: string };
      } catch {
        payload = { error: xhr.statusText } as T & { error?: string };
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new Error(payload.error || xhr.statusText));
        return;
      }
      onProgress(100);
      resolve(payload);
    };
    xhr.onerror = () => reject(new Error('上传失败，请重试'));
    xhr.send(body);
  });
}

const WorkspaceLoading = ({ label = '正在处理中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12 text-center">
    <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sky-200 border-t-sky-500" />
    <p className="font-medium text-slate-700 dark:text-slate-200">{label}</p>
  </div>
);

function SubjectSelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <select
      aria-label="科目"
      value={academicSubjectOptions.includes(value) ? value : ''}
      onChange={(event) => onChange(event.target.value)}
      className={cn(workspaceFieldClass, 'w-full', className)}
    >
      <option value="">选择科目</option>
      {academicSubjectOptions.map((option) => (
        <option key={option} value={option}>{option}</option>
      ))}
    </select>
  );
};

export function LessonInput({
  onSuccess,
  currentUser,
}: {
  onSuccess: (result: ReviewPlanCreateResponse) => void;
  currentUser: CurrentUser;
}) {
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [lessonDate, setLessonDate] = useState(new Date().toISOString().split('T')[0]);
  const [weakPoints, setWeakPoints] = useState('');
  const [summaryText, setSummaryText] = useState('');
  const [sameLessonMaterials, setSameLessonMaterials] = useState('');
  const [inputType, setInputType] = useState<'text' | 'file'>('text');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [classesLoading, setClassesLoading] = useState(true);
  const [error, setError] = useState('');
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    setClassesLoading(true);
    apiFetch<ClassItem[]>('/api/classes')
      .then((nextClasses) => {
        if (cancelled) {
          return;
        }
        setClasses(nextClasses);
      })
      .catch((fetchError) => {
        if (cancelled) {
          return;
        }
        setClasses([]);
        console.error(fetchError);
      })
      .finally(() => {
        if (!cancelled) {
          setClassesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentUser.id, currentUser.role]);

  useEffect(() => {
    if (classesLoading || classId === null) {
      return;
    }
    if (classes.some((item) => item.id === classId)) {
      return;
    }
    setClassId(null);
  }, [classId, classes, classesLoading]);

  useEffect(() => {
    if (classesLoading || currentUser.role !== 'member') {
      return;
    }

    setClassId((current) => syncMemberScopedClassSelection(currentUser.role, classes, current));
  }, [classes, classesLoading, currentUser.role]);

  const hasNoAssignableClasses = currentUser.role === 'member' && !classesLoading && classes.length === 0;

  const handleClassChange = (id: number) => {
    setClassId(id);
    const cls = classes.find((c) => c.id === id);
    if (cls?.subject && academicSubjectOptions.includes(cls.subject)) setSubject(cls.subject);
  };

  const handleAnalyze = async () => {
    if (!summaryText.trim()) return;
    setIsAnalyzing(true);
    try {
      const result = await apiFetch<{ subject: string; topic: string; weak_points: string }>('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ text: summaryText }),
      });
      if (result.subject) setSubject(academicSubjectOptions.includes(result.subject) ? result.subject : '');
      if (result.topic) setTopic(result.topic);
      if (result.weak_points) setWeakPoints(result.weak_points);
    } catch (e) {
      setError(e instanceof Error ? e.message : '识别失败，请重试');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    setError('');
    if (hasNoAssignableClasses) {
      setError('当前账号未分配负责班级，请先联系管理员分配班级');
      return;
    }
    if (!classId) {
      setError('请选择班级后再生成复习记录');
      return;
    }
    if (inputType === 'text' && !summaryText.trim()) {
      setError('请填写课堂笔记内容');
      return;
    }
    if (inputType === 'file' && !file) {
      setError('请选择上传文件');
      return;
    }

    setIsLoading(true);
    setUploadProgress(0);
    try {
      let result: ReviewPlanCreateResponse;
      if (inputType === 'text') {
        result = await apiFetch<ReviewPlanCreateResponse>('/api/review-plans', {
          method: 'POST',
          body: JSON.stringify({
            subject,
            class_id: classId ?? 0,
            topic,
            date: lessonDate,
            weak_points: weakPoints,
            summary_text: summaryText,
            same_lesson_materials: sameLessonMaterials,
          }),
        });
      } else {
        const formData = new FormData();
        formData.append('input_type', 'file');
        formData.append('subject', subject);
        formData.append('class_id', classId ? String(classId) : '0');
        formData.append('topic', topic);
        formData.append('date', lessonDate);
        formData.append('weak_points', weakPoints);
        formData.append('same_lesson_materials', sameLessonMaterials);
        if (file) formData.append('upload_file', file);
        result = await apiUploadFormWithProgress<ReviewPlanCreateResponse>('/api/review-plans', formData, setUploadProgress);
      }
      onSuccess(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '提交失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`${workspacePageClass} mx-auto max-w-6xl`}>
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={`${workspaceCardClass} flex min-h-[60vh] items-center justify-center p-8`}
          >
            <div className="w-full max-w-sm space-y-4">
              <WorkspaceLoading label={inputType === 'file' ? '正在上传课堂文件...' : '正在生成复习资料...'} />
              {inputType === 'file' && (
                <div className="space-y-2">
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10">
                    <div
                      className="h-full rounded-full bg-sky-500 transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                  <p className="text-center text-xs text-slate-500 dark:text-slate-400">{uploadProgress}%</p>
                </div>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="space-y-5">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Lesson Intake</p>
                <h3 className={`${workspaceSectionTitleClass} mt-3`}>生成复习文档</h3>
                <p className={`${workspaceSectionTextClass} mt-2`}>
                  上传录音或粘贴笔记，生成 AI 复习资料和教学素材。
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
                <SubjectSelect
                  value={subject}
                  onChange={setSubject}
                  className="w-full"
                />
                <select
                  value={classId ?? ''}
                  onChange={(e) => handleClassChange(Number(e.target.value))}
                  className={`${workspaceFieldClass} w-full`}
                >
                  <option value="">选择班级</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <input
                  type="date"
                  value={lessonDate}
                  onChange={(e) => setLessonDate(e.target.value)}
                  className={`${workspaceFieldClass} w-full`}
                />
              </div>
              {hasNoAssignableClasses && (
                <p className="text-sm text-amber-600 dark:text-amber-300">
                  当前账号未分配负责班级，请先联系管理员分配班级后再生成复习记录。
                </p>
              )}
            </div>

            {error && (
              <div className="flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={18} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
              <div className="space-y-6">
                <div className="inline-flex gap-2 rounded-2xl border border-sky-100 bg-white/85 p-1 shadow-sm dark:border-white/10 dark:bg-white/5">
                  <button
                    onClick={() => setInputType('text')}
                    className={cn(
                      'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                      inputType === 'text' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                    )}
                  >
                    文字笔记
                  </button>
                  <button
                    onClick={() => setInputType('file')}
                    className={cn(
                      'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                      inputType === 'file' ? 'bg-sky-600 text-white shadow-sm' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                    )}
                  >
                    上传文件
                  </button>
                </div>

                {inputType === 'file' ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`${workspaceCardClass} cursor-pointer p-12 text-center transition-all hover:border-sky-200 hover:shadow-[0_24px_64px_rgba(47,128,237,0.1)] dark:hover:border-white/15 dark:hover:shadow-[0_28px_72px_rgba(2,6,23,0.4)]`}
                  >
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-50 text-sky-600 transition-transform hover:scale-105 dark:bg-white/5 dark:text-sky-300">
                      <Upload size={32} />
                    </div>
                    <h4 className="font-semibold text-slate-900 dark:text-white">{file ? file.name : '上传课后录音或文本'}</h4>
                    <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">支持 m4a, mp3, wav, txt, md 格式</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac,.txt,.md"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                ) : null}

                <div className={`${workspaceCardClass} space-y-4 p-6`}>
                  <h4 className="flex items-center gap-2 font-semibold text-slate-900 dark:text-white">
                    <CheckCircle2 size={18} className="text-sky-500" />
                    课程信息
                  </h4>
                  <input
                    type="text"
                    placeholder="课程主题（选填）"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    className={workspaceFieldClass}
                  />
                  <textarea
                    placeholder="薄弱点（选填）"
                    value={weakPoints}
                    onChange={(e) => setWeakPoints(e.target.value)}
                    rows={3}
                    className={`${workspaceFieldClass} resize-none`}
                  />
                  <textarea
                    placeholder="同一节课补充材料（选填）：第二段录音纪要、飞书智能纪要或老师补充说明"
                    value={sameLessonMaterials}
                    onChange={(e) => setSameLessonMaterials(e.target.value)}
                    rows={5}
                    className={`${workspaceFieldClass} resize-none`}
                  />
                </div>
              </div>

              <div className="flex flex-col">
                {inputType === 'text' && (
                  <div className={`${workspaceCardClass} flex flex-1 flex-col p-6`}>
                    <div className="mb-4 flex items-center justify-between gap-4">
                      <div>
                        <h4 className="font-semibold text-slate-900 dark:text-white">课堂笔记</h4>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">支持长段文本、结构化大纲与老师备注。</p>
                      </div>
                      <button
                        onClick={handleAnalyze}
                        disabled={!summaryText.trim() || isAnalyzing}
                        className={workspaceGhostButtonClass}
                      >
                        <Cpu size={13} className={isAnalyzing ? 'text-sky-500' : 'text-slate-500 dark:text-slate-400'} />
                        {isAnalyzing ? '识别中...' : '识别'}
                      </button>
                    </div>
                    <textarea
                      placeholder="在此处粘贴您的课堂笔记或结构化大纲..."
                      value={summaryText}
                      onChange={(e) => setSummaryText(e.target.value)}
                      className="min-h-[320px] flex-1 resize-none rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,rgba(249,252,255,0.98)_0%,rgba(240,248,255,0.95)_100%)] px-5 py-4 text-sm leading-relaxed text-slate-700 outline-none transition focus:border-sky-200 focus:ring-4 focus:ring-sky-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:border-sky-500 dark:focus:ring-sky-500/15"
                    />
                  </div>
                )}
                <button onClick={handleGenerate} className={`${workspacePrimaryButtonClass} mt-6 w-full py-4 text-lg font-bold`}>
                  生成复习文档
                  <ArrowRight size={20} />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
