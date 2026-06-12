import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PlusCircle, RefreshCw } from 'lucide-react';
import { ClassFeedbackGenerationWorkspace } from '../../ClassFeedbackGenerationWorkspace';
import {
  buildClassFeedbackPeriodPreview,
  buildCreateClassFeedbackTaskRequest,
  listClassStudents,
  buildClassFeedbackConfirmPayload,
  buildClassFeedbackStudentCards,
  confirmClassFeedbackTask,
  createClassFeedbackTask,
  defaultStageLabelGroups,
  formatClassFeedbackStudentCopyText,
  generateClassFeedbackTask,
  hasCompleteClassFeedbackGeneratedContent,
  isClassFeedbackTaskGenerating,
  loadClassFeedbackLabels,
  loadClassFeedbackTask,
  normalizeClassFeedbackTaskResponse,
  saveClassFeedbackTaskDraft,
  type ClassFeedbackStageNotes,
  type ClassFeedbackStudentCard,
  type ClassFeedbackPeriodGranularity,
  type ClassFeedbackPeriodSelection,
  type ClassFeedbackStageName,
  type StageLabelGroup,
} from '../../classFeedbackGeneration';
import { formatClassDisplayName } from '../../domain/classNaming';
import {
  apiFetch,
  getTodayIsoDate,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from '../../workspaceShared';
import type { ClassItem, CurrentUser } from '../../appTypes';

function getIsoWeekParts(dateString: string): { year: number; week: number } {
  const base = new Date(`${dateString}T12:00:00`);
  const thursday = new Date(base.getTime());
  const weekday = thursday.getDay() || 7;
  thursday.setDate(thursday.getDate() + 4 - weekday);

  const year = thursday.getFullYear();
  const firstThursday = new Date(`${year}-01-04T12:00:00`);
  const firstWeekday = firstThursday.getDay() || 7;
  firstThursday.setDate(firstThursday.getDate() + 4 - firstWeekday);

  const diffDays = Math.round((thursday.getTime() - firstThursday.getTime()) / 86_400_000);
  return {
    year,
    week: Math.floor(diffDays / 7) + 1,
  };
}

function inferClassFeedbackStageName(dateString: string): ClassFeedbackStageName {
  const month = Number(dateString.slice(5, 7));
  if (month >= 3 && month <= 5) {
    return '春季';
  }
  if (month >= 7 && month <= 8) {
    return '暑假';
  }
  if (month >= 9 && month <= 11) {
    return '秋季';
  }
  return '寒假';
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

function createEmptyClassFeedbackStageNotes(): ClassFeedbackStageNotes {
  return {
    classStatusNote: '',
    parentFeedbackNote: '',
    teachingFocusNote: '',
    nextStagePreviewNote: '',
  };
}

function createEmptyClassFeedbackStudentCards(roster: Array<{ id: number; name: string }>): ClassFeedbackStudentCard[] {
  return roster.map((student) => ({
    studentId: student.id,
    name: student.name,
    aiDraft: '',
    finalText: '',
    checked: false,
    sourceSummary: '等待补充课堂反馈素材',
    highlightLabels: [],
    highlightNote: '',
  }));
}

function buildClassFeedbackDraftSnapshot(summary: string, students: ClassFeedbackStudentCard[]): string {
  return JSON.stringify({
    classSummary: summary,
    students: students.map((student) => ({
      studentId: student.studentId,
      finalText: student.finalText,
    })),
  });
}

type ClassFeedbackGenerationPageProps = {
  currentUser: CurrentUser;
};

export function ClassFeedbackGenerationPage({ currentUser }: ClassFeedbackGenerationPageProps) {
  const todayIsoDate = getTodayIsoDate();
  const initialIsoWeek = getIsoWeekParts(todayIsoDate);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [labelGroups, setLabelGroups] = useState<StageLabelGroup[]>(defaultStageLabelGroups);
  const [classesLoading, setClassesLoading] = useState(true);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [classFeedbackPeriodMode, setClassFeedbackPeriodMode] = useState<ClassFeedbackPeriodGranularity>('weekly');
  const [classFeedbackAnchorDate, setClassFeedbackAnchorDate] = useState(todayIsoDate);
  const [classFeedbackPeriodYear, setClassFeedbackPeriodYear] = useState(initialIsoWeek.year);
  const [classFeedbackPeriodWeek, setClassFeedbackPeriodWeek] = useState(initialIsoWeek.week);
  const [classFeedbackPeriodMonth, setClassFeedbackPeriodMonth] = useState(Number(todayIsoDate.slice(5, 7)));
  const [classFeedbackStageName, setClassFeedbackStageName] = useState<ClassFeedbackStageName>(
    inferClassFeedbackStageName(todayIsoDate),
  );
  const [activeClassFeedbackTaskId, setActiveClassFeedbackTaskId] = useState<number | null>(null);
  const [classFeedbackStudents, setClassFeedbackStudents] = useState<ClassFeedbackStudentCard[]>([]);
  const [classFeedbackSummary, setClassFeedbackSummary] = useState('');
  const [classFeedbackStatusMessage, setClassFeedbackStatusMessage] = useState('先选择班级和反馈阶段，再汇总阶段素材。');
  const [classFeedbackStageNotes, setClassFeedbackStageNotes] = useState<ClassFeedbackStageNotes>(
    createEmptyClassFeedbackStageNotes(),
  );
  const [classFeedbackStatusTags, setClassFeedbackStatusTags] = useState<string[]>([]);
  const [teacherNameLabel, setTeacherNameLabel] = useState(currentUser.display_name);
  const [currentTaskStatus, setCurrentTaskStatus] = useState<string>('draft');
  const [matchedLessonCount, setMatchedLessonCount] = useState(0);
  const [isRefreshingTask, setIsRefreshingTask] = useState(false);
  const [isGeneratingClassFeedback, setIsGeneratingClassFeedback] = useState(false);
  const [isSavingClassFeedback, setIsSavingClassFeedback] = useState(false);
  const [isConfirmingClassFeedback, setIsConfirmingClassFeedback] = useState(false);
  const classFeedbackDraftSnapshotRef = useRef('');

  const selectedClass = classes.find((item) => item.id === selectedClassId) ?? null;
  const classFeedbackPeriodSelection = useMemo<ClassFeedbackPeriodSelection>(() => {
    if (classFeedbackPeriodMode === 'daily') {
      return {
        periodGranularity: 'daily',
        anchorDate: classFeedbackAnchorDate,
      };
    }
    if (classFeedbackPeriodMode === 'weekly') {
      return {
        periodGranularity: 'weekly',
        year: classFeedbackPeriodYear,
        week: classFeedbackPeriodWeek,
      };
    }
    if (classFeedbackPeriodMode === 'monthly') {
      return {
        periodGranularity: 'monthly',
        year: classFeedbackPeriodYear,
        month: classFeedbackPeriodMonth,
      };
    }
    return {
      periodGranularity: 'stage',
      year: classFeedbackPeriodYear,
      stageName: classFeedbackStageName,
    };
  }, [
    classFeedbackAnchorDate,
    classFeedbackPeriodMode,
    classFeedbackPeriodMonth,
    classFeedbackPeriodWeek,
    classFeedbackPeriodYear,
    classFeedbackStageName,
  ]);
  const classFeedbackPeriodPreview = useMemo(
    () => buildClassFeedbackPeriodPreview(classFeedbackPeriodSelection),
    [classFeedbackPeriodSelection],
  );
  const classFeedbackPeriodYearOptions = useMemo(
    () => [classFeedbackPeriodYear - 1, classFeedbackPeriodYear, classFeedbackPeriodYear + 1],
    [classFeedbackPeriodYear],
  );

  const resetClassFeedbackWorkspaceState = useCallback((statusMessage = '先选择班级和反馈阶段，再汇总阶段素材。') => {
    setActiveClassFeedbackTaskId(null);
    setCurrentTaskStatus('draft');
    setTeacherNameLabel(currentUser.display_name);
    setClassFeedbackSummary('');
    setClassFeedbackStatusTags([]);
    setClassFeedbackStageNotes(createEmptyClassFeedbackStageNotes());
    setClassFeedbackStudents([]);
    setMatchedLessonCount(0);
    classFeedbackDraftSnapshotRef.current = '';
    setClassFeedbackStatusMessage(statusMessage);
  }, [currentUser.display_name]);

  const loadRosterOnly = useCallback(async (classId: number) => {
    const roster = await listClassStudents(classId);
    setClassFeedbackStudents(createEmptyClassFeedbackStudentCards(roster.students));
    return roster.students.length;
  }, []);

  const hydrateClassFeedbackTask = useCallback(async (taskId: number, classId: number) => {
    setIsRefreshingTask(true);
    try {
      const [rawTask, roster] = await Promise.all([
        loadClassFeedbackTask(taskId),
        listClassStudents(classId),
      ]);
      const task = normalizeClassFeedbackTaskResponse(rawTask);
      if (!task) {
        throw new Error('反馈任务响应格式异常，请刷新后重试。');
      }
      const hydratedStudents = buildClassFeedbackStudentCards({
        roster: roster.students,
        task,
      });
      const hydratedSummary =
        task.class_summary_final_text?.trim() ? task.class_summary_final_text : task.class_summary_ai_draft ?? '';
      setActiveClassFeedbackTaskId(task.id);
      setSelectedClassId(task.class_id);
      setTeacherNameLabel(task.teacher_name_snapshot || selectedClass?.teacher_name || currentUser.display_name);
      setClassFeedbackStatusTags(task.class_status_tags ?? []);
      setClassFeedbackStageNotes({
        classStatusNote: task.class_status_note ?? '',
        parentFeedbackNote: task.parent_feedback_note ?? '',
        teachingFocusNote: task.teaching_focus_note ?? '',
        nextStagePreviewNote: task.next_stage_preview_note ?? '',
      });
      setClassFeedbackStudents(hydratedStudents);
      setClassFeedbackSummary(hydratedSummary);
      setCurrentTaskStatus(task.status);
      classFeedbackDraftSnapshotRef.current = buildClassFeedbackDraftSnapshot(hydratedSummary, hydratedStudents);
      const isGeneratingTask = isClassFeedbackTaskGenerating(task);
      setClassFeedbackStatusMessage(
        isGeneratingTask
          ? '课堂反馈仍在生成中，请稍后点击刷新任务。'
          : task.status === 'confirmed'
            ? `已确认 ${roster.students.length} 名学生反馈，可直接复制内容。`
            : `已同步 ${roster.students.length} 名学生，可补充阶段备注并生成草稿。`,
      );
      return task;
    } finally {
      setIsRefreshingTask(false);
    }
  }, [currentUser.display_name, selectedClass?.teacher_name]);

  useEffect(() => {
    let cancelled = false;
    setClassesLoading(true);
    Promise.all([apiFetch<ClassItem[]>('/api/classes'), loadClassFeedbackLabels()])
      .then(([classItems, labelResult]) => {
        if (cancelled) {
          return;
        }
        setClasses(classItems);
        setSelectedClassId((current) => syncMemberScopedClassSelection(currentUser.role, classItems, current));
        setLabelGroups(labelResult.groups?.length ? labelResult.groups : defaultStageLabelGroups);
      })
      .catch((error) => {
        if (!cancelled) {
          setClassFeedbackStatusMessage(error instanceof Error ? error.message : '课堂反馈初始化失败，请刷新重试。');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setClassesLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser.role]);

  useEffect(() => {
    if (classesLoading || currentUser.role !== 'member') {
      return;
    }

    const nextClassId = syncMemberScopedClassSelection(currentUser.role, classes, selectedClassId);
    if (nextClassId === selectedClassId) {
      return;
    }

    resetClassFeedbackWorkspaceState('班级权限已变化，请重新同步反馈任务。');
    setTeacherNameLabel(
      nextClassId
        ? classes.find((item) => item.id === nextClassId)?.teacher_name || currentUser.display_name
        : currentUser.display_name,
    );
    setSelectedClassId(nextClassId);
  }, [classes, classesLoading, currentUser.display_name, currentUser.role, resetClassFeedbackWorkspaceState, selectedClassId]);

  useEffect(() => {
    if (classesLoading || currentUser.role === 'member' || selectedClassId === null) {
      return;
    }

    if (classes.some((item) => item.id === selectedClassId)) {
      return;
    }

    resetClassFeedbackWorkspaceState('班级权限已变化，请重新同步反馈任务。');
    setSelectedClassId(null);
  }, [classes, classesLoading, currentUser.role, resetClassFeedbackWorkspaceState, selectedClassId]);

  useEffect(() => {
    if (!selectedClassId) {
      setMatchedLessonCount(0);
      return;
    }

    let cancelled = false;
    apiFetch<Array<{ class_id: number | null; date: string }>>('/api/review-plans')
      .then((lessons) => {
        if (cancelled) {
          return;
        }
        const count = lessons.filter(
          (lesson) =>
            lesson.class_id === selectedClassId &&
            lesson.date >= classFeedbackPeriodPreview.startDate &&
            lesson.date <= classFeedbackPeriodPreview.endDate,
        ).length;
        setMatchedLessonCount(count);
      })
      .catch(() => {
        if (!cancelled) {
          setMatchedLessonCount(0);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [classFeedbackPeriodPreview.endDate, classFeedbackPeriodPreview.startDate, selectedClassId]);

  const handleClassChange = async (nextClassId: number | null) => {
    setSelectedClassId(nextClassId);
    resetClassFeedbackWorkspaceState();
    setTeacherNameLabel(nextClassId ? classes.find((item) => item.id === nextClassId)?.teacher_name || currentUser.display_name : currentUser.display_name);

    if (!nextClassId) {
      return;
    }

    setIsRefreshingTask(true);
    try {
      const studentCount = await loadRosterOnly(nextClassId);
      setClassFeedbackStatusMessage(
        studentCount > 0
          ? `已同步 ${studentCount} 名学生，请选择反馈阶段后创建反馈任务。`
          : '当前班级还没有学生，请先到学生管理页面添加学生。',
      );
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '班级学生同步失败，请重试。');
    } finally {
      setIsRefreshingTask(false);
    }
  };

  const handleCreateClassFeedbackTask = useCallback(async () => {
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsSavingClassFeedback(true);
    try {
      const created = await createClassFeedbackTask({
        ...buildCreateClassFeedbackTaskRequest({
          classId: selectedClassId,
          ...classFeedbackPeriodSelection,
        }),
      });
      await hydrateClassFeedbackTask(created.id, selectedClassId);
      setClassFeedbackStatusMessage(`已创建反馈任务，按 ${created.period_granularity} 粒度准备资料。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '创建课堂反馈任务失败，请重试。');
    } finally {
      setIsSavingClassFeedback(false);
    }
  }, [classFeedbackPeriodSelection, hydrateClassFeedbackTask, selectedClassId]);

  const handleRefreshClassFeedbackTask = useCallback(async () => {
    if (!activeClassFeedbackTaskId || !selectedClassId) {
      return;
    }

    try {
      await hydrateClassFeedbackTask(activeClassFeedbackTaskId, selectedClassId);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '刷新反馈任务失败，请重试。');
    }
  }, [activeClassFeedbackTaskId, hydrateClassFeedbackTask, selectedClassId]);

  const handleStageNoteChange = (key: keyof ClassFeedbackStageNotes, value: string) => {
    setClassFeedbackStageNotes((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleClassStatusTagToggle = (label: string) => {
    setClassFeedbackStatusTags((current) =>
      current.includes(label) ? current.filter((item) => item !== label) : [...current, label],
    );
  };

  const handleHighlightToggle = (studentId: number, label: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => {
        if (student.studentId !== studentId) {
          return student;
        }
        const alreadySelected = student.highlightLabels.includes(label);
        return {
          ...student,
          highlightLabels: alreadySelected
            ? student.highlightLabels.filter((item) => item !== label)
            : [...student.highlightLabels, label],
        };
      }),
    );
  };

  const handleHighlightNoteChange = (studentId: number, value: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, highlightNote: value } : student)),
    );
  };

  const handleStudentFinalTextChange = (studentId: number, value: string) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, finalText: value } : student)),
    );
  };

  const handleStudentCheckedChange = (studentId: number, checked: boolean) => {
    setClassFeedbackStudents((current) =>
      current.map((student) => (student.studentId === studentId ? { ...student, checked } : student)),
    );
  };

  const saveCurrentClassFeedbackDraft = useCallback(async () => {
    if (!activeClassFeedbackTaskId || currentTaskStatus === 'confirmed') {
      return;
    }

    const nextSnapshot = buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents);
    if (nextSnapshot === classFeedbackDraftSnapshotRef.current) {
      return;
    }

    setIsSavingClassFeedback(true);
    try {
      const savedTask = await saveClassFeedbackTaskDraft(activeClassFeedbackTaskId, {
        classSummaryDraftText: classFeedbackSummary,
        studentEntries: classFeedbackStudents.map((student) => ({
          studentId: student.studentId,
          finalText: student.finalText,
        })),
      });
      const savedStudents = buildClassFeedbackStudentCards({
        roster: classFeedbackStudents.map((student) => ({
          id: student.studentId,
          name: student.name,
        })),
        task: savedTask,
      }).map((student) => {
        const currentCard = classFeedbackStudents.find((item) => item.studentId === student.studentId);
        return currentCard
          ? {
              ...student,
              checked: currentCard.checked,
              highlightLabels: currentCard.highlightLabels,
              highlightNote: currentCard.highlightNote,
            }
          : student;
      });
      setClassFeedbackSummary(savedTask.class_summary_ai_draft ?? '');
      setClassFeedbackStudents(savedStudents);
      classFeedbackDraftSnapshotRef.current = buildClassFeedbackDraftSnapshot(
        savedTask.class_summary_ai_draft ?? '',
        savedStudents,
      );
      setClassFeedbackStatusMessage('课堂反馈草稿已保存。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '保存课堂反馈草稿失败，请重试。');
    } finally {
      setIsSavingClassFeedback(false);
    }
  }, [activeClassFeedbackTaskId, classFeedbackStudents, classFeedbackSummary, currentTaskStatus]);

  useEffect(() => {
    if (!activeClassFeedbackTaskId || currentTaskStatus === 'confirmed' || isRefreshingTask || isGeneratingClassFeedback || isConfirmingClassFeedback) {
      return;
    }
    const nextSnapshot = buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents);
    if (nextSnapshot === classFeedbackDraftSnapshotRef.current) {
      return;
    }
    const timer = window.setTimeout(() => {
      void saveCurrentClassFeedbackDraft();
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStudents,
    classFeedbackSummary,
    currentTaskStatus,
    isConfirmingClassFeedback,
    isGeneratingClassFeedback,
    isRefreshingTask,
    saveCurrentClassFeedbackDraft,
  ]);

  const handleGenerateClassFeedback = useCallback(async () => {
    if (!activeClassFeedbackTaskId) {
      setClassFeedbackStatusMessage('请先创建反馈任务。');
      return;
    }
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsGeneratingClassFeedback(true);
    try {
      const rawGenerated = await generateClassFeedbackTask(activeClassFeedbackTaskId, {
        classStatusTags: classFeedbackStatusTags,
        classStatusNote: classFeedbackStageNotes.classStatusNote,
        parentFeedbackNote: classFeedbackStageNotes.parentFeedbackNote,
        teachingFocusNote: classFeedbackStageNotes.teachingFocusNote,
        nextStagePreviewNote: classFeedbackStageNotes.nextStagePreviewNote,
        studentHighlights: classFeedbackStudents.map((student) => ({
          studentId: student.studentId,
          labels: student.highlightLabels,
          note: student.highlightNote,
        })),
      });
      const generated = normalizeClassFeedbackTaskResponse(rawGenerated, { fallbackClassId: selectedClassId });
      if (!generated) {
        throw new Error('反馈任务响应格式异常，请刷新后重试。');
      }
      const hydratedTask = await hydrateClassFeedbackTask(generated.id, selectedClassId);
      if (isClassFeedbackTaskGenerating(hydratedTask)) {
        setClassFeedbackStatusMessage('课堂反馈仍在生成中，请稍后点击刷新任务。');
        return;
      }
      if (!hasCompleteClassFeedbackGeneratedContent(hydratedTask, classFeedbackStudents.length)) {
        setClassFeedbackStatusMessage('反馈任务已返回，但生成内容不完整，请点击刷新任务确认。');
        return;
      }
      setClassFeedbackStatusMessage(`已生成班级总评和 ${classFeedbackStudents.length} 名学生反馈草稿。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '生成课堂反馈失败，请重试。');
    } finally {
      setIsGeneratingClassFeedback(false);
    }
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStageNotes.classStatusNote,
    classFeedbackStageNotes.nextStagePreviewNote,
    classFeedbackStageNotes.parentFeedbackNote,
    classFeedbackStageNotes.teachingFocusNote,
    classFeedbackStatusTags,
    classFeedbackStudents,
    hydrateClassFeedbackTask,
    selectedClassId,
  ]);

  const handleCopyClassFeedbackSummary = async () => {
    if (!classFeedbackSummary.trim()) {
      setClassFeedbackStatusMessage('当前还没有可复制的班级总评。');
      return;
    }
    try {
      await navigator.clipboard.writeText(classFeedbackSummary.trim());
      setClassFeedbackStatusMessage('班级总评已复制到剪贴板。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '复制班级总评失败，请重试。');
    }
  };

  const handleCopyAllClassFeedbackStudents = async () => {
    const content = formatClassFeedbackStudentCopyText(sortedClassFeedbackStudents);
    if (!content) {
      setClassFeedbackStatusMessage('当前还没有可复制的学生反馈。');
      return;
    }
    try {
      await navigator.clipboard.writeText(content);
      setClassFeedbackStatusMessage('全部学生反馈已复制到剪贴板。');
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '复制学生反馈失败，请重试。');
    }
  };

  const handleConfirmClassFeedback = useCallback(async () => {
    if (!activeClassFeedbackTaskId) {
      setClassFeedbackStatusMessage('请先创建反馈任务。');
      return;
    }
    if (!selectedClassId) {
      setClassFeedbackStatusMessage('请先选择班级。');
      return;
    }

    setIsConfirmingClassFeedback(true);
    try {
      const payload = buildClassFeedbackConfirmPayload({
        classSummaryFinalText: classFeedbackSummary,
        students: classFeedbackStudents,
      });
      const confirmed = await confirmClassFeedbackTask(activeClassFeedbackTaskId, payload);
      await hydrateClassFeedbackTask(confirmed.id, selectedClassId);
      setClassFeedbackStatusMessage(`已确认 ${classFeedbackStudents.length} 名学生反馈，并写入后续积累。`);
    } catch (error) {
      setClassFeedbackStatusMessage(error instanceof Error ? error.message : '确认课堂反馈失败，请重试。');
    } finally {
      setIsConfirmingClassFeedback(false);
    }
  }, [
    activeClassFeedbackTaskId,
    classFeedbackStudents,
    classFeedbackSummary,
    hydrateClassFeedbackTask,
    selectedClassId,
  ]);

  const checkedStudentCount = useMemo(
    () => classFeedbackStudents.filter((student) => student.checked).length,
    [classFeedbackStudents],
  );
  const uncheckedStudentCount = classFeedbackStudents.length - checkedStudentCount;
  const studentsWithHighlightsCount = useMemo(
    () =>
      classFeedbackStudents.filter(
        (student) => student.highlightLabels.length > 0 || student.highlightNote.trim(),
      ).length,
    [classFeedbackStudents],
  );
  const studentsAwaitingDraftCount = useMemo(
    () =>
      classFeedbackStudents.filter(
        (student) => !(student.finalText || student.aiDraft).trim(),
      ).length,
    [classFeedbackStudents],
  );
  const sortedClassFeedbackStudents = useMemo(
    () =>
      [...classFeedbackStudents].sort((left, right) => {
        if (left.checked !== right.checked) {
          return left.checked ? 1 : -1;
        }
        return left.name.localeCompare(right.name, 'zh-CN');
      }),
    [classFeedbackStudents],
  );
  const hasUnsavedDraftChanges =
    activeClassFeedbackTaskId !== null &&
    currentTaskStatus !== 'confirmed' &&
    buildClassFeedbackDraftSnapshot(classFeedbackSummary, classFeedbackStudents) !==
      classFeedbackDraftSnapshotRef.current;
  const classFeedbackDraftStatusLabel = currentTaskStatus === 'confirmed'
    ? '本次反馈已确认。'
    : !activeClassFeedbackTaskId
      ? '创建反馈任务后开始记录草稿。'
      : isSavingClassFeedback
        ? '正在保存草稿...'
        : hasUnsavedDraftChanges
          ? '有未保存修改，自动保存中。'
          : '草稿已保存。';

  const selectedClassDisplayName = getCurrentClassDisplayName(selectedClass);
  const sourceSummaryItems = [
    selectedClassDisplayName ? `当前班级：${selectedClassDisplayName}` : '当前班级：未选择',
    `反馈阶段：${classFeedbackPeriodPreview.label}`,
    `覆盖范围：${classFeedbackPeriodPreview.startDate} 至 ${classFeedbackPeriodPreview.endDate}`,
    `已命中 ${matchedLessonCount} 节课次记录`,
    `学生人数：${classFeedbackStudents.length} 名`,
    `已检查 ${checkedStudentCount} 名，待检查 ${uncheckedStudentCount} 名`,
    `已标记 ${studentsWithHighlightsCount} 名学生的阶段变化`,
    `已选择 ${classFeedbackStatusTags.length} 个班级状态标签`,
    ...(studentsAwaitingDraftCount > 0
      ? [`仍有 ${studentsAwaitingDraftCount} 名学生等待生成或补充反馈`]
      : []),
    `任务状态：${currentTaskStatus === 'confirmed' ? '已确认' : activeClassFeedbackTaskId ? '草稿中' : '待创建'}`,
    ...(selectedClassId && matchedLessonCount <= 1
      ? ['当前阶段课次较少，建议补充阶段备注帮助生成更稳定。']
      : []),
  ];
  const classFeedbackControlBar = (
    <div className="grid gap-3 sm:grid-cols-2 xl:max-w-[43rem] xl:grid-cols-4">
      <select
        value={selectedClassId ?? ''}
        onChange={(event) => void handleClassChange(event.target.value ? Number(event.target.value) : null)}
        className={workspaceFieldClass}
        disabled={classesLoading || isRefreshingTask || isSavingClassFeedback}
      >
        <option value="">选择班级</option>
        {classes.map((item) => (
          <option key={item.id} value={item.id}>
            {getCurrentClassDisplayName(item)}
          </option>
        ))}
      </select>
      <select
        value={classFeedbackPeriodMode}
        onChange={(event) => setClassFeedbackPeriodMode(event.target.value as ClassFeedbackPeriodGranularity)}
        className={workspaceFieldClass}
        disabled={isRefreshingTask || isSavingClassFeedback}
      >
        <option value="daily">按日</option>
        <option value="weekly">按周</option>
        <option value="monthly">按月</option>
        <option value="stage">按阶段</option>
      </select>
      {classFeedbackPeriodMode === 'daily' ? (
        <input
          type="date"
          value={classFeedbackAnchorDate}
          onChange={(event) => setClassFeedbackAnchorDate(event.target.value)}
          className={workspaceFieldClass}
          disabled={isRefreshingTask || isSavingClassFeedback}
        />
      ) : classFeedbackPeriodMode === 'weekly' ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackPeriodWeek}
            onChange={(event) => setClassFeedbackPeriodWeek(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {Array.from({ length: 53 }, (_, index) => index + 1).map((week) => (
              <option key={week} value={week}>
                第 {week} 周
              </option>
            ))}
          </select>
        </div>
      ) : classFeedbackPeriodMode === 'monthly' ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackPeriodMonth}
            onChange={(event) => setClassFeedbackPeriodMonth(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
              <option key={month} value={month}>
                {month} 月
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:col-span-2 xl:grid-cols-2">
          <select
            value={classFeedbackPeriodYear}
            onChange={(event) => setClassFeedbackPeriodYear(Number(event.target.value))}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {classFeedbackPeriodYearOptions.map((year) => (
              <option key={year} value={year}>
                {year} 年
              </option>
            ))}
          </select>
          <select
            value={classFeedbackStageName}
            onChange={(event) => setClassFeedbackStageName(event.target.value as ClassFeedbackStageName)}
            className={workspaceFieldClass}
            disabled={isRefreshingTask || isSavingClassFeedback}
          >
            {(['春季', '暑假', '秋季', '寒假'] as ClassFeedbackStageName[]).map((stageName) => (
              <option key={stageName} value={stageName}>
                {stageName}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
  const classFeedbackHeaderAside = (
    <div className="flex flex-col gap-3 xl:min-h-[10.5rem] xl:justify-between">
      <div className="min-w-0 rounded-2xl border border-slate-200 bg-white/85 px-4 py-3 text-left shadow-sm dark:border-white/10 dark:bg-slate-950/55">
        <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">当前周期</div>
        <div className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{classFeedbackPeriodPreview.label}</div>
        <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          {classFeedbackPeriodPreview.startDate} 至 {classFeedbackPeriodPreview.endDate}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => void handleCreateClassFeedbackTask()}
          disabled={!selectedClassId || isSavingClassFeedback}
          className={`${workspacePrimaryButtonClass} w-full justify-center`}
        >
          <PlusCircle size={18} />
          创建反馈任务
        </button>
        <button
          type="button"
          onClick={() => void handleRefreshClassFeedbackTask()}
          disabled={!activeClassFeedbackTaskId || isRefreshingTask}
          className={`${workspaceSecondaryButtonClass} w-full justify-center`}
        >
          <RefreshCw size={18} />
          刷新任务
        </button>
      </div>
    </div>
  );

  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <ClassFeedbackGenerationWorkspace
        classNameLabel={selectedClassDisplayName || '未选择班级'}
        teacherNameLabel={teacherNameLabel}
        controlBar={classFeedbackControlBar}
        headerAside={classFeedbackHeaderAside}
        sourceSummaryItems={sourceSummaryItems}
        labelGroups={labelGroups}
        classStatusTags={classFeedbackStatusTags}
        students={sortedClassFeedbackStudents}
        classSummaryText={classFeedbackSummary}
        statusMessage={classFeedbackStatusMessage}
        draftStatusLabel={classFeedbackDraftStatusLabel}
        stageNotes={classFeedbackStageNotes}
        isGenerating={isGeneratingClassFeedback}
        isSaving={isRefreshingTask || isSavingClassFeedback}
        isConfirming={isConfirmingClassFeedback}
        onClassSummaryChange={setClassFeedbackSummary}
        onStageNoteChange={handleStageNoteChange}
        onClassStatusTagToggle={handleClassStatusTagToggle}
        onHighlightToggle={handleHighlightToggle}
        onHighlightNoteChange={handleHighlightNoteChange}
        onStudentFinalTextChange={handleStudentFinalTextChange}
        onStudentCheckedChange={handleStudentCheckedChange}
        onGenerate={handleGenerateClassFeedback}
        onSaveDraft={saveCurrentClassFeedbackDraft}
        onCopyClassSummary={handleCopyClassFeedbackSummary}
        onCopyAllStudents={handleCopyAllClassFeedbackStudents}
        onConfirm={handleConfirmClassFeedback}
      />
    </div>
  );
}
