import { AlertCircle, Search, Trash2, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import {
  workspaceCardClass,
  workspaceFieldClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';
import type { ClassFormValues, ClassInviteInfo, ClassItem, UserItem } from './model';

type ClassStudent = { id: number; name: string };

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
  inviteInfo?: ClassInviteInfo;
  inviteLoading: boolean;
  inviteResetting: boolean;
  inviteError: string;
  students: ClassStudent[];
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
  onLoadClassInvite: (classId: number) => void;
  onResetClassInvite: (classId: number) => void;
  onRefreshAssignment: (classId: number) => void;
  onSelectTeacherForClass: (classId: number, teacherUserId: number) => void;
  onDeleteClass: (classId: number) => void;
  onStudentDraftNameChange: (classId: number, value: string) => void;
  onAddStudentToClass: (classId: number) => void;
  onDeleteStudentFromClass: (classId: number, studentId: number) => void;
};

type ClassEditorModalProps = {
  mode: ClassEditorModalMode;
  locks: ClassEditorModalLocks;
  errors: ClassEditorModalErrors;
  options: ClassEditorModalOptions;
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
            className="relative z-10 my-auto flex w-full max-w-5xl flex-col overflow-hidden rounded-[1.5rem] border border-sky-100 bg-white shadow-[0_30px_90px_rgba(15,23,42,0.18)] max-sm:min-h-[calc(100dvh-1.5rem)] max-sm:max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)] sm:rounded-[2rem] dark:border-white/10 dark:bg-slate-900 dark:shadow-[0_30px_90px_rgba(2,6,23,0.55)]"
          >
            <div className="flex items-start justify-between gap-4 border-b border-sky-100/80 px-4 py-4 sm:px-6 sm:py-5 dark:border-white/10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Class Management</p>
                <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">
                  {newClassExpanded ? '新建班级' : `编辑班级：${editingClass ? getClassDisplayName(editingClass) : ''}`}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void actions.onSaveClass(newClassExpanded ? 'new' : editingClass?.id || 'new')}
                  disabled={classCardInteractionLocked}
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
                    <label className="space-y-2 text-sm">
                      <span className="text-slate-500 dark:text-slate-400">班号</span>
                      <input type="number" min="1" value={newClass.form.class_number} onChange={(e) => actions.onFieldChange('new', 'class_number', e.target.value)} className={workspaceFieldClass} />
                    </label>
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={newClass.form.is_bridge}
                        onChange={(e) => actions.onNewClassBridgeChange(e.target.checked)}
                      />
                      <span className="text-slate-500 dark:text-slate-400">衔接班</span>
                    </label>
                    <div className="md:col-span-2 rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-sky-400/20 dark:bg-sky-400/10 dark:text-sky-100">
                      名称预览：{newClass.displayNamePreview}
                    </div>
                  </div>

                  <div className={`${workspaceCardClass} space-y-5 p-5`}>
                    <div>
                      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">新建班级时必须选择一个负责老师账号，系统会同步老师姓名。</p>
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
                      disabled={classCardInteractionLocked}
                      className={workspacePrimaryButtonClass}
                    >
                      {saving ? '保存中...' : '创建班级'}
                    </button>
                  </div>
                </div>
              ) : editingClass && editingFormState ? (
                <div className="space-y-5">
                  <div className="grid gap-4 lg:grid-cols-[minmax(260px,0.92fr)_minmax(0,1.08fr)] lg:items-start">
                    <div className={`${workspaceCardClass} space-y-4 p-4 sm:p-5`}>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <h4 className="text-lg font-semibold text-slate-900 dark:text-white">家长绑定邀请码</h4>
                          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">把邀请码发给家长后，家长就能在微信小程序里绑定该班级。</p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => actions.onLoadClassInvite(editingClass.id)}
                            disabled={editing.inviteLoading || editing.inviteResetting}
                            className={workspaceSecondaryButtonClass}
                          >
                            {editing.inviteLoading ? '加载中...' : '查看邀请码'}
                          </button>
                          <button
                            type="button"
                            onClick={() => actions.onResetClassInvite(editingClass.id)}
                            disabled={editing.inviteLoading || editing.inviteResetting}
                            className={workspacePrimaryButtonClass}
                          >
                            {editing.inviteResetting ? '重置中...' : '重置邀请码'}
                          </button>
                        </div>
                      </div>

                      {editing.inviteError ? (
                        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                          <AlertCircle size={16} />
                          {editing.inviteError}
                        </div>
                      ) : null}

                      <div className={`${workspaceSoftCardClass} p-4`}>
                        <p className="text-xs uppercase tracking-[0.2em] text-slate-400">当前邀请码</p>
                        <p className="mt-3 font-mono text-2xl font-bold tracking-[0.3em] text-slate-900 dark:text-white">
                          {editing.inviteInfo?.invite_code || (editing.inviteLoading ? '加载中' : '未加载')}
                        </p>
                      </div>
                    </div>

                    <div className={`${workspaceCardClass} space-y-4 p-5`}>
                      <div>
                        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">基础信息</h4>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">请分别填写学科、年级和班级名称，系统按「学科 + 年级 + 班级」理解班级，例如：数学七年级三班。</p>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
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
                        <label className="space-y-2 text-sm">
                          <span className="text-slate-500 dark:text-slate-400">班号</span>
                          <input type="number" min="1" value={editingFormState.class_number} onChange={(e) => actions.onFieldChange(editingClass.id, 'class_number', e.target.value)} className={workspaceFieldClass} />
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={editingFormState.is_bridge}
                            onChange={(e) => actions.onEditingClassBridgeChange(e.target.checked)}
                          />
                          <span className="text-slate-500 dark:text-slate-400">衔接班</span>
                        </label>
                        <div className="md:col-span-2 rounded-2xl border border-sky-100 bg-sky-50/70 px-4 py-3 text-sm font-semibold text-slate-700 dark:border-sky-400/20 dark:bg-sky-400/10 dark:text-sky-100">
                          名称预览：{editing.displayNamePreview}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
                    {editing.canEditTeacherBinding && (
                      <div className={`${workspaceCardClass} space-y-5 p-5`}>
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">负责老师</h4>
                            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">当前负责老师：{editing.teacherSummary}，可直接更换。</p>
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

                        <label className="relative block">
                          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-400" size={18} />
                          <input
                            type="text"
                            value={editing.teacherSearch}
                            onChange={(e) => actions.onTeacherSearchChange(editingClass.id, e.target.value)}
                            placeholder="搜索老师"
                            className={`${workspaceFieldClass} rounded-full py-2.5 pl-11 pr-4`}
                          />
                        </label>

                        {users.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            当前暂无成员，成员通过审批后会出现在这里。
                          </div>
                        ) : editing.filteredUsers.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                            没有匹配到老师，请调整搜索关键词。
                          </div>
                        ) : (
                          <select
                            value={editing.currentTeacherUserId == null ? '' : String(editing.currentTeacherUserId)}
                            onChange={(event) => {
                              const nextTeacherUserId = Number(event.target.value);
                              if (!Number.isFinite(nextTeacherUserId) || nextTeacherUserId <= 0 || nextTeacherUserId === editing.currentTeacherUserId) {
                                return;
                              }
                              actions.onSelectTeacherForClass(editingClass.id, nextTeacherUserId);
                            }}
                            disabled={editing.teacherBindingSaving || classInteractionLocked || editing.filteredUsers.length === 0}
                            className={workspaceFieldClass}
                          >
                            <option value="">请选择负责老师</option>
                            {editing.filteredUsers.map((user) => (
                              <option key={`${editingClass.id}-${user.id}`} value={user.id}>{user.name}</option>
                            ))}
                          </select>
                        )}

                        <div className="grid gap-3 border-t border-sky-100/80 pt-5 sm:grid-cols-2 dark:border-white/10">
                          <button
                            type="button"
                            onClick={() => actions.onDeleteClass(editingClass.id)}
                            disabled={classCardInteractionLocked}
                            className="inline-flex w-full items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-5 py-3 font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                          >
                            <Trash2 size={18} />
                            {deleting ? '删除中...' : '删除当前班级'}
                          </button>
                          <button
                            type="button"
                            onClick={() => actions.onSaveClass(editingClass.id)}
                            disabled={classCardInteractionLocked}
                            className={`${workspacePrimaryButtonClass} w-full`}
                          >
                            {saving ? '保存中...' : '保存班级'}
                          </button>
                        </div>
                      </div>
                    )}

                    <div className={`${workspaceCardClass} space-y-4 p-5`}>
                      <div>
                        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">编辑学生</h4>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">在这里维护当前班级学生名单。</p>
                      </div>

                      {editing.studentError ? (
                        <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                          <AlertCircle size={16} />
                          {editing.studentError}
                        </div>
                      ) : null}

                      <div className="flex flex-col gap-3 sm:flex-row">
                        <input
                          type="text"
                          value={editing.studentDraftName}
                          onChange={(e) => actions.onStudentDraftNameChange(editingClass.id, e.target.value)}
                          placeholder="输入学生姓名"
                          className={workspaceFieldClass}
                        />
                        <button
                          type="button"
                          onClick={() => actions.onAddStudentToClass(editingClass.id)}
                          disabled={editing.studentSaving}
                          className={workspacePrimaryButtonClass}
                        >
                          {editing.studentSaving ? '处理中...' : '新增学生'}
                        </button>
                      </div>

                      {editing.studentsLoading ? (
                        <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                          正在加载学生...
                        </div>
                      ) : editing.students.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
                          当前班级还没有学生。
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {editing.students.map((student) => (
                            <div
                              key={student.id}
                              className="flex items-center justify-between gap-3 rounded-2xl border border-sky-100 bg-sky-50/60 px-4 py-3 dark:border-white/10 dark:bg-white/5"
                            >
                              <span className="font-medium text-slate-900 dark:text-white">{student.name}</span>
                              <button
                                type="button"
                                onClick={() => actions.onDeleteStudentFromClass(editingClass.id, student.id)}
                                disabled={editing.studentSaving}
                                className="inline-flex items-center justify-center whitespace-nowrap rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300 dark:hover:bg-rose-500/15"
                              >
                                删除学生
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
