import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, CheckCircle2, Cpu, Upload } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import type { ClassItem, CurrentUser } from '../../appTypes';
import {
  apiFetch,
  apiUploadFormWithProgress,
  cn,
  workspaceFieldClass,
  workspaceGhostButtonClass,
  workspacePrimaryButtonClass,
} from '../../workspaceShared';
import { ReviewPlanGenerationOptionsFields } from './ReviewPlanGenerationOptionsFields';
import {
  DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS,
  buildGenerationOptionsPayload,
  getGenerationOptionsValidationError,
  getGenerationOptionsFormSummary,
  type ReviewPlanGenerationOptionsFormValue,
} from './reviewPlanGenerationOptions';

type ReviewPlanCreateResponse = {
  id: number;
  success?: boolean;
  status?: string;
  duplicate?: boolean;
};

const academicSubjectOptions = ['数学', '物理', '国际数学'];
const reviewFormSectionClass = 'space-y-4 border-b border-slate-200/80 pb-6 dark:border-white/10';
const reviewFormSectionTitleClass = 'text-sm font-semibold text-slate-900 dark:text-white';
const reviewFormSectionTextClass = 'mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400';
const reviewFormFieldClass = `${workspaceFieldClass} border-slate-200 focus:border-slate-300 focus:ring-slate-100`;

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
      className={cn(reviewFormFieldClass, 'w-full', className)}
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
  const [generationOptions, setGenerationOptions] = useState<ReviewPlanGenerationOptionsFormValue>({
    ...DEFAULT_REVIEW_PLAN_GENERATION_OPTIONS,
  });
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
    const generationOptionsError = getGenerationOptionsValidationError(generationOptions);
    if (generationOptionsError) {
      setError(generationOptionsError);
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
            generation_options: buildGenerationOptionsPayload(generationOptions),
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
        formData.append('generation_options', JSON.stringify(buildGenerationOptionsPayload(generationOptions)));
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
    <div className="space-y-6">
      <AnimatePresence mode="wait">
        {isLoading ? (
          <motion.div
            key="loading"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex min-h-[60vh] items-center justify-center p-8"
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
            className="space-y-6"
          >
            <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,0.9fr)]">
              <SubjectSelect
                value={subject}
                onChange={setSubject}
                className="w-full"
              />
              <select
                value={classId ?? ''}
                onChange={(e) => handleClassChange(Number(e.target.value))}
                className={`${reviewFormFieldClass} w-full`}
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
                className={`${reviewFormFieldClass} w-full`}
              />
            </div>

            {hasNoAssignableClasses && (
              <p className="text-sm text-amber-600 dark:text-amber-300">
                当前账号未分配负责班级，请先联系管理员分配班级后再生成复习记录。
              </p>
            )}

            {error && (
              <div className="flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={18} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_280px]">
              <div className="space-y-6">
                <section className={reviewFormSectionClass}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h4 className={reviewFormSectionTitleClass}>课堂材料</h4>
                    </div>
                    <div className="inline-flex gap-2 rounded-2xl border border-slate-200 bg-slate-50/80 p-1 dark:border-white/10 dark:bg-white/5">
                      <button
                        onClick={() => setInputType('text')}
                        className={cn(
                          'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                          inputType === 'text' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                        )}
                      >
                        文字笔记
                      </button>
                      <button
                        onClick={() => setInputType('file')}
                        className={cn(
                          'rounded-xl px-4 py-2 text-sm font-medium transition-all',
                          inputType === 'file' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
                        )}
                      >
                        上传文件
                      </button>
                    </div>
                  </div>

                  {inputType === 'file' ? (
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="cursor-pointer rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 px-6 py-10 text-center transition hover:border-slate-400 hover:bg-slate-50 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
                    >
                      <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center text-slate-700 dark:text-slate-200">
                        <Upload size={24} />
                      </div>
                      <h4 className="font-semibold text-slate-900 dark:text-white">{file ? file.name : '上传课后录音或文本'}</h4>
                      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">支持 m4a、mp3、wav、txt、md</p>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac,.txt,.md"
                        className="hidden"
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      />
                    </div>
                  ) : (
                    <div className="flex min-h-[420px] flex-col">
                      <div className="mb-4 flex items-center justify-between gap-4">
                        <h4 className={reviewFormSectionTitleClass}>课堂笔记</h4>
                        <button
                          onClick={handleAnalyze}
                          disabled={!summaryText.trim() || isAnalyzing}
                          className={workspaceGhostButtonClass}
                        >
                          <Cpu size={13} className={isAnalyzing ? 'text-sky-500' : 'text-slate-500 dark:text-slate-400'} />
                          {isAnalyzing ? '识别中...' : '识别课程信息'}
                        </button>
                      </div>
                      <textarea
                        placeholder="在此处粘贴课堂笔记、结构化大纲或老师补充说明..."
                        value={summaryText}
                        onChange={(e) => setSummaryText(e.target.value)}
                        className="min-h-[340px] flex-1 resize-none rounded-2xl border border-slate-200 bg-[#fcfdff] px-5 py-4 text-sm leading-relaxed text-slate-700 outline-none transition focus:border-slate-300 focus:ring-4 focus:ring-slate-100 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 dark:focus:border-slate-600 dark:focus:ring-white/10"
                      />
                    </div>
                  )}
                </section>

                <section className={reviewFormSectionClass}>
                  <h4 className={reviewFormSectionTitleClass}>教学信息</h4>
                  <div className="space-y-4">
                    <input
                      type="text"
                      placeholder="课程主题（选填）"
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      className={reviewFormFieldClass}
                    />
                    <textarea
                      placeholder="薄弱点（选填）"
                      value={weakPoints}
                      onChange={(e) => setWeakPoints(e.target.value)}
                      rows={4}
                      className={`${reviewFormFieldClass} resize-none`}
                    />
                    <textarea
                      placeholder="同一节课补充材料（选填）：第二段录音纪要、飞书智能纪要或老师补充说明"
                      value={sameLessonMaterials}
                      onChange={(e) => setSameLessonMaterials(e.target.value)}
                      rows={6}
                      className={`${reviewFormFieldClass} resize-none`}
                    />
                  </div>
                </section>

                <section className={reviewFormSectionClass}>
                  <ReviewPlanGenerationOptionsFields
                    value={generationOptions}
                    onChange={setGenerationOptions}
                  />
                </section>
              </div>

              <aside className="xl:border-l xl:border-slate-200/80 xl:pl-6 dark:xl:border-white/10">
                <section className="space-y-4 xl:sticky xl:top-0">
                  <div className="flex items-center gap-2 text-slate-900 dark:text-white">
                    <CheckCircle2 size={18} className="text-sky-500" />
                    <h4 className={reviewFormSectionTitleClass}>生成前检查</h4>
                  </div>
                  <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-3 dark:border-white/10">
                      <span>班级</span>
                      <span className="text-right font-medium text-slate-900 dark:text-white">
                        {classes.find((item) => item.id === classId)?.name || '未选择'}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-3 dark:border-white/10">
                      <span>科目</span>
                      <span className="text-right font-medium text-slate-900 dark:text-white">{subject || '未选择'}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-3 dark:border-white/10">
                      <span>日期</span>
                      <span className="text-right font-medium text-slate-900 dark:text-white">{lessonDate}</span>
                    </div>
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-3 dark:border-white/10">
                      <span>材料来源</span>
                      <span className="text-right font-medium text-slate-900 dark:text-white">
                        {inputType === 'text' ? '文字笔记' : file?.name || '上传文件'}
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-4 border-b border-slate-200/70 pb-3 dark:border-white/10">
                      <span>生成节奏</span>
                      <span className="text-right font-medium text-slate-900 dark:text-white">
                        {getGenerationOptionsFormSummary(generationOptions)}
                      </span>
                    </div>
                  </div>
                  <button onClick={handleGenerate} className={`${workspacePrimaryButtonClass} self-start bg-slate-950 px-4 py-3 text-base font-semibold text-white shadow-none hover:bg-slate-800`}>
                    生成复习文档
                    <ArrowRight size={20} />
                  </button>
                </section>
              </aside>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
