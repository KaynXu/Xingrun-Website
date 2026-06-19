import { useEffect, useState } from 'react';

import type { ClassItem } from '../../appTypes';
import { getCurrentClassDisplayName } from '../../classDisplay';
import { serializeBridgeTarget } from '../../domain/classNaming';
import {
  buildConsultationClassFilterDefaults,
  buildConsultationQuickClassForm,
  filterConsultationStudentCenterClasses,
  type ConsultationClassTypeFilter,
} from '../../domain/consultationStudentCenterClassAdapter';
import { cn } from '../../workspaceShared';
import type { ClassFormValues, UserItem } from '../student-center/model';
import type { ConsultationFormValues } from './consultationTypes';

const academicSubjectOptions = ['数学', '物理', '国际数学'];
const consultationGradeOptions = ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级', '初一', '初二', '初三', '高一', '高二', '高三'];
const consultationStageOptions = ['小奥', '小学', '初中', '高中'];

function buildCreateDraftFromAdapter(values: ConsultationFormValues): ClassFormValues {
  return buildConsultationQuickClassForm({
    consultationSubject: values.consultation_subject || '',
    consultationGrade: values.grade || '',
    subjectOptions: academicSubjectOptions,
  });
}

export const ConsultationEnterClassDialog = ({
  open,
  values,
  classes,
  users = [],
  teacherBindingByClassId = {},
  teachingTeacherUserId,
  creating,
  createError,
  onClose,
  onExistingClass,
  onCreateClass,
  onPending,
}: {
  open: boolean;
  values: ConsultationFormValues;
  classes: ClassItem[];
  users?: UserItem[];
  teacherBindingByClassId?: Record<number, number | null>;
  teachingTeacherUserId?: number | null;
  creating: boolean;
  createError: string;
  onClose: () => void;
  onExistingClass: (classId: number) => void;
  onCreateClass: (form: ClassFormValues) => Promise<void>;
  onPending: () => void;
}) => {
  const recommendedSubject = values.consultation_subject || '全部学科';
  const [mode, setMode] = useState<'existing' | 'create' | 'pending'>('existing');
  const initialFilters = buildConsultationClassFilterDefaults({
    consultationSubject: recommendedSubject === '全部学科' ? '' : recommendedSubject,
    consultationGrade: values.grade || '',
    teachingTeacherUserId,
    subjectOptions: academicSubjectOptions,
  });
  const [subjectFilter, setSubjectFilter] = useState(initialFilters.subjectFilter);
  const [teacherFilter, setTeacherFilter] = useState<number | 'all'>(initialFilters.teacherFilter);
  const [stageFilter, setStageFilter] = useState(initialFilters.stageFilter);
  const [gradeFilter, setGradeFilter] = useState(initialFilters.gradeFilter);
  const [classTypeFilter, setClassTypeFilter] = useState<ConsultationClassTypeFilter>(initialFilters.classTypeFilter);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [createDraft, setCreateDraft] = useState<ClassFormValues>(() => buildCreateDraftFromAdapter(values));

  useEffect(() => {
    if (!open) return;
    const defaults = buildConsultationClassFilterDefaults({
      consultationSubject: values.consultation_subject || '',
      consultationGrade: values.grade || '',
      teachingTeacherUserId,
      subjectOptions: academicSubjectOptions,
    });
    setMode('existing');
    setSubjectFilter(defaults.subjectFilter);
    setTeacherFilter(defaults.teacherFilter);
    setStageFilter(defaults.stageFilter);
    setGradeFilter(defaults.gradeFilter);
    setClassTypeFilter(defaults.classTypeFilter);
    setSelectedClassId(values.success_class_id ? String(values.success_class_id) : '');
    setCreateDraft(buildCreateDraftFromAdapter(values));
  }, [open, teachingTeacherUserId, values.consultation_subject, values.grade, values.success_class_id]);

  if (!open) return null;

  const filteredClasses = filterConsultationStudentCenterClasses({
    classes,
    subjectOptions: academicSubjectOptions,
    teacherBindingByClassId,
    filters: {
      subjectFilter,
      teacherFilter,
      stageFilter,
      gradeFilter,
      classTypeFilter,
    },
  });
  const classPreview = [
    createDraft.subject,
    createDraft.stage,
    createDraft.current_grade,
    createDraft.class_type === 'group' ? `${createDraft.class_number}班` : createDraft.class_type,
    createDraft.is_bridge ? '衔接' : '',
  ].filter(Boolean).join(' / ');
  const smallSelectClass = 'h-10 rounded-lg border border-[#BFE5F8] bg-white px-3 text-sm font-semibold text-[#1F2A44] outline-none focus:border-[#0EA5E9] dark:border-white/10 dark:bg-slate-900 dark:text-white';
  const cardClass = (active: boolean, tone: 'sky' | 'emerald' | 'amber') => cn(
    'rounded-xl border p-3 text-left transition',
    active && tone === 'sky' ? 'border-sky-300 bg-sky-50 text-sky-800' : '',
    active && tone === 'emerald' ? 'border-emerald-300 bg-emerald-50 text-emerald-800' : '',
    active && tone === 'amber' ? 'border-amber-300 bg-amber-50 text-amber-800' : '',
    !active ? 'border-[#D9EEF7] bg-white text-[#1F2A44] hover:bg-sky-50 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:hover:bg-white/5' : '',
  );

  return (
    <div className="fixed inset-0 z-[75] flex items-center justify-center bg-slate-950/35 px-4" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <div className="w-full max-w-[44rem] rounded-[18px] border border-[#D9EEF7] bg-white p-5 shadow-[0_24px_70px_rgba(31,42,68,0.22)] dark:border-white/10 dark:bg-slate-950">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-xl font-extrabold text-[#1F2A44] dark:text-white">进班与学员档案</h3>
            <p className="mt-1 text-sm text-[#7188A6] dark:text-slate-400">{values.child_name || '未填写学生'} · {values.consultation_subject || '未填写科目'} · {values.grade || '未填写年级'}</p>
          </div>
          <button type="button" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full bg-[#F1F9FE] text-[#7188A6] hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300">×</button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <button type="button" onClick={() => setMode('existing')} className={cardClass(mode === 'existing', 'sky')}>
            <p className="text-sm font-extrabold">已有班级</p>
            <p className="mt-2 text-xs font-semibold opacity-75">从筛选后的班级里选择，直接建立进班记录。</p>
          </button>
          <button type="button" onClick={() => setMode('create')} className={cardClass(mode === 'create', 'emerald')}>
            <p className="text-sm font-extrabold">快速建班</p>
            <p className="mt-2 text-xs font-semibold opacity-75">沿用学员中心规则生成班名，再完成进班。</p>
          </button>
          <button type="button" onClick={() => setMode('pending')} className={cardClass(mode === 'pending', 'amber')}>
            <p className="text-sm font-extrabold">转化待进班</p>
            <p className="mt-2 text-xs font-semibold opacity-75">先记为成功，班级和档案稍后补齐。</p>
          </button>
        </div>

        <div className="mt-4 rounded-xl border border-[#D9EEF7] bg-[#F9FDFF] p-3 dark:border-white/10 dark:bg-white/[0.03]">
          {mode === 'existing' && (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-5">
                <select value={subjectFilter} onChange={(event) => setSubjectFilter(event.target.value)} className={smallSelectClass}>
                  <option value="全部学科">全部学科</option>
                  {academicSubjectOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={teacherFilter} onChange={(event) => setTeacherFilter(event.target.value === 'all' ? 'all' : Number(event.target.value))} className={smallSelectClass}>
                  <option value="all">全部老师</option>
                  {users.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
                <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)} className={smallSelectClass}>
                  <option value="全部学段">全部学段</option>
                  {consultationStageOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={gradeFilter} onChange={(event) => setGradeFilter(event.target.value)} className={smallSelectClass}>
                  <option value="全部">全部年级</option>
                  {consultationGradeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={classTypeFilter} onChange={(event) => setClassTypeFilter(event.target.value as ConsultationClassTypeFilter)} className={smallSelectClass}>
                  <option value="all">全部类型</option>
                  <option value="small">小课</option>
                  <option value="group">班课</option>
                </select>
              </div>
              <select value={selectedClassId} onChange={(event) => setSelectedClassId(event.target.value)} className={`${smallSelectClass} w-full`}>
                <option value="">请选择班级</option>
                {filteredClasses.map((item) => <option key={item.id} value={item.id}>{getCurrentClassDisplayName(item)}</option>)}
              </select>
            </div>
          )}

          {mode === 'create' && (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_1fr_1fr_1fr_0.8fr]">
                <select value={createDraft.subject} onChange={(event) => setCreateDraft((current) => ({ ...current, subject: event.target.value }))} className={smallSelectClass}>
                  {academicSubjectOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={createDraft.stage} onChange={(event) => setCreateDraft((current) => ({ ...current, stage: event.target.value }))} className={smallSelectClass}>
                  {consultationStageOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={createDraft.current_grade} onChange={(event) => setCreateDraft((current) => ({ ...current, current_grade: event.target.value, grade: event.target.value }))} className={smallSelectClass}>
                  {consultationGradeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
                <select value={createDraft.class_type} onChange={(event) => setCreateDraft((current) => ({ ...current, class_type: event.target.value, class_number: event.target.value === 'group' ? current.class_number : '' }))} className={smallSelectClass}>
                  <option value="group">班课</option>
                  <option value="1v1">1v1</option>
                  <option value="1v2">1v2</option>
                  <option value="1v3">1v3</option>
                </select>
                <select value={createDraft.class_number} onChange={(event) => setCreateDraft((current) => ({ ...current, class_number: event.target.value }))} className={smallSelectClass} disabled={createDraft.class_type !== 'group'}>
                  {['1', '2', '3', '4', '5', '6'].map((item) => <option key={item} value={item}>{item}班</option>)}
                </select>
              </div>
              <div className="grid gap-2 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center">
                <label className="inline-flex h-10 items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 text-sm font-extrabold text-emerald-700">
                  <input type="checkbox" checked={createDraft.is_bridge} onChange={(event) => setCreateDraft((current) => ({ ...current, is_bridge: event.target.checked }))} />
                  衔接班
                </label>
                <select value={createDraft.bridge_target} onChange={(event) => setCreateDraft((current) => ({ ...current, bridge_target: event.target.value }))} className={smallSelectClass} disabled={!createDraft.is_bridge}>
                  <option value={serializeBridgeTarget('小学', '初中')}>小学衔接初中</option>
                  <option value={serializeBridgeTarget('初中', '高中')}>初中衔接高中</option>
                </select>
              </div>
              <p className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-[#7188A6] dark:bg-slate-900 dark:text-slate-300">修改之后的班名预览：{classPreview}</p>
              {createError ? <p className="text-sm font-semibold text-rose-600">{createError}</p> : null}
            </div>
          )}

          {mode === 'pending' && (
            <p className="text-sm font-semibold leading-6 text-[#7188A6] dark:text-slate-300">先把这条咨询标记为转化成功，但班级、学员档案和实际进班稍后补齐。</p>
          )}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3">
          <button type="button" onClick={onClose} className="inline-flex items-center justify-center rounded-xl border border-[#D9EEF7] bg-white px-4 py-3 text-sm font-bold text-[#1F2A44] hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100">取消</button>
          <button
            type="button"
            disabled={creating}
            onClick={() => {
              if (mode === 'existing' && selectedClassId) onExistingClass(Number(selectedClassId));
              if (mode === 'create') void onCreateClass(createDraft);
              if (mode === 'pending') onPending();
            }}
            className="inline-flex items-center justify-center rounded-xl bg-[#0EA5E9] px-4 py-3 text-sm font-bold text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {creating ? '创建中...' : mode === 'existing' ? '确认进班' : mode === 'create' ? '创建并进班' : '标记成功'}
          </button>
        </div>
      </div>
    </div>
  );
};
