import { useCallback, useEffect, useState } from 'react';
import type { CurrentUser } from '../../appTypes';
import {
  apiFetch,
  getToken,
  removeLocalStorageItem,
  writeLocalStorageItem,
} from '../../workspaceShared';
import {
  backToLoginState,
  closePublicAuthState,
  openApplyOrganizationState,
  openJoinOrganizationState,
  openPasswordResetState,
} from './authActions';
import {
  clearJoinInvitePathIfNeeded,
  getJoinInviteTokenFromPath,
} from './authFlow';
import {
  getInitialJoinInviteToken,
  getInitialPublicAuthModal,
} from './authState';
import type { PublicAuthModal } from './authState';

type WorkspaceAuthState = {
  authReady: boolean;
  backToLogin: () => void;
  closePublicAuthModal: () => void;
  currentUser: CurrentUser | null;
  handleLogin: (token: string) => void;
  handleLogout: () => void;
  joinInviteToken: string | null;
  openApplyOrganization: () => void;
  openJoinOrganization: () => void;
  openPasswordReset: () => void;
  publicAuthModal: PublicAuthModal | null;
  setCurrentUser: React.Dispatch<React.SetStateAction<CurrentUser | null>>;
  token: string;
};

export function useWorkspaceAuthState(): WorkspaceAuthState {
  const [token, setToken] = useState<string>(() => getToken());
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authReady, setAuthReady] = useState<boolean>(() => !Boolean(getToken()));
  const [publicAuthModal, setPublicAuthModal] = useState<PublicAuthModal | null>(() =>
    getInitialPublicAuthModal(typeof window === 'undefined' ? '' : window.location.pathname, Boolean(getToken())),
  );
  const [joinInviteToken, setJoinInviteToken] = useState<string | null>(() =>
    getInitialJoinInviteToken(typeof window === 'undefined' ? '' : window.location.pathname),
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncInvitePath = () => {
      if (token) {
        clearJoinInvitePathIfNeeded();
        setJoinInviteToken(null);
        setPublicAuthModal(null);
        return;
      }

      const nextToken = getJoinInviteTokenFromPath(window.location.pathname);
      setJoinInviteToken(nextToken);
      if (nextToken && !token) {
        setPublicAuthModal('join-organization');
        return;
      }
      setPublicAuthModal((current) => (current === 'join-organization' ? null : current));
    };

    syncInvitePath();
    window.addEventListener('popstate', syncInvitePath);
    return () => window.removeEventListener('popstate', syncInvitePath);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setCurrentUser(null);
      setAuthReady(true);
      return;
    }

    let cancelled = false;
    setAuthReady(false);

    apiFetch<CurrentUser>('/api/me', { reloadOnUnauthorized: false })
      .then((user) => {
        if (!cancelled) {
          setCurrentUser(user);
        }
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        removeLocalStorageItem('xr_token');
        setToken('');
        setCurrentUser(null);
      })
      .finally(() => {
        if (!cancelled) {
          setAuthReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  const handleLogin = useCallback((nextToken: string) => {
    clearJoinInvitePathIfNeeded();
    writeLocalStorageItem('xr_token', nextToken);
    setToken(nextToken);
    setPublicAuthModal(null);
    setJoinInviteToken(null);
  }, []);

  const handleLogout = useCallback(() => {
    clearJoinInvitePathIfNeeded();
    removeLocalStorageItem('xr_token');
    setToken('');
    setCurrentUser(null);
    setPublicAuthModal(null);
    setJoinInviteToken(null);
  }, []);

  const closePublicAuthModal = useCallback(() => {
    clearJoinInvitePathIfNeeded();
    const nextState = closePublicAuthState();
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  }, []);

  const openApplyOrganization = useCallback(() => {
    const nextState = openApplyOrganizationState();
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  }, []);

  const openJoinOrganization = useCallback(() => {
    const nextState = openJoinOrganizationState(typeof window === 'undefined' ? '' : window.location.pathname);
    setJoinInviteToken(nextState.joinInviteToken);
    setPublicAuthModal(nextState.publicAuthModal);
  }, []);

  const openPasswordReset = useCallback(() => {
    setPublicAuthModal(openPasswordResetState());
  }, []);

  const backToLogin = useCallback(() => {
    setPublicAuthModal(backToLoginState());
  }, []);

  return {
    authReady,
    backToLogin,
    closePublicAuthModal,
    currentUser,
    handleLogin,
    handleLogout,
    joinInviteToken,
    openApplyOrganization,
    openJoinOrganization,
    openPasswordReset,
    publicAuthModal,
    setCurrentUser,
    token,
  };
}
