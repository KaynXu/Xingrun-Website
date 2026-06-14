import { AlertCircle, Save, Trash2, X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import {
  workspaceCardClass,
  workspaceFieldClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';
import {
  resolveStudentProfileDraftDirty,
  type ClassStudent,
  type StudentProfileDraft,
} from './classStudentRules';

export type StudentProfileModalMode = 'create' | 'edit' | null;

type StudentProfileModalProps = {
  mode: StudentProfileModalMode;
  draft: StudentProfileDraft;
  savedDraft: StudentProfileDraft | null;
  detail: ClassStudent | null;
  canManageStudents: boolean;
  loading: boolean;
  saving: boolean;
  deleting: boolean;
  error: string;
  duplicateWarning: string;
  onDraftChange: (key: keyof StudentProfileDraft, value: string) => void;
  onSave: () => void;
  onDeleteOrArchive: () => void;
  onClose: () => void;
};

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return '保存后自动生成';
  }
  return value.slice(0, 10);
}

function formatClassType(value: string | undefined): string {
  if (value === '1v1' || value === '1v2' || value === '1v3') {
    return value;
  }
  return '班课';
}

export function StudentProfileModal({
  mode,
  draft,
  savedDraft,
  detail,
  canManageStudents,
  loading,
  saving,
  deleting,
  error,
  duplicateWarning,
  onDraftChange,
  onSave,
  onDeleteOrArchive,
  onClose,
}: StudentProfileModalProps) {
  const [nameBlurred, setNameBlurred] = useState(false);
  const dirty = resolveStudentProfileDraftDirty(draft, savedDraft);
  const saveDisabled = !canManageStudents || loading || saving || deleting || !dirty;
  const isOpen = mode !== null;
  const title = mode === 'create' ? '新建学员' : `学员档案：${detail?.name || draft.name || ''}`;
  const studyRecords = detail?.study_records || [];
  const historyItems = detail?.history_items || [];
  const isArchived = detail?.status === 'archived';
  const showDuplicateWarning = Boolean(duplicateWarning && nameBlurred);

  useEffect(() => {
    setNameBlurred(false);
  }, [mode, detail?.id]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto px-3 py-3 sm:items-center sm:px-4 sm:py-6"
          onClick={(event) => event.target === event.currentTarget && !saving && !deleting && onClose()}
        >
          <div className="absolute inset-0 bg-black/45 backdrop-blur-[6px]" />
          <motion.div
            initial={{ opacity: 0, scale: 0.97, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 18 }}
            transition={{ duration: 0.2 }}
            className="relative z-10 my-auto flex w-full max-w-4xl flex-col overflow-hidden rounded-[1.5rem] border border-sky-100 bg-white max-sm:min-h-[calc(100dvh-1.5rem)] max-sm:max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)] sm:rounded-[2rem] dark:border-white/10 dark:bg-slate-900"
          >
            <div className="flex items-start justify-between gap-4 border-b border-sky-100/80 px-4 py-4 sm:px-6 sm:py-5 dark:border-white/10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Student Profile</p>
                <h3 className="mt-2 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl dark:text-white">
                  {title}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                {canManageStudents ? (
                  <button
                    type="button"
                    onClick={onSave}
                    disabled={saveDisabled}
                    className={`${workspacePrimaryButtonClass} h-10 px-4 py-2 text-sm`}
                    title="Command+S / Ctrl+S"
                  >
                    <Save size={16} />
                    {saving ? '保存中...' : '保存'}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={onClose}
                  disabled={saving || deleting}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-50 text-slate-500 transition-colors hover:bg-sky-100 hover:text-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white/5 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
                  aria-label="关闭学员档案窗口"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
              {error ? (
                <div className="flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                  <AlertCircle size={16} />
                  {error}
                </div>
              ) : null}
              {showDuplicateWarning ? (
                <div className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
                  <AlertCircle size={16} />
                  {duplicateWarning}
                </div>
              ) : null}
              {isArchived ? (
                <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                  <AlertCircle size={16} />
                  此学员档案已停用，历史记录仍保留。
                </div>
              ) : null}

              <div className={`${workspaceCardClass} grid gap-4 p-5 md:grid-cols-3`}>
                <label className="space-y-2">
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">学员姓名</span>
                  <input
                    value={draft.name}
                    onChange={(event) => {
                      setNameBlurred(false);
                      onDraftChange('name', event.target.value);
                    }}
                    onBlur={() => setNameBlurred(true)}
                    disabled={!canManageStudents || loading || saving}
                    className={workspaceFieldClass}
                    placeholder="请输入学员姓名"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">来源（可选）</span>
                  <input
                    value={draft.source}
                    onChange={(event) => onDraftChange('source', event.target.value)}
                    disabled={!canManageStudents || loading || saving}
                    className={workspaceFieldClass}
                    placeholder="转介绍 / 咨询转化"
                  />
                </label>
                <label className="space-y-2">
                  <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">家长联系方式（可选）</span>
                  <input
                    value={draft.parent_contact}
                    onChange={(event) => onDraftChange('parent_contact', event.target.value)}
                    disabled={!canManageStudents || loading || saving}
                    className={workspaceFieldClass}
                    placeholder="手机号 / 微信备注"
                  />
                </label>
              </div>

              <div className="grid gap-3 md:grid-cols-3">
                {[
                  ['入学时间', formatDate(detail?.created_at)],
                  ['就读时长', detail?.study_duration_label || '暂未上课'],
                  ['在读状态', detail?.study_status || (mode === 'create' ? '保存后生成' : '待确认')],
                ].map(([label, value]) => (
                  <div key={label} className={`${workspaceSoftCardClass} p-4`}>
                    <p className="text-xs font-semibold text-slate-400 dark:text-slate-500">{label}</p>
                    <p className="mt-2 text-lg font-bold text-slate-900 dark:text-white">{value}</p>
                  </div>
                ))}
              </div>

              <div className={`${workspaceCardClass} space-y-3 p-5`}>
                <div className="flex items-center justify-between gap-3">
                  <h4 className="text-base font-bold text-slate-900 dark:text-white">在读情况与历史情况</h4>
                  {loading ? <span className="text-sm text-slate-400">加载中...</span> : null}
                </div>

                {studyRecords.length ? (
                  <div className="grid gap-3">
                    {studyRecords.map((record) => (
                      <div key={`${record.class_id}-${record.first_lesson_date || ''}`} className={`${workspaceSoftCardClass} p-4`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-sky-100 px-2.5 py-1 text-xs font-bold text-sky-700 dark:bg-sky-400/15 dark:text-sky-100">
                            {record.subject || '未填学科'}
                          </span>
                          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-500 dark:bg-white/10 dark:text-slate-200">
                            {formatClassType(record.class_type)}
                          </span>
                        </div>
                        <p className="mt-3 text-sm font-semibold text-slate-800 dark:text-slate-100">{record.class_name || `课程 ${record.class_id}`}</p>
                        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                          {[
                            record.stage,
                            record.current_grade || record.grade,
                            record.teacher_name || '未分配老师',
                            `${record.lesson_count || 0} 节课`,
                          ].filter(Boolean).join(' · ')}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-sky-200 p-6 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
                    暂无课程记录。
                  </div>
                )}

                {historyItems.length ? (
                  <div className="space-y-2 border-t border-sky-100 pt-4 dark:border-white/10">
                    {historyItems.map((item, index) => (
                      <p key={`${item.id || index}-${item.created_at || ''}`} className="text-sm text-slate-500 dark:text-slate-400">
                        {formatDate(item.created_at)} · {item.action || '记录'} · {item.class_name || (item.class_id ? `课程 ${item.class_id}` : '未关联课程')}{item.note ? ` · ${item.note}` : ''}
                      </p>
                    ))}
                  </div>
                ) : null}
              </div>

              {canManageStudents ? (
                <div className="flex flex-wrap justify-end gap-3">
                  {mode === 'edit' ? (
                    <button
                      type="button"
                      onClick={onDeleteOrArchive}
                      disabled={loading || saving || deleting}
                      className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-600 transition hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/25 dark:bg-rose-500/10 dark:text-rose-200 dark:hover:bg-rose-500/15"
                    >
                      <Trash2 size={16} />
                      {deleting ? '处理中...' : '删除/停用档案'}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={onSave}
                    disabled={saveDisabled}
                    className={`${workspaceSecondaryButtonClass} h-10 px-4 py-2 text-sm`}
                    title="Command+S / Ctrl+S"
                  >
                    <Save size={16} />
                    {saving ? '保存中...' : '保存学员档案'}
                  </button>
                </div>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
