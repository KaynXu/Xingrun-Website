import { normalizeAcademicGradeLabel, serializeBridgeTarget } from '../../domain/classNaming';

export type StudentCenterRole = 'super_owner' | 'owner' | 'admin' | 'member';

export interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: StudentCenterRole;
  status: string;
  organization_id: number;
  organization_name: string;
  created_at: string;
  visible_pages?: string[];
  requires_class_claim?: boolean;
}

export interface ClassItem {
  id: number;
  name: string;
  class_type?: string;
  subject: string;
  grade: string;
  stage?: string;
  current_grade?: string;
  class_number?: string;
  cohort_year?: number;
  show_cohort_year?: boolean | number;
  is_bridge?: boolean;
  bridge_target?: string;
  content_track?: string;
  last_promoted_at?: string;
  teacher_name?: string;
  teacher_email?: string;
  teacher_user_id?: number | null;
  lesson_count?: number;
  student_count?: number;
}

export interface UserItem {
  id: number;
  name: string;
  org: string;
  role: StudentCenterRole;
  username?: string;
  last_login?: string | null;
  visible_pages?: string[];
}

export type ClassStudentOption = {
  id: number;
  name: string;
  source?: string;
  parent_contact?: string;
  status?: string;
  archived_at?: string;
  created_at?: string;
  study_status?: string;
  study_duration_label?: string;
  first_lesson_date?: string | null;
  last_lesson_date?: string | null;
  study_records?: Array<{
    class_id: number;
    class_name?: string;
    class_type?: string;
    subject?: string;
    stage?: string;
    current_grade?: string;
    grade?: string;
    teacher_name?: string;
    lesson_count?: number;
    first_lesson_date?: string | null;
    last_lesson_date?: string | null;
  }>;
  history_items?: Array<{
    id?: number;
    class_id?: number;
    class_name?: string;
    action?: string;
    created_at?: string;
    note?: string;
  }>;
};

export interface ClassInviteInfo {
  id: number;
  class_id: number;
  invite_code: string;
  status: string;
  created_at: string;
}

export type ClassBindingTarget = {
  teacherUserId: number;
  teacherName: string;
};

export interface ClassFormValues {
  name: string;
  class_type: string;
  subject: string;
  grade: string;
  teacher_name: string;
  stage: string;
  current_grade: string;
  class_number: string;
  cohort_year: string;
  show_cohort_year: boolean;
  is_bridge: boolean;
  bridge_target: string;
  content_track: string;
  selected_student_ids: number[];
}

export type LoadPageResult =
  | { status: 'success' }
  | { status: 'stale' }
  | { status: 'refresh-error'; error: Error };

export function getClassFormDirtySignature(form: Pick<ClassFormValues, 'class_type' | 'subject' | 'stage' | 'current_grade' | 'grade' | 'class_number' | 'cohort_year' | 'is_bridge' | 'bridge_target' | 'content_track'>): string {
  return JSON.stringify({
    subject: form.subject.trim(),
    class_type: form.class_type || 'group',
    stage: form.stage,
    current_grade: normalizeAcademicGradeLabel(form.current_grade || form.grade),
    class_number: form.class_number.trim(),
    cohort_year: form.cohort_year ? String(Number(form.cohort_year)) : '',
    is_bridge: Boolean(form.is_bridge),
    bridge_target: form.bridge_target || '',
    content_track: form.content_track || '',
  });
}

export function createEmptyClassForm(): ClassFormValues {
  return {
    name: '',
    class_type: 'group',
    subject: '',
    grade: '',
    teacher_name: '',
    stage: '小奥',
    current_grade: '一年级',
    class_number: '1',
    cohort_year: '',
    show_cohort_year: false,
    is_bridge: false,
    bridge_target: serializeBridgeTarget('小学', '初中'),
    content_track: '',
    selected_student_ids: [],
  };
}

export function toClassFormValues(item: ClassItem): ClassFormValues {
  return {
    name: item.name || '',
    class_type: item.class_type || 'group',
    subject: item.subject || '',
    grade: item.grade || '',
    teacher_name: item.teacher_name || '',
    stage: item.stage || '',
    current_grade: normalizeAcademicGradeLabel(item.current_grade || item.grade || ''),
    class_number: item.class_number || '',
    cohort_year: item.cohort_year ? String(item.cohort_year) : '',
    show_cohort_year: item.show_cohort_year !== false && item.show_cohort_year !== 0,
    is_bridge: Boolean(item.is_bridge),
    bridge_target: item.bridge_target || serializeBridgeTarget(item.stage || '', ''),
    content_track: item.content_track || '',
    selected_student_ids: [],
  };
}
