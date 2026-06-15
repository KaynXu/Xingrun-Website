import { useEffect, useMemo, useState, type ChangeEvent } from 'react';

import type { CurrentUser } from '../../appTypes';
import { getRoleLabel } from '../../appDisplay';
import {
  apiFetch,
  buildDiceBearAvatarUrl,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTitleClass,
} from '../../workspaceShared';

type SettingsPageProps = {
  currentUser: CurrentUser;
  onLogout: () => void;
  onCurrentUserUpdated: (user: CurrentUser) => void;
};

type ProfileUpdateResponse = {
  ok: boolean;
  user: CurrentUser;
};

const avatarPresetNames = ['ink', 'moss', 'pebble', 'ember', 'mist', 'wave'] as const;

function getAvatarSeedBase(user: CurrentUser): string {
  return [user.id, user.username, user.display_name].filter((item) => String(item || '').trim()).join('-') || 'xingrun-user';
}

function getAvatarPresetSeeds(user: CurrentUser): string[] {
  const base = getAvatarSeedBase(user);
  return avatarPresetNames.map((name) => `${base}-${name}`);
}

export function SettingsPage({ currentUser, onLogout, onCurrentUserUpdated }: SettingsPageProps) {
  const avatarPresetSeeds = useMemo(
    () => getAvatarPresetSeeds(currentUser),
    [currentUser.id, currentUser.username, currentUser.display_name],
  );
  const [selectedAvatarSeed, setSelectedAvatarSeed] = useState(
    currentUser.avatar_seed?.trim() || avatarPresetSeeds[0] || getAvatarSeedBase(currentUser),
  );
  const [avatarSaving, setAvatarSaving] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState('');
  const [avatarSuccess, setAvatarSuccess] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');

  useEffect(() => {
    setSelectedAvatarSeed(currentUser.avatar_seed?.trim() || avatarPresetSeeds[0] || getAvatarSeedBase(currentUser));
  }, [avatarPresetSeeds, currentUser.avatar_seed, currentUser.id, currentUser.username, currentUser.display_name]);

  const previewAvatarUrl = currentUser.avatar_source === 'upload'
    ? buildDiceBearAvatarUrl(currentUser)
    : buildDiceBearAvatarUrl({ ...currentUser, avatar_source: 'dicebear', avatar_seed: selectedAvatarSeed });

  const saveDiceBearAvatar = async (seed: string) => {
    setAvatarSaving(true);
    setAvatarError('');
    setAvatarSuccess('');
    try {
      const payload = await apiFetch<ProfileUpdateResponse>('/api/profile/avatar', {
        method: 'PUT',
        body: JSON.stringify({ avatar_source: 'dicebear', avatar_seed: seed }),
      });
      setSelectedAvatarSeed(payload.user.avatar_seed?.trim() || seed);
      setAvatarSuccess('头像已更新');
      onCurrentUserUpdated(payload.user);
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : '头像更新失败');
    } finally {
      setAvatarSaving(false);
    }
  };

  const handleAvatarUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    setAvatarUploading(true);
    setAvatarError('');
    setAvatarSuccess('');
    try {
      const formData = new FormData();
      formData.append('avatar', file);
      const payload = await apiFetch<ProfileUpdateResponse>('/api/profile/avatar-upload', {
        method: 'POST',
        body: formData,
      });
      setAvatarSuccess('头像已上传');
      onCurrentUserUpdated(payload.user);
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : '头像上传失败');
    } finally {
      setAvatarUploading(false);
    }
  };

  const savePassword = async () => {
    if (!currentPassword || !newPassword || !confirmPassword) {
      setPasswordError('请填写完整');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('两次输入的新密码不一致');
      return;
    }
    setPasswordSaving(true);
    setPasswordError('');
    setPasswordSuccess('');
    try {
      await apiFetch('/api/profile/password', {
        method: 'PUT',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordSuccess('密码已更新');
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : '密码修改失败');
    } finally {
      setPasswordSaving(false);
    }
  };

  return (
    <div className={`${workspacePageClass} space-y-8`}>
      <h3 className={workspaceSectionTitleClass}>系统设置</h3>

      <section className={`${workspaceCardClass} flex flex-col gap-5 p-6 md:flex-row md:items-center md:justify-between`}>
        <div className="flex items-center gap-4">
          <img src={previewAvatarUrl} alt={`${currentUser.display_name} 头像`} className="h-16 w-16 rounded-2xl bg-slate-100 object-cover" />
          <div className="space-y-2">
            <p className="text-lg font-semibold text-slate-900 dark:text-white">{currentUser.display_name}</p>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {getRoleLabel(currentUser.role)}
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {currentUser.organization_name}
              </span>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300">
                {currentUser.username}
              </span>
            </div>
          </div>
        </div>
        <button onClick={onLogout} className={workspaceSecondaryButtonClass}>
          退出登录
        </button>
      </section>

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="space-y-1">
          <h4 className="text-base font-semibold text-slate-900 dark:text-white">更换头像</h4>
          <p className="text-sm text-slate-500 dark:text-slate-400">选择一个 DiceBear seed，或上传自己的头像。</p>
        </div>
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
          {avatarPresetSeeds.map((seed) => {
            const active = currentUser.avatar_source !== 'upload' && selectedAvatarSeed === seed;
            return (
              <button
                key={seed}
                type="button"
                onClick={() => {
                  setSelectedAvatarSeed(seed);
                  void saveDiceBearAvatar(seed);
                }}
                disabled={avatarSaving || avatarUploading}
                className={`rounded-2xl border p-2 transition ${
                  active
                    ? 'border-slate-900 bg-slate-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <img
                  src={buildDiceBearAvatarUrl({ ...currentUser, avatar_source: 'dicebear', avatar_seed: seed })}
                  alt="头像候选"
                  className="h-16 w-full rounded-xl bg-slate-100 object-cover"
                />
              </button>
            );
          })}
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className={`${workspaceSecondaryButtonClass} cursor-pointer`}>
            <input type="file" accept="image/*" className="hidden" onChange={(event) => void handleAvatarUpload(event)} />
            {avatarUploading ? '上传中...' : '上传头像'}
          </label>
          <span className="text-sm text-slate-500 dark:text-slate-400">
            支持 `png / jpg / webp / gif`，不超过 4MB
          </span>
        </div>
        {avatarError && <p className="text-sm text-rose-500 dark:text-rose-400">{avatarError}</p>}
        {avatarSuccess && <p className="text-sm text-emerald-600 dark:text-emerald-400">{avatarSuccess}</p>}
      </section>

      <section className={`${workspaceCardClass} space-y-5 p-6`}>
        <div className="space-y-1">
          <h4 className="text-base font-semibold text-slate-900 dark:text-white">修改账号密码</h4>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <input
            type="password"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            className={workspaceFieldClass}
            placeholder="当前密码"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            className={workspaceFieldClass}
            placeholder="新密码"
          />
          <input
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className={workspaceFieldClass}
            placeholder="确认新密码"
          />
        </div>
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => void savePassword()} disabled={passwordSaving} className={workspacePrimaryButtonClass}>
            {passwordSaving ? '保存中...' : '更新密码'}
          </button>
        </div>
        {passwordError && <p className="text-sm text-rose-500 dark:text-rose-400">{passwordError}</p>}
        {passwordSuccess && <p className="text-sm text-emerald-600 dark:text-emerald-400">{passwordSuccess}</p>}
      </section>
    </div>
  );
}
