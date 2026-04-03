import React, { useMemo, useState } from 'react';

import type {
  ClassFeedbackStageNotes,
  ClassFeedbackStudentCard,
  StageLabelGroup,
} from './classFeedbackGeneration';

interface ClassFeedbackGenerationWorkspaceProps {
  classNameLabel: string;
  teacherNameLabel: string;
  sourceSummaryItems: string[];
  labelGroups: StageLabelGroup[];
  students: ClassFeedbackStudentCard[];
  classSummaryText: string;
  statusMessage: string;
  stageNotes: ClassFeedbackStageNotes;
  isGenerating: boolean;
  isSaving: boolean;
  isConfirming: boolean;
  onClassSummaryChange: (value: string) => void;
  onStageNoteChange: (key: keyof ClassFeedbackStageNotes, value: string) => void;
  onHighlightToggle: (studentId: number, label: string) => void;
  onHighlightNoteChange: (studentId: number, value: string) => void;
  onStudentFinalTextChange: (studentId: number, value: string) => void;
  onStudentCheckedChange: (studentId: number, checked: boolean) => void;
  onAddStudent: (name: string) => void | Promise<void>;
  onGenerate: () => void | Promise<void>;
  onCopyClassSummary: () => void | Promise<void>;
  onCopyAllStudents: () => void | Promise<void>;
  onConfirm: () => void | Promise<void>;
}

const cardClass =
  'rounded-[28px] border border-sky-100/80 bg-white/92 p-5 shadow-[0_18px_70px_rgba(15,23,42,0.06)]';
const fieldClass =
  'w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-sky-300';

export function ClassFeedbackGenerationWorkspace(props: ClassFeedbackGenerationWorkspaceProps) {
  const [newStudentName, setNewStudentName] = useState('');

  const labelLookup = useMemo(
    () => props.labelGroups.flatMap((group) => group.labels.map((label) => ({ group: group.group, label }))),
    [props.labelGroups],
  );

  const handleAddStudent = () => {
    const name = newStudentName.trim();
    if (!name) {
      return;
    }
    void Promise.resolve(props.onAddStudent(name))
      .then(() => setNewStudentName(''))
      .catch(() => undefined);
  };

  return (
    <section className="space-y-6">
      <header className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600">Class Feedback</p>
        <h3 className="mt-3 text-2xl font-semibold text-slate-900">班级反馈生成</h3>
        <p className="mt-2 text-sm text-slate-500">
          {props.classNameLabel} · {props.teacherNameLabel}
        </p>
        <p className="mt-2 text-sm text-slate-500">{props.statusMessage}</p>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className={`${cardClass} space-y-6`}>
          <div>
            <h4 className="text-lg font-semibold text-slate-900">资料摘要</h4>
            <ul className="mt-4 space-y-2 text-sm text-slate-600">
              {props.sourceSummaryItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-slate-900">阶段备注</h4>
            <div className="mt-4 grid gap-3">
              <textarea
                value={props.stageNotes.classStatusNote}
                onChange={(event) => props.onStageNoteChange('classStatusNote', event.target.value)}
                placeholder="本阶段班级整体状态"
                className={`${fieldClass} min-h-[88px] leading-6`}
              />
              <textarea
                value={props.stageNotes.parentFeedbackNote}
                onChange={(event) => props.onStageNoteChange('parentFeedbackNote', event.target.value)}
                placeholder="家长共性反馈"
                className={`${fieldClass} min-h-[88px] leading-6`}
              />
              <textarea
                value={props.stageNotes.teachingFocusNote}
                onChange={(event) => props.onStageNoteChange('teachingFocusNote', event.target.value)}
                placeholder="本阶段教学重点或考试节点"
                className={`${fieldClass} min-h-[88px] leading-6`}
              />
              <textarea
                value={props.stageNotes.nextStagePreviewNote}
                onChange={(event) => props.onStageNoteChange('nextStagePreviewNote', event.target.value)}
                placeholder="下阶段教学预告与本阶段的联系"
                className={`${fieldClass} min-h-[88px] leading-6`}
              />
            </div>
          </div>

          <div>
            <h4 className="text-lg font-semibold text-slate-900">补充学生</h4>
            <div className="mt-3 rounded-[22px] border border-dashed border-sky-200 p-4">
              <input
                value={newStudentName}
                onChange={(event) => setNewStudentName(event.target.value)}
                placeholder="新增学生姓名"
                className={fieldClass}
              />
              <button
                type="button"
                onClick={handleAddStudent}
                className="mt-3 w-full rounded-2xl bg-sky-50 px-4 py-3 text-sm font-medium text-sky-700 transition hover:bg-sky-100"
              >
                新增学生
              </button>
            </div>
          </div>
        </section>

        <section className={`${cardClass} space-y-6`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className="text-lg font-semibold text-slate-900">班级总评</h4>
              <p className="mt-1 text-sm text-slate-500">{props.statusMessage}</p>
            </div>
            <button
              type="button"
              onClick={() => void props.onCopyClassSummary()}
              className="rounded-full bg-sky-500 px-4 py-2 text-sm font-medium text-white"
            >
              复制班级总评
            </button>
          </div>
          <textarea
            value={props.classSummaryText}
            onChange={(event) => props.onClassSummaryChange(event.target.value)}
            className={`${fieldClass} min-h-[160px] leading-7`}
          />

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void props.onGenerate()}
              disabled={props.isGenerating}
              className="rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {props.isGenerating ? '生成中...' : '生成阶段反馈草稿'}
            </button>
            <button
              type="button"
              onClick={() => void props.onCopyAllStudents()}
              disabled={props.isSaving}
              className="rounded-2xl bg-sky-50 px-5 py-3 text-sm font-semibold text-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              复制全部学生反馈
            </button>
            <button
              type="button"
              onClick={() => void props.onConfirm()}
              disabled={props.isConfirming}
              className="rounded-2xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {props.isConfirming ? '确认中...' : '确认本次反馈'}
            </button>
          </div>

          <div className="space-y-4">
            {props.students.map((student) => (
              <article key={student.studentId} className="rounded-[22px] border border-slate-100 bg-slate-50/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-900">{student.name}</p>
                    <p className="mt-1 text-xs text-slate-500">{student.sourceSummary}</p>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-slate-600">
                    <input
                      type="checkbox"
                      checked={student.checked}
                      onChange={(event) => props.onStudentCheckedChange(student.studentId, event.target.checked)}
                    />
                    标记已检查
                  </label>
                </div>

                <div className="mt-4 space-y-3 rounded-[20px] border border-slate-100 bg-white/85 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">阶段变化</p>
                  <div className="flex flex-wrap gap-2">
                    {labelLookup.map((item) => {
                      const selected = student.highlightLabels.includes(item.label);
                      return (
                        <button
                          key={`${student.studentId}-${item.group}-${item.label}`}
                          type="button"
                          onClick={() => props.onHighlightToggle(student.studentId, item.label)}
                          className={`rounded-full px-3 py-1.5 text-sm transition ${
                            selected
                              ? 'bg-sky-500 text-white'
                              : 'border border-slate-200 bg-white text-slate-600 hover:border-sky-300 hover:text-sky-700'
                          }`}
                        >
                          {item.label}
                        </button>
                      );
                    })}
                  </div>
                  <textarea
                    value={student.highlightNote}
                    onChange={(event) => props.onHighlightNoteChange(student.studentId, event.target.value)}
                    placeholder="补充这一阶段特别想强调的变化"
                    className={`${fieldClass} min-h-[80px] leading-6`}
                  />
                </div>

                <textarea
                  value={student.finalText}
                  onChange={(event) => props.onStudentFinalTextChange(student.studentId, event.target.value)}
                  className={`${fieldClass} mt-4 min-h-[132px] leading-7`}
                />
              </article>
            ))}
          </div>
        </section>
      </div>
    </section>
  );
}
