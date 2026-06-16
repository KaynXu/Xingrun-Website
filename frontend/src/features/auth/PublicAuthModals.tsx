import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { motion } from 'motion/react';

import type { ClassItem, CurrentUser } from '../../appTypes';
import { getCurrentClassDisplayName } from '../../classDisplay';
import {
  academicGradeGroups,
  academicGradeOptions,
  academicStageOptions,
  getAcademicGradeRank,
  getAcademicStageFromGrade,
  normalizeAcademicGradeLabel,
} from '../../domain/classNaming';
import {
  apiFetch,
  cn,
  workspaceCardClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from '../../workspaceShared';

type RecoveryMethod = 'phone' | 'security';

const authInputClass = 'w-full bg-black border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500 transition-colors';
const academicSubjectOptions = ['数学', '物理', '国际数学'];
const academicSubjectFilterOptions = ['全部学科', ...academicSubjectOptions];
const studentCenterStageOptions = [...academicStageOptions];
const studentCenterGradeOptions = [...academicGradeOptions];
const studentCenterGradeGroups: Record<string, string[]> = academicGradeGroups;

function buildRecoveryPayload(
  recoveryMethod: RecoveryMethod,
  recoveryPhone: string,
  securityQuestion: string,
  securityAnswer: string,
) {
  if (recoveryMethod === 'phone') {
    return { recovery_phone: recoveryPhone };
  }
  return { security_question: securityQuestion, security_answer: securityAnswer };
}

const WorkspaceLoading = ({ label }: { label: string }) => (
  <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">
    {label}
  </div>
);

const RecoverySetupFields = ({
  recoveryMethod,
  setRecoveryMethod,
  recoveryPhone,
  setRecoveryPhone,
  securityQuestion,
  setSecurityQuestion,
  securityAnswer,
  setSecurityAnswer,
}: {
  recoveryMethod: RecoveryMethod;
  setRecoveryMethod: (method: RecoveryMethod) => void;
  recoveryPhone: string;
  setRecoveryPhone: (value: string) => void;
  securityQuestion: string;
  setSecurityQuestion: (value: string) => void;
  securityAnswer: string;
  setSecurityAnswer: (value: string) => void;
}) => (
  <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
    <div className="grid grid-cols-2 gap-2 rounded-xl bg-black p-1">
      <button type="button" onClick={() => setRecoveryMethod('phone')} className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${recoveryMethod === 'phone' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
        电话号码
      </button>
      <button type="button" onClick={() => setRecoveryMethod('security')} className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${recoveryMethod === 'security' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}>
        密保问题
      </button>
    </div>

    {recoveryMethod === 'phone' ? (
      <div className="space-y-1.5">
        <label className="text-sm text-gray-400">找回密码电话</label>
        <input type="tel" value={recoveryPhone} onChange={(e) => setRecoveryPhone(e.target.value)} required placeholder="输入电话号码即可验证" className={authInputClass} />
      </div>
    ) : (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <label className="text-sm text-gray-400">密保问题</label>
          <input type="text" value={securityQuestion} onChange={(e) => setSecurityQuestion(e.target.value)} required placeholder="例如：我的入职年份？" className={authInputClass} />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm text-gray-400">密保答案</label>
          <input type="text" value={securityAnswer} onChange={(e) => setSecurityAnswer(e.target.value)} required placeholder="请输入答案" className={authInputClass} />
        </div>
      </div>
    )}
  </div>
);

export const ClassClaimPage = ({
  currentUser,
  onClaimed,
  onLogout,
}: {
  currentUser: CurrentUser;
  onClaimed: (user: CurrentUser) => void;
  onLogout: () => void;
}) => {
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [selectedClassIds, setSelectedClassIds] = useState<number[]>([]);
  const [selectedGradeFilter, setSelectedGradeFilter] = useState<string>('全部');
  const [selectedStageFilter, setSelectedStageFilter] = useState<string>('全部学段');
  const [selectedSubjectFilter, setSelectedSubjectFilter] = useState<string>('全部学科');
  const [activeClaimFilterLayer, setActiveClaimFilterLayer] = useState<'subject' | 'stage' | 'grade'>('subject');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiFetch<{ items: ClassItem[] }>('/api/me/unbound-classes')
      .then((payload) => {
        if (!cancelled) {
          setClasses(payload.items);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '班级加载失败');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const claimGradeFilterOptions = ['全部', ...studentCenterGradeOptions.filter((grade) => {
    if (selectedStageFilter !== '全部学段' && !studentCenterGradeGroups[selectedStageFilter]?.includes(grade)) {
      return false;
    }
    return classes.some((item) => normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === grade);
  })];
  const claimSubjectFilterOptions = academicSubjectFilterOptions;
  const claimFilterSummary = [
    selectedSubjectFilter !== '全部学科' ? selectedSubjectFilter : '',
    selectedStageFilter !== '全部学段' ? selectedStageFilter : '',
    selectedGradeFilter !== '全部' ? selectedGradeFilter : '',
  ].filter(Boolean).join(' / ') || '全部';
  const filteredClasses = classes.filter((item) => {
    if (selectedSubjectFilter !== '全部学科' && item.subject !== selectedSubjectFilter) {
      return false;
    }
    if (selectedStageFilter !== '全部学段' && (item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '')) !== selectedStageFilter) {
      return false;
    }
    if (selectedGradeFilter === '全部') {
      return true;
    }
    return normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === selectedGradeFilter;
  }).sort((left, right) => {
    const gradeDelta = getAcademicGradeRank(left.current_grade || left.grade || '') - getAcademicGradeRank(right.current_grade || right.grade || '');
    return gradeDelta || `${left.subject}${left.name}`.localeCompare(`${right.subject}${right.name}`, 'zh-CN') || left.id - right.id;
  });

  const toggleClass = (classId: number) => {
    setSelectedClassIds((current) => current.includes(classId) ? current.filter((id) => id !== classId) : [...current, classId]);
  };

  const handleClaim = async () => {
    setError('');
    if (classes.length > 0 && selectedClassIds.length === 0) {
      setError('请选择需要绑定的班级');
      return;
    }
    setSaving(true);
    try {
      const payload = await apiFetch<{ ok: boolean; user: CurrentUser }>('/api/me/claim-classes', {
        method: 'POST',
        body: JSON.stringify({ class_ids: selectedClassIds }),
      });
      onClaimed(payload.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : '班级认领失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="relative flex min-h-[100svh] items-center justify-center overflow-hidden bg-[linear-gradient(180deg,#f8fbff_0%,#eef6ff_100%)] px-4 py-8 text-slate-900 dark:bg-[linear-gradient(180deg,#020617_0%,#0f172a_100%)] dark:text-slate-100">
      <div className={`${workspaceCardClass} relative w-full max-w-3xl p-6 md:p-8`}>
        <div className="flex flex-col gap-3 border-b border-sky-100 pb-5 dark:border-white/10">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-medium text-sky-600 dark:text-sky-300">首次登录</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">认领你的班级</h1>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{currentUser.display_name}，请选择需要绑定到你账号下的未绑定班级。</p>
            </div>
            <button type="button" onClick={onLogout} className={workspaceSecondaryButtonClass}>退出登录</button>
          </div>
        </div>
        {error && <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300"><AlertCircle size={16} />{error}</div>}
        {!loading && classes.length > 0 ? (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">筛选：{claimFilterSummary}</span>
              {[
                { key: 'subject' as const, label: selectedSubjectFilter },
                { key: 'stage' as const, label: selectedStageFilter },
                { key: 'grade' as const, label: selectedGradeFilter === '全部' ? '全部年级' : selectedGradeFilter },
              ].map((item) => (
                <button key={item.key} type="button" onClick={() => setActiveClaimFilterLayer(item.key)} className={cn('rounded-full border px-3 py-2 text-sm font-semibold transition', activeClaimFilterLayer === item.key ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{item.label}</button>
              ))}
            </div>
            <div className="rounded-2xl border border-sky-100 bg-sky-50/60 p-3 dark:border-white/10 dark:bg-white/5">
              {activeClaimFilterLayer === 'subject' && (
                <div className="flex flex-wrap gap-2">
                  {claimSubjectFilterOptions.map((option) => (
                    <button key={option} type="button" onClick={() => { setSelectedSubjectFilter(option); setSelectedStageFilter('全部学段'); setSelectedGradeFilter('全部'); }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedSubjectFilter === option ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{option}</button>
                  ))}
                </div>
              )}
              {activeClaimFilterLayer === 'stage' && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => { setSelectedStageFilter('全部学段'); setSelectedGradeFilter('全部'); }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedStageFilter === '全部学段' ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>全部学段</button>
                  {studentCenterStageOptions.map((stage) => (
                    <button key={stage} type="button" onClick={() => { setSelectedStageFilter(stage); setSelectedGradeFilter('全部'); }} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedStageFilter === stage ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{stage}</button>
                  ))}
                </div>
              )}
              {activeClaimFilterLayer === 'grade' && (
                <div className="flex flex-wrap gap-2">
                  {claimGradeFilterOptions.map((option) => (
                    <button key={option} type="button" onClick={() => setSelectedGradeFilter(option)} className={cn('rounded-full border px-3 py-2 text-sm font-semibold', selectedGradeFilter === option ? 'border-sky-500 bg-sky-500 text-white' : 'border-sky-100 bg-white text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-slate-300')}>{option === '全部' ? '全部年级' : option}</button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
        <div className="mt-5 space-y-3">
          {loading ? (
            <WorkspaceLoading label="正在加载未绑定班级..." />
          ) : classes.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">当前没有未绑定班级。</div>
          ) : filteredClasses.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-sky-200 p-8 text-center text-sm text-slate-500 dark:border-white/10 dark:text-slate-400">{`当前筛选“${claimFilterSummary}”下暂无未绑定班级。`}</div>
          ) : (
            filteredClasses.map((item) => {
              const checked = selectedClassIds.includes(item.id);
              return (
                <button key={item.id} type="button" onClick={() => toggleClass(item.id)} className={`flex w-full items-center justify-between gap-4 rounded-2xl border px-4 py-4 text-left transition ${checked ? 'border-sky-300 bg-sky-50 text-slate-900 dark:border-sky-500/40 dark:bg-sky-500/10 dark:text-white' : 'border-sky-100 bg-white/70 text-slate-700 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10'}`}>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold">{getCurrentClassDisplayName(item)}</span>
                    <span className="mt-1 block text-sm text-slate-500 dark:text-slate-400">{[item.grade, item.subject].filter(Boolean).join(' · ') || '未设置年级科目'}</span>
                  </span>
                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border ${checked ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-300 dark:border-slate-600'}`}>{checked ? <CheckCircle2 size={14} /> : null}</span>
                </button>
              );
            })
          )}
        </div>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={() => void handleClaim()} disabled={loading || saving} className={workspacePrimaryButtonClass}>{saving ? '绑定中...' : classes.length === 0 ? '完成' : '绑定所选班级'}</button>
        </div>
      </div>
    </div>
  );
};

export const LoginModal = ({ onLogin, onClose, onOpenApplyOrganization, onOpenJoinOrganization, onOpenPasswordReset }: { onLogin: (token: string) => void; onClose: () => void; onOpenApplyOrganization: () => void; onOpenJoinOrganization: () => void; onOpenPasswordReset: () => void; }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
      const raw = await res.text();
      const data = raw ? JSON.parse(raw) as { error?: string; token?: string } : {};
      if (!res.ok) {
        throw new Error(data.error || '登录服务不可用，请确认后端已启动');
      }
      if (!data.token) {
        throw new Error('登录响应缺少令牌，请稍后再试');
      }
      onLogin(data.token);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center px-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 16 }} transition={{ duration: 0.2 }} className="relative z-10 w-full max-w-md">
        <div className="rounded-3xl border border-white/10 bg-[#0a0a0a] p-8 text-white shadow-2xl">
          <div className="mb-6 flex items-center justify-between"><h2 className="text-xl font-semibold">登录账号</h2><button onClick={onClose} className="text-2xl leading-none text-gray-500 transition-colors hover:text-white">×</button></div>
          {error && <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={16} />{error}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5"><label className="text-sm text-gray-400">账号</label><input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus placeholder="请输入账号" className={authInputClass} /></div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-3"><label className="text-sm text-gray-400">密码</label><button type="button" onClick={onOpenPasswordReset} className="text-sm font-medium text-sky-300 transition-colors hover:text-sky-100">找回密码</button></div>
              <div className="relative">
                <input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="请输入密码" className={`${authInputClass} pr-11`} />
                <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">{showPwd ? <EyeOff size={18} /> : <Eye size={18} />}</button>
              </div>
            </div>
            <button type="submit" disabled={loading} className="mt-2 w-full rounded-xl bg-blue-600 py-3 font-semibold text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-500 disabled:opacity-50">{loading ? '登录中...' : '登录'}</button>
          </form>
          <div className="mt-4 space-y-3"><button type="button" onClick={onOpenApplyOrganization} className="w-full rounded-xl border border-white/10 bg-white/5 py-3 text-sm font-medium transition-colors hover:bg-white/10">申请开通机构</button><button type="button" onClick={onOpenJoinOrganization} className="w-full rounded-xl border border-sky-500/30 bg-sky-500/10 py-3 text-sm font-medium text-sky-100 transition-colors hover:bg-sky-500/20">加入已有机构</button></div>
        </div>
      </motion.div>
    </motion.div>
  );
};

export const PasswordResetModal = ({ onClose, onBackToLogin }: { onClose: () => void; onBackToLogin: () => void; }) => {
  const [username, setUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }
    setLoading(true);
    try {
      await apiFetch<{ ok: boolean }>('/api/password-reset', { method: 'POST', body: JSON.stringify({ username, new_password: newPassword, ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer) }) });
      setSuccess('密码已重置，请使用新密码登录。');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '密码重置失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center px-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 16 }} transition={{ duration: 0.2 }} className="relative z-10 w-full max-w-lg">
        <div className="rounded-3xl border border-white/10 bg-[#0a0a0a] p-8 text-white shadow-2xl">
          <div className="mb-6 flex items-center justify-between"><h2 className="text-xl font-semibold">找回密码</h2><button onClick={onClose} className="text-2xl leading-none text-gray-500 transition-colors hover:text-white">×</button></div>
          {error && <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={16} />{error}</div>}
          {success && <div className="mb-4 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-300"><CheckCircle2 size={16} />{success}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5"><label className="text-sm text-gray-400">账号</label><input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder="请输入账号" className={authInputClass} /></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="space-y-1.5"><label className="text-sm text-gray-400">新密码</label><div className="relative"><input type={showPwd ? 'text' : 'password'} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={6} placeholder="至少 6 位" className={`${authInputClass} pr-11`} /><button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">{showPwd ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></div>
              <div className="space-y-1.5"><label className="text-sm text-gray-400">确认新密码</label><input type={showPwd ? 'text' : 'password'} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} placeholder="再次输入新密码" className={authInputClass} /></div>
            </div>
            <RecoverySetupFields recoveryMethod={recoveryMethod} setRecoveryMethod={setRecoveryMethod} recoveryPhone={recoveryPhone} setRecoveryPhone={setRecoveryPhone} securityQuestion={securityQuestion} setSecurityQuestion={setSecurityQuestion} securityAnswer={securityAnswer} setSecurityAnswer={setSecurityAnswer} />
            <button type="submit" disabled={loading} className="mt-2 w-full rounded-xl bg-blue-600 py-3 font-semibold text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-500 disabled:opacity-50">{loading ? '提交中...' : '重置密码'}</button>
          </form>
          <button type="button" onClick={onBackToLogin} className="mt-4 w-full text-sm text-sky-300 transition-colors hover:text-sky-100">返回登录</button>
        </div>
      </motion.div>
    </motion.div>
  );
};

export const OrganizationApplyModal = ({ onClose }: { onClose: () => void }) => {
  const [organizationName, setOrganizationName] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      await apiFetch<{ id: number; status: string }>('/api/organization-requests', { method: 'POST', body: JSON.stringify({ organization_name: organizationName, username, display_name: displayName, password, ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer) }) });
      setSuccess('机构申请已提交，等待审核。');
      setOrganizationName('');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
      setRecoveryPhone('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '机构申请提交失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center px-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 16 }} transition={{ duration: 0.2 }} className="relative z-10 w-full max-w-xl">
        <div className="rounded-3xl border border-white/10 bg-[#0a0a0a] p-8 text-white shadow-2xl">
          <div className="mb-6 flex items-center justify-between"><div><h2 className="text-xl font-semibold">申请开通机构</h2></div><button onClick={onClose} className="text-2xl leading-none text-gray-500 transition-colors hover:text-white">×</button></div>
          {error && <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={16} />{error}</div>}
          {success && <div className="mb-4 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-300"><CheckCircle2 size={16} />{success}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5"><label className="text-sm text-gray-400">机构名称</label><input type="text" value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} required placeholder="例如：北辰实验学校" className={authInputClass} /></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div className="space-y-1.5"><label className="text-sm text-gray-400">账号</label><input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder="首位管理员登录账号" className={authInputClass} /></div><div className="space-y-1.5"><label className="text-sm text-gray-400">姓名</label><input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required placeholder="对外显示的姓名" className={authInputClass} /></div></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div className="space-y-1.5"><label className="text-sm text-gray-400">密码</label><div className="relative"><input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} placeholder="至少 6 位" className={`${authInputClass} pr-11`} /><button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">{showPwd ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></div><div className="space-y-1.5"><label className="text-sm text-gray-400">确认密码</label><input type={showPwd ? 'text' : 'password'} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} placeholder="再次输入密码" className={authInputClass} /></div></div>
            <RecoverySetupFields recoveryMethod={recoveryMethod} setRecoveryMethod={setRecoveryMethod} recoveryPhone={recoveryPhone} setRecoveryPhone={setRecoveryPhone} securityQuestion={securityQuestion} setSecurityQuestion={setSecurityQuestion} securityAnswer={securityAnswer} setSecurityAnswer={setSecurityAnswer} />
            <button type="submit" disabled={loading} className="mt-2 w-full rounded-xl bg-blue-600 py-3 font-semibold text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-500 disabled:opacity-50">{loading ? '提交中...' : '提交机构申请'}</button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};

export const JoinOrganizationModal = ({ onClose, inviteToken }: { onClose: () => void; inviteToken?: string | null; }) => {
  const [inviteCode, setInviteCode] = useState('');
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [recoveryMethod, setRecoveryMethod] = useState<RecoveryMethod>('phone');
  const [recoveryPhone, setRecoveryPhone] = useState('');
  const [securityQuestion, setSecurityQuestion] = useState('');
  const [securityAnswer, setSecurityAnswer] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [organizationName, setOrganizationName] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError('');
    setSuccess('');
    if (!inviteToken) {
      setOrganizationName('');
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    apiFetch<{ organization_name: string }>(`/api/invite/${inviteToken}`)
      .then((payload) => {
        if (!cancelled) {
          setOrganizationName(payload.organization_name);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setOrganizationName('');
          setError(err instanceof Error ? err.message : '邀请链接已失效');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setPreviewLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [inviteToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      const path = inviteToken ? `/api/join-by-invite-link/${inviteToken}` : '/api/join-by-invite-code';
      const payload = await apiFetch<{ user: CurrentUser }>(path, { method: 'POST', body: inviteToken ? JSON.stringify({ username, display_name: displayName, password, ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer) }) : JSON.stringify({ invite_code: inviteCode, username, display_name: displayName, password, ...buildRecoveryPayload(recoveryMethod, recoveryPhone, securityQuestion, securityAnswer) }) });
      setSuccess(`已加入 ${payload.user.organization_name}，现在可以使用新账号登录。`);
      setInviteCode('');
      setUsername('');
      setDisplayName('');
      setPassword('');
      setConfirmPassword('');
      setRecoveryPhone('');
      setSecurityQuestion('');
      setSecurityAnswer('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '加入机构失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 flex items-center justify-center px-4" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />
      <motion.div initial={{ opacity: 0, scale: 0.95, y: 16 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95, y: 16 }} transition={{ duration: 0.2 }} className="relative z-10 w-full max-w-xl">
        <div className="rounded-3xl border border-white/10 bg-[#0a0a0a] p-8 text-white shadow-2xl">
          <div className="mb-6 flex items-center justify-between"><div><h2 className="text-xl font-semibold">加入已有机构</h2><p className="mt-1 text-sm text-gray-400">通过邀请码或邀请链接加入机构，成功后即可直接登录。</p></div><button onClick={onClose} className="text-2xl leading-none text-gray-500 transition-colors hover:text-white">×</button></div>
          {error && <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400"><AlertCircle size={16} />{error}</div>}
          {success && <div className="mb-4 flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-500/10 p-3 text-sm text-green-300"><CheckCircle2 size={16} />{success}</div>}
          <form onSubmit={handleSubmit} className="space-y-4">
            {inviteToken ? <div className="space-y-1.5"><label className="text-sm text-gray-400">邀请链接目标机构</label><div className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-gray-200">{previewLoading ? '正在识别机构...' : organizationName || '邀请链接已失效'}</div></div> : <div className="space-y-1.5"><label className="text-sm text-gray-400">邀请码</label><input type="text" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} required placeholder="输入机构邀请码" className={authInputClass} /></div>}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div className="space-y-1.5"><label className="text-sm text-gray-400">账号</label><input type="text" value={username} onChange={(e) => setUsername(e.target.value)} required placeholder="用于登录" className={authInputClass} /></div><div className="space-y-1.5"><label className="text-sm text-gray-400">姓名</label><input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required placeholder="对外显示的姓名" className={authInputClass} /></div></div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2"><div className="space-y-1.5"><label className="text-sm text-gray-400">密码</label><div className="relative"><input type={showPwd ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} placeholder="至少 6 位" className={`${authInputClass} pr-11`} /><button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white">{showPwd ? <EyeOff size={18} /> : <Eye size={18} />}</button></div></div><div className="space-y-1.5"><label className="text-sm text-gray-400">确认密码</label><input type={showPwd ? 'text' : 'password'} value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required minLength={6} placeholder="再次输入密码" className={authInputClass} /></div></div>
            <RecoverySetupFields recoveryMethod={recoveryMethod} setRecoveryMethod={setRecoveryMethod} recoveryPhone={recoveryPhone} setRecoveryPhone={setRecoveryPhone} securityQuestion={securityQuestion} setSecurityQuestion={setSecurityQuestion} securityAnswer={securityAnswer} setSecurityAnswer={setSecurityAnswer} />
            <button type="submit" disabled={loading || (Boolean(inviteToken) && !organizationName)} className="mt-2 w-full rounded-xl bg-blue-600 py-3 font-semibold text-white shadow-lg shadow-blue-600/20 transition-all hover:bg-blue-500 disabled:opacity-50">{loading ? '提交中...' : '加入机构'}</button>
          </form>
        </div>
      </motion.div>
    </motion.div>
  );
};
