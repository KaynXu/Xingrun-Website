import type { ClassInviteInfo } from './model';

type ApiFetch = <T>(endpoint: string, init?: RequestInit) => Promise<T>;

export function buildClassInviteLoadRequest(classId: number): {
  endpoint: string;
} {
  return {
    endpoint: `/api/classes/${classId}/invite`,
  };
}

export function buildClassInviteResetRequest(classId: number): {
  endpoint: string;
  init: RequestInit;
} {
  return {
    endpoint: `/api/classes/${classId}/invite/reset`,
    init: { method: 'POST' },
  };
}

export async function executeClassInviteLoadRequest(
  classId: number,
  apiFetch: ApiFetch,
): Promise<ClassInviteInfo> {
  const request = buildClassInviteLoadRequest(classId);
  return apiFetch<ClassInviteInfo>(request.endpoint);
}

export async function executeClassInviteResetRequest(
  classId: number,
  apiFetch: ApiFetch,
): Promise<ClassInviteInfo> {
  const request = buildClassInviteResetRequest(classId);
  return apiFetch<ClassInviteInfo>(request.endpoint, request.init);
}

export function resolveInviteLoadingStartState(
  current: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  return { ...current, [classId]: true };
}

export function resolveInviteLoadingEndState(
  current: Record<number, boolean>,
  classId: number,
): Record<number, boolean> {
  return { ...current, [classId]: false };
}

export function resolveClassInviteErrorMessage(
  err: unknown,
  action: 'load' | 'reset',
): string {
  if (err instanceof Error) {
    return err.message;
  }
  return action === 'load' ? '邀请码加载失败' : '邀请码重置失败';
}
