export function readLocalStorageItem(key: string): string {
  try {
    return globalThis.localStorage?.getItem?.(key) || '';
  } catch {
    return '';
  }
}

export function writeLocalStorageItem(key: string, value: string): void {
  try {
    globalThis.localStorage?.setItem?.(key, value);
  } catch {
    // Ignore storage access issues and keep the UI functional.
  }
}

export function removeLocalStorageItem(key: string): void {
  try {
    globalThis.localStorage?.removeItem?.(key);
  } catch {
    // Ignore storage access issues and keep the UI functional.
  }
}

export function getToken(): string {
  return readLocalStorageItem('xr_token');
}

export function buildAuthedPath(path: string): string {
  const token = getToken();
  if (!token) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}token=${encodeURIComponent(token)}`;
}

export interface ApiFetchOptions extends RequestInit {
  reloadOnUnauthorized?: boolean;
}

export async function apiFetch<T = unknown>(path: string, options?: ApiFetchOptions): Promise<T> {
  const { reloadOnUnauthorized = true, ...fetchOptions } = options ?? {};
  const isFormData = fetchOptions.body instanceof FormData;
  const token = getToken();
  const res = await fetch(path, {
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { 'X-Auth-Token': token } : {}),
      ...(fetchOptions.headers ?? {}),
    },
    ...fetchOptions,
  });
  if (res.status === 401) {
    removeLocalStorageItem('xr_token');
    if (reloadOnUnauthorized) {
      window.location.reload();
    }
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error((err as { error?: string }).error || res.statusText);
  }
  return res.json() as Promise<T>;
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

export const workspacePageClass = 'mx-auto w-full max-w-[1280px] px-4 py-6 sm:px-6 sm:py-6 lg:px-8 lg:py-8 xl:px-10 xl:py-10';
export const workspaceCardClass =
  'rounded-[1.75rem] border border-sky-100/90 bg-white/88 shadow-[0_22px_54px_rgba(47,128,237,0.08)] backdrop-blur-sm dark:border-white/10 dark:bg-slate-950/78 dark:shadow-[0_24px_60px_rgba(2,6,23,0.52)]';
export const workspaceSoftCardClass =
  'rounded-[1.5rem] border border-sky-100 bg-[linear-gradient(180deg,rgba(255,255,255,0.94)_0%,rgba(239,248,255,0.78)_100%)] shadow-[0_14px_36px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] dark:shadow-[0_18px_40px_rgba(2,6,23,0.44)]';
export const workspaceFieldClass =
  'w-full rounded-xl border border-sky-200 bg-white/92 px-4 py-2.5 text-sm text-slate-700 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] outline-none transition focus:border-sky-400 focus:ring-4 focus:ring-sky-100 placeholder:text-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] dark:focus:border-sky-500 dark:focus:ring-sky-500/15 dark:placeholder:text-slate-500';
export const workspacePrimaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-sky-600 px-5 py-3 font-semibold text-white shadow-[0_16px_40px_rgba(34,199,232,0.24)] transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60';
export const workspaceSecondaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-sky-200 bg-white px-5 py-3 font-semibold text-slate-700 shadow-sm transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10';
export const workspaceGhostButtonClass =
  'inline-flex items-center justify-center gap-2 rounded-xl bg-sky-50/80 px-4 py-2.5 font-medium text-slate-600 transition hover:bg-sky-100 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10';
export const workspaceSectionTitleClass = 'text-2xl font-bold tracking-tight text-slate-900 dark:text-white';
export const workspaceSectionTextClass = 'text-sm leading-relaxed text-slate-500 dark:text-slate-400';
