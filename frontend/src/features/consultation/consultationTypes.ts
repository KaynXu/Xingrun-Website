export interface ConsultationRecord {
  id: number;
  date: string;
  parent_wechat_name: string;
  child_name: string;
  grade: string;
  receiving_teacher: string;
  teacher_id: string;
  teacher_display_name?: string;
  consultation_subject: string;
  need_detail: string;
  source_channel: string;
  source_channel_note: string;
  screenshot: string;
  follow_up_status: string;
  follow_up_note: string;
  flow_stage: string;
  completed_stages: string[];
  stage_teacher_ids: Record<string, string>;
  assigned_stage: string;
  assignment_note: string;
  is_transferred_consultation: boolean;
  can_edit_consultation: boolean;
  transfer_marker: string;
  current_responsibility: string;
  customer_service_added: string;
  customer_service_teacher: string;
  customer_service_note: string;
  communication_teacher_added: string;
  communication_teacher_note: string;
  test_taken: string;
  test_teacher: string;
  test_note: string;
  test_images: Array<{ url: string; filename: string }>;
  trial_teacher_added: string;
  trial_teacher_note: string;
  trial_taken: string;
  trial_time_slot: string;
  trial_class_id: number | null;
  trial_class_manual: string;
  trial_teacher: string;
  trial_feedback: string;
  success_class_id: number | null;
  teaching_teacher_added: string;
  teaching_teacher: string;
  teaching_teacher_user_id?: number | null;
  teaching_teacher_note: string;
  success_class_manual: string;
  closing_result: string;
  end_note: string;
  ended_at: string;
  created_at: string;
  updated_at: string;
}

export type ConsultationFormValues = Omit<ConsultationRecord, 'id' | 'created_at' | 'updated_at'>;
export type ConsultationResultStage = '成功进班' | '试听失败';
export type ConsultationScope = 'current' | 'history';
export type ConsultationOwnership = 'all' | 'created' | 'transferred';
export type ConsultationFilterKey =
  | 'pending-7'
  | 'pending-30'
  | 'pending-over30'
  | 'ended-success'
  | 'ended-unsuccessful';

export interface ConsultationTeacherOption {
  teacher_id: string;
  display_name: string;
  aliases: string[];
}

export interface ConsultationBatchDraftItem {
  action: 'create' | 'update';
  target_id: number | null;
  reason: string;
  fields: Partial<ConsultationFormValues>;
  warnings: string[];
}

export interface ConsultationBatchParseResponse {
  items: ConsultationBatchDraftItem[];
  warnings: string[];
}
