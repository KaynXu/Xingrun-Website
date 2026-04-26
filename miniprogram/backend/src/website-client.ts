interface WebsiteRequestOptions {
  method?: string;
  body?: Record<string, unknown>;
}

function getWebsiteBridgeConfig() {
  return {
    baseUrl: String(process.env.WEBSITE_API_BASE_URL || 'https://xingrun.online').trim().replace(/\/+$/, ''),
    token: String(process.env.WEBSITE_API_TOKEN || '').trim(),
  };
}

async function readWebsiteError(response: Response): Promise<string> {
  const payload = await response.json().catch(() => null);
  if (payload && typeof payload === 'object' && typeof payload.error === 'string' && payload.error.trim()) {
    return payload.error.trim();
  }

  return `网站接口请求失败：HTTP ${response.status}`;
}

async function requestWebsite<T>(path: string, options: WebsiteRequestOptions = {}): Promise<T> {
  const config = getWebsiteBridgeConfig();
  if (!config.token) {
    throw new Error('缺少 WEBSITE_API_TOKEN 配置');
  }
  if (!config.baseUrl) {
    throw new Error('缺少 WEBSITE_API_BASE_URL 配置');
  }

  const response = await fetch(`${config.baseUrl}${path}`, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Wechat-Service-Token': config.token,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    throw new Error(await readWebsiteError(response));
  }

  return response.json() as Promise<T>;
}

export interface WebsiteWechatAccount {
  id: number;
  openid: string;
  nickname_snapshot?: string;
  avatar_url_snapshot?: string;
  status?: string;
}

export interface WebsiteClassInvitePreview {
  class_id: number;
  class_name?: string;
  students: Array<{ id: number; name: string }>;
}

export interface WebsiteParentBinding {
  id: number;
  class_id: number;
  class_name?: string;
  student_id: number;
  student_name?: string;
  teacher_user_id: number | null;
  teacher_name?: string;
  status: string;
}

export interface WebsiteWrongQuestionSubmission {
  id: string;
  binding_id: number;
  class_id: number;
  student_id: number;
  teacher_user_id: number | null;
  source: string;
  status: string;
  image_url: string;
  parent_note?: string;
  teacher_comment?: string;
}

export interface WebsiteReasonTranscription {
  transcript_text: string;
}

export interface WebsiteReasonClassification {
  display_text: string;
  primary_error_type: string;
  secondary_error_summary: string;
}

export interface WebsiteWrongQuestionUploadTask {
  id: number;
  binding_id: number;
  student_id: number;
  image_url: string;
  child_raw_reason_text?: string;
  child_reason_input_mode?: string;
  child_reason_audio_url?: string;
  status: string;
  record_id?: string;
  error_message?: string;
}

export async function loginParentWechatAccount(input: {
  openId: string;
  nicknameSnapshot?: string;
  avatarUrlSnapshot?: string;
}) {
  return requestWebsite<{ account: WebsiteWechatAccount }>('/api/wechat/login', {
    method: 'POST',
    body: {
      open_id: input.openId,
      nickname_snapshot: input.nicknameSnapshot || '',
      avatar_url_snapshot: input.avatarUrlSnapshot || '',
    },
  });
}

export async function previewParentClassBinding(input: {
  openId: string;
  inviteCode: string;
}) {
  return requestWebsite<WebsiteClassInvitePreview>('/api/wechat/bind-class', {
    method: 'POST',
    body: {
      open_id: input.openId,
      invite_code: input.inviteCode,
    },
  });
}

export async function bindParentStudentOnWebsite(input: {
  openId: string;
  classId: number;
  studentId: number;
}) {
  return requestWebsite<{ binding: WebsiteParentBinding }>('/api/wechat/bind-student', {
    method: 'POST',
    body: {
      open_id: input.openId,
      class_id: input.classId,
      student_id: input.studentId,
    },
  });
}

export async function listParentBindingsOnWebsite(input: {
  openId: string;
}) {
  const normalizedOpenId = String(input.openId || '').trim();
  const query = new URLSearchParams({ open_id: normalizedOpenId });
  return requestWebsite<{ bindings: WebsiteParentBinding[] }>(`/api/wechat/bindings?${query.toString()}`);
}

export async function transcribeParentReasonOnWebsite(input: {
  audioUrl: string;
}) {
  return requestWebsite<WebsiteReasonTranscription>('/api/wechat/reason-transcriptions', {
    method: 'POST',
    body: {
      audio_url: input.audioUrl,
    },
  });
}

export async function classifyParentReasonOnWebsite(input: {
  childReasonText: string;
}) {
  return requestWebsite<WebsiteReasonClassification>('/api/wechat/reason-classifications', {
    method: 'POST',
    body: {
      child_reason_text: input.childReasonText,
    },
  });
}

export async function submitWechatWrongQuestionToWebsite(input: {
  openId: string;
  bindingId: number;
  imageUrl: string;
  childReasonText: string;
  childReasonInputMode?: string;
  childReasonAudioUrl?: string;
}) {
  return requestWebsite<{ task: WebsiteWrongQuestionUploadTask; student_library_pdf_url?: string }>('/api/wechat/wrong-questions', {
    method: 'POST',
    body: {
      open_id: input.openId,
      binding_id: input.bindingId,
      image_url: input.imageUrl,
      child_raw_reason_text: input.childReasonText,
      child_reason_input_mode: input.childReasonInputMode || 'text',
      child_reason_audio_url: input.childReasonAudioUrl || '',
    },
  });
}

export async function getWrongQuestionUploadTaskOnWebsite(input: {
  openId: string;
  taskId: number;
}) {
  const query = new URLSearchParams({ open_id: String(input.openId || '').trim() });
  return requestWebsite<{ task: WebsiteWrongQuestionUploadTask }>(
    `/api/wechat/wrong-question-upload-tasks/${input.taskId}?${query.toString()}`
  );
}

export interface WebsiteWrongQuestionItem {
  id: string;
  student_id: number;
  class_id: number;
  teacher_user_id: number | null;
  image_url: string;
  primary_error_type?: string;
  secondary_error_summary?: string;
  archive_status?: string;
  is_mastered?: boolean;
  created_at?: string;
  student_name?: string;
  teacher_display_name?: string;
  analysis?: {
    error_type: string;
    selected_error_type: string;
    student_note: string;
  };
}

export interface WebsiteWrongQuestionLibrarySummary {
  student_id: number;
  pdf_url: string;
  updated_at?: string;
  total_items: number;
}

export async function listWrongQuestionsForChildOnWebsite(input: {
  openId: string;
  studentId: number;
}) {
  const query = new URLSearchParams({ open_id: input.openId });
  return requestWebsite<{ items: WebsiteWrongQuestionItem[]; total: number }>(
    `/api/wechat/children/${input.studentId}/wrong-questions?${query.toString()}`
  );
}

export async function getWrongQuestionLibraryForChildOnWebsite(input: {
  openId: string;
  studentId: number;
}) {
  const query = new URLSearchParams({ open_id: input.openId });
  return requestWebsite<WebsiteWrongQuestionLibrarySummary>(
    `/api/wechat/children/${input.studentId}/wrong-question-library?${query.toString()}`
  );
}
