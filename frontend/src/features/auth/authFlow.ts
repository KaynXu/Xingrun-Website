export function getJoinInviteTokenFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/join\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function clearJoinInvitePathIfNeeded(): void {
  if (typeof window === 'undefined') {
    return;
  }
  if (!getJoinInviteTokenFromPath(window.location.pathname)) {
    return;
  }
  window.history.replaceState({}, '', '/');
}
