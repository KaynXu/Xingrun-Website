import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, RefreshCw, X } from 'lucide-react';

import {
  apiFetch,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from './App';
import {
  buildMemberStudentNotebookSummaries,
  buildWeeklyWrongQuestionFollowupArchivePath,
  buildWeeklyWrongQuestionFollowupMessagePath,
  buildWeeklyWrongQuestionFollowupsPath,
  buildWrongQuestionDetailPath,
  buildWrongQuestionPracticeSheetsPath,
  buildWrongQuestionReviewDraft,
  buildWrongQuestionQuery,
  buildWrongQuestionReviewPayload,
  buildWrongQuestionReviewPath,
  buildWrongQuestionTopicSummaries,
  filterWrongQuestionRecordsByTopic,
  filterWrongQuestionRecordsForMemberNotebook,
  getWrongQuestionSemanticModel,
  getWrongQuestionSourceLabel,
  hydrateWrongQuestionReviewDraftFromDetail,
  isWechatMiniProgramWrongQuestionRecord,
  normalizeWeeklyWrongQuestionFollowupResponse,
  normalizeWrongQuestionPracticeSheetListResponse,
  normalizeWrongQuestionRecord,
  normalizeWrongQuestionListResponse,
  resolveSavedWrongQuestionRecord,
  summarizeWrongQuestionRecords,
  type MemberStudentNotebookSummary,
  type WeeklyWrongQuestionFollowupItem,
  type WrongQuestionPracticeSheetListApiResponse,
  type WrongQuestionPracticeSheetSummary,
  type WrongQuestionFilters,
  type WrongQuestionListApiResponse,
  type WrongQuestionRecord,
  type WrongQuestionReviewDraft,
  type WrongQuestionSummary,
} from './smartWrongQuestions';
import { buildWrongQuestionLatexPreviewModel } from './wrongQuestionLatex.js';

type SmartWrongQuestionsPageProps = {
  currentUser: {
    display_name: string;
    organization_name: string;
    role: 'super_owner' | 'owner' | 'admin' | 'member';
  };
};

type WrongQuestionClassFilterOption = {
  id: number;
  name: string;
  subject: string;
  teacherUserId: number | null;
};

type WrongQuestionTeacherFilterOption = {
  id: number;
  name: string;
};

type WrongQuestionStudentFilterOption = {
  id: number;
  name: string;
};

type NotebookModalView = 'questions' | 'practice_history';

const WRONG_QUESTION_ERROR_TYPE_OPTIONS = [
  '知识点问题',
  '细节问题',
  '方法问题',
  '审题问题',
];

const WRONG_QUESTION_TOPIC_CATEGORY_OPTIONS = [
  '未分类',
  '计算',
  '经济',
  '浓度',
  '工程',
  '行程',
  '几何',
  '数论',
];

const initialFilters: WrongQuestionFilters = {
  studentName: '',
  className: '',
  subject: '',
  teacherName: '',
  errorType: '',
};

function hasSnapshotDifference(canonicalValue: string, snapshotValue: string): boolean {
  const canonical = canonicalValue.trim();
  const snapshot = snapshotValue.trim();
  return Boolean(snapshot) && snapshot !== canonical;
}

function getWrongQuestionSourceBadgeClass(source: string): string {
  return source === 'wechat_mp'
    ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300'
    : 'border-sky-200 bg-white/80 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300';
}

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function canGenerateWrongQuestionPractice(record: WrongQuestionRecord): boolean {
  return record.source === 'wechat_mp'
    && Boolean(record.studentId)
    && record.recognitionStatus === 'recognized'
    && !record.isMastered;
}

function getWrongQuestionPracticeStatusLabel(status: string): string {
  if (status === 'ready') {
    return '已完成';
  }
  if (status === 'failed') {
    return '生成失败';
  }
  return '生成中';
}

function readWrongQuestionToken(): string {
  try {
    return globalThis.localStorage?.getItem?.('xr_token') || '';
  } catch {
    return '';
  }
}

function normalizeStudentLibraryPdfPath(path: string): string {
  const normalizedPath = path.trim();
  if (!normalizedPath) {
    return '';
  }
  if (/^(https?:\/\/|\/api\/)/.test(normalizedPath)) {
    return normalizedPath;
  }
  const studentLibraryMatch = normalizedPath.match(/(?:^|\/)student-(\d+)\.pdf$/i);
  if (studentLibraryMatch) {
    return `/api/wechat/student-libraries/${studentLibraryMatch[1]}`;
  }
  return normalizedPath;
}

function buildWrongQuestionAuthedPath(path: string): string {
  const normalizedPath = normalizeStudentLibraryPdfPath(path);
  if (!normalizedPath) {
    return '';
  }
  const token = readWrongQuestionToken();
  if (!token) {
    return normalizedPath;
  }
  const separator = normalizedPath.includes('?') ? '&' : '?';
  return `${normalizedPath}${separator}token=${encodeURIComponent(token)}`;
}

function getCurrentMondayDateInputValue(): string {
  const date = new Date();
  const day = date.getDay();
  const daysSinceMonday = day === 0 ? 6 : day - 1;
  date.setDate(date.getDate() - daysSinceMonday);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const dayOfMonth = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${dayOfMonth}`;
}

function parseWeeklyFollowupMessageId(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function normalizeWeeklyFollowupSourceRecordIds(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => String(item ?? '').trim())
    .filter(Boolean);
}

function extractGeneratedWeeklyFollowupMessage(response: unknown): WeeklyWrongQuestionFollowupItem['message'] {
  if (!isObjectRecord(response) || !isObjectRecord(response.message)) {
    return null;
  }

  const message = response.message;
  const messageText = typeof message.message_text === 'string'
    ? message.message_text
    : typeof message.messageText === 'string'
      ? message.messageText
      : '';
  const sourceRecordIds = Object.prototype.hasOwnProperty.call(message, 'source_record_ids')
    ? normalizeWeeklyFollowupSourceRecordIds(message.source_record_ids)
    : normalizeWeeklyFollowupSourceRecordIds(message.sourceRecordIds);

  return {
    id: parseWeeklyFollowupMessageId(message.id),
    messageText,
    sourceRecordIds,
  };
}

function extractSavedWrongQuestionResponseRecord(response: unknown): unknown {
  if (!isObjectRecord(response)) {
    return undefined;
  }

  if (Object.prototype.hasOwnProperty.call(response, 'record')) {
    return response.record;
  }

  if (
    Object.prototype.hasOwnProperty.call(response, 'id')
    || Object.prototype.hasOwnProperty.call(response, 'analysis')
    || Object.prototype.hasOwnProperty.call(response, 'student_name')
    || Object.prototype.hasOwnProperty.call(response, 'studentName')
  ) {
    return response;
  }

  return undefined;
}

export function SmartWrongQuestionsPage({ currentUser }: SmartWrongQuestionsPageProps) {
  const hasStaffScope = currentUser.role === 'super_owner' || currentUser.role === 'owner' || currentUser.role === 'admin';
  const isMemberScope = currentUser.role === 'member';
  const usesStudentNotebook = true;
  const [filters, setFilters] = useState<WrongQuestionFilters>(initialFilters);
  const [records, setRecords] = useState<WrongQuestionRecord[]>([]);
  const [classOptions, setClassOptions] = useState<WrongQuestionClassFilterOption[]>([]);
  const [teacherOptions, setTeacherOptions] = useState<WrongQuestionTeacherFilterOption[]>([]);
  const [studentOptions, setStudentOptions] = useState<WrongQuestionStudentFilterOption[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [selectedStudentName, setSelectedStudentName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [savingReview, setSavingReview] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [pdfRefreshNotice, setPdfRefreshNotice] = useState('');
  const [refreshingLibraryPdf, setRefreshingLibraryPdf] = useState(false);
  const [reviewDraftByRecordId, setReviewDraftByRecordId] = useState<Record<string, WrongQuestionReviewDraft>>({});
  const [reviewDraftDirtyByRecordId, setReviewDraftDirtyByRecordId] = useState<Record<string, boolean>>({});
  const [serverSummary, setServerSummary] = useState<WrongQuestionSummary | null>(null);
  const requestVersionRef = useRef(0);
  const detailRequestVersionRef = useRef(0);
  const practiceHistoryRequestVersionRef = useRef(0);
  const reviewDraftDirtyByRecordIdRef = useRef<Record<string, boolean>>({});
  const reviewDraftByRecordIdRef = useRef<Record<string, WrongQuestionReviewDraft>>({});
  const recordsRef = useRef(records);
  recordsRef.current = records;
  reviewDraftByRecordIdRef.current = reviewDraftByRecordId;
  const [notebookModalView, setNotebookModalView] = useState<NotebookModalView>('questions');
  const [notebookMasteryFilter, setNotebookMasteryFilter] = useState<'all' | 'pending' | 'mastered'>('all');
  const [notebookTopicFilter, setNotebookTopicFilter] = useState('全部');
  const [selectedPracticeRecordIds, setSelectedPracticeRecordIds] = useState<string[]>([]);
  const [practiceSelectionTouched, setPracticeSelectionTouched] = useState(false);
  const [practiceSheets, setPracticeSheets] = useState<WrongQuestionPracticeSheetSummary[]>([]);
  const [practiceHistoryLoading, setPracticeHistoryLoading] = useState(false);
  const [practiceHistoryError, setPracticeHistoryError] = useState('');
  const [creatingPractice, setCreatingPractice] = useState(false);
  const [practiceActionError, setPracticeActionError] = useState('');
  const [practiceActionNotice, setPracticeActionNotice] = useState('');
  const [weeklyFollowupOpen, setWeeklyFollowupOpen] = useState(false);
  const [weeklyFollowupWeekStart, setWeeklyFollowupWeekStart] = useState(getCurrentMondayDateInputValue);
  const [weeklyFollowupItems, setWeeklyFollowupItems] = useState<WeeklyWrongQuestionFollowupItem[]>([]);
  const [weeklyFollowupLoading, setWeeklyFollowupLoading] = useState(false);
  const [weeklyFollowupError, setWeeklyFollowupError] = useState('');
  const [weeklyFollowupNotice, setWeeklyFollowupNotice] = useState('');
  const [generatingWeeklyFollowupStudentId, setGeneratingWeeklyFollowupStudentId] = useState<number | null>(null);

  const summary = useMemo(() => {
    if (records.some((item) => isWechatMiniProgramWrongQuestionRecord(item))) {
      return summarizeWrongQuestionRecords(records);
    }

    return serverSummary ?? summarizeWrongQuestionRecords(records);
  }, [records, serverSummary]);
  const selectedTeacherId = useMemo(() => {
    const normalizedTeacherName = filters.teacherName?.trim() ?? '';
    if (!normalizedTeacherName) {
      return null;
    }

    return teacherOptions.find((item) => item.name === normalizedTeacherName)?.id ?? null;
  }, [filters.teacherName, teacherOptions]);
  const visibleClassOptions = useMemo(() => {
    if (!hasStaffScope || selectedTeacherId === null) {
      return classOptions;
    }

    return classOptions.filter((item) => item.teacherUserId === selectedTeacherId);
  }, [classOptions, hasStaffScope, selectedTeacherId]);
  const selectedStaffClassOption = useMemo(() => {
    const normalizedClassName = filters.className?.trim() ?? '';
    if (!normalizedClassName) {
      return null;
    }

    return visibleClassOptions.find((item) => item.name === normalizedClassName) ?? null;
  }, [filters.className, visibleClassOptions]);
  const subjectOptions = useMemo(() => {
    const optionSource = selectedStaffClassOption ? [selectedStaffClassOption] : visibleClassOptions;
    return Array.from(new Set(optionSource.map((item) => item.subject.trim()).filter(Boolean)));
  }, [selectedStaffClassOption, visibleClassOptions]);
  const activeNotebookClassId = hasStaffScope
    ? (selectedStaffClassOption?.id ?? null)
    : selectedClassId;
  const activeWeeklyFollowupClassId = selectedClassId ?? selectedStaffClassOption?.id ?? null;
  const memberNotebookSummaries = useMemo<MemberStudentNotebookSummary[]>(() => {
    if (!usesStudentNotebook) {
      return [];
    }
    return buildMemberStudentNotebookSummaries(records, activeNotebookClassId);
  }, [activeNotebookClassId, records, usesStudentNotebook]);
  const memberNotebookRecords = useMemo(() => {
    if (!usesStudentNotebook) {
      return [];
    }
    return filterWrongQuestionRecordsForMemberNotebook(records, activeNotebookClassId, selectedStudentName);
  }, [activeNotebookClassId, records, selectedStudentName, usesStudentNotebook]);
  const memberNotebookQuestionNumberById = useMemo(() => {
    return new Map(
      memberNotebookRecords.map((item, index) => [item.id, index + 1]),
    );
  }, [memberNotebookRecords]);
  const notebookTopicSummaries = useMemo(() => {
    return buildWrongQuestionTopicSummaries(memberNotebookRecords);
  }, [memberNotebookRecords]);
  const displayedNotebookRecords = useMemo(() => {
    const filtered = notebookMasteryFilter === 'mastered'
      ? memberNotebookRecords.filter((item) => item.isMastered === true)
      : notebookMasteryFilter === 'pending'
        ? memberNotebookRecords.filter((item) => item.isMastered !== true)
        : memberNotebookRecords;
    return [...filterWrongQuestionRecordsByTopic(filtered, notebookTopicFilter)].reverse();
  }, [memberNotebookRecords, notebookMasteryFilter, notebookTopicFilter]);
  const selectedNotebookStudentId = useMemo(() => {
    const matchedRecord = memberNotebookRecords.find((item) => typeof item.studentId === 'number' && item.studentId > 0);
    return matchedRecord?.studentId ?? null;
  }, [memberNotebookRecords]);
  const defaultPracticeRecordIds = useMemo(() => {
    const selectableRecords = memberNotebookRecords.filter((item) => canGenerateWrongQuestionPractice(item));
    return selectableRecords.length === 1 ? [selectableRecords[0].id] : [];
  }, [memberNotebookRecords]);
  const effectiveSelectedPracticeRecordIds = practiceSelectionTouched ? selectedPracticeRecordIds : defaultPracticeRecordIds;
  const selectedRecord = memberNotebookRecords.find((item) => item.id === selectedId) ?? null;
  const selectedDraft = selectedRecord ? reviewDraftByRecordId[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord) : null;
  const selectedQuestionTextPreview = useMemo(() => {
    if (!selectedRecord || !selectedDraft || selectedRecord.source !== 'wechat_mp' || selectedRecord.isGeometry) {
      return null;
    }

    return buildWrongQuestionLatexPreviewModel(selectedDraft.questionText ?? '');
  }, [selectedDraft, selectedRecord]);
  const finalErrorTypeOptions = useMemo(() => {
    return Array.from(new Set([
      ...WRONG_QUESTION_ERROR_TYPE_OPTIONS,
      selectedRecord?.analysis.errorType?.trim() ?? '',
      selectedDraft?.selectedErrorType?.trim() ?? '',
    ].filter(Boolean)));
  }, [selectedDraft?.selectedErrorType, selectedRecord?.analysis.errorType]);
  const topicCategoryOptions = useMemo(() => {
    return Array.from(new Set([
      ...WRONG_QUESTION_TOPIC_CATEGORY_OPTIONS,
      selectedRecord?.topicCategory?.trim() ?? '',
      selectedDraft?.topicCategory?.trim() ?? '',
    ].filter(Boolean)));
  }, [selectedDraft?.topicCategory, selectedRecord?.topicCategory]);

  const updateDraftDirtyState = useCallback((recordId: string, isDirty: boolean) => {
    reviewDraftDirtyByRecordIdRef.current = {
      ...reviewDraftDirtyByRecordIdRef.current,
      [recordId]: isDirty,
    };

    setReviewDraftDirtyByRecordId((current) => {
      if (current[recordId] === isDirty) {
        return current;
      }

      return {
        ...current,
        [recordId]: isDirty,
      };
    });
  }, []);

  const loadList = useCallback(async (nextFilters: WrongQuestionFilters) => {
    const requestVersion = requestVersionRef.current + 1;
    requestVersionRef.current = requestVersion;
    setLoading(true);
    setError('');
    try {
      const response = await apiFetch<WrongQuestionListApiResponse>(`/api/wrong-questions${buildWrongQuestionQuery(nextFilters)}`);
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      const normalized = normalizeWrongQuestionListResponse(response);
      const nextRecords = normalized.items;
      setRecords(nextRecords);
      setServerSummary(normalized.summary);
      setSelectedId((current) => {
        if (current && nextRecords.some((item) => item.id === current)) {
          return current;
        }
        return nextRecords[0]?.id ?? null;
      });
    } catch (loadError) {
      if (requestVersion !== requestVersionRef.current) {
        return;
      }

      setError(loadError instanceof Error ? loadError.message : '智能错题列表加载失败');
      setRecords([]);
      setServerSummary(null);
      setSelectedId(null);
    } finally {
      if (requestVersion === requestVersionRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const loadPracticeHistory = useCallback(async (studentId: number) => {
    const requestVersion = practiceHistoryRequestVersionRef.current + 1;
    practiceHistoryRequestVersionRef.current = requestVersion;
    setPracticeHistoryLoading(true);
    setPracticeHistoryError('');

    try {
      const response = await apiFetch<WrongQuestionPracticeSheetListApiResponse>(buildWrongQuestionPracticeSheetsPath(studentId));
      if (requestVersion !== practiceHistoryRequestVersionRef.current) {
        return;
      }

      setPracticeSheets(normalizeWrongQuestionPracticeSheetListResponse(response));
    } catch (loadError) {
      if (requestVersion !== practiceHistoryRequestVersionRef.current) {
        return;
      }

      setPracticeSheets([]);
      setPracticeHistoryError(loadError instanceof Error ? loadError.message : '错题练习记录加载失败');
    } finally {
      if (requestVersion === practiceHistoryRequestVersionRef.current) {
        setPracticeHistoryLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const [classItems, userItems] = await Promise.all([
          apiFetch<Array<{ id: number; name: string; subject?: string; teacher_user_id?: number | null }>>('/api/classes'),
          hasStaffScope ? apiFetch<Array<{ id: number; name: string }>>('/api/admin/users') : Promise.resolve([]),
        ]);

        if (!active) {
          return;
        }

        setClassOptions(classItems.map((item) => ({
          id: item.id,
          name: item.name,
          subject: item.subject?.trim() ?? '',
          teacherUserId: typeof item.teacher_user_id === 'number' ? item.teacher_user_id : null,
        })));
        setTeacherOptions(userItems.map((item) => ({
          id: item.id,
          name: item.name,
        })));
      } catch (loadOptionsError) {
        console.error(loadOptionsError);
      }
    })();

    return () => {
      active = false;
    };
  }, [hasStaffScope]);

  useEffect(() => {
    void loadList(initialFilters);
  }, [loadList]);

  useEffect(() => {
    setWeeklyFollowupItems([]);
    setWeeklyFollowupNotice('');
    setWeeklyFollowupError('');
    setGeneratingWeeklyFollowupStudentId(null);
  }, [activeWeeklyFollowupClassId, weeklyFollowupWeekStart]);

  useEffect(() => {
    if (!usesStudentNotebook || hasStaffScope) {
      return;
    }

    setSelectedClassId((current) => current && classOptions.some((item) => item.id === current) ? current : null);
  }, [classOptions, hasStaffScope, usesStudentNotebook]);

  useEffect(() => {
    if (!usesStudentNotebook || !selectedStudentName) {
      return;
    }

    if (!memberNotebookSummaries.some((item) => item.studentName === selectedStudentName)) {
      setSelectedStudentName(null);
      setSelectedId(null);
    }
  }, [memberNotebookSummaries, selectedStudentName, usesStudentNotebook]);

  useEffect(() => {
    setNotebookModalView('questions');
    setPracticeActionError('');
    setPracticeActionNotice('');
  }, [selectedStudentName]);

  useEffect(() => {
    if (!selectedRecord) {
      setDetailError('');
      setSaveError('');
      return;
    }

    if (reviewDraftDirtyByRecordId[selectedRecord.id] === undefined) {
      updateDraftDirtyState(selectedRecord.id, false);
    }

    setReviewDraftByRecordId((current) => {
      if (current[selectedRecord.id]) {
        return current;
      }

      return {
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(selectedRecord),
      };
    });
  }, [reviewDraftDirtyByRecordId, selectedRecord, updateDraftDirtyState]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    const selectedRecordForDetail = recordsRef.current.find((item) => item.id === selectedId);
    if (!selectedRecordForDetail) {
      return;
    }

    const requestVersion = detailRequestVersionRef.current + 1;
    detailRequestVersionRef.current = requestVersion;
    setDetailLoading(true);
    setDetailError('');

    void (async () => {
      try {
        const response = await apiFetch<WrongQuestionRecord>(
          buildWrongQuestionDetailPath(selectedId, selectedRecordForDetail?.roomId),
        );
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        const detailRecord = normalizeWrongQuestionRecord(response);
        const hasLocalEdits = Boolean(reviewDraftDirtyByRecordIdRef.current[detailRecord.id]);
        setRecords((current) => current.map((item) => item.id === detailRecord.id ? detailRecord : item));
        setServerSummary(null);
        setReviewDraftByRecordId((current) => {
          return {
            ...current,
            [detailRecord.id]: hydrateWrongQuestionReviewDraftFromDetail(detailRecord, current[detailRecord.id], hasLocalEdits),
          };
        });
        if (!hasLocalEdits) {
          updateDraftDirtyState(detailRecord.id, false);
        }
      } catch (loadDetailError) {
        if (requestVersion !== detailRequestVersionRef.current) {
          return;
        }

        setDetailError(loadDetailError instanceof Error ? loadDetailError.message : '智能错题详情加载失败');
      } finally {
        if (requestVersion === detailRequestVersionRef.current) {
          setDetailLoading(false);
        }
      }
    })();
  }, [selectedId]);

  useEffect(() => {
    setSelectedPracticeRecordIds((current) => current.filter((recordId) => {
      const matchedRecord = memberNotebookRecords.find((item) => item.id === recordId);
      return Boolean(matchedRecord && canGenerateWrongQuestionPractice(matchedRecord));
    }));
  }, [memberNotebookRecords]);

  useEffect(() => {
    if (!selectedStudentName || !selectedNotebookStudentId) {
      practiceHistoryRequestVersionRef.current += 1;
      setPracticeSheets([]);
      setPracticeHistoryLoading(false);
      setPracticeHistoryError('');
      return;
    }

    void loadPracticeHistory(selectedNotebookStudentId);
  }, [loadPracticeHistory, selectedNotebookStudentId, selectedStudentName]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    setFilters((current) => {
      const normalizedClassName = current.className?.trim() ?? '';
      if (!normalizedClassName) {
        return current;
      }

      if (visibleClassOptions.some((item) => item.name === normalizedClassName)) {
        return current;
      }

      return {
        ...current,
        className: '',
        studentName: '',
      };
    });
  }, [hasStaffScope, visibleClassOptions]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    setFilters((current) => {
      const normalizedSubject = current.subject?.trim() ?? '';
      if (!normalizedSubject || subjectOptions.includes(normalizedSubject)) {
        return current;
      }

      return {
        ...current,
        subject: '',
      };
    });
  }, [hasStaffScope, subjectOptions]);

  useEffect(() => {
    if (!hasStaffScope) {
      return;
    }

    if (!selectedStaffClassOption) {
      setStudentOptions([]);
      return;
    }

    let active = true;

    void (async () => {
      try {
        const response = await apiFetch<{ students?: Array<{ id: number; name: string }> }>(`/api/classes/${selectedStaffClassOption.id}/students`);
        if (!active) {
          return;
        }

        setStudentOptions(
          Array.isArray(response.students)
            ? response.students.map((item) => ({
              id: item.id,
              name: String(item.name ?? '').trim(),
            })).filter((item) => item.name)
            : [],
        );
      } catch (loadStudentsError) {
        if (!active) {
          return;
        }

        console.error(loadStudentsError);
        setStudentOptions([]);
      }
    })();

    return () => {
      active = false;
    };
  }, [hasStaffScope, selectedStaffClassOption]);

  useEffect(() => {
    if (!hasStaffScope || !selectedStaffClassOption) {
      return;
    }

    setFilters((current) => {
      const normalizedStudentName = current.studentName?.trim() ?? '';
      if (!normalizedStudentName || studentOptions.some((item) => item.name === normalizedStudentName)) {
        return current;
      }

      return {
        ...current,
        studentName: '',
      };
    });
  }, [hasStaffScope, selectedStaffClassOption, studentOptions]);

  const handleFilterChange = <K extends keyof WrongQuestionFilters>(key: K, value: WrongQuestionFilters[K]) => {
    setFilters((current) => ({
      ...current,
      studentName: key === 'className' ? '' : current.studentName,
      [key]: value,
    }));
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void loadList(filters);
  };

  const handleDraftChange = <K extends keyof WrongQuestionReviewDraft>(key: K, value: WrongQuestionReviewDraft[K]) => {
    if (!selectedRecord) {
      return;
    }

    const nextDraft = {
      ...(reviewDraftByRecordIdRef.current[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord)),
      [key]: value,
    };
    reviewDraftByRecordIdRef.current = {
      ...reviewDraftByRecordIdRef.current,
      [selectedRecord.id]: nextDraft,
    };

    setReviewDraftByRecordId((current) => ({
      ...current,
      [selectedRecord.id]: nextDraft,
    }));
    updateDraftDirtyState(selectedRecord.id, true);
  };

  const handleSaveReview = async () => {
    if (!selectedRecord) {
      return;
    }

    const latestDraft = reviewDraftByRecordIdRef.current[selectedRecord.id] ?? buildWrongQuestionReviewDraft(selectedRecord);

    setSavingReview(true);
    setSaveError('');

    try {
      const payload = buildWrongQuestionReviewPayload(latestDraft);
      const response = await apiFetch<unknown>(buildWrongQuestionReviewPath(selectedRecord.id, selectedRecord.roomId), {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      let nextRecord = resolveSavedWrongQuestionRecord(
        selectedRecord,
        payload,
        extractSavedWrongQuestionResponseRecord(response),
      );
      const currentTopicCategory = (selectedRecord.topicCategory || selectedRecord.analysis.topicCategory || '未分类').trim() || '未分类';
      const nextTopicCategory = payload.topicCategory || '未分类';
      if (selectedRecord.source === 'wechat_mp' && nextTopicCategory !== currentTopicCategory) {
        const topicResponse = await apiFetch<unknown>(`/api/wrong-questions/${encodeURIComponent(selectedRecord.id)}/topic-category`, {
          method: 'PUT',
          body: JSON.stringify({ topic_category: nextTopicCategory }),
        });
        nextRecord = resolveSavedWrongQuestionRecord(
          nextRecord,
          payload,
          extractSavedWrongQuestionResponseRecord(topicResponse),
        );
      }

      setRecords((current) => current.map((item) => item.id === selectedRecord.id ? nextRecord : item));
      setServerSummary(null);
      setReviewDraftByRecordId((current) => ({
        ...current,
        [selectedRecord.id]: buildWrongQuestionReviewDraft(nextRecord),
      }));
      updateDraftDirtyState(selectedRecord.id, false);
    } catch (saveReviewError) {
      setSaveError(saveReviewError instanceof Error ? saveReviewError.message : '智能错题保存失败');
    } finally {
      setSavingReview(false);
    }
  };

  const handleDeleteRecord = async () => {
    if (!selectedRecord || selectedRecord.source !== 'wechat_mp') {
      return;
    }

    if (!globalThis.window?.confirm?.('确定删除这道错题吗？删除后会同步更新该学生错题库 PDF。')) {
      return;
    }

    setSaveError('');

    try {
      const selectedIndex = memberNotebookRecords.findIndex((item) => item.id === selectedRecord.id);
      const nextSelectedRecord = selectedIndex >= 0
        ? memberNotebookRecords[selectedIndex + 1] ?? memberNotebookRecords[selectedIndex - 1] ?? null
        : null;

      await apiFetch(`/api/wrong-questions/${encodeURIComponent(selectedRecord.id)}`, {
        method: 'DELETE',
      });

      setRecords((current) => current.filter((item) => item.id !== selectedRecord.id));
      setServerSummary(null);
      setDetailError('');
      setSelectedId(nextSelectedRecord?.id ?? null);
      setReviewDraftByRecordId((current) => {
        const next = { ...current };
        delete next[selectedRecord.id];
        return next;
      });
      setReviewDraftDirtyByRecordId((current) => {
        const next = { ...current };
        delete next[selectedRecord.id];
        return next;
      });
      reviewDraftByRecordIdRef.current = Object.fromEntries(
        Object.entries(reviewDraftByRecordIdRef.current).filter(([recordId]) => recordId !== selectedRecord.id),
      );
      reviewDraftDirtyByRecordIdRef.current = Object.fromEntries(
        Object.entries(reviewDraftDirtyByRecordIdRef.current).filter(([recordId]) => recordId !== selectedRecord.id),
      );
    } catch (deleteError) {
      setSaveError(deleteError instanceof Error ? deleteError.message : '删除错题失败');
    }
  };

  const handleRefreshStudentLibraryPdf = async () => {
    if (!selectedRecord || selectedRecord.source !== 'wechat_mp' || !selectedRecord.studentId) {
      return;
    }

    setRefreshingLibraryPdf(true);
    setSaveError('');
    setPdfRefreshNotice('');

    try {
      const response = await apiFetch<{
        pdf_url?: string;
        student_library_pdf_path?: string;
      }>(`/api/wrong-question-student-libraries/${encodeURIComponent(String(selectedRecord.studentId))}/refresh`, {
        method: 'POST',
      });
      const nextPdfPath = String(response.pdf_url || response.student_library_pdf_path || selectedRecord.studentLibraryPdfPath || '').trim();
      if (nextPdfPath) {
        setRecords((current) => current.map((item) => (
          item.studentId === selectedRecord.studentId
            ? { ...item, studentLibraryPdfPath: nextPdfPath }
            : item
        )));
      }
      setPdfRefreshNotice('PDF 已重新生成。');
    } catch (refreshError) {
      setSaveError(refreshError instanceof Error ? refreshError.message : '重新生成 PDF 失败');
    } finally {
      setRefreshingLibraryPdf(false);
    }
  };

  const handlePracticeRecordCheckedChange = (recordId: string, checked: boolean) => {
    setPracticeSelectionTouched(true);
    setSelectedPracticeRecordIds((current) => {
      if (checked) {
        return current.includes(recordId) ? current : [...current, recordId];
      }

      return current.filter((item) => item !== recordId);
    });
  };

  const handleCreatePracticeSheet = async () => {
    if (!selectedNotebookStudentId || effectiveSelectedPracticeRecordIds.length === 0) {
      return;
    }

    setCreatingPractice(true);
    setPracticeActionError('');
    setPracticeActionNotice('');

    try {
      await apiFetch('/api/wrong-question-practice-sheets', {
        method: 'POST',
        body: JSON.stringify({
          student_id: selectedNotebookStudentId,
          wrong_question_ids: effectiveSelectedPracticeRecordIds,
        }),
      });
      setSelectedPracticeRecordIds([]);
      setPracticeSelectionTouched(false);
      setNotebookModalView('practice_history');
      setPracticeActionNotice('已提交错题练习生成任务，可在错题练习记录里查看 PDF。');
      await loadPracticeHistory(selectedNotebookStudentId);
    } catch (createError) {
      setPracticeActionError(createError instanceof Error ? createError.message : '错题练习生成失败');
    } finally {
      setCreatingPractice(false);
    }
  };

  const handleDeletePracticeSheet = async (sheet: WrongQuestionPracticeSheetSummary) => {
    if (!globalThis.window?.confirm?.('确定删除这份错题练习吗？删除后将无法再预览或下载这份 PDF。')) {
      return;
    }

    setPracticeActionError('');
    setPracticeActionNotice('');

    try {
      await apiFetch(`/api/wrong-question-practice-sheets/${encodeURIComponent(String(sheet.id))}`, {
        method: 'DELETE',
      });
      setPracticeSheets((current) => current.filter((item) => item.id !== sheet.id));
      setPracticeActionNotice('已删除这份错题练习。');
    } catch (deleteError) {
      setPracticeActionError(deleteError instanceof Error ? deleteError.message : '删除错题练习失败');
    }
  };

  const handleLoadWeeklyFollowups = async () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    setWeeklyFollowupLoading(true);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(
        buildWeeklyWrongQuestionFollowupsPath(activeWeeklyFollowupClassId, weeklyFollowupWeekStart),
      );
      const normalized = normalizeWeeklyWrongQuestionFollowupResponse(response);
      setWeeklyFollowupItems(normalized.items);
      setWeeklyFollowupNotice(normalized.items.length > 0 ? `已加载 ${normalized.items.length} 名学生。` : '本周暂无待跟进学生。');
    } catch (loadWeeklyError) {
      setWeeklyFollowupItems([]);
      setWeeklyFollowupError(loadWeeklyError instanceof Error ? loadWeeklyError.message : '每周跟进清单加载失败');
    } finally {
      setWeeklyFollowupLoading(false);
    }
  };

  const handleGenerateWeeklyFollowupMessage = async (studentId: number) => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    setGeneratingWeeklyFollowupStudentId(studentId);
    setWeeklyFollowupError('');
    setWeeklyFollowupNotice('');

    try {
      const response = await apiFetch<unknown>(buildWeeklyWrongQuestionFollowupMessagePath(), {
        method: 'POST',
        body: JSON.stringify({
          class_id: activeWeeklyFollowupClassId,
          week_start: weeklyFollowupWeekStart,
          student_id: studentId,
        }),
      });
      const responseMessage = extractGeneratedWeeklyFollowupMessage(response);
      if (responseMessage) {
        setWeeklyFollowupItems((current) => current.map((item) => {
          if (item.studentId !== studentId) {
            return item;
          }
          return {
            ...item,
            message: responseMessage,
          };
        }));
      }
      setWeeklyFollowupNotice('已生成家长沟通话术。');
    } catch (generateError) {
      setWeeklyFollowupError(generateError instanceof Error ? generateError.message : '家长沟通话术生成失败');
    } finally {
      setGeneratingWeeklyFollowupStudentId(null);
    }
  };

  const handleCopyWeeklyFollowupMessage = async (messageText: string) => {
    const clipboard = globalThis.navigator?.clipboard;
    if (!clipboard?.writeText) {
      setWeeklyFollowupError('当前浏览器不支持复制。');
      setWeeklyFollowupNotice('');
      return;
    }

    try {
      await clipboard.writeText(messageText);
      setWeeklyFollowupError('');
      setWeeklyFollowupNotice('已复制。');
    } catch (copyError) {
      setWeeklyFollowupError(copyError instanceof Error ? copyError.message : '复制失败');
      setWeeklyFollowupNotice('');
    }
  };

  const handleOpenWeeklyFollowupArchive = () => {
    if (!activeWeeklyFollowupClassId) {
      setWeeklyFollowupError('请选择班级。');
      setWeeklyFollowupNotice('');
      return;
    }

    const archivePath = buildWrongQuestionAuthedPath(
      buildWeeklyWrongQuestionFollowupArchivePath(activeWeeklyFollowupClassId, weeklyFollowupWeekStart),
    );
    globalThis.window?.open?.(archivePath, '_blank', 'noopener,noreferrer');
  };

  const selectedKnowledgePointText = selectedDraft?.selectedKnowledgePoints.join('\n') ?? '';
  const selectedActionsText = selectedDraft?.selectedActions.join('\n') ?? '';
  const selectedReasonsText = selectedDraft?.selectedReasons.join('\n') ?? '';
  const selectedRecordLibraryPdfPath = selectedRecord?.studentLibraryPdfPath
    ? buildWrongQuestionAuthedPath(selectedRecord.studentLibraryPdfPath)
    : '';
  const selectedPracticeCount = effectiveSelectedPracticeRecordIds.length;
  const detailHeader = selectedRecord ? (
    <div className="mb-5 border-b border-slate-200/80 pb-5 dark:border-white/10">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题详情</h4>
            <span className="text-base font-medium text-slate-900 dark:text-white">{selectedRecord.studentName}</span>
            {selectedRecord.source === 'wechat_mp' ? (
              <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                微信小程序
              </span>
            ) : (
              <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold ${getWrongQuestionSourceBadgeClass(selectedRecord.source)}`}>
                {getWrongQuestionSourceLabel(selectedRecord.source)}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
            <span>班级：{selectedRecord.className || '未标注班级'}</span>
            <span>老师：{selectedRecord.teacherName || '未标注老师'}</span>
            <span>记录时间：{selectedRecord.createdAt}</span>
          </div>
          {hasSnapshotDifference(selectedRecord.className, selectedRecord.classNameSnapshot) && (
            <p className="text-sm text-amber-700 dark:text-amber-300">原始班级：{selectedRecord.classNameSnapshot}</p>
          )}
          {hasSnapshotDifference(selectedRecord.teacherName, selectedRecord.teacherNameSnapshot) && (
            <p className="text-sm text-amber-700 dark:text-amber-300">原始老师：{selectedRecord.teacherNameSnapshot}</p>
          )}
        </div>
        {selectedRecord.source === 'wechat_mp' && selectedRecordLibraryPdfPath ? (
          <div className="flex flex-wrap gap-3">
            <a
              href={selectedRecordLibraryPdfPath}
              target="_blank"
              rel="noreferrer"
              className={workspaceSecondaryButtonClass}
            >
              预览 PDF
            </a>
            <a
              href={selectedRecordLibraryPdfPath}
              download="student-library.pdf"
              className={workspacePrimaryButtonClass}
            >
              下载 PDF
            </a>
            <button
              type="button"
              onClick={() => void handleRefreshStudentLibraryPdf()}
              disabled={refreshingLibraryPdf}
              className={workspaceSecondaryButtonClass}
            >
              {refreshingLibraryPdf ? '正在生成 PDF' : '重新生成 PDF'}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  ) : (
    <div className="mb-5">
      <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题详情</h4>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">查看当前题目并保存跟进内容。</p>
    </div>
  );
  const handleMemberClassChange = (value: string) => {
    const nextClassId = value ? Number(value) : null;
    setSelectedClassId(Number.isFinite(nextClassId) ? nextClassId : null);
    setSelectedStudentName(null);
    setSelectedId(null);
  };
  const handleStaffClassChange = (value: string) => {
    const nextClassId = value ? Number(value) : null;
    const nextClassOption = Number.isFinite(nextClassId)
      ? visibleClassOptions.find((item) => item.id === nextClassId) ?? null
      : null;
    handleFilterChange('className', nextClassOption?.name ?? '');
  };
  const handleCloseMemberNotebook = () => {
    setSelectedStudentName(null);
    setSelectedId(null);
    setDetailError('');
    setSaveError('');
    setPdfRefreshNotice('');
    setNotebookModalView('questions');
    setSelectedPracticeRecordIds([]);
    setPracticeSelectionTouched(false);
    setPracticeSheets([]);
    setPracticeHistoryError('');
    setPracticeActionError('');
    setPracticeActionNotice('');
  };
  const handleOpenMemberNotebook = (studentName: string) => {
    const nextRecords = filterWrongQuestionRecordsForMemberNotebook(records, activeNotebookClassId, studentName);
    setSelectedStudentName(studentName);
    setSelectedId(nextRecords.length > 0 ? nextRecords[nextRecords.length - 1].id : null);
    setNotebookModalView('questions');
    setSelectedPracticeRecordIds([]);
    setPracticeSelectionTouched(false);
  };
  const practiceHistoryPanel = (
    <>
      <div className="mb-5 border-b border-slate-200/80 pb-5 dark:border-white/10">
        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">错题练习记录</h4>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">老师生成后的练习单会保存在这里，生成完成后可直接预览或下载 PDF。</p>
      </div>

      {practiceHistoryLoading ? (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在加载错题练习记录...
        </div>
      ) : practiceSheets.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-6 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          还没有生成过错题练习。
        </div>
      ) : (
        <div className="space-y-4">
          {practiceSheets.map((sheet, index) => {
            const displaySheetNumber = practiceSheets.length - index;
            const previewPath = sheet.pdfUrl || sheet.pdfPath || sheet.downloadUrl || '';
            const downloadPath = sheet.downloadUrl || sheet.pdfUrl || sheet.pdfPath || '';
            const previewUrl = previewPath ? buildWrongQuestionAuthedPath(previewPath) : '';
            const downloadUrl = downloadPath ? buildWrongQuestionAuthedPath(downloadPath) : previewUrl;
            return (
              <article key={sheet.id} className={`${workspaceSoftCardClass} space-y-4 p-4`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-base font-semibold text-slate-900 dark:text-white">练习单 #{displaySheetNumber}</span>
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${sheet.status === 'ready' ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300' : sheet.status === 'failed' ? 'border-rose-200 bg-rose-50 text-rose-600 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300' : 'border-sky-200 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300'}`}>
                        {getWrongQuestionPracticeStatusLabel(sheet.status)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
                      <span>{sheet.createdAt || '未记录时间'}</span>
                      <span className="whitespace-nowrap">{sheet.questionCount}题</span>
                      <span>{sheet.teacherNameSnapshot || '未记录老师'}</span>
                    </div>
                    {sheet.generationError ? (
                      <p className="text-sm text-rose-600 dark:text-rose-300">{sheet.generationError}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap gap-3">
                    {previewUrl ? (
                      <>
                        <a
                          href={previewUrl}
                          target="_blank"
                          rel="noreferrer"
                          className={workspaceSecondaryButtonClass}
                        >
                          预览 PDF
                        </a>
                        <a
                          href={downloadUrl}
                          className={workspacePrimaryButtonClass}
                        >
                          下载 PDF
                        </a>
                      </>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => void handleDeletePracticeSheet(sheet)}
                      className="inline-flex items-center justify-center rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 dark:border-rose-400/30 dark:bg-slate-950/70 dark:text-rose-300 dark:hover:bg-rose-500/10"
                    >
                      删除练习
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
  const detailPanel = selectedRecord ? (
    <>
      {selectedDraft && selectedRecord.source === 'wechat_mp' && !selectedRecord.isGeometry && (
        <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">题目文本</span>
            <textarea
              value={selectedDraft.questionText ?? ''}
              onChange={(event) => handleDraftChange('questionText', event.target.value)}
              onInput={(event) => handleDraftChange('questionText', (event.target as HTMLTextAreaElement).value)}
              className={`${workspaceFieldClass} min-h-28 resize-y`}
              placeholder="填写可直接进入错题库 PDF 的题目文本"
            />
          </label>
          <p className="text-xs leading-6 text-slate-500 dark:text-slate-400">
            正文直接写，公式片段用 <code>$...$</code> 或 <code>$$...$$</code>。保存不会拦截公式错误，但下面会提示渲染失败的位置。
          </p>
          <div className="rounded-2xl border border-sky-100 bg-white/80 p-4 dark:border-white/10 dark:bg-slate-950/70">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">公式预览</span>
              {selectedQuestionTextPreview && selectedQuestionTextPreview.errors.length > 0 ? (
                <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-600 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300">
                  {selectedQuestionTextPreview.errors.length} 处渲染失败
                </span>
              ) : (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-600 dark:border-emerald-400/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                  预览正常
                </span>
              )}
            </div>
            <div
              className="xr-latex-preview mt-3 rounded-2xl border border-slate-200/80 bg-white px-4 py-3 text-[15px] text-slate-700 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
              dangerouslySetInnerHTML={{
                __html: selectedQuestionTextPreview?.html || '<span class="xr-latex-empty">暂无题目文本</span>',
              }}
            />
            {selectedQuestionTextPreview && selectedQuestionTextPreview.errors.length > 0 ? (
              <div className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs leading-6 text-rose-700 dark:border-rose-400/30 dark:bg-rose-500/10 dark:text-rose-300">
                {selectedQuestionTextPreview.errors.map((error) => (
                  <div key={`${error.type}-${error.source}`}>
                    {error.message}：{error.source}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {selectedRecord.source === 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          {selectedRecord.imageUrl ? (
            <a
              href={selectedRecord.imageUrl}
              target="_blank"
              rel="noreferrer"
              className="block overflow-hidden rounded-2xl border border-sky-100 bg-white/80 dark:border-white/10 dark:bg-slate-950/70"
            >
              <img
                src={selectedRecord.imageUrl}
                alt={`${selectedRecord.studentName} 的错题图片`}
                className="max-h-72 w-full object-cover"
              />
            </a>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">孩子自述错因</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{selectedRecord.childReasonText || '孩子还没有填写错因描述。'}</p>
            </div>
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">小学专题</p>
              {selectedDraft ? (
                <div className="mt-2 space-y-2">
                  <select
                    aria-label="小学专题"
                    value={topicCategoryOptions.includes(selectedDraft.topicCategory ?? '') ? selectedDraft.topicCategory : '自定义'}
                    onChange={(event) => handleDraftChange('topicCategory', event.target.value === '自定义' ? '' : event.target.value)}
                    className={workspaceFieldClass}
                  >
                    {topicCategoryOptions.map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                    <option value="自定义">自定义</option>
                  </select>
                  <input
                    aria-label="自定义小学专题"
                    value={selectedDraft.topicCategory ?? '未分类'}
                    onChange={(event) => handleDraftChange('topicCategory', event.target.value)}
                    className={workspaceFieldClass}
                    placeholder="如：周期问题"
                  />
                </div>
              ) : (
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{selectedRecord.topicCategory || '未分类'}</p>
              )}
            </div>
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">问题归类</p>
              {selectedDraft ? (
                <select
                  aria-label="问题归类"
                  value={selectedDraft.selectedErrorType}
                  onChange={(event) => handleDraftChange('selectedErrorType', event.target.value)}
                  className={`${workspaceFieldClass} mt-2`}
                >
                  <option value="">请选择问题归类</option>
                  {finalErrorTypeOptions.map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              ) : (
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{selectedRecord.primaryErrorType || selectedRecord.analysis.errorType || '待归类'}</p>
              )}
            </div>
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">补充备注</p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-500 dark:text-slate-400">{selectedRecord.causeNote || selectedRecord.analysis.studentNote || '暂无备注'}</p>
            </div>
          </div>
          {(selectedRecord.reasonCoreIssue || selectedRecord.reasonKeyOmission || selectedRecord.reasonNextStep) ? (
            <div className={`${workspaceCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">AI 错因分析</p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">核心错因</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonCoreIssue || '暂无'}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">关键遗漏</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonKeyOmission || '暂无'}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">后续操作</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-200">{selectedRecord.reasonNextStep || '暂无'}</p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {selectedRecord.mappingStatus !== 'mapped' && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-400/20 dark:bg-amber-500/10 dark:text-amber-200">
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="mt-0.5" />
            <div>
              <p className="font-semibold">老师与班级归属待确认</p>
              <p className="mt-1">
                {hasStaffScope
                  ? '当前老师或班级仍在沿用原始信息。请先在班级管理中确认负责班级；如果老师名称与系统成员姓名不一致，需要补充老师别名映射。'
                  : '当前老师或班级仍在沿用原始信息，请联系机构负责人在班级管理中确认负责班级，并补充老师别名映射。'}
              </p>
            </div>
          </div>
        </div>
      )}

      {detailLoading && (
        <div className="rounded-2xl border border-dashed border-sky-200 px-4 py-3 text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在加载记录详情...
        </div>
      )}

      {selectedRecord.source !== 'wechat_mp' && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={`${workspaceSoftCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">题型分类</p>
              <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.questionCategory || '待识别'}</p>
            </div>
            <div className={`${workspaceSoftCardClass} p-4`}>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">重复错题</p>
              <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedRecord.analysis.isRepeatedMistake || '待确认'}</p>
            </div>
          </div>

          <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">知识点</p>
            <div className="flex flex-wrap gap-2">
              {selectedRecord.analysis.knowledgePoints.length > 0 ? selectedRecord.analysis.knowledgePoints.map((point) => (
                <span
                  key={point}
                  className="rounded-full border border-sky-200 bg-white/80 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300"
                >
                  {point}
                </span>
              )) : (
                <span className="text-sm text-slate-500 dark:text-slate-400">暂无知识点标签</span>
              )}
            </div>
          </div>
        </>
      )}

      {selectedDraft && selectedRecord.source === 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">掌握情况</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">仅保留掌握状态。标记为已掌握后，后续错题练习会自动排除。</p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void handleDeleteRecord()}
                disabled={savingReview}
                className="inline-flex items-center justify-center rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-400/30 dark:bg-slate-950/70 dark:text-rose-300 dark:hover:bg-rose-500/10"
              >
                删除本题
              </button>
              <button
                type="button"
                onClick={() => void handleSaveReview()}
                disabled={savingReview}
                className={workspacePrimaryButtonClass}
              >
                保存掌握情况
              </button>
            </div>
          </div>

          <label className="flex items-center gap-3 rounded-2xl border border-sky-100 bg-white/80 px-4 py-3 text-sm text-slate-700 dark:border-white/10 dark:bg-slate-950/70 dark:text-slate-200">
            <input
              type="checkbox"
              checked={Boolean(selectedDraft.isMastered)}
              onChange={(event) => handleDraftChange('isMastered', (event.target as HTMLInputElement).checked)}
              className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
            />
            <span>是否掌握</span>
          </label>
        </div>
      )}

      {selectedDraft && selectedRecord.source !== 'wechat_mp' && (
        <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-white">跟进记录</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">保存失败后保留当前草稿。</p>
            </div>
            <button
              type="button"
              onClick={() => void handleSaveReview()}
              disabled={savingReview}
              className={workspacePrimaryButtonClass}
            >
              保存跟进记录
            </button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-2 text-sm sm:col-span-2">
              <span className="text-slate-500 dark:text-slate-400">最终问题归类</span>
              <select
                aria-label="最终问题归类"
                value={selectedDraft.selectedErrorType}
                onChange={(event) => handleDraftChange('selectedErrorType', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">请选择问题归类</option>
                {finalErrorTypeOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">核心知识点</span>
              <textarea
                value={selectedKnowledgePointText}
                onChange={(event) => handleDraftChange('selectedKnowledgePoints', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedKnowledgePoints', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个知识点"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">后续练习建议</span>
              <textarea
                value={selectedActionsText}
                onChange={(event) => handleDraftChange('selectedActions', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedActions', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个后续动作"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">原因分析</span>
              <textarea
                value={selectedReasonsText}
                onChange={(event) => handleDraftChange('selectedReasons', event.target.value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                onInput={(event) => handleDraftChange('selectedReasons', (event.target as HTMLTextAreaElement).value.split(/\n|,/).map((item) => item.trim()).filter(Boolean))}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="每行一个原因"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">教师备注</span>
              <textarea
                value={selectedDraft.studentNote}
                onChange={(event) => handleDraftChange('studentNote', event.target.value)}
                onInput={(event) => handleDraftChange('studentNote', (event.target as HTMLTextAreaElement).value)}
                className={`${workspaceFieldClass} min-h-28 resize-y`}
                placeholder="补充学生当前表现或教师备注"
              />
            </label>
          </div>
        </div>
      )}
    </>
  ) : (
    <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
      请先选择学生查看这个孩子的错题本。
    </div>
  );

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <p className="text-sm uppercase tracking-[0.25em] text-sky-600">错题跟进</p>
        <div>
          <h3 className="text-2xl font-bold text-slate-900 dark:text-white">智能错题</h3>
          <p className="mt-2 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
            {hasStaffScope
              ? `查看 ${currentUser.organization_name} 的错题记录，按班级或学生打开错题本。`
              : '查看负责范围内的错题记录。'}
          </p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">当前操作人：{currentUser.display_name}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">错题总数</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.totalCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">未掌握</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.pendingReviewCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责班级</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.uniqueClassCount}</p>
          </div>
          <div className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">负责学生</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{summary.uniqueStudentCount}</p>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-xl font-semibold text-slate-900 dark:text-white">学生错题本</h4>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {hasStaffScope
                ? '先按筛选条件缩小范围，再选择班级并打开学生卡片查看错题本。'
                : '先选择班级，再打开学生卡片查看这个孩子的错题库。'}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setWeeklyFollowupOpen((current) => !current)}
              className={workspaceSecondaryButtonClass}
            >
              每周跟进
            </button>
            <button
              type="button"
              onClick={() => void loadList(filters)}
              disabled={loading}
              className={workspaceSecondaryButtonClass}
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              刷新列表
            </button>
          </div>
        </div>

        {weeklyFollowupOpen && (
          <div className={`${workspaceSoftCardClass} space-y-4 p-4`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">网页智能错题</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">每周跟进</p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <label className="space-y-2 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">周次</span>
                  <input
                    aria-label="周次"
                    type="date"
                    value={weeklyFollowupWeekStart}
                    onChange={(event) => setWeeklyFollowupWeekStart(event.target.value)}
                    className={workspaceFieldClass}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => void handleLoadWeeklyFollowups()}
                  disabled={weeklyFollowupLoading}
                  className={workspacePrimaryButtonClass}
                >
                  {weeklyFollowupLoading ? '正在加载' : '查看跟进清单'}
                </button>
                <button
                  type="button"
                  onClick={handleOpenWeeklyFollowupArchive}
                  className={workspaceSecondaryButtonClass}
                >
                  下载本班错题本合集
                </button>
              </div>
            </div>

            {weeklyFollowupError && (
              <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                <AlertCircle size={16} />
                {weeklyFollowupError}
              </div>
            )}

            {weeklyFollowupNotice && (
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                {weeklyFollowupNotice}
              </div>
            )}

            {weeklyFollowupItems.length > 0 && (
              <div className="grid gap-3 md:grid-cols-2">
                {weeklyFollowupItems.map((item) => {
                  const messageText = item.message?.messageText.trim() ?? '';
                  const studentPdfUrl = item.studentLibraryPdfUrl ? buildWrongQuestionAuthedPath(item.studentLibraryPdfUrl) : '';
                  return (
                    <article key={item.studentId} className="rounded-2xl border border-slate-200/80 bg-white p-4 dark:border-white/10 dark:bg-slate-950/60">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-base font-semibold text-slate-900 dark:text-white">{item.studentName}</p>
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-slate-400">
                            <span>{item.weeklyQuestionCount}题</span>
                            <span>{item.totalActiveQuestionCount}未掌握</span>
                            {item.topicCategories.slice(0, 3).map((topic) => (
                              <span key={topic} className="rounded-full border border-sky-100 bg-sky-50 px-2 py-0.5 font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                                {topic}
                              </span>
                            ))}
                          </div>
                        </div>
                        {studentPdfUrl && (
                          <a
                            href={studentPdfUrl}
                            target="_blank"
                            rel="noreferrer"
                            className={workspaceSecondaryButtonClass}
                          >
                            打开错题本 PDF
                          </a>
                        )}
                      </div>
                      {messageText ? (
                        <p className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200">
                          {messageText}
                        </p>
                      ) : null}
                      <div className="mt-4 flex flex-wrap gap-3">
                        <button
                          type="button"
                          onClick={() => void handleGenerateWeeklyFollowupMessage(item.studentId)}
                          disabled={generatingWeeklyFollowupStudentId === item.studentId}
                          className={workspacePrimaryButtonClass}
                        >
                          {generatingWeeklyFollowupStudentId === item.studentId ? '正在生成' : messageText ? '重新生成话术' : '生成话术'}
                        </button>
                        {messageText ? (
                          <button
                            type="button"
                            onClick={() => void handleCopyWeeklyFollowupMessage(messageText)}
                            className={workspaceSecondaryButtonClass}
                          >
                            复制
                          </button>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {hasStaffScope && (
          <form className="grid gap-4 lg:grid-cols-3" onSubmit={handleSubmit}>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">学生姓名</span>
              {selectedStaffClassOption ? (
                <select
                  aria-label="学生姓名"
                  value={filters.studentName ?? ''}
                  onChange={(event) => handleFilterChange('studentName', event.target.value)}
                  className={workspaceFieldClass}
                >
                  <option value="">全部学生</option>
                  {studentOptions.map((item) => (
                    <option key={item.id} value={item.name}>{item.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label="学生姓名"
                  type="text"
                  value={filters.studentName ?? ''}
                  onChange={(event) => handleFilterChange('studentName', event.target.value)}
                  className={workspaceFieldClass}
                  placeholder="如：Alice"
                />
              )}
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">班级</span>
              <select
                aria-label="班级"
                value={selectedStaffClassOption ? String(selectedStaffClassOption.id) : ''}
                onChange={(event) => handleStaffClassChange(event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部班级</option>
                {visibleClassOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.subject ? `${item.name} · ${item.subject}` : item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">科目</span>
              <select
                aria-label="科目"
                value={filters.subject ?? ''}
                onChange={(event) => handleFilterChange('subject', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部科目</option>
                {subjectOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">老师</span>
              <select
                aria-label="老师"
                value={filters.teacherName ?? ''}
                onChange={(event) => handleFilterChange('teacherName', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部老师</option>
                {teacherOptions.map((item) => (
                  <option key={item.id} value={item.name}>{item.name}</option>
                ))}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-slate-500 dark:text-slate-400">问题归类</span>
              <select
                aria-label="问题归类筛选"
                value={filters.errorType ?? ''}
                onChange={(event) => handleFilterChange('errorType', event.target.value)}
                className={workspaceFieldClass}
              >
                <option value="">全部问题归类</option>
                {WRONG_QUESTION_ERROR_TYPE_OPTIONS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap gap-3 lg:col-span-3 lg:justify-end">
              <button
                type="button"
                onClick={() => {
                  setFilters(initialFilters);
                  void loadList(initialFilters);
                }}
                disabled={loading}
                className={workspaceSecondaryButtonClass}
              >
                重置筛选
              </button>
              <button type="submit" disabled={loading} className={workspacePrimaryButtonClass}>
                应用筛选
              </button>
            </div>
          </form>
        )}

        {!hasStaffScope && (
          <label className="space-y-2 text-sm">
            <span className="text-slate-500 dark:text-slate-400">班级</span>
            <select
              aria-label="班级"
              value={selectedClassId ? String(selectedClassId) : ''}
              onChange={(event) => handleMemberClassChange(event.target.value)}
              className={workspaceFieldClass}
            >
              <option value="">请选择班级</option>
              {classOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.subject ? `${item.name} · ${item.subject}` : item.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {!activeNotebookClassId ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            请选择班级查看学生错题本。
          </div>
        ) : loading ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            正在加载学生错题本...
          </div>
        ) : memberNotebookSummaries.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
            当前班级下暂无错题记录。
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {memberNotebookSummaries.map((item) => {
              const isActive = item.studentName === selectedStudentName;
              return (
                <button
                  key={`${item.classId}-${item.studentName}`}
                  type="button"
                  onClick={() => handleOpenMemberNotebook(item.studentName)}
                  className={`${workspaceSoftCardClass} w-full p-5 text-left transition ${isActive ? 'border-sky-400 shadow-[0_18px_48px_rgba(47,128,237,0.12)]' : ''}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-lg font-semibold text-slate-900 dark:text-white">{item.studentName}</p>
                      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{item.className}</p>
                    </div>
                    {item.hasTeacherFollowUp ? (
                      <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
                        已掌握
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-3 text-sm text-slate-500 dark:text-slate-400">
                    <span className="whitespace-nowrap">{item.totalCount}题</span>
                    <span className="whitespace-nowrap">{item.pendingReviewCount}未掌握</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {selectedStudentName && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6 backdrop-blur-sm"
          onClick={(event) => event.target === event.currentTarget && handleCloseMemberNotebook()}
        >
          <div className="flex max-h-[92vh] w-full max-w-7xl flex-col overflow-hidden rounded-[28px] border border-sky-100 bg-white shadow-[0_32px_90px_rgba(15,23,42,0.22)] dark:border-white/10 dark:bg-slate-950">
            <div className="flex items-start justify-between gap-4 border-b border-slate-200/80 px-6 py-5 dark:border-white/10">
              <div>
                <h4 className="text-2xl font-semibold text-slate-900 dark:text-white">{selectedStudentName} 的错题库</h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">左侧最新上传的题目排在最上方，题号保持原始上传顺序。</p>
              </div>
              <button
                type="button"
                onClick={handleCloseMemberNotebook}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:text-slate-400 dark:hover:text-white"
                aria-label="关闭错题库"
              >
                <X size={18} />
                <span className="sr-only">关闭错题库</span>
              </button>
            </div>

            <div className="grid min-h-0 flex-1 gap-0 xl:grid-cols-[minmax(20rem,25rem)_minmax(0,1fr)]">
              <div className="min-h-0 overflow-y-auto border-b border-slate-200/80 p-5 dark:border-white/10 xl:border-b-0 xl:border-r">
                <div className="mb-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setNotebookModalView('questions')}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${notebookModalView === 'questions' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                  >
                    错题目录
                  </button>
                  <button
                    type="button"
                    onClick={() => setNotebookModalView('practice_history')}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${notebookModalView === 'practice_history' ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                  >
                    错题练习记录
                  </button>
                </div>

                {notebookModalView === 'questions' ? (
                  <>
                    <div className={`${workspaceSoftCardClass} mb-4 space-y-3 p-4`}>
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">错题目录</p>
                          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">最新上传的题目排在最上方，题号沿用上传顺序。勾选后可直接生成一份错题练习。</p>
                        </div>
                        <span className="whitespace-nowrap rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                          {memberNotebookRecords.length}题
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="掌握状态筛选">
                        {([
                          { value: 'all', label: '全部' },
                          { value: 'pending', label: '未掌握' },
                          { value: 'mastered', label: '已掌握' },
                        ] as const).map((option) => {
                          const active = notebookMasteryFilter === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              aria-pressed={active}
                              onClick={() => setNotebookMasteryFilter(option.value)}
                              className={`rounded-full px-3 py-1 text-xs font-semibold transition ${active ? 'bg-slate-900 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-300 dark:hover:text-white'}`}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                        <span className="ml-auto whitespace-nowrap text-xs text-slate-500 dark:text-slate-400">
                          当前显示 {displayedNotebookRecords.length}题
                        </span>
                      </div>
                      <div className="space-y-2">
                        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">专题分类</p>
                        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="小学专题筛选">
                          {notebookTopicSummaries.map((item) => {
                            const active = notebookTopicFilter === item.topicCategory;
                            return (
                              <button
                                key={item.topicCategory}
                                type="button"
                                aria-pressed={active}
                                onClick={() => setNotebookTopicFilter(item.topicCategory)}
                                className={`rounded-full px-3 py-1 text-xs font-semibold transition ${active ? 'bg-sky-600 text-white dark:bg-sky-400 dark:text-slate-950' : 'border border-sky-100 bg-white text-sky-700 hover:border-sky-200 dark:border-sky-500/20 dark:bg-slate-950/60 dark:text-sky-300'}`}
                              >
                                {item.topicCategory} · {item.count}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                      <div className="flex flex-col gap-3">
                        <p className="text-sm text-slate-500 dark:text-slate-400">已选择 {selectedPracticeCount} 题</p>
                        <button
                          type="button"
                          onClick={() => void handleCreatePracticeSheet()}
                          disabled={creatingPractice || selectedPracticeCount === 0}
                          className={workspacePrimaryButtonClass}
                        >
                          生成错题练习
                        </button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      {displayedNotebookRecords.length === 0 ? (
                        <p className="rounded-xl border border-dashed border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-400">
                          当前筛选下没有匹配的错题。
                        </p>
                      ) : null}
                      {displayedNotebookRecords.map((item) => {
                        const active = item.id === selectedRecord?.id;
                        const questionNumber = memberNotebookQuestionNumberById.get(item.id) ?? 0;
                        const canSelect = canGenerateWrongQuestionPractice(item);
                        const checked = effectiveSelectedPracticeRecordIds.includes(item.id);
                        return (
                          <div
                            key={item.id}
                            className={`flex items-start gap-3 rounded-xl border px-3 py-3 transition ${active ? 'border-sky-400 bg-sky-50/70 dark:bg-sky-500/10' : 'border-slate-200/80 bg-white dark:border-white/10 dark:bg-slate-950/60'}`}
                          >
                            <input
                              type="checkbox"
                              aria-label={`选择第 ${questionNumber} 题`}
                              checked={checked}
                              disabled={!canSelect}
                              onChange={(event) => handlePracticeRecordCheckedChange(item.id, (event.target as HTMLInputElement).checked)}
                              onChangeCapture={(event) => handlePracticeRecordCheckedChange(item.id, (event.target as HTMLInputElement).checked)}
                              className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
                            />
                            <button
                              type="button"
                              onClick={() => setSelectedId(item.id)}
                              className="min-w-0 flex-1 text-left"
                            >
                              <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
                                <span className="font-semibold text-slate-900 dark:text-white">第 {questionNumber} 题</span>
                                <span className="text-slate-500 dark:text-slate-400">{item.createdAt || '未记录时间'}</span>
                                <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${item.isMastered ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300' : 'border-slate-200 bg-white/80 text-slate-600 dark:border-white/10 dark:bg-slate-900 dark:text-slate-300'}`}>
                                  {item.isMastered ? '已掌握' : '未掌握'}
                                </span>
                                <span className="rounded-full border border-sky-100 bg-sky-50 px-2.5 py-1 text-[11px] font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                                  {item.topicCategory || '未分类'}
                                </span>
                              </div>
                              {!canSelect ? (
                                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                                  {item.isMastered ? '已掌握题目不会加入新的错题练习。' : '当前题目还不能加入错题练习。'}
                                </p>
                              ) : null}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <div className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">错题练习记录</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">查看这个学生已经生成过的错题练习，生成完成后可直接打开 PDF。</p>
                    <span className="whitespace-nowrap rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                      {practiceSheets.length}份记录
                    </span>
                  </div>
                )}
              </div>

              <div className="min-h-0 overflow-y-auto p-5">
                {practiceActionNotice && (
                  <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                    {practiceActionNotice}
                  </div>
                )}

                {practiceActionError && (
                  <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertCircle size={16} />
                    {practiceActionError}
                  </div>
                )}

                {practiceHistoryError && notebookModalView === 'practice_history' && (
                  <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                    <AlertCircle size={16} />
                    {practiceHistoryError}
                  </div>
                )}

                {notebookModalView === 'questions' ? (
                  <>
                    {detailHeader}

                    {detailError && (
                      <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                        <AlertCircle size={16} />
                        {detailError}
                      </div>
                    )}

                    {saveError && (
                      <div className="mb-4 flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
                        <AlertCircle size={16} />
                        {saveError}
                      </div>
                    )}

                    {pdfRefreshNotice && (
                      <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-500/10 dark:text-emerald-300">
                        {pdfRefreshNotice}
                      </div>
                    )}

                    <div className="space-y-5">{detailPanel}</div>
                  </>
                ) : (
                  practiceHistoryPanel
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
