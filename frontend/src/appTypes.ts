export type Role = 'super_owner' | 'owner' | 'admin' | 'member';

export type WorkspacePage =
  | 'dashboard'
  | 'review-generation'
  | 'class-feedback-generation'
  | 'consultation'
  | 'calendar'
  | 'smartWrongQuestions'
  | 'classes'
  | 'accounts'
  | 'credit'
  | 'settings';

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

export interface CurrentUser {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  status: string;
  organization_id: number;
  organization_name: string;
  created_at: string;
  visible_pages?: WorkspacePage[];
  requires_class_claim?: boolean;
  avatar_source?: 'dicebear' | 'upload';
  avatar_seed?: string;
  avatar_upload_url?: string;
}

export interface UserItem {
  id: number;
  name: string;
  org: string;
  role: Role;
  username?: string;
  last_login?: string | null;
  visible_pages?: WorkspacePage[];
  avatar_source?: 'dicebear' | 'upload';
  avatar_seed?: string;
  avatar_upload_url?: string;
}

export type ClassBindingTarget = {
  teacherUserId: number;
  teacherName: string;
};
