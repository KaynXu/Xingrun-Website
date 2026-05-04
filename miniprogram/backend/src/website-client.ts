interface WebsiteRequestOptions {
  method?: string;
  body?: Record<string, unknown>;
  timeoutMs?: number;
}

const WRONG_QUESTION_UPLOAD_WEBSITE_TIMEOUT_MS = 25000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function getWebsiteBridgeConfig() {
  return {
    baseUrl: String(process.env.WEBSITE_API_BASE_URL || 'https://xingrun.online').trim().replace(/\/+$/, ''),
    token: String(process.env.WEBSITE_API_TOKEN || '').trim(),
  };
}

export class WebsiteRequestError extends Error {
  statusCode: number;
  retryable: boolean;
  payload: Record<string, unknown>;

  constructor(message: string, options: {
    statusCode: number;
    retryable: boolean;
    payload?: Record<string, unknown>;
  }) {
    super(message);
    this.name = 'WebsiteRequestError';
    this.statusCode = options.statusCode;
    this.retryable = options.retryable;
    this.payload = options.payload || {};
  }
}

function getWebsitePayloadMessage(payload: unknown, fallbackMessage: string) {
  if (isRecord(payload)) {
    if (typeof payload.error === 'string' && payload.error.trim()) {
      return payload.error.trim();
    }
    if (typeof payload.message === 'string' && payload.message.trim()) {
      return payload.message.trim();
    }
  }

  return fallbackMessage;
}

function getWebsitePayloadRetryable(payload: unknown, statusCode: number) {
  if (isRecord(payload) && typeof payload.retryable === 'boolean') {
    return payload.retryable;
  }
  return statusCode >= 500;
}

function buildWebsiteErrorPayload(payload: unknown, message: string, retryable: boolean) {
  const body = isRecord(payload) ? { ...payload } : {};
  body.error = message;
  body.retryable = retryable;
  return body;
}

function isTimeoutError(error: unknown) {
  const source = error && typeof error === 'object' ? error as { name?: unknown; message?: unknown } : {};
  const name = String(source.name || '');
  const message = String(source.message || '');
  return name === 'AbortError' || name === 'TimeoutError' || /timeout|aborted/i.test(message);
}

function getMalformedResponseMessage(path: string) {
  return path === '/api/wechat/wrong-questions'
    ? '网站上传接口返回异常，请稍后重试'
    : '网站接口返回异常，请稍后重试';
}

function getTimeoutMessage(path: string) {
  return path === '/api/wechat/wrong-questions'
    ? '网站上传接口超时，请稍后重试'
    : '网站接口超时，请稍后重试';
}

async function requestWebsite<T>(path: string, options: WebsiteRequestOptions = {}): Promise<T> {
  const config = getWebsiteBridgeConfig();
  if (!config.token) {
    throw new Error('缺少 WEBSITE_API_TOKEN 配置');
  }
  if (!config.baseUrl) {
    throw new Error('缺少 WEBSITE_API_BASE_URL 配置');
  }

  const controller = Number(options.timeoutMs || 0) > 0 ? new AbortController() : null;
  const timeout = controller
    ? setTimeout(() => controller.abort(), Number(options.timeoutMs))
    : null;
  let response: Response;

  try {
    response = await fetch(`${config.baseUrl}${path}`, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Wechat-Service-Token': config.token,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller ? controller.signal : undefined,
    });
  } catch (error) {
    if (isTimeoutError(error)) {
      const message = getTimeoutMessage(path);
      throw new WebsiteRequestError(message, {
        statusCode: 504,
        retryable: true,
        payload: { error: message, retryable: true },
      });
    }
    throw error;
  } finally {
    if (timeout) {
      clearTimeout(timeout);
    }
  }

  const responseText = await response.text();
  let payload: unknown = {};
  if (responseText.trim()) {
    try {
      payload = JSON.parse(responseText);
    } catch (_error) {
      if (!response.ok) {
        const message = `网站接口请求失败：HTTP ${response.status}`;
        const retryable = response.status >= 500;
        throw new WebsiteRequestError(message, {
          statusCode: response.status,
          retryable,
          payload: { error: message, retryable },
        });
      }

      const message = getMalformedResponseMessage(path);
      throw new WebsiteRequestError(message, {
        statusCode: 502,
        retryable: true,
        payload: { error: message, retryable: true },
      });
    }
  }

  if (!response.ok) {
    const message = getWebsitePayloadMessage(payload, `网站接口请求失败：HTTP ${response.status}`);
    const retryable = getWebsitePayloadRetryable(payload, response.status);
    throw new WebsiteRequestError(message, {
      statusCode: response.status,
      retryable,
      payload: buildWebsiteErrorPayload(payload, message, retryable),
    });
  }

  return payload as T;
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
  class_grade?: string;
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
  parent_error_message?: string;
  maintainer_error_detail?: string;
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

export async function listPrimaryTopicCategorySuggestionsOnWebsite(input: {
  openId: string;
  topicCategory?: string;
}) {
  const query = new URLSearchParams({
    open_id: String(input.openId || '').trim(),
    topic_category: String(input.topicCategory || '').trim(),
  });
  return requestWebsite<{ items: string[] }>(`/api/wechat/primary-topic-category-suggestions?${query.toString()}`);
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
  topicCategory?: string;
}) {
  return requestWebsite<{ task: WebsiteWrongQuestionUploadTask; student_library_pdf_url?: string }>('/api/wechat/wrong-questions', {
    method: 'POST',
    timeoutMs: WRONG_QUESTION_UPLOAD_WEBSITE_TIMEOUT_MS,
    body: {
      open_id: input.openId,
      binding_id: input.bindingId,
      image_url: input.imageUrl,
      child_raw_reason_text: input.childReasonText,
      child_reason_input_mode: input.childReasonInputMode || 'text',
      child_reason_audio_url: input.childReasonAudioUrl || '',
      topic_category: input.topicCategory || '未分类',
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
    topic_category?: string;
  };
  topic_category?: string;
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

export async function updateWrongQuestionTopicCategoryOnWebsite(input: {
  openId: string;
  recordId: string;
  topicCategory: string;
}) {
  return requestWebsite<{ ok: boolean; record: WebsiteWrongQuestionItem }>(
    `/api/wechat/wrong-questions/${encodeURIComponent(input.recordId)}/topic-category`,
    {
      method: 'PUT',
      body: {
        open_id: input.openId,
        topic_category: input.topicCategory,
      },
    }
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
