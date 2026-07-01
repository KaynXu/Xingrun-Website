import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, ChevronDown, Cpu, FileText, Upload, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import type { ClassItem, CurrentUser } from '../../appTypes';
import {
  apiFetch,
  apiUploadFormWithProgress,
  cn,
} from '../../workspaceShared';
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

function SectionHeader({
  number,
  title,
  optional = false,
}: {
  number: number;
  title: string;
  optional?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5 mb-3">
      <span
        className="inline-flex shrink-0 items-center justify-center"
        style={{
          width: '24px',
          height: '24px',
          borderRadius: '9999px',
          background: optional ? '#f1f5f9' : 'rgba(30, 41, 59, 0.05)',
          color: optional ? '#94a3b8' : '#1e293b',
          fontSize: '0.75rem',
          fontWeight: 700,
          border: optional ? '1px solid #e2e8f0' : 'none',
        }}
      >
        {number}
      </span>
      <h2
        className="text-sm font-semibold"
        style={{ color: '#64748b', fontSize: '0.875rem' }}
      >
        {title}
      </h2>
      {optional && (
        <span
          className="text-xs"
          style={{ color: '#94a3b8', fontSize: '0.75rem' }}
        >
          可选
        </span>
      )}
    </div>
  );
}

function SelectField({
  label,
  value,
  onChange,
  options,
  placeholder,
  icon,
}: {
  label: string;
  value: string | number;
  onChange: (v: string | number) => void;
  options: Array<{ value: string | number; label: string }>;
  placeholder?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="px-4 py-3">
      <label
        className="block mb-1.5 text-xs font-medium"
        style={{ color: '#94a3b8', fontSize: '0.75rem' }}
      >
        {label}
      </label>
      <div
        className="flex items-center gap-2 px-3 py-2.5 cursor-pointer"
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
        }}
      >
        {icon && <span style={{ color: '#94a3b8' }}>{icon}</span>}
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="truncate min-w-0 flex-1 appearance-none text-sm bg-transparent outline-none cursor-pointer"
          style={{
            color: value ? '#0f172a' : '#94a3b8',
            fontSize: '0.875rem',
            appearance: 'none',
            WebkitAppearance: 'none',
            MozAppearance: 'none',
          }}
        >
          {placeholder && <option value="" disabled>{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#94a3b8' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  icon,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: 'text' | 'date';
  icon?: React.ReactNode;
}) {
  return (
    <div className="px-4 py-3">
      <label
        className="block mb-1.5 text-xs font-medium"
        style={{ color: '#94a3b8', fontSize: '0.75rem' }}
      >
        {label}
      </label>
      <div
        className="flex items-center gap-2 px-3 py-2.5"
        style={{
          background: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
        }}
      >
        {icon && <span style={{ color: '#94a3b8' }}>{icon}</span>}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="truncate flex-1 text-sm bg-transparent outline-none"
          style={{ color: value ? '#0f172a' : '#94a3b8', fontSize: '0.875rem' }}
        />
      </div>
    </div>
  );
}

function SegmentedControl({
  options,
  value,
  onChange,
  columns = 4,
}: {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (v: string) => void;
  columns?: number;
}) {
  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-4 gap-1 p-1"
      style={{
        background: '#ffffff',
        borderRadius: '8px',
      }}
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className="inline-flex items-center justify-center px-3 py-2 text-sm font-medium whitespace-nowrap"
          style={{
            borderRadius: '8px',
            background: value === opt.value ? '#1e293b' : 'transparent',
            color: value === opt.value ? '#ffffff' : '#64748b',
            fontSize: '0.875rem',
            transition: 'background 0.15s, color 0.15s',
          }}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

const scheduleModes = [
  { value: 'standard', label: '标准', description: '按照艾宾浩斯遗忘曲线标准间隔生成复习计划,每日复习量适中,适合大多数学生。' },
  { value: 'compressed', label: '压缩', description: '将复习任务集中在较短天数完成,适合考前突击或时间紧张的学生。' },
  { value: 'daily', label: '连续', description: '每天生成固定题量复习,适合持续巩固基础知识。' },
  { value: 'custom', label: '自定义', description: '自定义复习天数和间隔,灵活配置复习节奏。' },
];

export function LessonInput({
  onSuccess,
  currentUser,
  onCancel,
}: {
  onSuccess: (result: ReviewPlanCreateResponse) => void;
  currentUser: CurrentUser;
  onCancel?: () => void;
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
  const [supplementOpen, setSupplementOpen] = useState(false);
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
  const generationOptionsError = getGenerationOptionsValidationError(generationOptions);
  const missingItems = [
    hasNoAssignableClasses || !classId ? '班级' : '',
    inputType === 'text' && !summaryText.trim() ? '课堂材料' : '',
    inputType === 'file' && !file ? '课堂材料' : '',
  ].filter(Boolean);
  const formStatusText = hasNoAssignableClasses
    ? '未分配班级'
    : generationOptionsError || (missingItems.length ? `缺少:${missingItems.join(',')}` : '可生成');
  const canGenerate = !hasNoAssignableClasses && !generationOptionsError && missingItems.length === 0 && !isLoading;

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
      setError(e instanceof Error ? e.message : '识别失败,请重试');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    setError('');
    if (hasNoAssignableClasses) {
      setError('未分配班级');
      return;
    }
    if (!classId) {
      setError('请选择班级');
      return;
    }
    if (inputType === 'text' && !summaryText.trim()) {
      setError('请输入课堂材料');
      return;
    }
    if (inputType === 'file' && !file) {
      setError('请选择文件');
      return;
    }
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
      setError(e instanceof Error ? e.message : '提交失败,请重试');
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
            {/* ① 基本信息 */}
            <section>
              <SectionHeader number={1} title="基本信息" />
              <div
                className="grid grid-cols-1 sm:grid-cols-3 overflow-hidden"
                style={{
                  background: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                }}
              >
                <SelectField
                  label="科目"
                  value={subject}
                  onChange={setSubject}
                  placeholder="选择科目"
                  options={academicSubjectOptions.map(opt => ({ value: opt, label: opt }))}
                />
                <div className="sm:border-l" style={{ borderTop: '1px solid #e2e8f0', borderLeftColor: '#e2e8f0' }}>
                  <SelectField
                    label="班级"
                    value={classId ?? ''}
                    onChange={(v) => handleClassChange(Number(v))}
                    placeholder="选择班级"
                    options={classes.map(c => ({ value: c.id, label: c.name }))}
                  />
                </div>
                <div className="sm:border-l" style={{ borderTop: '1px solid #e2e8f0', borderLeftColor: '#e2e8f0' }}>
                  <InputField
                    label="日期"
                    type="date"
                    value={lessonDate}
                    onChange={setLessonDate}
                    icon={
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                        <line x1="16" y1="2" x2="16" y2="6" />
                        <line x1="8" y1="2" x2="8" y2="6" />
                        <line x1="3" y1="10" x2="21" y2="10" />
                      </svg>
                    }
                  />
                </div>
              </div>
            </section>

            {/* ② 生成设置 */}
            <section>
              <SectionHeader number={2} title="生成设置" />
              <div
                className="rounded-xl p-4"
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                }}
              >
                <SegmentedControl
                  options={scheduleModes.map(m => ({ value: m.value, label: m.label }))}
                  value={generationOptions.scheduleMode}
                  onChange={(v) => setGenerationOptions({ ...generationOptions, scheduleMode: v })}
                />
                <p
                  className="text-xs mt-3 mb-4"
                  style={{ color: '#94a3b8', fontSize: '0.75rem', lineHeight: '1.5' }}
                >
                  {scheduleModes.find(m => m.value === generationOptions.scheduleMode)?.description}
                </p>

                {generationOptions.scheduleMode === 'daily' && (
                  <div className="flex items-center gap-2 mb-4">
                    <label className="text-xs font-medium whitespace-nowrap" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                      复习天数
                    </label>
                    <div
                      className="inline-flex items-center px-3 py-2"
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <input
                        type="number"
                        min={1}
                        max={30}
                        value={generationOptions.dailyCount}
                        onChange={(e) => setGenerationOptions({
                          ...generationOptions,
                          dailyCount: Math.max(1, Math.min(30, Number(e.target.value) || 1)),
                        })}
                        className="text-sm bg-transparent outline-none w-12"
                        style={{ color: '#0f172a', fontSize: '0.875rem' }}
                      />
                    </div>
                    <span className="text-xs" style={{ color: '#94a3b8', fontSize: '0.75rem' }}>天</span>
                  </div>
                )}

                {generationOptions.scheduleMode === 'custom' && (
                  <div className="flex items-center gap-2 mb-4">
                    <label className="text-xs font-medium whitespace-nowrap" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                      日期点
                    </label>
                    <div
                      className="inline-flex items-center px-3 py-2 flex-1"
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <input
                        type="text"
                        value={generationOptions.customDays}
                        onChange={(e) => setGenerationOptions({ ...generationOptions, customDays: e.target.value })}
                        placeholder="1,3,7"
                        className="text-sm bg-transparent outline-none flex-1"
                        style={{ color: '#0f172a', fontSize: '0.875rem' }}
                      />
                    </div>
                  </div>
                )}

                <label className="block text-xs font-medium mb-1.5" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                  本次要求
                </label>
                <textarea
                  value={generationOptions.userRequirements}
                  onChange={(e) => setGenerationOptions({ ...generationOptions, userRequirements: e.target.value })}
                  placeholder="例如:重点复习三角函数和数列..."
                  rows={3}
                  maxLength={1000}
                  className="px-3 py-2.5 text-sm w-full resize-none outline-none"
                  style={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    color: generationOptions.userRequirements ? '#0f172a' : '#94a3b8',
                    fontSize: '0.875rem',
                    minHeight: '60px',
                  }}
                />
              </div>
            </section>

            {/* ③ 课堂材料 */}
            <section>
              <SectionHeader number={3} title="课堂材料" />
              <div
                className="rounded-xl p-4"
                style={{
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px',
                }}
              >
                <div
                  className="flex gap-1 p-1 mb-3 w-fit"
                  style={{
                    background: '#ffffff',
                    borderRadius: '8px',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setInputType('text')}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium whitespace-nowrap"
                    style={{
                      borderRadius: '8px',
                      background: inputType === 'text' ? '#1e293b' : 'transparent',
                      color: inputType === 'text' ? '#ffffff' : '#64748b',
                      fontSize: '0.875rem',
                      transition: 'background 0.15s, color 0.15s',
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    文字
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputType('file')}
                    className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-sm font-medium whitespace-nowrap"
                    style={{
                      borderRadius: '8px',
                      background: inputType === 'file' ? '#1e293b' : 'transparent',
                      color: inputType === 'file' ? '#ffffff' : '#64748b',
                      fontSize: '0.875rem',
                      transition: 'background 0.15s, color 0.15s',
                    }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                    文件
                  </button>
                </div>

                {inputType === 'text' ? (
                  <>
                    <textarea
                      value={summaryText}
                      onChange={(e) => setSummaryText(e.target.value)}
                      placeholder="请在此粘贴课堂笔记内容,支持直接从教案、课件中复制文本粘贴..."
                      rows={7}
                      className="rounded-lg px-3 py-2.5 text-sm mb-3 w-full resize-none outline-none"
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                        color: summaryText ? '#0f172a' : '#94a3b8',
                        fontSize: '0.875rem',
                        minHeight: '140px',
                        lineHeight: '1.625',
                      }}
                    />
                    <button
                      type="button"
                      onClick={handleAnalyze}
                      disabled={!summaryText.trim() || isAnalyzing}
                      className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap"
                      style={{
                        background: 'rgba(30, 41, 59, 0.05)',
                        color: '#1e293b',
                        border: '1px solid #1e293b',
                        borderRadius: '12px',
                        fontSize: '0.875rem',
                        opacity: !summaryText.trim() || isAnalyzing ? 0.6 : 1,
                        cursor: !summaryText.trim() || isAnalyzing ? 'not-allowed' : 'pointer',
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
                        <path d="M5 3v4" />
                        <path d="M19 17v4" />
                        <path d="M3 5h4" />
                        <path d="M17 19h4" />
                      </svg>
                      {isAnalyzing ? 'AI 识别中...' : 'AI 识别'}
                    </button>
                  </>
                ) : (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="cursor-pointer rounded-xl border border-dashed bg-slate-50/70 px-6 py-8 text-center transition hover:border-slate-400 hover:bg-slate-50"
                    style={{
                      border: '1px dashed #e2e8f0',
                      background: '#ffffff',
                      borderRadius: '8px',
                      minHeight: '140px',
                    }}
                  >
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center text-slate-700 dark:text-slate-200">
                      <Upload size={22} />
                    </div>
                    <div className="flex items-center justify-center gap-2">
                      <h4 className="max-w-full truncate font-semibold text-slate-900 dark:text-white">
                        {file ? file.name : '点击或拖拽上传课堂材料文件'}
                      </h4>
                      {file && (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            setFile(null);
                            if (fileInputRef.current) {
                              fileInputRef.current.value = '';
                            }
                          }}
                          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
                          aria-label="删除文件"
                          title="删除"
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".mp3,.m4a,.mp4,.wav,.ogg,.webm,.flac,.txt,.md"
                      className="hidden"
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </div>
                )}
              </div>
            </section>

            {/* ④ 补充信息(可选) */}
            <section>
              <div className="flex items-center justify-between mb-3">
                <SectionHeader number={4} title="补充信息" optional />
                <button
                  type="button"
                  onClick={() => setSupplementOpen(!supplementOpen)}
                  className="flex items-center gap-2 text-xs"
                  style={{ color: '#94a3b8', fontSize: '0.75rem' }}
                >
                  <span>{supplementOpen ? '收起' : '展开'}</span>
                  <ChevronDown
                    size={14}
                    style={{
                      transform: supplementOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                      transition: 'transform 0.15s',
                    }}
                  />
                </button>
              </div>
              {supplementOpen && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium mb-1.5" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                      复习主题
                    </label>
                    <div
                      className="flex items-center px-3 py-2.5"
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <input
                        type="text"
                        value={topic}
                        onChange={(e) => setTopic(e.target.value)}
                        placeholder="例如:三角函数"
                        className="text-sm truncate flex-1 bg-transparent outline-none"
                        style={{ color: topic ? '#0f172a' : '#94a3b8', fontSize: '0.875rem' }}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium mb-1.5" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                      薄弱知识点
                    </label>
                    <div
                      className="flex items-center px-3 py-2.5"
                      style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <input
                        type="text"
                        value={weakPoints}
                        onChange={(e) => setWeakPoints(e.target.value)}
                        placeholder="例如:诱导公式"
                        className="text-sm truncate flex-1 bg-transparent outline-none"
                        style={{ color: weakPoints ? '#0f172a' : '#94a3b8', fontSize: '0.875rem' }}
                      />
                    </div>
                  </div>
                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium mb-1.5" style={{ color: '#64748b', fontSize: '0.75rem' }}>
                      补充材料
                    </label>
                    <div
                      className="flex items-center px-3 py-2.5 cursor-pointer"
                      style={{
                        background: '#ffffff',
                        border: '1px dashed #e2e8f0',
                        borderRadius: '8px',
                      }}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#94a3b8' }}>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="17 8 12 3 7 8" />
                        <line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                      <span className="text-sm ml-2 truncate" style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                        点击或拖拽上传补充材料文件
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {hasNoAssignableClasses && (
              <p className="text-sm font-medium text-amber-600 dark:text-amber-300">未分配班级</p>
            )}

            {error && (
              <div className="flex items-center gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={18} />
                <span className="text-sm">{error}</span>
              </div>
            )}

            {/* Footer Action Bar */}
            <div
              className="flex flex-col-reverse sm:flex-row items-center justify-between shrink-0 gap-3 sm:gap-0 px-6 py-4 mt-6"
              style={{
                borderTop: '1px solid #e2e8f0',
                background: '#ffffff',
                borderRadius: '16px',
              }}
            >
              <div className="flex items-center gap-2 min-w-0 flex-1">
                <span
                  className="inline-block shrink-0"
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '9999px',
                    background: canGenerate ? '#22c55e' : '#94a3b8',
                  }}
                />
                <span
                  className="text-sm truncate"
                  style={{ color: '#94a3b8', fontSize: '0.875rem' }}
                >
                  {formStatusText}
                </span>
              </div>
              <div className="flex items-center gap-3 shrink-0 w-full sm:w-auto">
                {onCancel && (
                  <button
                    type="button"
                    onClick={onCancel}
                    className="inline-flex items-center justify-center px-4 py-2.5 text-sm font-medium whitespace-nowrap flex-1 sm:flex-initial"
                    style={{
                      background: '#f1f5f9',
                      color: '#64748b',
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      fontSize: '0.875rem',
                    }}
                  >
                    取消
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={!canGenerate}
                  className="inline-flex items-center justify-center gap-2 px-5 py-2.5 text-sm font-medium whitespace-nowrap flex-1 sm:flex-initial"
                  style={{
                    background: canGenerate ? '#1e293b' : '#94a3b8',
                    color: '#ffffff',
                    borderRadius: '12px',
                    fontSize: '0.875rem',
                    opacity: canGenerate ? 1 : 0.6,
                    cursor: canGenerate ? 'pointer' : 'not-allowed',
                  }}
                >
                  生成复习文档
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12" />
                    <polyline points="12 5 19 12 12 19" />
                  </svg>
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
