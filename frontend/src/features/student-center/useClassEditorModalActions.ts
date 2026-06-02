import { useMemo, type Dispatch, type SetStateAction } from 'react';
import { parseBridgeTarget, serializeBridgeTarget } from '../../domain/classNaming';
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
  handleCopyClassInvite: (classId: number) => Promise<void>;
  handleResetClassInvite: (classId: number) => Promise<void>;
  handleSelectTeacherForClass: (classId: number, teacherUserId: number) => Promise<void>;
  handleDeleteClass: (classId: number) => void;
  handleNewClassStudentSelectionChange: (studentId: number, checked: boolean) => void;
  handleStudentDraftNameChange: (classId: number, value: string) => void;
  handleAddStudentToClass: (classId: number, studentId: number) => Promise<void>;
  handleDeleteStudentFromClass: (classId: number, studentId: number) => Promise<void>;
  handleOpenStudentProfile: (studentId: number) => void;
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
  handleCopyClassInvite,
  handleResetClassInvite,
  handleSelectTeacherForClass,
  handleDeleteClass,
  handleNewClassStudentSelectionChange,
  handleStudentDraftNameChange,
  handleAddStudentToClass,
  handleDeleteStudentFromClass,
  handleOpenStudentProfile,
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
        bridge_target: checked
          ? serializeBridgeTarget(
            parseBridgeTarget((current.new || createEmptyClassForm()).bridge_target, (current.new || createEmptyClassForm()).stage).fromStage,
            parseBridgeTarget((current.new || createEmptyClassForm()).bridge_target, (current.new || createEmptyClassForm()).stage).toStage,
          )
          : (current.new || createEmptyClassForm()).bridge_target,
      },
    })),
    onEditingClassBridgeChange: (checked) => {
      if (!editingClass) {
        return;
      }
      const stateKey = getClassStateKey(editingClass.id);
      setFormByClassId((current) => ({
        ...current,
        [stateKey]: (() => {
          const currentForm = current[stateKey] || toClassFormValues(editingClass);
          const bridge = parseBridgeTarget(currentForm.bridge_target, currentForm.stage);
          return {
            ...currentForm,
            is_bridge: checked,
            bridge_target: checked ? serializeBridgeTarget(bridge.fromStage, bridge.toStage) : currentForm.bridge_target,
          };
        })(),
      }));
    },
    onTeacherSearchChange: handleTeacherSearchChange,
    onNewClassTeacherUserIdChange: setNewClassTeacherUserId,
    onLoadClassInvite: (classId) => void handleLoadClassInvite(classId),
    onCopyClassInvite: handleCopyClassInvite,
    onResetClassInvite: (classId) => void handleResetClassInvite(classId),
    onRefreshAssignment: (classId) => loadPage(classId, { preserveStateOnError: true }).catch(() => undefined),
    onSelectTeacherForClass: (classId, teacherUserId) => void handleSelectTeacherForClass(classId, teacherUserId),
    onDeleteClass: handleDeleteClass,
    onNewClassStudentSelectionChange: handleNewClassStudentSelectionChange,
    onStudentDraftNameChange: handleStudentDraftNameChange,
    onAddStudentToClass: (classId, studentId) => void handleAddStudentToClass(classId, studentId),
    onDeleteStudentFromClass: (classId, studentId) => void handleDeleteStudentFromClass(classId, studentId),
    onOpenStudentProfile: handleOpenStudentProfile,
  }), [
    attemptCloseClassEditor,
    editingClass,
    getClassStateKey,
    handleAddStudentToClass,
    handleDeleteClass,
    handleDeleteStudentFromClass,
    handleFieldChange,
    handleLoadClassInvite,
    handleCopyClassInvite,
    handleNewClassStudentSelectionChange,
    handleOpenStudentProfile,
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
