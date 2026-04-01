import React, { useState } from 'react';

import type {
  TeacherFeedbackStudentDraft,
  TeacherFeedbackTemplate,
} from './reviewGenerationTeacherFeedback';

export interface TeacherFeedbackWorkspaceProps {
  students: TeacherFeedbackStudentDraft[];
  templates: TeacherFeedbackTemplate[];
  feedbackText: string;
  generateLabel: string;
  isLoadingStudents: boolean;
  isGenerating: boolean;
  isSaving: boolean;
  statusMessage: string;
  onSelectTemplate: (studentId: number, templateId: string) => void;
  onRemarkChange: (studentId: number, remark: string) => void;
  onFeedbackTextChange: (value: string) => void;
  onAddTemplate: (draft: { label: string; guidance: string }) => void;
  onAddStudent: (name: string) => void | Promise<void>;
  onRemoveStudent: (studentId: number) => void | Promise<void>;
  onGenerate: () => void | Promise<void>;
  onCopyAll: () => void | Promise<void>;
}

const workspaceShellClass =
  'rounded-[28px] border border-sky-100/80 bg-white/92 p-5 shadow-[0_18px_70px_rgba(15,23,42,0.06)] dark:border-white/10 dark:bg-white/5';
const fieldClass =
  'w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-sky-300 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100';

export function TeacherFeedbackWorkspace({
  students,
  templates,
  feedbackText,
  generateLabel,
  isLoadingStudents,
  isGenerating,
  isSaving,
  statusMessage,
  onSelectTemplate,
  onRemarkChange,
  onFeedbackTextChange,
  onAddTemplate,
  onAddStudent,
  onRemoveStudent,
  onGenerate,
  onCopyAll,
}: TeacherFeedbackWorkspaceProps) {
  const [templateLabelDraft, setTemplateLabelDraft] = useState('');
  const [templateGuidanceDraft, setTemplateGuidanceDraft] = useState('');
  const [newStudentName, setNewStudentName] = useState('');
  const [pickerStudentId, setPickerStudentId] = useState<number | null>(null);

  const handleAddTemplate = () => {
    const label = templateLabelDraft.trim();
    const guidance = templateGuidanceDraft.trim();
    if (!label || !guidance) {
      return;
    }
    onAddTemplate({ label, guidance });
    setTemplateLabelDraft('');
    setTemplateGuidanceDraft('');
  };

  const handleAddStudent = () => {
    const name = newStudentName.trim();
    if (!name) {
      return;
    }
    void Promise.resolve(onAddStudent(name))
      .then(() => setNewStudentName(''))
      .catch(() => undefined);
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section className={workspaceShellClass}>
        <header>
          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">学生区</h4>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            根据班级名单选择学生状态，并可补充备注。
          </p>
        </header>

        <div className="mt-4 rounded-[22px] border border-slate-100 bg-slate-50/80 p-4 dark:border-white/10 dark:bg-white/5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">状态模板池</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                支持内置模板和老师现场新增的自定义模板。
              </p>
            </div>
            <button
              type="button"
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white dark:bg-sky-500"
            >
              新增模板
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {templates.map((template) => (
              <span
                key={template.id}
                className="rounded-full border border-sky-100 bg-white px-3 py-1.5 text-sm text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-200"
              >
                {template.label}
              </span>
            ))}
          </div>

          <div className="mt-4 grid gap-3 rounded-[20px] border border-slate-100 bg-white/92 p-4 dark:border-white/10 dark:bg-slate-900/60">
            <input
              value={templateLabelDraft}
              onChange={(event) => setTemplateLabelDraft(event.target.value)}
              placeholder="模板名称"
              className={fieldClass}
            />
            <textarea
              value={templateGuidanceDraft}
              onChange={(event) => setTemplateGuidanceDraft(event.target.value)}
              placeholder="生成提示"
              className={`${fieldClass} min-h-[88px] leading-6`}
            />
            <button
              type="button"
              onClick={handleAddTemplate}
              className="rounded-2xl bg-sky-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-sky-600"
            >
              加入模板池
            </button>
          </div>
        </div>

        <div className="mt-4 space-y-3">
          {isLoadingStudents ? (
            <div className="rounded-[22px] border border-slate-100 bg-white/92 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
              正在同步班级学生名单...
            </div>
          ) : null}

          {!isLoadingStudents && students.length === 0 ? (
            <div className="rounded-[22px] border border-dashed border-sky-200 bg-sky-50/50 px-4 py-6 text-sm text-slate-500 dark:border-sky-400/40 dark:bg-sky-500/5 dark:text-slate-300">
              当前班级还没有学生，可以先新增学生再生成课后反馈。
            </div>
          ) : null}

          {students.map((student) => {
            const selectedTemplate = templates.find((item) => item.id === student.selectedTemplateId);
            const pickerOpen = pickerStudentId === student.studentId;

            return (
              <article
                key={student.studentId}
                className="rounded-[22px] border border-slate-100 bg-white/92 p-4 dark:border-white/10 dark:bg-white/5"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-900 dark:text-white">{student.name}</p>
                    <button
                      type="button"
                      onClick={() =>
                        setPickerStudentId((current) => (current === student.studentId ? null : student.studentId))
                      }
                      className="mt-2 rounded-full border border-sky-100 px-3 py-1.5 text-sm text-slate-600 transition hover:border-sky-300 hover:bg-sky-50 dark:border-white/10 dark:text-slate-200 dark:hover:bg-white/10"
                    >
                      {selectedTemplate?.label ?? '选择模板'}
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => void onRemoveStudent(student.studentId)}
                    className="text-sm text-rose-500 transition hover:text-rose-600"
                  >
                    移出当前班级
                  </button>
                </div>

                {pickerOpen ? (
                  <div className="mt-3 max-h-[220px] space-y-2 overflow-y-auto rounded-[18px] border border-slate-100 bg-slate-50/80 p-3 dark:border-white/10 dark:bg-slate-900/70">
                    {templates.map((template) => (
                      <button
                        key={`${student.studentId}-${template.id}`}
                        type="button"
                        onClick={() => {
                          onSelectTemplate(student.studentId, template.id);
                          setPickerStudentId(null);
                        }}
                        className="w-full rounded-2xl border border-sky-100 bg-white px-3 py-2 text-left text-sm text-slate-700 transition hover:border-sky-300 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10"
                      >
                        <span className="font-medium">{template.label}</span>
                        <span className="mt-1 block text-xs leading-5 text-slate-500 dark:text-slate-400">
                          {template.guidance}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : null}

                <textarea
                  value={student.remark}
                  onChange={(event) => onRemarkChange(student.studentId, event.target.value)}
                  placeholder="老师备注（可选）"
                  className={`${fieldClass} mt-3 min-h-[88px] leading-6`}
                />
              </article>
            );
          })}

          <div className="rounded-[22px] border border-dashed border-sky-200 p-4 dark:border-sky-400/40">
            <input
              value={newStudentName}
              onChange={(event) => setNewStudentName(event.target.value)}
              placeholder="新增学生姓名"
              className={fieldClass}
            />
            <button
              type="button"
              onClick={handleAddStudent}
              className="mt-3 w-full rounded-2xl bg-sky-50 px-4 py-3 text-sm font-medium text-sky-700 transition hover:bg-sky-100 dark:bg-sky-500/10 dark:text-sky-300"
            >
              新增学生
            </button>
          </div>
        </div>
      </section>

      <section className={workspaceShellClass}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">课后反馈预览</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{statusMessage}</p>
          </div>
          <button
            type="button"
            onClick={() => void onCopyAll()}
            disabled={isSaving}
            className="rounded-full bg-sky-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            复制全部
          </button>
        </div>

        <textarea
          value={feedbackText}
          onChange={(event) => onFeedbackTextChange(event.target.value)}
          className="mt-4 min-h-[420px] w-full resize-y rounded-[28px] border border-sky-100 bg-white/92 px-5 py-4 text-[15px] leading-7 text-slate-700 outline-none transition focus:border-sky-300 focus:ring-4 focus:ring-sky-100/70 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:focus:ring-sky-500/15 md:min-h-[560px]"
        />

        <button
          type="button"
          onClick={() => void onGenerate()}
          disabled={isGenerating}
          className="mt-4 inline-flex w-full items-center justify-center rounded-2xl bg-slate-900 px-5 py-4 text-base font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-sky-500 dark:hover:bg-sky-400"
        >
          {isGenerating ? '生成中...' : generateLabel}
        </button>
      </section>
    </div>
  );
}
