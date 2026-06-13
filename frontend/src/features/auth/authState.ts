import { getJoinInviteTokenFromPath } from './authFlow';

export type PublicAuthModal = 'login' | 'apply-organization' | 'join-organization' | 'password-reset';

export function getInitialPublicAuthModal(pathname: string, hasToken: boolean): PublicAuthModal | null {
  if (hasToken) {
    return null;
  }
  return getJoinInviteTokenFromPath(pathname) ? 'join-organization' : null;
}

export function getInitialJoinInviteToken(pathname: string): string | null {
  return getJoinInviteTokenFromPath(pathname);
}
