import React, { useMemo } from 'react';

import {
  workspaceCardClass,
  workspaceFieldClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from './App';
import type {
  ClassFeedbackStageNotes,
  ClassFeedbackStudentCard,
  StageLabelGroup,
} from './classFeedbackGeneration';

interface ClassFeedbackGenerationWorkspaceProps {
  classNameLabel: string;
  teacherNameLabel: string;
  controlBar?: React.ReactNode;
  sourceSummaryItems: string[];
  labelGroups: StageLabelGroup[];
  classStatusTags: string[];
  students: ClassFeedbackStudentCard[];
  classSummaryText: string;
  statusMessage: string;
  draftStatusLabel: string;
  stageNotes: ClassFeedbackStageNotes;
  isGenerating: boolean;
  isSaving: boolean;
  isConfirming: boolean;
  onClassSummaryChange: (value: string) => void;
  onStageNoteChange: (key: keyof ClassFeedbackStageNotes, value: string) => void;
  onClassStatusTagToggle: (label: string) => void;
  onHighlightToggle: (studentId: number, label: string) => void;
  onHighlightNoteChange: (studentId: number, value: string) => void;
  onStudentFinalTextChange: (studentId: number, value: string) => void;
  onStudentCheckedChange: (studentId: number, checked: boolean) => void;
  onGenerate: () => void | Promise<void>;
  onSaveDraft: () => void | Promise<void>;
  onCopyClassSummary: () => void | Promise<void>;
  onCopyAllStudents: () => void | Promise<void>;
  onConfirm: () => void | Promise<void>;
}

export function ClassFeedbackGenerationWorkspace(props: ClassFeedbackGenerationWorkspaceProps) {
  const labelLookup = useMemo(
    () => props.labelGroups.flatMap((group) => group.labels.map((label) => ({ group: group.group, label }))),
    [props.labelGroups],
  );

  const cardClass = `${workspaceCardClass} p-6`;
  const softCardClass = `${workspaceSoftCardClass} p-4`;
  const fieldClass = workspaceFieldClass;
  const sectionTitleClass = 'text-xl font-semibold tracking-tight text-slate-900 dark:text-white';
  const sectionBodyClass = 'text-sm leading-relaxed text-slate-600 dark:text-slate-300';
  const helperLabelClass =
    'text-xs font-semibold uppercase tracking-[0.24em] text-slate-400 dark:text-slate-500';
  const toggleButtonClass = (selected: boolean) =>
    [
      'rounded-full border px-3.5 py-2 text-sm font-medium transition',
      selected
        ? 'border-sky-500 bg-sky-600 text-white shadow-sm shadow-sky-200/70 dark:border-sky-400 dark:bg-sky-500 dark:shadow-sky-500/10'
        : 'border-sky-200 bg-white/92 text-slate-700 hover:border-sky-300 hover:bg-sky-50 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:hover:bg-white/10',
    ].join(' ');

  return (
    <section className="space-y-6">
      <header className={cardClass}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-600 dark:text-sky-300">Class Feedback</p>
        <h3 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">课堂反馈</h3>
        {props.controlBar ? <div className="mt-4">{props.controlBar}</div> : null}
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          {props.classNameLabel} · {props.teacherNameLabel}
        </p>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{props.statusMessage}</p>
        <p className="mt-3 inline-flex w-fit rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
          {props.draftStatusLabel}
        </p>
      </header>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className={`${cardClass} space-y-6`}>
          <div>
            <h4 className={sectionTitleClass}>资料摘要</h4>
            <ul className={`mt-4 space-y-2 ${sectionBodyClass}`}>
              {props.sourceSummaryItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div>
            <h4 className={sectionTitleClass}>阶段备注</h4>
            <div className="mt-4 grid gap-3">
              <div className={softCardClass}>
                <p className={helperLabelClass}>班级状态标签</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {labelLookup.map((item) => {
                    const selected = props.classStatusTags.includes(item.label);
                    return (
                      <button
                        key={`class-status-${item.group}-${item.label}`}
                        type="button"
                        onClick={() => props.onClassStatusTagToggle(item.label)}
                        className={toggleButtonClass(selected)}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>
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

        </section>

        <section className={`${cardClass} space-y-6`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h4 className={sectionTitleClass}>班级总评</h4>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{props.statusMessage}</p>
            </div>
            <button
              type="button"
              onClick={() => void props.onCopyClassSummary()}
              className={`${workspaceSecondaryButtonClass} rounded-full px-4 py-2`}
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
              className={workspacePrimaryButtonClass}
            >
              {props.isGenerating ? '生成中...' : '生成阶段反馈草稿'}
            </button>
            <button
              type="button"
              onClick={() => void props.onCopyAllStudents()}
              disabled={props.isSaving}
              className={workspaceSecondaryButtonClass}
            >
              复制全部学生反馈
            </button>
            <button
              type="button"
              onClick={() => void props.onSaveDraft()}
              disabled={props.isSaving}
              className={workspaceSecondaryButtonClass}
            >
              {props.isSaving ? '保存中...' : '保存草稿'}
            </button>
            <button
              type="button"
              onClick={() => void props.onConfirm()}
              disabled={props.isConfirming}
              className={workspacePrimaryButtonClass}
            >
              {props.isConfirming ? '确认中...' : '确认本次反馈'}
            </button>
          </div>

          <div>
            <div className="flex items-center justify-between gap-3">
              <h4 className={sectionTitleClass}>学生反馈</h4>
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">按未检查优先排序</p>
            </div>
          </div>

          <div className="space-y-4">
            {props.students.map((student) => (
              <article key={student.studentId} className={`${workspaceSoftCardClass} p-4`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-base font-semibold text-slate-900 dark:text-white">{student.name}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{student.sourceSummary}</p>
                  </div>
                  <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                    <input
                      type="checkbox"
                      checked={student.checked}
                      onChange={(event) => props.onStudentCheckedChange(student.studentId, event.target.checked)}
                      className="h-4 w-4 rounded border-sky-300 text-sky-600 focus:ring-sky-500 dark:border-white/20 dark:bg-slate-900/70"
                    />
                    标记已检查
                  </label>
                </div>

                <div className={`mt-4 space-y-3 ${softCardClass}`}>
                  <p className={helperLabelClass}>阶段变化</p>
                  <div className="flex flex-wrap gap-2">
                    {labelLookup.map((item) => {
                      const selected = student.highlightLabels.includes(item.label);
                      return (
                        <button
                          key={`${student.studentId}-${item.group}-${item.label}`}
                          type="button"
                          onClick={() => props.onHighlightToggle(student.studentId, item.label)}
                          className={toggleButtonClass(selected)}
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
