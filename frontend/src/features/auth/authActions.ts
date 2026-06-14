import { getJoinInviteTokenFromPath } from './authFlow';
import type { PublicAuthModal } from './authState';

export function closePublicAuthState(): { publicAuthModal: PublicAuthModal | null; joinInviteToken: string | null } {
  return {
    publicAuthModal: null,
    joinInviteToken: null,
  };
}

export function openApplyOrganizationState(): { publicAuthModal: PublicAuthModal; joinInviteToken: string | null } {
  return {
    publicAuthModal: 'apply-organization',
    joinInviteToken: null,
  };
}

export function openJoinOrganizationState(pathname: string): { publicAuthModal: PublicAuthModal; joinInviteToken: string | null } {
  return {
    publicAuthModal: 'join-organization',
    joinInviteToken: getJoinInviteTokenFromPath(pathname),
  };
}

export function openPasswordResetState(): PublicAuthModal {
  return 'password-reset';
}

export function backToLoginState(): PublicAuthModal {
  return 'login';
}
