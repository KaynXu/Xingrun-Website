export type WrongQuestionMappingStatus = 'mapped' | 'unmapped' | 'ambiguous' | 'needs_review';

type WrongQuestionMappingQueueResponse = {
  items?: unknown[];
};

type WrongQuestionMappingApiItem = {
  record_id?: string | number;
  teacher_user_id?: number | null;
  class_id?: number | null;
  teacher_name_snapshot?: string | null;
  class_name_snapshot?: string | null;
  subject_snapshot?: string | null;
  teacher_display_name?: string | null;
  class_display_name?: string | null;
  mapping_status?: string | null;
  updated_at?: string | null;
};

export type WrongQuestionMappingQueueItem = {
  recordId: string;
  teacherUserId: number | null;
  classId: number | null;
  sourceTeacherName: string;
  sourceClassName: string;
  sourceSubject: string;
  mappedTeacherName: string;
  mappedClassName: string;
  mappingStatus: WrongQuestionMappingStatus;
  updatedAt: string;
};

export type ResolveWrongQuestionMappingPayload = {
  teacher_user_id: number | null;
  class_id: number | null;
  mapping_status: WrongQuestionMappingStatus;
};

type AliasResponse = {
  aliases?: string[];
};

function getToken(): string {
  return localStorage.getItem('xr_token') || '';
}

async function masterDataFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'X-Auth-Token': token } : {}),
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (response.status === 401) {
    localStorage.removeItem('xr_token');
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error((errorBody as { error?: string }).error || response.statusText);
  }

  return response.json() as Promise<T>;
}

function normalizeMappingStatus(value: string | null | undefined): WrongQuestionMappingStatus {
  if (value === 'mapped' || value === 'unmapped' || value === 'ambiguous' || value === 'needs_review') {
    return value;
  }

  return 'needs_review';
}

function normalizeQueueItem(item: WrongQuestionMappingApiItem): WrongQuestionMappingQueueItem {
  return {
    recordId: String(item.record_id ?? ''),
    teacherUserId: typeof item.teacher_user_id === 'number' ? item.teacher_user_id : null,
    classId: typeof item.class_id === 'number' ? item.class_id : null,
    sourceTeacherName: item.teacher_name_snapshot?.trim() || '未识别老师',
    sourceClassName: item.class_name_snapshot?.trim() || '未识别班级',
    sourceSubject: item.subject_snapshot?.trim() || '未识别科目',
    mappedTeacherName: item.teacher_display_name?.trim() || '未映射老师',
    mappedClassName: item.class_display_name?.trim() || '未映射班级',
    mappingStatus: normalizeMappingStatus(item.mapping_status),
    updatedAt: item.updated_at?.trim() || '',
  };
}

export async function fetchWrongQuestionMappingQueue(): Promise<WrongQuestionMappingQueueItem[]> {
  const response = await masterDataFetch<WrongQuestionMappingQueueResponse>('/api/master-data/mappings/wrong-questions');
  return (response.items ?? []).map((item) => normalizeQueueItem(item as WrongQuestionMappingApiItem));
}

export async function resolveWrongQuestionMapping(
  recordId: string,
  payload: ResolveWrongQuestionMappingPayload,
): Promise<WrongQuestionMappingQueueItem> {
  const response = await masterDataFetch<WrongQuestionMappingApiItem>(
    `/api/master-data/mappings/wrong-questions/${encodeURIComponent(recordId)}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );

  return normalizeQueueItem(response);
}

export async function fetchUserAliases(userId: number): Promise<string[]> {
  const response = await masterDataFetch<AliasResponse>(`/api/master-data/users/${userId}/aliases`);
  return Array.isArray(response.aliases) ? response.aliases : [];
}

export async function updateUserAliases(userId: number, aliases: string[]): Promise<string[]> {
  const response = await masterDataFetch<AliasResponse>(`/api/master-data/users/${userId}/aliases`, {
    method: 'PUT',
    body: JSON.stringify({ aliases }),
  });

  return Array.isArray(response.aliases) ? response.aliases : [];
}