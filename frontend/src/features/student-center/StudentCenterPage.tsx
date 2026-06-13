import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import { getCurrentClassDisplayName } from '../../classDisplay';
import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
} from '../../domain/classNaming';
import {
  apiFetch,
  cn,
  workspacePageClass,
} from '../../workspaceShared';
import {
  createClassStudent,
  deleteClassStudent,
  listClassStudents,
} from '../../classFeedbackGeneration';
import {
  createEmptyClassForm,
  toClassFormValues,
  type ClassBindingTarget,
  type ClassFormValues,
  type ClassInviteInfo,
  type ClassItem,
  type ClassStudentOption,
  type CurrentUser,
  type LoadPageResult,
  type UserItem,
} from './model';
import { CampusOverview } from './CampusOverview';
import { ClassEditorModal } from './ClassEditorModal';
import { ClassManagementTab } from './ClassManagementTab';
import { StudentManagementTab } from './StudentManagementTab';
import { StudentProfileModal, type StudentProfileModalMode } from './StudentProfileModal';
import { getStudentCenterPermissions } from './permissions';
import {
  buildOptimisticCreatedClassItem,
  buildClassSavePayload,
  executeClassCreateRequest,
  executeClassUpdateRequest,
  findDuplicateClass,
  resolveClassesAfterOptimisticCreate,
  resolveClassSaveFormWithCurrentStudents,
  resolveClassFormDraftDirty,
  resolveExpandedClassAfterOptimisticCreate,
  resolveFormsAfterClassDraftReset,
  resolveFormsAfterCreateDraftReset,
  resolveFormsAfterOptimisticCreate,
  resolveNewClassTeacherAfterDraftReset,
  resolveNewClassTeacherAfterCreate,
  resolveTeacherSearchAfterClassDraftReset,
  resolveTeacherBindingsAfterOptimisticCreate,
  resolveClassSaveErrorMessage,
  resolveClassSaveRefreshErrorMessage,
  resolveCreatedClassTeacherBindingErrorMessage,
  validateClassSaveDraft,
} from './classSaveRules';
import {
  buildClassDeleteConfirmMessage,
  executeClassDeleteRequest,
  resolveClassesAfterDelete,
  resolveClassDeleteErrorMessage,
  resolveExpandedClassAfterDelete,
  resolveFormsAfterClassDelete,
  resolveTeacherBindingsAfterClassDelete,
  resolveTeacherSearchAfterClassDelete,
} from './classDeleteRules';
import {
  executeTeacherBindingRequest,
  resolveTeacherBindingSavingEndState,
  resolveTeacherBindingSavingStartState,
} from './teacherBindingRules';
import {
  buildClassLoadFailureState,
  buildClassLoadSuccessState,
  executeStudentCenterLoadRequest,
  isCurrentClassLoadRequest,
  resolveClassLoadError,
  resolveClassLoadStartState,
} from './loadPageRules';
import {
  executeClassInviteLoadRequest,
  executeClassInviteResetRequest,
  resolveClassInviteErrorMessage,
  resolveInviteLoadingEndState,
  resolveInviteLoadingStartState,
} from './classInviteRules';
import {
  buildStudentProfileSavePayload,
  buildDuplicateStudentProfileWarning,
  executeClassStudentCreateRequest,
  executeClassStudentDeleteRequest,
  executeClassStudentListRequest,
  executeStudentProfileCreateRequest,
  executeStudentProfileDeleteRequest,
  executeStudentProfileGetRequest,
  executeStudentProfileUpdateRequest,
  getDuplicateStudentProfileMatches,
  resolveClassStudentDraftAfterCreate,
  resolveClassStudentErrorMessage,
  resolveClassStudentSavingEndState,
  resolveClassStudentSavingStartState,
  resolveClassStudentsAfterCreate,
  resolveClassStudentsAfterDelete,
  resolveClassStudentsAfterLoad,
  resolveStudentProfileDraftDirty,
  validateStudentProfileDraft,
  type ClassStudent,
  type StudentProfileDraft,
} from './classStudentRules';
import {
  buildOverviewFilterItems,
  buildOverviewFilterSummary,
  resolveOverviewFilteredClasses,
  resolveOverviewFilterOptions,
  resolveOverviewSummaryItems,
} from './overviewFilterRules';
import {
  buildClassFilterItems,
  buildClassFilterSummary,
  getClassEffectiveSubject as resolveClassEffectiveSubject,
  getClassInfoIssues as resolveClassInfoIssues,
  getClassTeacherUserId as resolveClassTeacherUserId,
  resolveActiveClassFilterOptions,
  resolveClassFilterOptions,
  resolveFilteredClasses,
} from './classFilterRules';
import {
  buildStudentFilterItems,
  buildStudentFilterSummary,
  buildStudentRows,
  resolveActiveStudentFilterOptions,
  resolveFilteredStudentRows,
  resolveStudentFilterOptions,
  type StudentScheduleStatusFilter,
} from './studentFilterRules';
import {
  resolveClassEditorErrorsAfterToggle,
  resolveExpandedClassAfterToggle,
  resolveFormsAfterFieldChange,
  resolveTeacherSearchAfterChange,
} from './classEditorStateRules';
import { buildClassEditorModalState } from './classEditorModalState';
import {
  cancelFilterCloseTimer,
  resolveOverviewFilterItemClick,
  resolveOverviewFilterItemHover,
  resolveOverviewFilterTriggerClick,
  scheduleFilterClose,
} from './filterInteractionRules';
import { useClassEditorModalActions } from './useClassEditorModalActions';

const academicSubjectOptions = ['数学', '物理', '国际数学'];
const studentCenterStageOptions = [...academicStageOptions];
const studentCenterGradeOptions = [...academicGradeOptions];
const studentCenterGradeGroups: Record<string, string[]> = academicGradeGroups;
const emptyStudentProfileDraft: StudentProfileDraft = { name: '', source: '', parent_contact: '' };

async function copyTextToClipboard(value: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', 'true');
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);
  if (!copied) {
    throw new Error('邀请码复制失败');
  }
}

function buildStudentProfileDraft(student: Partial<ClassStudent> | null | undefined): StudentProfileDraft {
  return {
    name: student?.name || '',
    source: student?.source || '',
    parent_contact: student?.parent_contact || '',
  };
}

export function StudentCenterPage({
  currentUser,
  classBindingTarget,
  onClearClassBindingTarget,
}: {
  currentUser: CurrentUser;
  classBindingTarget?: ClassBindingTarget | null;
  onClearClassBindingTarget?: () => void;
}) {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [allStudents, setAllStudents] = useState<ClassStudentOption[]>([]);
  const [teacherBindingByClassId, setTeacherBindingByClassId] = useState<Record<number, number | null>>({});
  const [inviteByClassId, setInviteByClassId] = useState<Record<number, ClassInviteInfo>>({});
  const [studentsByClassId, setStudentsByClassId] = useState<Record<number, Array<{ id: number; name: string }>>>({});
  const [savedStudentsByClassId, setSavedStudentsByClassId] = useState<Record<number, Array<{ id: number; name: string }>>>({});
  const [expandedClassId, setExpandedClassId] = useState<number | 'new' | null>(null);
  const [formByClassId, setFormByClassId] = useState<Record<string, ClassFormValues>>(() => ({
    new: createEmptyClassForm(),
  }));
  const [studentCenterTab, setStudentCenterTab] = useState<'classes' | 'students'>('classes');
  const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');
  const [selectedClassStageFilter, setSelectedClassStageFilter] = useState<string>('全部学段');
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('全部学科');
  const [selectedClassTeacherFilter, setSelectedClassTeacherFilter] = useState<number | 'all'>('all');
  const [activeClassFilterLayer, setActiveClassFilterLayer] = useState<'subject' | 'teacher' | 'stage' | 'grade' | null>(null);
  const [overviewSubjectFilter, setOverviewSubjectFilter] = useState<string>('全部学科');
  const [overviewTeacherFilter, setOverviewTeacherFilter] = useState<number | 'all'>('all');
  const [overviewStageFilter, setOverviewStageFilter] = useState<string>('全部学段');
  const [overviewGradeFilter, setOverviewGradeFilter] = useState<string>('全部');
  const [activeOverviewFilterLayer, setActiveOverviewFilterLayer] = useState<'subject' | 'teacher' | 'stage' | 'grade' | null>(null);
  const [clickedOverviewFilterLayer, setClickedOverviewFilterLayer] = useState<'subject' | 'teacher' | 'stage' | 'grade' | null>(null);
  const [isOverviewFilterOpen, setIsOverviewFilterOpen] = useState(false);
  const [studentSubjectFilter, setStudentSubjectFilter] = useState<string>('全部学科');
  const [studentTeacherFilter, setStudentTeacherFilter] = useState<number | 'all'>('all');
  const [studentStageFilter, setStudentStageFilter] = useState<string>('全部学段');
  const [studentGradeFilter, setStudentGradeFilter] = useState<string>('全部');
  const [studentClassFilter, setStudentClassFilter] = useState<number | 'all'>('all');
  const [studentNameFilter, setStudentNameFilter] = useState('');
  const [studentScheduleStatusFilter, setStudentScheduleStatusFilter] = useState<StudentScheduleStatusFilter>('all');
  const [activeStudentFilterLayer, setActiveStudentFilterLayer] = useState<'subject' | 'teacher' | 'stage' | 'grade' | 'class' | null>(null);
  const [studentProfileMode, setStudentProfileMode] = useState<StudentProfileModalMode>(null);
  const [studentProfileStudentId, setStudentProfileStudentId] = useState<number | null>(null);
  const [studentProfileDraft, setStudentProfileDraft] = useState<StudentProfileDraft>(emptyStudentProfileDraft);
  const [savedStudentProfileDraft, setSavedStudentProfileDraft] = useState<StudentProfileDraft | null>(null);
  const [studentProfileDetail, setStudentProfileDetail] = useState<ClassStudent | null>(null);
  const [studentProfileLoading, setStudentProfileLoading] = useState(false);
  const [studentProfileSaving, setStudentProfileSaving] = useState(false);
  const [studentProfileDeleting, setStudentProfileDeleting] = useState(false);
  const [studentProfileError, setStudentProfileError] = useState('');
  const [showClassCohortYear, setShowClassCohortYear] = useState(false);
  const [activeClassHelpKey, setActiveClassHelpKey] = useState<'overview' | null>(null);
  const [newClassTeacherUserId, setNewClassTeacherUserId] = useState<number | null>(null);
  const [teacherSearchByClassId, setTeacherSearchByClassId] = useState<Record<string, string>>({});
  const [studentDraftNameByClassId, setStudentDraftNameByClassId] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const [formError, setFormError] = useState('');
  const [assignmentError, setAssignmentError] = useState('');
  const [studentErrorByClassId, setStudentErrorByClassId] = useState<Record<number, string>>({});
  const [inviteErrorByClassId, setInviteErrorByClassId] = useState<Record<number, string>>({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [teacherBindingSavingByClassId, setTeacherBindingSavingByClassId] = useState<Record<number, boolean>>({});
  const [studentsLoadingByClassId, setStudentsLoadingByClassId] = useState<Record<number, boolean>>({});
  const [studentSavingByClassId, setStudentSavingByClassId] = useState<Record<number, boolean>>({});
  const [inviteLoadingByClassId, setInviteLoadingByClassId] = useState<Record<number, boolean>>({});
  const [inviteResettingByClassId, setInviteResettingByClassId] = useState<Record<number, boolean>>({});
  const loadPageRequestVersionRef = useRef(0);
  const formByClassIdRef = useRef(formByClassId);
  const expandedClassIdRef = useRef(expandedClassId);
  const classFilterCloseTimerRef = useRef<number | null>(null);
  const overviewFilterCloseTimerRef = useRef<number | null>(null);
  const overviewLayerCloseTimerRef = useRef<number | null>(null);
  const studentFilterCloseTimerRef = useRef<number | null>(null);
  const classInteractionLocked = saving || deleting;
  const hasTeacherBindingSavingRows = Object.values(teacherBindingSavingByClassId).some(Boolean);
  const classCardInteractionLocked = classInteractionLocked || hasTeacherBindingSavingRows;
  const pageRefreshLocked = loading || classInteractionLocked || hasTeacherBindingSavingRows;
  const assignmentRefreshLocked = loading || classInteractionLocked || hasTeacherBindingSavingRows;
  const studentCenterPermissions = getStudentCenterPermissions(currentUser);

  const getClassStateKey = (classId: number | 'new') => String(classId);

  useEffect(() => {
    formByClassIdRef.current = formByClassId;
  }, [formByClassId]);

  useEffect(() => {
    expandedClassIdRef.current = expandedClassId;
  }, [expandedClassId]);

  const loadPage = useCallback(async (preferredExpandedClassId?: number | 'new' | null, options?: { preserveStateOnError?: boolean }): Promise<LoadPageResult> => {
    const preserveStateOnError = options?.preserveStateOnError ?? false;
    const loadStartState = resolveClassLoadStartState(loadPageRequestVersionRef.current);
    const requestVersion = loadStartState.requestVersion;
    loadPageRequestVersionRef.current = requestVersion;
    setLoading(loadStartState.loading);
    setPageError(loadStartState.pageError);
    try {
      const { classItems, userItems, teacherBindingData, allStudents: loadedStudents } = await executeStudentCenterLoadRequest(
        apiFetch,
        studentCenterPermissions.canLoadStaffMembers,
      );

      if (!isCurrentClassLoadRequest(requestVersion, loadPageRequestVersionRef.current)) {
        return { status: 'stale' };
      }

      const nextState = buildClassLoadSuccessState({
        classItems,
        userItems,
        allStudents: loadedStudents,
        rawTeacherBindings: teacherBindingData.teacher_bindings,
        currentFormByClassId: formByClassIdRef.current,
        currentExpandedClassId: expandedClassIdRef.current,
        preferredExpandedClassId,
        emptyClassForm: createEmptyClassForm(),
      });

      setClasses(nextState.classes);
      setUsers(nextState.users);
      setAllStudents(nextState.allStudents);
      setTeacherBindingByClassId(nextState.teacherBindingByClassId);
      setFormByClassId(nextState.formByClassId);
      setExpandedClassId(nextState.expandedClassId);
      return { status: 'success' };
    } catch (err) {
      if (!isCurrentClassLoadRequest(requestVersion, loadPageRequestVersionRef.current)) {
        return { status: 'stale' };
      }

      const error = resolveClassLoadError(err);
      setPageError(error.message);
      if (!preserveStateOnError) {
        const nextState = buildClassLoadFailureState(createEmptyClassForm());
        setClasses(nextState.classes);
        setUsers(nextState.users);
        setAllStudents(nextState.allStudents);
        setTeacherBindingByClassId(nextState.teacherBindingByClassId);
        setFormByClassId(nextState.formByClassId);
        setNewClassTeacherUserId(nextState.newClassTeacherUserId);
        setExpandedClassId(nextState.expandedClassId);
      }
      return { status: 'refresh-error', error };
    } finally {
      if (isCurrentClassLoadRequest(requestVersion, loadPageRequestVersionRef.current)) {
        setLoading(false);
      }
    }
  }, [studentCenterPermissions.canLoadStaffMembers]);

  useEffect(() => {
    loadPage().catch(() => undefined);
  }, [loadPage]);

  useEffect(() => () => {
    if (classFilterCloseTimerRef.current !== null) {
      window.clearTimeout(classFilterCloseTimerRef.current);
    }
    if (overviewFilterCloseTimerRef.current !== null) {
      window.clearTimeout(overviewFilterCloseTimerRef.current);
    }
    if (overviewLayerCloseTimerRef.current !== null) {
      window.clearTimeout(overviewLayerCloseTimerRef.current);
    }
    if (studentFilterCloseTimerRef.current !== null) {
      window.clearTimeout(studentFilterCloseTimerRef.current);
    }
  }, []);

  const handleLoadClassInvite = useCallback(async (classId: number) => {
    setInviteLoadingByClassId((current) => resolveInviteLoadingStartState(current, classId));
    setInviteErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await executeClassInviteLoadRequest(classId, apiFetch);
      setInviteByClassId((current) => ({ ...current, [classId]: payload }));
    } catch (err) {
      setInviteErrorByClassId((current) => ({
        ...current,
        [classId]: resolveClassInviteErrorMessage(err, 'load'),
      }));
    } finally {
      setInviteLoadingByClassId((current) => resolveInviteLoadingEndState(current, classId));
    }
  }, []);

  const handleCopyClassInvite = useCallback(async (classId: number) => {
    setInviteErrorByClassId((current) => ({ ...current, [classId]: '' }));
    let inviteInfo = inviteByClassId[classId];

    try {
      if (!inviteInfo) {
        setInviteLoadingByClassId((current) => resolveInviteLoadingStartState(current, classId));
        inviteInfo = await executeClassInviteLoadRequest(classId, apiFetch);
        setInviteByClassId((current) => ({ ...current, [classId]: inviteInfo }));
      }
      await copyTextToClipboard(inviteInfo.invite_code);
    } catch (err) {
      setInviteErrorByClassId((current) => ({
        ...current,
        [classId]: resolveClassInviteErrorMessage(err, 'copy'),
      }));
      throw err;
    } finally {
      if (!inviteByClassId[classId]) {
        setInviteLoadingByClassId((current) => resolveInviteLoadingEndState(current, classId));
      }
    }
  }, [inviteByClassId]);

  const handleResetClassInvite = useCallback(async (classId: number) => {
    setInviteResettingByClassId((current) => resolveInviteLoadingStartState(current, classId));
    setInviteErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await executeClassInviteResetRequest(classId, apiFetch);
      setInviteByClassId((current) => ({ ...current, [classId]: payload }));
    } catch (err) {
      setInviteErrorByClassId((current) => ({
        ...current,
        [classId]: resolveClassInviteErrorMessage(err, 'reset'),
      }));
    } finally {
      setInviteResettingByClassId((current) => resolveInviteLoadingEndState(current, classId));
    }
  }, []);

  const loadStudentsForClass = useCallback(async (classId: number) => {
    setStudentsLoadingByClassId((current) => resolveClassStudentSavingStartState(current, classId));
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));

    try {
      const payload = await executeClassStudentListRequest(classId, listClassStudents);
      setStudentsByClassId((current) => resolveClassStudentsAfterLoad(current, classId, payload.students));
      setSavedStudentsByClassId((current) => resolveClassStudentsAfterLoad(current, classId, payload.students));
    } catch (err) {
      setStudentErrorByClassId((current) => ({
        ...current,
        [classId]: resolveClassStudentErrorMessage(err, 'load'),
      }));
    } finally {
      setStudentsLoadingByClassId((current) => resolveClassStudentSavingEndState(current, classId));
    }
  }, []);

  useEffect(() => {
    if (typeof expandedClassId !== 'number' || inviteByClassId[expandedClassId]) {
      return;
    }

    void handleLoadClassInvite(expandedClassId);
  }, [expandedClassId, handleLoadClassInvite, inviteByClassId]);

  useEffect(() => {
    if (typeof expandedClassId !== 'number') {
      return;
    }
    if (Object.prototype.hasOwnProperty.call(studentsByClassId, expandedClassId)) {
      return;
    }

    void loadStudentsForClass(expandedClassId);
  }, [expandedClassId, loadStudentsForClass, studentsByClassId]);

  useEffect(() => {
    if (studentCenterTab !== 'students') {
      return;
    }
    classes.forEach((item) => {
      if (!Object.prototype.hasOwnProperty.call(studentsByClassId, item.id)) {
        void loadStudentsForClass(item.id);
      }
    });
  }, [classes, loadStudentsForClass, studentCenterTab, studentsByClassId]);

  const handleFieldChange = (classId: number | 'new', field: keyof ClassFormValues, value: string) => {
    setFormByClassId((current) => resolveFormsAfterFieldChange(
      current,
      classId,
      field,
      value,
      createEmptyClassForm(),
      studentCenterGradeGroups,
      studentCenterGradeOptions,
    ));
  };

  const handleTeacherSearchChange = (classId: number | 'new', value: string) => {
    setTeacherSearchByClassId((current) => resolveTeacherSearchAfterChange(current, classId, value));
  };

  const handleStudentDraftNameChange = (classId: number, value: string) => {
    setStudentDraftNameByClassId((current) => ({
      ...current,
      [classId]: value,
    }));
  };

  const handleNewClassStudentSelectionChange = (studentId: number, checked: boolean) => {
    setFormByClassId((current) => {
      const currentForm = current.new || createEmptyClassForm();
      const currentIds = currentForm.selected_student_ids || [];
      const nextIds = checked
        ? [...currentIds.filter((id) => id !== studentId), studentId]
        : currentIds.filter((id) => id !== studentId);
      return {
        ...current,
        new: {
          ...currentForm,
          selected_student_ids: nextIds,
        },
      };
    });
  };

  const handleToggleExpandedClass = (classId: number | 'new') => {
    const nextExpandedClassId = resolveExpandedClassAfterToggle(expandedClassId, classId, classCardInteractionLocked);
    if (nextExpandedClassId === expandedClassId && classCardInteractionLocked) {
      return;
    }
    const nextErrors = resolveClassEditorErrorsAfterToggle();
    setExpandedClassId(nextExpandedClassId);
    setFormError(nextErrors.formError);
    setAssignmentError(nextErrors.assignmentError);
  };

  useEffect(() => {
    if (!classBindingTarget || expandedClassId === null) {
      return;
    }

    const stateKey = getClassStateKey(expandedClassId);
    setTeacherSearchByClassId((current) => (
      current[stateKey]
        ? current
        : { ...current, [stateKey]: classBindingTarget.teacherName }
    ));
    if (expandedClassId === 'new') {
      setNewClassTeacherUserId(classBindingTarget.teacherUserId);
    }
  }, [classBindingTarget, expandedClassId]);

  const handleSaveClass = async (classId: number | 'new') => {
    const currentForm = resolveClassSaveFormWithCurrentStudents({
      classId,
      form: formByClassId[getClassStateKey(classId)] || createEmptyClassForm(),
      studentsByClassId,
    });
    const selectedTeacherUserId = classId === 'new'
      ? newClassTeacherUserId
      : (teacherBindingByClassId[classId] ?? classes.find((item) => item.id === classId)?.teacher_user_id ?? null);
    const savedTeacherUserId = classId === 'new'
      ? null
      : (classes.find((item) => item.id === classId)?.teacher_user_id ?? null);
    const selectedTeacher = typeof selectedTeacherUserId === 'number' ? users.find((user) => user.id === selectedTeacherUserId) : undefined;
    const payload = buildClassSavePayload({
      classId,
      form: currentForm,
      selectedTeacher,
      selectedTeacherUserId,
      existingStudents: allStudents,
    });
    const validationError = validateClassSaveDraft({
      classId,
      selectedTeacherUserId,
      payload,
      gradeOptions: studentCenterGradeOptions,
    });

    if (validationError) {
      setFormError(validationError);
      return;
    }

    if (findDuplicateClass(classes, classId, payload)) {
      setFormError('已存在相同学科、学段、年级、班号和入学年份的班级，请调整后再保存。');
      return;
    }

    setSaving(true);
    setFormError('');

    let createdClassId: number | null = null;
    let teacherBindingSucceeded = false;

    try {
      if (classId === 'new') {
        const created = await executeClassCreateRequest<{ id: number; name: string }>(payload, apiFetch);
        createdClassId = created.id;
        setFormByClassId((current) => resolveFormsAfterCreateDraftReset(current, createEmptyClassForm()));
        setNewClassTeacherUserId(resolveNewClassTeacherAfterCreate());
        loadPageRequestVersionRef.current += 1;
        await executeTeacherBindingRequest(created.id, selectedTeacherUserId as number, apiFetch);
        teacherBindingSucceeded = true;
        const optimisticCreatedClass = buildOptimisticCreatedClassItem({
          createdClassId: created.id,
          payload,
          selectedTeacher,
          selectedTeacherUserId,
        });
        setClasses((current) => resolveClassesAfterOptimisticCreate(current, optimisticCreatedClass));
        setTeacherBindingByClassId((current) => resolveTeacherBindingsAfterOptimisticCreate(current, created.id, selectedTeacherUserId));
        setFormByClassId((current) => resolveFormsAfterOptimisticCreate(
          current,
          created.id,
          toClassFormValues(optimisticCreatedClass),
        ));
        setExpandedClassId(resolveExpandedClassAfterOptimisticCreate(created.id));
        const refreshResult = await loadPage(created.id, { preserveStateOnError: true });
        if (refreshResult.status === 'refresh-error') {
          setFormError(resolveClassSaveRefreshErrorMessage(classId, refreshResult.error));
        }
      } else {
        await executeClassUpdateRequest(classId, payload, apiFetch);
        if (selectedTeacherUserId !== savedTeacherUserId && typeof selectedTeacherUserId === 'number') {
          setTeacherBindingSavingByClassId((current) => resolveTeacherBindingSavingStartState(current, classId));
          await executeTeacherBindingRequest(classId, selectedTeacherUserId, apiFetch);
          setTeacherBindingByClassId((current) => ({ ...current, [classId]: selectedTeacherUserId }));
        }
        const savedStudents = savedStudentsByClassId[classId] || [];
        const currentStudents = studentsByClassId[classId] || [];
        const savedStudentIds = new Set(savedStudents.map((student) => student.id));
        const currentStudentIds = new Set(currentStudents.map((student) => student.id));
        const studentsToAdd = currentStudents.filter((student) => !savedStudentIds.has(student.id));
        const studentsToDelete = savedStudents.filter((student) => !currentStudentIds.has(student.id));
        if (studentsToAdd.length || studentsToDelete.length) {
          setStudentSavingByClassId((current) => resolveClassStudentSavingStartState(current, classId));
          for (const student of studentsToAdd) {
            await executeClassStudentCreateRequest(classId, student.id, createClassStudent);
          }
          for (const student of studentsToDelete) {
            await executeClassStudentDeleteRequest(classId, student.id, deleteClassStudent);
          }
          setSavedStudentsByClassId((current) => resolveClassStudentsAfterLoad(current, classId, currentStudents));
        }
        const refreshResult = await loadPage(classId, { preserveStateOnError: true });
        if (refreshResult.status === 'refresh-error') {
          setFormError(resolveClassSaveRefreshErrorMessage(classId, refreshResult.error));
        }
      }
    } catch (err) {
      if (classId === 'new' && createdClassId != null && !teacherBindingSucceeded) {
        setFormError(resolveCreatedClassTeacherBindingErrorMessage(err));
        await loadPage(createdClassId, { preserveStateOnError: true });
        return;
      }
      setFormError(resolveClassSaveErrorMessage(err));
    } finally {
      if (classId !== 'new') {
        setTeacherBindingSavingByClassId((current) => resolveTeacherBindingSavingEndState(current, classId));
        setStudentSavingByClassId((current) => resolveClassStudentSavingEndState(current, classId));
      }
      setSaving(false);
    }
  };

  useEffect(() => {
    if (expandedClassId === null) {
      return undefined;
    }
    const handleSaveShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void handleSaveClass(expandedClassId);
      }
    };
    window.addEventListener('keydown', handleSaveShortcut);
    return () => window.removeEventListener('keydown', handleSaveShortcut);
  }, [expandedClassId, formByClassId, newClassTeacherUserId, teacherBindingByClassId, studentsByClassId, savedStudentsByClassId, classes, users, saving, deleting]);

  const handleDeleteClass = async (classId: number) => {
    const targetClass = classes.find((item) => item.id === classId);
    if (!targetClass) {
      return;
    }

    if (!window.confirm(buildClassDeleteConfirmMessage(targetClass))) {
      return;
    }

    setDeleting(true);
    setFormError('');

    try {
      await executeClassDeleteRequest(classId, apiFetch);
      setClasses((current) => resolveClassesAfterDelete(current, classId));
      setTeacherBindingByClassId((current) => resolveTeacherBindingsAfterClassDelete(current, classId));
      setFormByClassId((current) => resolveFormsAfterClassDelete(current, classId));
      setTeacherSearchByClassId((current) => resolveTeacherSearchAfterClassDelete(current, classId));
      setExpandedClassId((current) => resolveExpandedClassAfterDelete(current, classId));
      await loadPage(null);
    } catch (err) {
      setFormError(resolveClassDeleteErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  };

  const handleSelectTeacherForClass = async (classId: number, teacherUserId: number) => {
    if (classInteractionLocked || teacherBindingSavingByClassId[classId]) {
      return;
    }

    setAssignmentError('');
    setTeacherBindingByClassId((current) => ({ ...current, [classId]: teacherUserId }));
  };

  const handleAddStudentToClass = async (classId: number, studentId: number) => {
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));
    const selectedStudent = allStudents.find((student) => student.id === studentId);
    if (!selectedStudent) {
      setStudentErrorByClassId((current) => ({ ...current, [classId]: '没有找到该学员，请先在学员管理中建立学员档案。' }));
      return;
    }
    setStudentsByClassId((current) => resolveClassStudentsAfterCreate(current, classId, selectedStudent));
    setStudentDraftNameByClassId((current) => resolveClassStudentDraftAfterCreate(current, classId));
  };

  const handleDeleteStudentFromClass = async (classId: number, studentId: number) => {
    setStudentErrorByClassId((current) => ({ ...current, [classId]: '' }));
    setStudentsByClassId((current) => resolveClassStudentsAfterDelete(current, classId, studentId));
  };

  const updateStudentCaches = (student: ClassStudent) => {
    setAllStudents((current) => {
      const existing = current.some((item) => item.id === student.id);
      if (existing) {
        return current.map((item) => (item.id === student.id ? { ...item, ...student } : item));
      }
      return [...current, student];
    });
    setStudentsByClassId((current) => Object.fromEntries(
      Object.entries(current).map(([classId, students]) => [
        classId,
        students.map((item) => (item.id === student.id ? { ...item, ...student } : item)),
      ]),
    ));
    setSavedStudentsByClassId((current) => Object.fromEntries(
      Object.entries(current).map(([classId, students]) => [
        classId,
        students.map((item) => (item.id === student.id ? { ...item, ...student } : item)),
      ]),
    ));
  };

  const removeStudentFromCaches = (studentId: number) => {
    setAllStudents((current) => current.filter((item) => item.id !== studentId));
    setStudentsByClassId((current) => Object.fromEntries(
      Object.entries(current).map(([classId, students]) => [
        classId,
        students.filter((item) => item.id !== studentId),
      ]),
    ));
    setSavedStudentsByClassId((current) => Object.fromEntries(
      Object.entries(current).map(([classId, students]) => [
        classId,
        students.filter((item) => item.id !== studentId),
      ]),
    ));
  };

  const openCreateStudentProfile = () => {
    if (!studentCenterPermissions.canManageStudents) {
      return;
    }
    setStudentProfileMode('create');
    setStudentProfileStudentId(null);
    setStudentProfileDraft(emptyStudentProfileDraft);
    setSavedStudentProfileDraft(null);
    setStudentProfileDetail(null);
    setStudentProfileError('');
    setStudentProfileLoading(false);
    setStudentProfileDeleting(false);
  };

  const openStudentProfile = async (studentId: number) => {
    const listStudent = allStudents.find((student) => student.id === studentId) || null;
    const initialDraft = buildStudentProfileDraft(listStudent);
    setStudentProfileMode('edit');
    setStudentProfileStudentId(studentId);
    setStudentProfileDraft(initialDraft);
    setSavedStudentProfileDraft(initialDraft);
    setStudentProfileDetail(listStudent);
    setStudentProfileError('');
    setStudentProfileLoading(true);
    setStudentProfileDeleting(false);

    try {
      const payload = await executeStudentProfileGetRequest(studentId, apiFetch);
      const detailDraft = buildStudentProfileDraft(payload.student);
      setStudentProfileDetail(payload.student);
      setStudentProfileDraft(detailDraft);
      setSavedStudentProfileDraft(detailDraft);
      updateStudentCaches(payload.student);
    } catch (err) {
      setStudentProfileError(err instanceof Error ? err.message : '学员档案加载失败');
    } finally {
      setStudentProfileLoading(false);
    }
  };

  const handleStudentProfileDraftChange = (key: keyof StudentProfileDraft, value: string) => {
    setStudentProfileDraft((current) => ({ ...current, [key]: value }));
  };

  const isStudentProfileDraftDirty = () => resolveStudentProfileDraftDirty(studentProfileDraft, savedStudentProfileDraft);
  const studentProfileDuplicateMatches = getDuplicateStudentProfileMatches(
    studentProfileDraft,
    allStudents,
    studentProfileMode === 'edit' ? studentProfileStudentId : null,
  );
  const studentProfileDuplicateWarning = studentProfileMode === 'create'
    ? buildDuplicateStudentProfileWarning(studentProfileDuplicateMatches)
    : '';

  const closeStudentProfile = () => {
    if (studentProfileSaving || studentProfileDeleting) {
      return;
    }
    if (isStudentProfileDraftDirty() && !window.confirm('有未保存的修改，确定放弃并关闭吗？')) {
      return;
    }
    setStudentProfileMode(null);
    setStudentProfileStudentId(null);
    setStudentProfileDraft(emptyStudentProfileDraft);
    setSavedStudentProfileDraft(null);
    setStudentProfileDetail(null);
    setStudentProfileError('');
    setStudentProfileDeleting(false);
  };

  const saveStudentProfile = async () => {
    if (!studentCenterPermissions.canManageStudents || studentProfileSaving || studentProfileLoading || !isStudentProfileDraftDirty()) {
      return;
    }
    const payload = buildStudentProfileSavePayload(studentProfileDraft);
    const validationError = validateStudentProfileDraft(payload);
    if (validationError) {
      setStudentProfileError(validationError);
      return;
    }
    if (
      studentProfileMode === 'create'
      && studentProfileDuplicateMatches.length
      && !window.confirm(`已存在 ${studentProfileDuplicateMatches.length} 位同名学员，仍要新建吗？`)
    ) {
      return;
    }

    setStudentProfileSaving(true);
    setStudentProfileError('');
    try {
      const result = studentProfileMode === 'create'
        ? await executeStudentProfileCreateRequest(payload, apiFetch)
        : studentProfileStudentId != null
          ? await executeStudentProfileUpdateRequest(studentProfileStudentId, payload, apiFetch)
          : null;
      if (!result) {
        setStudentProfileError('学员档案保存失败，请重新打开后再试。');
        return;
      }
      const nextDraft = buildStudentProfileDraft(result.student);
      setStudentProfileMode('edit');
      setStudentProfileStudentId(result.student.id);
      setStudentProfileDetail(result.student);
      setStudentProfileDraft(nextDraft);
      setSavedStudentProfileDraft(nextDraft);
      updateStudentCaches(result.student);
      await loadPage(expandedClassId, { preserveStateOnError: true });
    } catch (err) {
      setStudentProfileError(err instanceof Error ? err.message : '学员档案保存失败，请重试。');
    } finally {
      setStudentProfileSaving(false);
    }
  };

  const deleteOrArchiveStudentProfile = async () => {
    if (!studentCenterPermissions.canManageStudents || studentProfileMode !== 'edit' || studentProfileStudentId == null || studentProfileSaving || studentProfileLoading || studentProfileDeleting) {
      return;
    }
    if (!window.confirm('确定处理此学员档案吗？无关联档案会永久删除；已有课程、历史或错题记录的档案会停用并默认隐藏。')) {
      return;
    }
    setStudentProfileDeleting(true);
    setStudentProfileError('');
    try {
      await executeStudentProfileDeleteRequest(studentProfileStudentId, apiFetch);
      removeStudentFromCaches(studentProfileStudentId);
      setStudentProfileMode(null);
      setStudentProfileStudentId(null);
      setStudentProfileDraft(emptyStudentProfileDraft);
      setSavedStudentProfileDraft(null);
      setStudentProfileDetail(null);
      await loadPage(expandedClassId, { preserveStateOnError: true });
    } catch (err) {
      setStudentProfileError(err instanceof Error ? err.message : '学员档案处理失败，请重试。');
    } finally {
      setStudentProfileDeleting(false);
    }
  };

  useEffect(() => {
    if (studentProfileMode === null || !isStudentProfileDraftDirty()) {
      return undefined;
    }
    const handleSaveShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        void saveStudentProfile();
      }
    };
    window.addEventListener('keydown', handleSaveShortcut);
    return () => window.removeEventListener('keydown', handleSaveShortcut);
  }, [studentProfileMode, studentProfileDraft, savedStudentProfileDraft, studentProfileSaving, studentProfileLoading, studentProfileDeleting, studentCenterPermissions.canManageStudents]);

  const getClassTeacherUserId = (item: ClassItem) => resolveClassTeacherUserId(item, teacherBindingByClassId);
  const getClassEffectiveSubject = (item: ClassItem) => resolveClassEffectiveSubject(item, classes, teacherBindingByClassId, academicSubjectOptions);
  const scopedClassItems = classes.filter((item) => {
    if (!studentCenterPermissions.isTeacherScoped) {
      return true;
    }
    const itemTeacherUserId = getClassTeacherUserId(item);
    return itemTeacherUserId === currentUser.id || item.teacher_name === currentUser.display_name;
  });
  const classFilters = {
    subjectFilter: selectedSubjectFilter,
    teacherFilter: selectedClassTeacherFilter,
    stageFilter: selectedClassStageFilter,
    gradeFilter: selectedGradeFilter,
  };
  const classFilterOptions = resolveClassFilterOptions({
    classes: scopedClassItems,
    subjectLookupClasses: classes,
    users,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    stageOptions: studentCenterStageOptions,
    gradeOptions: studentCenterGradeOptions,
    gradeGroups: studentCenterGradeGroups,
    filters: classFilters,
  });
  const classSubjectFilterOptions = classFilterOptions.subjectOptions;
  const classTeacherFilterOptions = classFilterOptions.teacherOptions;
  const classStageFilterOptions = classFilterOptions.stageOptions;
  const classGradeFilterOptions = classFilterOptions.gradeOptions;
  const activeClassFilterSummary = buildClassFilterSummary(classFilters, users);
  const overviewFilters = {
    subjectFilter: overviewSubjectFilter,
    teacherFilter: overviewTeacherFilter,
    stageFilter: overviewStageFilter,
    gradeFilter: overviewGradeFilter,
  };
  const overviewFilterOptions = resolveOverviewFilterOptions({
    classes: scopedClassItems,
    subjectLookupClasses: classes,
    users,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    stageOptions: studentCenterStageOptions,
    gradeOptions: studentCenterGradeOptions,
    gradeGroups: studentCenterGradeGroups,
    filters: overviewFilters,
  });
  const overviewSubjectFilterOptions = overviewFilterOptions.subjectOptions;
  const overviewTeacherFilterOptions = overviewFilterOptions.teacherOptions;
  const overviewStageFilterOptions = overviewFilterOptions.stageOptions;
  const overviewGradeFilterOptions = overviewFilterOptions.gradeOptions;
  const activeOverviewFilterSummary = buildOverviewFilterSummary(overviewFilters, users);
  const overviewFilterItems = buildOverviewFilterItems(overviewFilters, studentCenterPermissions.canUseOrganizationScope);
  const handleClearOverviewFilters = () => {
    setOverviewSubjectFilter('全部学科');
    setOverviewTeacherFilter('all');
    setOverviewStageFilter('全部学段');
    setOverviewGradeFilter('全部');
    setActiveOverviewFilterLayer(null);
    setClickedOverviewFilterLayer(null);
  };
  const handleSelectOverviewFilterOption = (value: string | number) => {
    if (!activeOverviewFilterLayer) {
      return;
    }
    if (activeOverviewFilterLayer === 'subject') {
      setOverviewSubjectFilter(String(value));
    } else if (activeOverviewFilterLayer === 'teacher') {
      setOverviewTeacherFilter(value === 'all' ? 'all' : Number(value));
    } else if (activeOverviewFilterLayer === 'stage') {
      setOverviewStageFilter(String(value));
    } else {
      setOverviewGradeFilter(String(value));
    }
  };
  const handleOverviewFilterAreaEnter = () => {
    cancelFilterCloseTimer(overviewFilterCloseTimerRef, window.clearTimeout);
    setIsOverviewFilterOpen(true);
  };
  const handleOverviewFilterAreaLeave = () => {
    cancelFilterCloseTimer(overviewLayerCloseTimerRef, window.clearTimeout);
    scheduleFilterClose(overviewFilterCloseTimerRef, {
      clearTimeoutFn: window.clearTimeout,
      setTimeoutFn: window.setTimeout,
      onClose: () => {
        setIsOverviewFilterOpen(false);
        setActiveOverviewFilterLayer(null);
        setClickedOverviewFilterLayer(null);
      },
    });
  };
  const handleOverviewLayerEnter = () => {
    cancelFilterCloseTimer(overviewLayerCloseTimerRef, window.clearTimeout);
  };
  const handleOverviewLayerLeave = () => {
    scheduleFilterClose(overviewLayerCloseTimerRef, {
      clearTimeoutFn: window.clearTimeout,
      setTimeoutFn: window.setTimeout,
      onClose: () => {
        setActiveOverviewFilterLayer(null);
        setClickedOverviewFilterLayer(null);
      },
    });
  };
  const classFilterItems = buildClassFilterItems(classFilters, users);
  const handleClearClassFilter = (layer: typeof activeClassFilterLayer) => {
    if (layer === 'subject') {
      setSelectedSubjectFilter('全部学科');
      return;
    }
    if (layer === 'teacher') {
      setSelectedClassTeacherFilter('all');
      return;
    }
    if (layer === 'stage') {
      setSelectedClassStageFilter('全部学段');
      return;
    }
    setSelectedGradeFilter('全部');
  };
  const handleSelectClassFilterOption = (value: string | number) => {
    if (!activeClassFilterLayer) {
      return;
    }
    if (activeClassFilterLayer === 'subject') {
      setSelectedSubjectFilter(String(value));
    } else if (activeClassFilterLayer === 'teacher') {
      setSelectedClassTeacherFilter(value === 'all' ? 'all' : Number(value));
    } else if (activeClassFilterLayer === 'stage') {
      setSelectedClassStageFilter(String(value));
    } else {
      setSelectedGradeFilter(String(value));
    }
  };
  const handleClassFilterAreaEnter = () => {
    cancelFilterCloseTimer(classFilterCloseTimerRef, window.clearTimeout);
  };
  const handleClassFilterAreaLeave = () => {
    scheduleFilterClose(classFilterCloseTimerRef, {
      clearTimeoutFn: window.clearTimeout,
      setTimeoutFn: window.setTimeout,
      onClose: () => setActiveClassFilterLayer(null),
    });
  };
  useEffect(() => {
    if (selectedSubjectFilter !== '全部学科' && !classSubjectFilterOptions.includes(selectedSubjectFilter)) {
      setSelectedSubjectFilter('全部学科');
    }
    if (selectedClassTeacherFilter !== 'all' && !classTeacherFilterOptions.some((user) => user.id === selectedClassTeacherFilter)) {
      setSelectedClassTeacherFilter('all');
    }
    if (selectedClassStageFilter !== '全部学段' && !classStageFilterOptions.includes(selectedClassStageFilter)) {
      setSelectedClassStageFilter('全部学段');
    }
    if (selectedGradeFilter !== '全部' && !classGradeFilterOptions.includes(selectedGradeFilter)) {
      setSelectedGradeFilter('全部');
    }
  }, [classSubjectFilterOptions, classTeacherFilterOptions, classStageFilterOptions, classGradeFilterOptions, selectedSubjectFilter, selectedClassTeacherFilter, selectedClassStageFilter, selectedGradeFilter]);
  useEffect(() => {
    if (overviewSubjectFilter !== '全部学科' && !overviewSubjectFilterOptions.includes(overviewSubjectFilter)) {
      setOverviewSubjectFilter('全部学科');
    }
    if (overviewTeacherFilter !== 'all' && !overviewTeacherFilterOptions.some((user) => user.id === overviewTeacherFilter)) {
      setOverviewTeacherFilter('all');
    }
    if (overviewStageFilter !== '全部学段' && !overviewStageFilterOptions.includes(overviewStageFilter)) {
      setOverviewStageFilter('全部学段');
    }
    if (overviewGradeFilter !== '全部' && !overviewGradeFilterOptions.includes(overviewGradeFilter)) {
      setOverviewGradeFilter('全部');
    }
  }, [overviewSubjectFilterOptions, overviewTeacherFilterOptions, overviewStageFilterOptions, overviewGradeFilterOptions, overviewSubjectFilter, overviewTeacherFilter, overviewStageFilter, overviewGradeFilter]);
  const activeClassFilterOptions = resolveActiveClassFilterOptions(activeClassFilterLayer, classFilters, classFilterOptions);
  const activeOverviewFilterOptions = !activeOverviewFilterLayer
    ? []
    : activeOverviewFilterLayer === 'subject'
      ? overviewSubjectFilterOptions.map((option) => ({ id: option, label: option, selected: overviewSubjectFilter === option }))
      : activeOverviewFilterLayer === 'teacher'
        ? overviewTeacherFilterOptions.map((teacher) => ({ id: teacher.id, label: teacher.name, selected: overviewTeacherFilter === teacher.id }))
        : activeOverviewFilterLayer === 'stage'
          ? overviewStageFilterOptions.map((stage) => ({ id: stage, label: stage, selected: overviewStageFilter === stage }))
          : overviewGradeFilterOptions.map((grade) => ({ id: grade, label: grade, selected: overviewGradeFilter === grade }));
  const getClassInfoIssues = (item: ClassItem) => resolveClassInfoIssues(item, teacherBindingByClassId, academicSubjectOptions);
  const filteredClasses = resolveFilteredClasses({
    classes: scopedClassItems,
    subjectLookupClasses: classes,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    filters: classFilters,
  });
  const overviewFilteredClasses = resolveOverviewFilteredClasses({
    classes: scopedClassItems,
    subjectLookupClasses: classes,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    filters: overviewFilters,
  });
  const classSummaryItems = resolveOverviewSummaryItems({
    filteredClasses: overviewFilteredClasses,
    currentUser,
    canUseOrganizationScope: studentCenterPermissions.canUseOrganizationScope,
    teacherBindingByClassId,
  });

  const isClassFormDraftDirty = (classId: number | 'new') => {
    const currentForm = formByClassId[getClassStateKey(classId)] || createEmptyClassForm();
    const savedClass = classId === 'new' ? null : classes.find((item) => item.id === classId) ?? null;
    const savedForm = classId === 'new' ? createEmptyClassForm() : (savedClass ? toClassFormValues(savedClass) : null);
    const currentTeacherUserId = classId === 'new' ? null : (teacherBindingByClassId[classId] ?? savedClass?.teacher_user_id ?? null);
    const savedTeacherUserId = classId === 'new' ? null : (savedClass?.teacher_user_id ?? null);
    return resolveClassFormDraftDirty({
      classId,
      currentForm,
      savedForm,
      newClassTeacherUserId,
      currentTeacherUserId,
      savedTeacherUserId,
      currentStudentIds: classId === 'new' ? undefined : (studentsByClassId[classId] || []).map((student) => student.id),
      savedStudentIds: classId === 'new' ? undefined : (savedStudentsByClassId[classId] || []).map((student) => student.id),
    });
  };
  const canSaveExpandedClassDraft = expandedClassId !== null && isClassFormDraftDirty(expandedClassId);

  const classEditorModalState = buildClassEditorModalState({
    expandedClassId,
    classes,
    users,
    formByClassId,
    emptyClassForm: createEmptyClassForm(),
    teacherSearchByClassId,
    newClassTeacherUserId,
    teacherBindingByClassId,
    teacherBindingSavingByClassId,
    inviteByClassId,
    inviteLoadingByClassId,
    inviteResettingByClassId,
    inviteErrorByClassId,
    studentsByClassId,
    allStudents,
    studentsLoadingByClassId,
    studentSavingByClassId,
    studentErrorByClassId,
    studentDraftNameByClassId,
    gradeGroups: studentCenterGradeGroups,
    gradeOptions: studentCenterGradeOptions,
    canEditTeacherBinding: studentCenterPermissions.canEditTeacherBinding,
    classCardInteractionLocked,
    classInteractionLocked,
    assignmentRefreshLocked,
    saving,
    deleting,
    formError,
    assignmentError,
    academicSubjectOptions,
    studentCenterStageOptions,
  });
  const {
    mode: classEditorMode,
    locks: classEditorLocks,
    errors: classEditorErrors,
    options: classEditorOptions,
    newClass: classEditorNewClass,
    editing: classEditorEditing,
  } = classEditorModalState;
  const { editingClass } = classEditorMode;
  const getClassDisplayName = (item: ClassItem) => getCurrentClassDisplayName(item, showClassCohortYear);
  const resetClassFormDraft = (classId: number | 'new') => {
    if (classId === 'new') {
      setFormByClassId((current) => resolveFormsAfterClassDraftReset(current, classId, createEmptyClassForm()));
      setNewClassTeacherUserId((current) => resolveNewClassTeacherAfterDraftReset(classId, current));
      setTeacherSearchByClassId((current) => resolveTeacherSearchAfterClassDraftReset(current, classId));
      return;
    }
    const savedClass = classes.find((item) => item.id === classId);
    if (!savedClass) {
      return;
    }
    setFormByClassId((current) => resolveFormsAfterClassDraftReset(current, classId, toClassFormValues(savedClass)));
    setTeacherBindingByClassId((current) => ({ ...current, [classId]: savedClass.teacher_user_id ?? null }));
    if (Object.prototype.hasOwnProperty.call(savedStudentsByClassId, classId)) {
      setStudentsByClassId((current) => ({ ...current, [classId]: savedStudentsByClassId[classId] || [] }));
    }
  };
  const attemptCloseClassEditor = () => {
    if (expandedClassId === null) {
      return;
    }
    if (isClassFormDraftDirty(expandedClassId) && !window.confirm('有未保存的修改，确定放弃并关闭吗？')) {
      return;
    }
    resetClassFormDraft(expandedClassId);
    setFormError('');
    setAssignmentError('');
    setExpandedClassId(null);
  };
  const studentRows = buildStudentRows({
    classes: scopedClassItems,
    studentsByClassId,
    allStudents,
    teacherBindingByClassId,
  });
  const studentFilters = {
    subjectFilter: studentSubjectFilter,
    teacherFilter: studentTeacherFilter,
    stageFilter: studentStageFilter,
    gradeFilter: studentGradeFilter,
    classFilter: studentClassFilter,
    nameFilter: studentNameFilter,
    scheduleStatusFilter: studentScheduleStatusFilter,
  };
  const studentFilterOptions = resolveStudentFilterOptions({
    rows: studentRows,
    classes,
    scopedClasses: scopedClassItems,
    users,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    stageOptions: studentCenterStageOptions,
    gradeOptions: studentCenterGradeOptions,
    gradeGroups: studentCenterGradeGroups,
    filters: studentFilters,
  });
  const studentSubjectFilterOptions = studentFilterOptions.subjectOptions;
  const studentTeacherFilterOptions = studentFilterOptions.teacherOptions;
  const studentStageFilterOptions = studentFilterOptions.stageOptions;
  const studentGradeFilterOptions = studentFilterOptions.gradeOptions;
  const studentClassFilterOptions = studentFilterOptions.classOptions;
  const filteredStudentRows = resolveFilteredStudentRows({
    rows: studentRows,
    classes,
    teacherBindingByClassId,
    subjectOptions: academicSubjectOptions,
    filters: studentFilters,
  });
  const activeStudentFilterSummary = buildStudentFilterSummary(studentFilters, users, scopedClassItems);
  const studentFilterItems = buildStudentFilterItems(studentFilters, users, scopedClassItems);
  const handleClearStudentFilter = (layer: typeof activeStudentFilterLayer) => {
    if (layer === 'subject') {
      setStudentSubjectFilter('全部学科');
      return;
    }
    if (layer === 'teacher') {
      setStudentTeacherFilter('all');
      return;
    }
    if (layer === 'stage') {
      setStudentStageFilter('全部学段');
      return;
    }
    if (layer === 'grade') {
      setStudentGradeFilter('全部');
      return;
    }
    setStudentClassFilter('all');
  };
  const handleSelectStudentFilterOption = (value: string | number) => {
    if (!activeStudentFilterLayer) {
      return;
    }
    if (activeStudentFilterLayer === 'subject') {
      setStudentSubjectFilter(String(value));
    } else if (activeStudentFilterLayer === 'teacher') {
      setStudentTeacherFilter(value === 'all' ? 'all' : Number(value));
    } else if (activeStudentFilterLayer === 'stage') {
      setStudentStageFilter(String(value));
    } else if (activeStudentFilterLayer === 'grade') {
      setStudentGradeFilter(String(value));
    } else if (activeStudentFilterLayer === 'class') {
      setStudentClassFilter(value === 'all' ? 'all' : Number(value));
    }
  };
  const handleStudentFilterAreaEnter = () => {
    cancelFilterCloseTimer(studentFilterCloseTimerRef, window.clearTimeout);
  };
  const handleStudentFilterAreaLeave = () => {
    scheduleFilterClose(studentFilterCloseTimerRef, {
      clearTimeoutFn: window.clearTimeout,
      setTimeoutFn: window.setTimeout,
      onClose: () => setActiveStudentFilterLayer(null),
    });
  };
  const handleStudentScheduleStatusFilterChange = (value: StudentScheduleStatusFilter) => {
    setStudentScheduleStatusFilter(value);
    if (value !== 'scheduled') {
      setActiveStudentFilterLayer(null);
    }
  };
  useEffect(() => {
    if (studentSubjectFilter !== '全部学科' && !studentSubjectFilterOptions.includes(studentSubjectFilter)) {
      setStudentSubjectFilter('全部学科');
    }
    if (studentTeacherFilter !== 'all' && !studentTeacherFilterOptions.some((user) => user.id === studentTeacherFilter)) {
      setStudentTeacherFilter('all');
    }
    if (studentStageFilter !== '全部学段' && !studentStageFilterOptions.includes(studentStageFilter)) {
      setStudentStageFilter('全部学段');
    }
    if (studentGradeFilter !== '全部' && !studentGradeFilterOptions.includes(studentGradeFilter)) {
      setStudentGradeFilter('全部');
    }
    if (studentClassFilter !== 'all' && !studentClassFilterOptions.some((item) => item.id === studentClassFilter)) {
      setStudentClassFilter('all');
    }
  }, [studentSubjectFilterOptions, studentTeacherFilterOptions, studentStageFilterOptions, studentGradeFilterOptions, studentClassFilterOptions, studentSubjectFilter, studentTeacherFilter, studentStageFilter, studentGradeFilter, studentClassFilter]);
  const activeStudentFilterOptions = resolveActiveStudentFilterOptions(activeStudentFilterLayer, studentFilters, studentFilterOptions);
  const handleClassCardClick = (event: React.MouseEvent, classId: number) => {
    if ((event.target as HTMLElement).closest('button, a, input, select, textarea')) {
      return;
    }
    handleToggleExpandedClass(classId);
  };
  const classEditorActions = useClassEditorModalActions({
    editingClass,
    setFormByClassId,
    getClassStateKey,
    loadPage,
    attemptCloseClassEditor,
    handleSaveClass,
    handleFieldChange,
    handleTeacherSearchChange,
    setNewClassTeacherUserId,
    handleLoadClassInvite,
    handleCopyClassInvite,
    handleResetClassInvite,
    handleSelectTeacherForClass,
    handleDeleteClass,
    handleNewClassStudentSelectionChange,
    handleStudentDraftNameChange,
    handleAddStudentToClass,
    handleDeleteStudentFromClass,
    handleOpenStudentProfile: (studentId) => {
      void openStudentProfile(studentId);
    },
  });

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <CampusOverview
        currentUser={currentUser}
        classBindingTarget={classBindingTarget}
        onClearClassBindingTarget={onClearClassBindingTarget}
        activeHelpKey={activeClassHelpKey}
        onHelpEnter={() => setActiveClassHelpKey('overview')}
        onHelpLeave={() => setActiveClassHelpKey(null)}
        onHelpToggle={() => setActiveClassHelpKey((current) => current === 'overview' ? null : 'overview')}
        selectedSummary={activeOverviewFilterSummary}
        open={isOverviewFilterOpen}
        items={overviewFilterItems}
        activeKey={activeOverviewFilterLayer}
        options={activeOverviewFilterOptions}
        summaryItems={classSummaryItems}
        onAreaEnter={handleOverviewFilterAreaEnter}
        onAreaLeave={handleOverviewFilterAreaLeave}
        onTriggerClick={() => {
          setIsOverviewFilterOpen((currentOpen) => {
            const nextState = resolveOverviewFilterTriggerClick({
              open: currentOpen,
              activeLayer: activeOverviewFilterLayer,
              clickedLayer: clickedOverviewFilterLayer,
            });
            setActiveOverviewFilterLayer(nextState.activeLayer);
            setClickedOverviewFilterLayer(nextState.clickedLayer);
            return nextState.open;
          });
        }}
        onLayerEnter={handleOverviewLayerEnter}
        onLayerLeave={handleOverviewLayerLeave}
        onHoverItem={(key) => {
          const nextState = resolveOverviewFilterItemHover(key);
          setActiveOverviewFilterLayer(nextState.activeLayer);
          setClickedOverviewFilterLayer(nextState.clickedLayer);
        }}
        onClickItem={(key) => {
          const nextState = resolveOverviewFilterItemClick({
            activeLayer: activeOverviewFilterLayer,
            clickedLayer: clickedOverviewFilterLayer,
            targetLayer: key,
          });
          setActiveOverviewFilterLayer(nextState.activeLayer);
          setClickedOverviewFilterLayer(nextState.clickedLayer);
        }}
        onClear={handleClearOverviewFilters}
        onSelect={handleSelectOverviewFilterOption}
      />

      {pageError && (
        <div className="flex items-center gap-2 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300">
          <AlertCircle size={16} />
          {pageError}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 rounded-2xl bg-sky-50 p-1 dark:bg-white/5">
        {[
          { key: 'classes' as const, label: '班级管理' },
          { key: 'students' as const, label: '学员管理' },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => setStudentCenterTab(item.key)}
            className={cn(
              'h-10 rounded-xl text-sm font-bold transition',
              studentCenterTab === item.key
                ? 'bg-white text-sky-700 shadow-sm dark:bg-sky-400/15 dark:text-sky-100'
                : 'text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {studentCenterTab === 'students' && (
        <StudentManagementTab
          filteredStudentRows={filteredStudentRows}
          users={users}
          studentFilterItems={studentFilterItems}
          activeStudentFilterLayer={activeStudentFilterLayer}
          activeStudentFilterOptions={activeStudentFilterOptions}
          studentScopeLabel={studentCenterPermissions.studentScopeLabel}
          activeStudentFilterSummary={activeStudentFilterSummary}
          studentNameFilter={studentNameFilter}
          scheduleStatusFilter={studentScheduleStatusFilter}
          canManageStudents={studentCenterPermissions.canManageStudents}
          onStudentFilterAreaEnter={handleStudentFilterAreaEnter}
          onStudentFilterAreaLeave={handleStudentFilterAreaLeave}
          onActivateStudentFilter={setActiveStudentFilterLayer}
          onClearStudentFilter={handleClearStudentFilter}
          onSelectStudentFilterOption={handleSelectStudentFilterOption}
          onStudentNameFilterChange={setStudentNameFilter}
          onScheduleStatusFilterChange={handleStudentScheduleStatusFilterChange}
          onCreateStudent={openCreateStudentProfile}
          onOpenStudentProfile={(studentId) => {
            void openStudentProfile(studentId);
          }}
          getClassDisplayName={getClassDisplayName}
        />
      )}

      {studentCenterTab === 'classes' && (
        <ClassManagementTab
          loading={loading}
          classes={classes}
          filteredClasses={filteredClasses}
          users={users}
          studentsByClassId={studentsByClassId}
          teacherBindingByClassId={teacherBindingByClassId}
          expandedClassId={expandedClassId}
          classCardInteractionLocked={classCardInteractionLocked}
          pageRefreshLocked={pageRefreshLocked}
          canCreateClass={studentCenterPermissions.canCreateClass}
          classScopeLabel={studentCenterPermissions.classScopeLabel}
          classFilterItems={classFilterItems}
          activeClassFilterLayer={activeClassFilterLayer}
          activeClassFilterOptions={activeClassFilterOptions}
          activeClassFilterSummary={activeClassFilterSummary}
          showClassCohortYear={showClassCohortYear}
          subjectOptions={academicSubjectOptions}
          onRefresh={() => loadPage(expandedClassId, { preserveStateOnError: true }).catch(() => undefined)}
          onCreateClass={() => handleToggleExpandedClass('new')}
          onClassFilterAreaEnter={handleClassFilterAreaEnter}
          onClassFilterAreaLeave={handleClassFilterAreaLeave}
          onActivateClassFilter={setActiveClassFilterLayer}
          onClearClassFilter={handleClearClassFilter}
          onSelectClassFilterOption={handleSelectClassFilterOption}
          onShowClassCohortYearChange={setShowClassCohortYear}
          onClassCardClick={handleClassCardClick}
          onToggleExpandedClass={handleToggleExpandedClass}
          getClassEffectiveSubject={getClassEffectiveSubject}
          getClassInfoIssues={getClassInfoIssues}
          getClassDisplayName={getClassDisplayName}
        />
      )}

      <ClassEditorModal
        mode={classEditorMode}
        locks={classEditorLocks}
        errors={classEditorErrors}
        options={classEditorOptions}
        canSaveClassDraft={canSaveExpandedClassDraft}
        teacherSearchByClassId={teacherSearchByClassId}
        users={users}
        newClass={classEditorNewClass}
        editing={classEditorEditing}
        actions={classEditorActions}
        getClassDisplayName={getClassDisplayName}
      />

      <StudentProfileModal
        mode={studentProfileMode}
        draft={studentProfileDraft}
        savedDraft={savedStudentProfileDraft}
        detail={studentProfileDetail}
        canManageStudents={studentCenterPermissions.canManageStudents}
        loading={studentProfileLoading}
        saving={studentProfileSaving}
        deleting={studentProfileDeleting}
        error={studentProfileError}
        duplicateWarning={studentProfileDuplicateWarning}
        onDraftChange={handleStudentProfileDraftChange}
        onSave={() => void saveStudentProfile()}
        onDeleteOrArchive={() => void deleteOrArchiveStudentProfile()}
        onClose={closeStudentProfile}
      />
    </div>
  );
}
