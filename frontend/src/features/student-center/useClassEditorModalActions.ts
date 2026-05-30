import { useMemo, type Dispatch, type SetStateAction } from 'react';
import type { ClassEditorActions } from './ClassEditorModal';
import {
  createEmptyClassForm,
  toClassFormValues,
  type ClassFormValues,
  type ClassItem,
  type LoadPageResult,
} from './model';

type UseClassEditorModalActionsParams = {
  editingClass: ClassItem | null;
  setFormByClassId: Dispatch<SetStateAction<Record<string, ClassFormValues>>>;
  getClassStateKey: (classId: number | 'new') => string;
  loadPage: (preferredExpandedClassId?: number | 'new' | null, options?: { preserveStateOnError?: boolean }) => Promise<LoadPageResult>;
  attemptCloseClassEditor: () => void;
  handleSaveClass: (classId: number | 'new') => void;
  handleFieldChange: (classId: number | 'new', key: keyof ClassFormValues, value: string) => void;
  handleTeacherSearchChange: (classId: number | 'new', value: string) => void;
  setNewClassTeacherUserId: Dispatch<SetStateAction<number | null>>;
  handleLoadClassInvite: (classId: number) => Promise<void>;
  handleResetClassInvite: (classId: number) => Promise<void>;
  handleSelectTeacherForClass: (classId: number, teacherUserId: number) => Promise<void>;
  handleDeleteClass: (classId: number) => void;
  handleStudentDraftNameChange: (classId: number, value: string) => void;
  handleAddStudentToClass: (classId: number) => Promise<void>;
  handleDeleteStudentFromClass: (classId: number, studentId: number) => Promise<void>;
};

export function useClassEditorModalActions({
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
  handleResetClassInvite,
  handleSelectTeacherForClass,
  handleDeleteClass,
  handleStudentDraftNameChange,
  handleAddStudentToClass,
  handleDeleteStudentFromClass,
}: UseClassEditorModalActionsParams): ClassEditorActions {
  return useMemo(() => ({
    onClose: attemptCloseClassEditor,
    onSaveClass: handleSaveClass,
    onFieldChange: handleFieldChange,
    onNewClassBridgeChange: (checked) => setFormByClassId((current) => ({
      ...current,
      new: {
        ...(current.new || createEmptyClassForm()),
        is_bridge: checked,
      },
    })),
    onEditingClassBridgeChange: (checked) => {
      if (!editingClass) {
        return;
      }
      const stateKey = getClassStateKey(editingClass.id);
      setFormByClassId((current) => ({
        ...current,
        [stateKey]: {
          ...(current[stateKey] || toClassFormValues(editingClass)),
          is_bridge: checked,
        },
      }));
    },
    onTeacherSearchChange: handleTeacherSearchChange,
    onNewClassTeacherUserIdChange: setNewClassTeacherUserId,
    onLoadClassInvite: (classId) => void handleLoadClassInvite(classId),
    onResetClassInvite: (classId) => void handleResetClassInvite(classId),
    onRefreshAssignment: (classId) => loadPage(classId, { preserveStateOnError: true }).catch(() => undefined),
    onSelectTeacherForClass: (classId, teacherUserId) => void handleSelectTeacherForClass(classId, teacherUserId),
    onDeleteClass: handleDeleteClass,
    onStudentDraftNameChange: handleStudentDraftNameChange,
    onAddStudentToClass: (classId) => void handleAddStudentToClass(classId),
    onDeleteStudentFromClass: (classId, studentId) => void handleDeleteStudentFromClass(classId, studentId),
  }), [
    attemptCloseClassEditor,
    editingClass,
    getClassStateKey,
    handleAddStudentToClass,
    handleDeleteClass,
    handleDeleteStudentFromClass,
    handleFieldChange,
    handleLoadClassInvite,
    handleResetClassInvite,
    handleSaveClass,
    handleSelectTeacherForClass,
    handleStudentDraftNameChange,
    handleTeacherSearchChange,
    loadPage,
    setFormByClassId,
    setNewClassTeacherUserId,
  ]);
}
