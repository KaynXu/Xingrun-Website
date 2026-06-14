import { AlertCircle, Search, Trash2, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useMemo, useState } from 'react';
import { FloatingFilterBar, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import {
  bridgeStageOptions,
  isReverseBridgeTarget,
  parseBridgeTarget,
  serializeBridgeTarget,
} from '../../domain/classNaming';
import { getClassInviteCopyButtonLabel } from './classInviteRules';
import {
  workspaceCardClass,
  workspaceFieldClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from '../../workspaceShared';
import type { ClassFormValues, ClassInviteInfo, ClassItem, ClassStudentOption, UserItem } from './model';

type ClassStudent = { id: number; name: string };
type TeacherFilterLayer = 'subject' | 'stage';
type TeacherFilterContextItem = { teacherUserId: number; subject: string; stage: string };

export type ClassEditorModalMode = {
  newClassExpanded: boolean;
  editingClass: ClassItem | null;
  editingFormState: ClassFormValues | null;
};

export type ClassEditorModalLocks = {
  classCardInteractionLocked: boolean;
  classInteractionLocked: boolean;
  assignmentRefreshLocked: boolean;
  saving: boolean;
  deleting: boolean;
};

export type ClassEditorModalErrors = {
  formError: string;
  assignmentError: string;
};

export type ClassEditorModalOptions = {
  academicSubjectOptions: string[];
  studentCenterStageOptions: string[];
};

export type ClassEditorNewClassState = {
  form: ClassFormValues;
  teacher?: UserItem;
  teacherUserId: number | null;
  filteredUsers: UserItem[];
  gradeOptions: string[];
  displayNamePreview: string;
  allStudents: ClassStudentOption[];
};

export type ClassEditorEditingState = {
  canEditTeacherBinding: boolean;
  gradeOptions: string[];
  displayNamePreview: string;
  teacherSearch: string;
  currentTeacherUserId: number | null;
  teacherSummary: string;
  teacherBindingSaving: boolean;
  filteredUsers: UserItem[];
  teacherFilterContext: TeacherFilterContextItem[];
  inviteInfo?: ClassInviteInfo;
  inviteLoading: boolean;
  inviteResetting: boolean;
  inviteError: string;
  students: ClassStudent[];
  allStudents: ClassStudentOption[];
  studentsLoading: boolean;
  studentSaving: boolean;
  studentError: string;
  studentDraftName: string;
};

export type ClassEditorActions = {
  onClose: () => void;
  onSaveClass: (classId: number | 'new') => void;
  onFieldChange: (classId: number | 'new', key: keyof ClassFormValues, value: string) => void;
  onNewClassBridgeChange: (checked: boolean) => void;
  onEditingClassBridgeChange: (checked: boolean) => void;
  onTeacherSearchChange: (classId: number | 'new', value: string) => void;
  onNewClassTeacherUserIdChange: (teacherUserId: number | null) => void;
  onNewClassStudentSelectionChange: (studentId: number, checked: boolean) => void;
  onLoadClassInvite: (classId: number) => void;
  onCopyClassInvite: (classId: number) => Promise<void>;
  onResetClassInvite: (classId: number) => void;
  onRefreshAssignment: (classId: number) => void;
  onSelectTeacherForClass: (classId: number, teacherUserId: number) => void;
  onDeleteClass: (classId: number) => void;
  onStudentDraftNameChange: (classId: number, value: string) => void;
  onAddStudentToClass: (classId: number, studentId: number) => void;
  onDeleteStudentFromClass: (classId: number, studentId: number) => void;
  onOpenStudentProfile: (studentId: number) => void;
};

type ClassEditorModalProps = {
  mode: ClassEditorModalMode;
  locks: ClassEditorModalLocks;
  errors: ClassEditorModalErrors;
  options: ClassEditorModalOptions;
  canSaveClassDraft: boolean;
  teacherSearchByClassId: Record<string, string>;
  users: UserItem[];
  newClass: ClassEditorNewClassState;
  editing: ClassEditorEditingState;
  actions: ClassEditorActions;
  getClassDisplayName: (item: ClassItem) => string;
};

export function ClassEditorModal({
  mode,
  locks,
  errors,
  options,
  canSaveClassDraft,
  teacherSearchByClassId,
  users,
  newClass,
  editing,
  actions,
  getClassDisplayName,
}: ClassEditorModalProps) {
  const { newClassExpanded, editingClass, editingFormState } = mode;
  const { classCardInteractionLocked, classInteractionLocked, assignmentRefreshLocked, saving, deleting } = locks;
  const { formError, assignmentError } = errors;
  const { academicSubjectOptions, studentCenterStageOptions } = options;
  const [newClassStudentSearch, setNewClassStudentSearch] = useState('');
  const [editingStudentSearch, setEditingStudentSearch] = useState('');
  const [copyingInviteClassId, setCopyingInviteClassId] = useState<number | null>(null);
  const [copiedInviteClassId, setCopiedInviteClassId] = useState<number | null>(null);
  const [activeTeacherFilterLayer, setActiveTeacherFilterLayer] = useState<TeacherFilterLayer | null>(null);
  const [teacherSubjectFilter, setTeacherSubjectFilter] = useState('全部学科');
  const [teacherStageFilter, setTeacherStageFilter] = useState('全部学段');
  const [teacherResultsOpen, setTeacherResultsOpen] = useState(false);
  const teacherSearchHasText = editing.teacherSearch.trim().length > 0;
  const normalizedNewClassStudentSearch = newClassStudentSearch.trim().toLowerCase();
  const selectedNewClassStudents = useMemo(
    () => newClass.allStudents.filter((student) => newClass.form.selected_student_ids.includes(student.id)),
    [newClass.allStudents, newClass.form.selected_student_ids],
  );
  const filteredNewClassStudents = useMemo(
    () => newClass.allStudents.filter((student) => (
      !normalizedNewClassStudentSearch
      || student.name.toLowerCase().includes(normalizedNewClassStudentSearch)
    )),
    [newClass.allStudents, normalizedNewClassStudentSearch],
  );
  const normalizedEditingStudentSearch = editingStudentSearch.trim().toLowerCase();
  const editingStudentIds = useMemo(() => new Set(editing.students.map((student) => student.id)), [editing.students]);
  const editingSmallClassLimit = editingClass?.class_type === '1v1' ? 1 : editingClass?.class_type === '1v2' ? 2 : editingClass?.class_type === '1v3' ? 3 : null;
  const editingSmallClassFull = editingSmallClassLimit != null && editing.students.length >= editingSmallClassLimit;
  const teacherFilterItems = [
    {
      key: 'subject' as const,
      defaultLabel: '科目',
      label: teacherSubjectFilter === '全部学科' ? '科目' : `科目：${teacherSubjectFilter}`,
      selected: teacherSubjectFilter !== '全部学科',
    },
    {
      key: 'stage' as const,
      defaultLabel: '学段',
      label: teacherStageFilter === '全部学段' ? '学段' : teacherStageFilter,
      selected: teacherStageFilter !== '全部学段',
    },
  ];
  const teacherFilterOptions: FloatingFilterOption[] = activeTeacherFilterLayer === 'subject'
    ? academicSubjectOptions.map((subject) => ({ id: subject, label: subject, selected: teacherSubjectFilter === subject }))
    : activeTeacherFilterLayer === 'stage'
      ? studentCenterStageOptions.map((stage) => ({ id: stage, label: stage, selected: teacherStageFilter === stage }))
      : [];
  const filteredTeacherUsers = useMemo(
    () => editing.filteredUsers.filter((user) => {
      if (editing.currentTeacherUserId === user.id) {
        return true;
      }
      const teacherClasses = editing.teacherFilterContext.filter((item) => item.teacherUserId === user.id);
      if (teacherSubjectFilter !== '全部学科' && !teacherClasses.some((item) => item.subject === teacherSubjectFilter)) {
        return false;
      }
      if (teacherStageFilter !== '全部学段' && !teacherClasses.some((item) => item.stage === teacherStageFilter)) {
        return false;
      }
      return true;
    }),
    [editing.currentTeacherUserId, editing.filteredUsers, editing.teacherFilterContext, teacherStageFilter, teacherSubjectFilter],
  );
  const filteredEditingStudentOptions = useMemo(
    () => editing.allStudents.filter((student) => (
      !editingStudentIds.has(student.id)
      && (!normalizedEditingStudentSearch || student.name.toLowerCase().includes(normalizedEditingStudentSearch))
    )),
    [editing.allStudents, editingStudentIds, normalizedEditingStudentSearch],
  );
  const newClassBridge = parseBridgeTarget(newClass.form.bridge_target, newClass.form.stage);
  const editingBridge = editingFormState ? parseBridgeTarget(editingFormState.bridge_target, editingFormState.stage) : null;
  const saveClassDisabled = classCardInteractionLocked || !canSaveClassDraft;
  const handleCopyInvite = async (classId: number) => {
    setCopyingInviteClassId(classId);
    setCopiedInviteClassId(null);
    try {
      await actions.onCopyClassInvite(classId);
      setCopiedInviteClassId(classId);
      window.setTimeout(() => {
        setCopiedInviteClassId((current) => (current === classId ? null : current));
      }, 1400);
    } catch {
      setCopiedInviteClassId(null);
    } finally {
      setCopyingInviteClassId((current) => (current === classId ? null : current));
    }
  };
  const handleClearTeacherFilter = (key: TeacherFilterLayer) => {
    if (key === 'subject') {
      setTeacherSubjectFilter('全部学科');
    } else {
      setTeacherStageFilter('全部学段');
    }
    setActiveTeacherFilterLayer(null);
    setTeacherResultsOpen(true);
  };
  const handleSelectTeacherFilter = (value: string | number) => {
    if (activeTeacherFilterLayer === 'subject') {
      setTeacherSubjectFilter(String(value));
    } else if (activeTeacherFilterLayer === 'stage') {
      setTeacherStageFilter(String(value));
    }
    setActiveTeacherFilterLayer(null);
    setTeacherResultsOpen(true);
  };
  const updateBridgeTarget = (classId: number | 'new', fromStage: string, toStage: string) => {
    actions.onFieldChange(classId, 'bridge_target', serializeBridgeTarget(fromStage, toStage));
    actions.onFieldChange(classId, 'content_track', toStage);
  };

  return (
    <AnimatePresence>
      {(newClassExpanded || editingClass) && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"
          onClick={(e) => e.target === e.currentTarget && !classCardInteractionLocked && actions.onClose()}
        >
          <div className="absolute inset-0 bg-black/45 backdrop-blur-[6px]" />
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 18 }}
            transition={{ duration: 0.2 }}
            className="relative z-10 my-auto flex w-full max-w-5xl flex-col overflow-hidden rounded-[1.5rem] border border-sky-100 bg-white max-sm:min-h-[calc(100dvh-1.5rem)] max-sm:max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)] sm:rounded-[2rem] dark:border-white/10 dark:bg-slate-900"
          >
            <div className="flex items-start justify-between gap-4 border-b border-sky-100/80 px-4 py-4 sm:px-6 sm:py-5 dark:border-white/10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Class Management</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <h3 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">
                    {newClassExpanded ? '新建班级' : `编辑班级：${editingClass ? getClassDisplayName(editingClass) : ''}`}
                  </h3>
                  {editingClass ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-sm font-semibold text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200">
                      <span>邀请码：{editing.inviteInfo?.invite_code || (editing.inviteLoading ? '加载中' : '未加载')}</span>
                      <button
                        type="button"
                        onClick={() => void handleCopyInvite(editingClass.id)}
                        disabled={editing.inviteLoading || editing.inviteResetting || copyingInviteClassId === editingClass.id}
                        className="rounded-full px-2 py-1 text-sky-600 transition hover:bg-white hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50 dark:text-sky-300 dark:hover:bg-white/10"
                      >
                        {getClassInviteCopyButtonLabel({
                          loading: editing.inviteLoading,
                          copying: copyingInviteClassId === editingClass.id,
                          copied: copiedInviteClassId === editingClass.id,
                        })}
                      </button>
                      <button
                        type="button"
                        onClick={() => actions.onResetClassInvite(editingClass.id)}
                        disabled={editing.inviteLoading || editing.inviteResetting}
                        className="rounded-full px-2 py-1 text-sky-600 transition hover:bg-white hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-50 dark:text-sky-300 dark:hover:bg-white/10"
                      >
                        {editing.inviteResetting ? '重置中' : '重置'}
                      </button>
                    </div>
                  ) : null}
                </div>
                {editingClass && editing.inviteError ? (
                  <div className="mt-2 flex items-center gap-2 text-xs text-rose-500 dark:text-rose-300">
                    <AlertCircle size={14} />
                    {editing.inviteError}
                  </div>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void actions.onSaveClass(newClassExpanded ? 'new' : editingClass?.id || 'new')}
                  disabled={saveClassDisabled}
                  className={`${workspacePrimaryButtonClass} h-10 px-4 py-2 text-sm`}
                  title="Command+S / Ctrl+S"
                >
                  {saving ? '保存中...' : (newClassExpanded ? '创建班级' : '保存更改')}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (!classCardInteractionLocked) {
                      actions.onClose();
                    }
                  }}
                  disabled={classCardInteractionLocked}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
                  aria-label="关闭班级编辑窗口"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
              {formError && (
                <div className="mb-4 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                  <AlertCircle size={16} />
                  {formError}
                </div>
              )}

              {newClassExpanded ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                    {newClass.form.subject.trim() ? (
                      <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                        {newClass.form.subject.trim()}
                      </span>
                    ) : null}
                    <span>当前负责老师：{newClass.teacher?.name || '待选择负责老师'}</span>
                    <span>创建时会直接绑定该老师账号</span>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">班型</span>
                      <select
                        value={newClass.form.class_type}
                        onChange={(e) => actions.onFieldChange('new', 'class_type', e.target.value)}
                        className={workspaceFieldClass}
                      >
                        <option value="group">多人班课</option>
                        <option value="1v1">1v1</option>
                        <option value="1v2">1v2</option>
                        <option value="1v3">1v3</option>
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">学科</span>
                      <select
                        value={academicSubjectOptions.includes(newClass.form.subject) ? newClass.form.subject : ''}
                        onChange={(e) => actions.onFieldChange('new', 'subject', e.target.value)}
                        className={workspaceFieldClass}
                      >
                        <option value="">请选择学科</option>
                        {academicSubjectOptions.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">学段</span>
                      <select value={newClass.form.stage} onChange={(e) => actions.onFieldChange('new', 'stage', e.target.value)} className={workspaceFieldClass}>
                        {studentCenterStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                      </select>
                    </label>
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">年级</span>
                      <select
                        value={newClass.form.current_grade}
                        onChange={(e) => actions.onFieldChange('new', 'current_grade', e.target.value)}
                        className={workspaceFieldClass}
                      >
                        {newClass.gradeOptions.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    </label>
                    {newClass.form.class_type === 'group' ? (
                      <label className="space-y-2 text-sm">
                        <span className="text-slate-500 dark:text-slate-400">班号</span>
                        <input type="number" min="1" value={newClass.form.class_number} onChange={(e) => actions.onFieldChange('new', 'class_number', e.target.value)} className={workspaceFieldClass} />
                      </label>
                    ) : (
                      <div className="space-y-2 text-sm md:col-span-2">
                        <span className="text-slate-500 dark:text-slate-400">选择学员</span>
                        <div className="rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-white/5">
                          <label className="relative block">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={16} />
                            <input
                              value={newClassStudentSearch}
                              onChange={(event) => setNewClassStudentSearch(event.target.value)}
                              placeholder="搜索学员姓名"
                              className={`${workspaceFieldClass} h-10 pl-9`}
                            />
                          </label>
                          {selectedNewClassStudents.length ? (
                            <div className="mt-3 flex flex-wrap gap-2">
                              {selectedNewClassStudents.map((student) => (
                                <button
                                  key={student.id}
                                  type="button"
                                  onClick={() => actions.onNewClassStudentSelectionChange(student.id, false)}
                                  className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 transition-colors hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-200 dark:hover:bg-sky-500/20"
                                >
                                  {student.name} ×
                                </button>
                              ))}
                            </div>
                          ) : null}
                          <div className="mt-3 grid max-h-40 gap-2 overflow-y-auto sm:grid-cols-2">
                            {newClass.allStudents.length ? filteredNewClassStudents.map((student) => (
                              <label key={student.id} className="flex items-center gap-2 rounded-xl px-2 py-1 text-sm text-slate-700 hover:bg-sky-50 dark:text-slate-200 dark:hover:bg-white/10">
                                <input
                                  type="checkbox"
                                  checked={newClass.form.selected_student_ids.includes(student.id)}
                                  onChange={(event) => actions.onNewClassStudentSelectionChange(student.id, event.target.checked)}
                                />
                                <span>{student.name}</span>
                              </label>
                            )) : (
                              <div className="rounded-xl border border-dashed border-sky-200 p-4 text-center text-slate-500 dark:border-white/10 dark:text-slate-400 sm:col-span-2">
                              暂无已有学员，请先在学员管理中建立学员档案。
                              </div>
                            )}
                            {newClass.allStudents.length && !filteredNewClassStudents.length ? (
                              <div className="rounded-xl border border-dashed border-sky-200 p-4 text-center text-slate-500 dark:border-white/10 dark:text-slate-400 sm:col-span-2">
                                没有匹配的学员
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    )}
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={newClass.form.is_bridge}
                        onChange={(e) => actions.onNewClassBridgeChange(e.target.checked)}
                      />
                      <span className="text-slate-500 dark:text-slate-400">衔接班</span>
                    </label>
                    {newClass.form.is_bridge ? (
                      <div className="space-y-2 rounded-2xl border border-sky-100 bg-sky-50/60 px-4 py-3 text-sm md:col-span-2 dark:border-white/10 dark:bg-white/5">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                          <span className="font-semibold text-slate-700 dark:text-slate-200">衔接方向</span>
                          <select
                            value={newClassBridge.fromStage}
                            onChange={(event) => updateBridgeTarget('new', event.target.value, newClassBridge.toStage)}
                            className={`${workspaceFieldClass} h-10 sm:max-w-40`}
                          >
                            {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                          </select>
                          <span className="text-slate-500 dark:text-slate-400">衔</span>
                          <select
                            value={newClassBridge.toStage}
                            onChange={(event) => updateBridgeTarget('new', newClassBridge.fromStage, event.target.value)}
                            className={`${workspaceFieldClass} h-10 sm:max-w-40`}
                          >
                            {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                          </select>
                        </div>
                        {isReverseBridgeTarget(newClass.form.bridge_target, newClass.form.stage) ? (
                          <p className="text-xs text-slate-500 dark:text-slate-400">提醒：当前是反向衔接方向，请确认后再保存。</p>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="md:col-span-2 rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-sky-400/20 dark:bg-sky-400/10 dark:text-sky-100">
                      名称预览：{newClass.displayNamePreview}
                    </div>
                  </div>

                  <div className={`${workspaceCardClass} space-y-5 p-5`}>
                    <div>
                      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                    </div>

                    <label className="relative block">
                      <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
                      <input
                        type="text"
                        value={teacherSearchByClassId.new || ''}
                        onChange={(e) => actions.onTeacherSearchChange('new', e.target.value)}
                        placeholder="搜索老师"
                        className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                      />
                    </label>

                    {users.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                        当前暂无成员，成员通过审批后会出现在这里。
                      </div>
                    ) : newClass.filteredUsers.length === 0 ? (
                      <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                        没有匹配到老师，请调整搜索关键词。
                      </div>
                    ) : (
                      <select
                        value={newClass.teacherUserId == null ? '' : String(newClass.teacherUserId)}
                        onChange={(event) => {
                          const nextTeacherUserId = Number(event.target.value);
                          actions.onNewClassTeacherUserIdChange(Number.isFinite(nextTeacherUserId) && nextTeacherUserId > 0 ? nextTeacherUserId : null);
                        }}
                        disabled={classInteractionLocked || newClass.filteredUsers.length === 0}
                        className={workspaceFieldClass}
                      >
                        <option value="">请选择负责老师</option>
                        {newClass.filteredUsers.map((user) => (
                          <option key={`new-${user.id}`} value={user.id}>{user.name}</option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="flex flex-col gap-3 border-t border-sky-100/80 pt-5 sm:flex-row sm:items-center sm:justify-end dark:border-white/10">
                    <button
                      type="button"
                      onClick={() => actions.onSaveClass('new')}
                      disabled={saveClassDisabled}
                      className={workspacePrimaryButtonClass}
                    >
                      {saving ? '保存中...' : '创建班级'}
                    </button>
                  </div>
                </div>
              ) : editingClass && editingFormState ? (
                <div className="space-y-5">
                  <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.95fr)] lg:items-start">
                    <div className="space-y-4">
                      <div className={`${workspaceCardClass} space-y-4 p-5`}>
                        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">基础信息</h4>

                        <div className="grid gap-4 md:grid-cols-2">
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">班型</span>
                            <select
                              value={editingFormState.class_type}
                              onChange={(e) => actions.onFieldChange(editingClass.id, 'class_type', e.target.value)}
                              className={workspaceFieldClass}
                            >
                              <option value="group">多人班课</option>
                              <option value="1v1">1v1</option>
                              <option value="1v2">1v2</option>
                              <option value="1v3">1v3</option>
                            </select>
                          </label>
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">学科</span>
                            <select
                              value={academicSubjectOptions.includes(editingFormState.subject) ? editingFormState.subject : ''}
                              onChange={(e) => actions.onFieldChange(editingClass.id, 'subject', e.target.value)}
                              className={workspaceFieldClass}
                            >
                              <option value="">请选择学科</option>
                              {academicSubjectOptions.map((option) => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          </label>
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">学段</span>
                            <select value={editingFormState.stage} onChange={(e) => actions.onFieldChange(editingClass.id, 'stage', e.target.value)} className={workspaceFieldClass}>
                              {studentCenterStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                            </select>
                          </label>
                          <label className="space-y-2 text-sm">
                            <span className="text-slate-500 dark:text-slate-400">年级</span>
                            <select
                              value={editingFormState.current_grade || editingFormState.grade}
                              onChange={(e) => actions.onFieldChange(editingClass.id, 'current_grade', e.target.value)}
                              className={workspaceFieldClass}
                            >
                              {editing.gradeOptions.map((option) => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          </label>
                          {editingFormState.class_type === 'group' ? (
                            <label className="space-y-2 text-sm">
                              <span className="text-slate-500 dark:text-slate-400">班号</span>
                              <input type="number" min="1" value={editingFormState.class_number} onChange={(e) => actions.onFieldChange(editingClass.id, 'class_number', e.target.value)} className={workspaceFieldClass} />
                            </label>
                          ) : null}
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={editingFormState.is_bridge}
                              onChange={(e) => actions.onEditingClassBridgeChange(e.target.checked)}
                            />
                            <span className="text-slate-500 dark:text-slate-400">衔接班</span>
                          </label>
                          {editingFormState.is_bridge && editingBridge ? (
                            <div className="space-y-2 rounded-2xl border border-sky-100 bg-sky-50/60 px-4 py-3 text-sm md:col-span-2 dark:border-white/10 dark:bg-white/5">
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                                <span className="font-semibold text-slate-700 dark:text-slate-200">衔接方向</span>
                                <select
                                  value={editingBridge.fromStage}
                                  onChange={(event) => updateBridgeTarget(editingClass.id, event.target.value, editingBridge.toStage)}
                                  className={`${workspaceFieldClass} h-10 sm:max-w-40`}
                                >
                                  {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                                </select>
                                <span className="text-slate-500 dark:text-slate-400">衔</span>
                                <select
                                  value={editingBridge.toStage}
                                  onChange={(event) => updateBridgeTarget(editingClass.id, editingBridge.fromStage, event.target.value)}
                                  className={`${workspaceFieldClass} h-10 sm:max-w-40`}
                                >
                                  {bridgeStageOptions.map((option) => <option key={option} value={option}>{option}</option>)}
                                </select>
                              </div>
                              {isReverseBridgeTarget(editingFormState.bridge_target, editingFormState.stage) ? (
                                <p className="text-xs text-slate-500 dark:text-slate-400">提醒：当前是反向衔接方向，请确认后再保存。</p>
                              ) : null}
                            </div>
                          ) : null}
                          <div className="md:col-span-2 rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-sky-400/20 dark:bg-sky-400/10 dark:text-sky-100">
                            名称预览：{editing.displayNamePreview}
                          </div>
                        </div>
                      </div>

                      {editing.canEditTeacherBinding && (
                        <div className={`${workspaceCardClass} relative space-y-5 overflow-visible p-5`}>
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="flex flex-wrap items-center gap-3">
                              <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                              <FloatingFilterBar
                                items={teacherFilterItems}
                                activeKey={activeTeacherFilterLayer}
                                options={teacherFilterOptions}
                                summary={[teacherSubjectFilter !== '全部学科' ? teacherSubjectFilter : '', teacherStageFilter !== '全部学段' ? teacherStageFilter : ''].filter(Boolean).join(' / ') || '全部'}
                                emptyText="当前条件下暂无可选老师。"
                                floatingOptions
                                compact
                                activateOnHover={false}
                                onAreaEnter={() => undefined}
                                onAreaLeave={() => undefined}
                                onActivate={(key) => {
                                  setActiveTeacherFilterLayer(key);
                                  if (key) {
                                    setTeacherResultsOpen(true);
                                  }
                                }}
                                onClear={handleClearTeacherFilter}
                                onSelect={handleSelectTeacherFilter}
                              />
                            </div>
                            <button
                              type="button"
                              onClick={() => actions.onRefreshAssignment(editingClass.id)}
                              disabled={assignmentRefreshLocked}
                              className={workspaceSecondaryButtonClass}
                            >
                              刷新分配
                            </button>
                          </div>

                        {assignmentError && (
                          <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                            <AlertCircle size={16} />
                            {assignmentError}
                          </div>
                        )}

                        <div
                          className="relative"
                          onMouseLeave={() => {
                            if (!teacherSearchHasText) {
                              setTeacherResultsOpen(false);
                            }
                          }}
                        >
                          <label className="relative block max-w-[220px]">
                            <span className="pointer-events-none absolute inset-y-0 left-4 flex items-center text-sky-500 dark:text-sky-400">
                              <Search size={18} />
                            </span>
                            <input
                              type="text"
                              value={editing.teacherSearch}
                              onFocus={() => setTeacherResultsOpen(true)}
                              onClick={() => setTeacherResultsOpen(true)}
                              onChange={(e) => {
                                actions.onTeacherSearchChange(editingClass.id, e.target.value);
                                setTeacherResultsOpen(true);
                              }}
                              placeholder="搜索老师"
                              className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                            />
                          </label>

                          {teacherResultsOpen || teacherSearchHasText ? (
                          <div className="mt-4 min-h-24 rounded-2xl border border-sky-100 bg-sky-50/40 p-2 lg:absolute lg:left-[calc(100%+2rem)] lg:top-1/2 lg:z-30 lg:mt-0 lg:w-[320px] lg:-translate-y-1/2 dark:border-white/10 dark:bg-slate-900/95">
                            {users.length === 0 ? (
                              <div className="px-3 py-2 text-sm text-slate-400 dark:text-slate-500">当前暂无成员</div>
                            ) : filteredTeacherUsers.length === 0 ? (
                              <div className="px-3 py-2 text-sm text-slate-400 dark:text-slate-500">未搜索到对应教师</div>
                            ) : (
                              <div className="flex flex-wrap gap-2">
                                {filteredTeacherUsers.map((user) => {
                                  const selected = user.id === editing.currentTeacherUserId;
                                  return (
                                    <button
                                      key={`${editingClass.id}-${user.id}`}
                                      type="button"
                                      onClick={() => {
                                        if (!selected) {
                                          actions.onSelectTeacherForClass(editingClass.id, user.id);
                                        }
                                        setTeacherResultsOpen(false);
                                      }}
                                      disabled={editing.teacherBindingSaving || classInteractionLocked}
                                      className={`rounded-full border px-3 py-1.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                                        selected
                                          ? 'border-sky-500 bg-sky-500 text-white'
                                          : 'border-sky-100 bg-white text-slate-600 hover:border-sky-300 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10'
                                      }`}
                                    >
                                      {user.name}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                          ) : null}
                        </div>

                        <div className="border-t border-sky-100/80 pt-5 dark:border-white/10">
                          <button
                            type="button"
                            onClick={() => actions.onDeleteClass(editingClass.id)}
                            disabled={classCardInteractionLocked}
                            className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                          >
                            <Trash2 size={18} />
                            {deleting ? '删除中...' : '删除当前班级'}
                          </button>
                        </div>
                      </div>
                      )}
                    </div>

                    <div className={`${workspaceCardClass} space-y-4 p-5`}>
                      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">编辑学生</h4>

                      {editing.studentError ? (
                        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                          <AlertCircle size={16} />
                          {editing.studentError}
                        </div>
                      ) : null}

                      {editingClass.class_type === 'group' && editing.students.length >= 10 ? (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
                          提醒：当前多人班课已超过 10 人，请确认班级容量。
                        </div>
                      ) : null}
                      {editingSmallClassFull ? (
                        <div className="rounded-xl border border-sky-100 bg-sky-50 px-3 py-2 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                          当前班型最多 {editingSmallClassLimit} 名学员，如需调整请先移除原学员。
                        </div>
                      ) : (
                        <div className="space-y-3">
                          <label className="relative block">
                            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
                            <input
                              type="text"
                              value={editingStudentSearch}
                              onChange={(e) => setEditingStudentSearch(e.target.value)}
                              placeholder="搜索已有学员"
                              className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                            />
                          </label>
                          {normalizedEditingStudentSearch ? (
                            <div className="grid max-h-40 gap-2 overflow-y-auto rounded-2xl border border-sky-100 bg-white/70 p-3 dark:border-white/10 dark:bg-white/5 sm:grid-cols-2">
                              {filteredEditingStudentOptions.length ? filteredEditingStudentOptions.map((student) => (
                                <button
                                  key={student.id}
                                  type="button"
                                  onClick={() => {
                                    actions.onAddStudentToClass(editingClass.id, student.id);
                                    setEditingStudentSearch('');
                                  }}
                                  disabled={editing.studentSaving}
                                  className="rounded-xl px-3 py-2 text-left text-sm font-medium text-slate-700 transition-colors hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:text-slate-200 dark:hover:bg-white/10"
                                >
                                  {student.name}
                                </button>
                              )) : (
                                <div className="rounded-xl border border-dashed border-sky-200 p-4 text-center text-slate-500 dark:border-white/10 dark:text-slate-400 sm:col-span-2">
                                  {editing.allStudents.length ? '没有匹配的可添加学员' : '暂无已有学员，请先在学员管理中建立学员档案。'}
                                </div>
                              )}
                            </div>
                          ) : null}
                        </div>
                      )}

                      {editing.studentsLoading ? (
                        <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                          正在加载学生...
                        </div>
                      ) : editing.students.length === 0 ? (
                        <div className="min-h-56 rounded-2xl border border-sky-100 bg-sky-50/40 p-3 dark:border-white/10 dark:bg-white/5" />
                      ) : (
                        <div className="grid min-h-56 grid-cols-2 content-start gap-2 rounded-2xl border border-sky-100 bg-sky-50/40 p-3 sm:grid-cols-3 dark:border-white/10 dark:bg-white/5">
                          {editing.students.map((student) => (
                            <div
                              key={student.id}
                              className="flex h-9 min-w-0 items-center overflow-hidden rounded-full border border-sky-100 bg-white text-sm font-semibold text-slate-700 dark:border-white/10 dark:bg-white/10 dark:text-slate-100"
                            >
                              <button
                                type="button"
                                onClick={() => actions.onOpenStudentProfile(student.id)}
                                className="flex h-full min-w-0 flex-1 items-center justify-center px-3 text-center transition-colors hover:bg-sky-50 dark:hover:bg-white/10"
                                title="查看学员详情"
                              >
                                <span className="truncate">{student.name}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => actions.onDeleteStudentFromClass(editingClass.id, student.id)}
                                disabled={editing.studentSaving}
                                className="flex h-full w-9 shrink-0 items-center justify-center bg-rose-50 text-base font-bold text-rose-500 transition hover:bg-rose-100 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/20"
                                aria-label={`移除${student.name}`}
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
