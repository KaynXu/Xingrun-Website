import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { CurrentUser } from '../../appTypes';
import {
  apiFetch,
  cn,
  workspaceCardClass,
  workspaceFieldClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
  workspaceSectionTextClass,
  workspaceSectionTitleClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';

interface CreditOverview {
  organization_id: number;
  credit_balance: number;
  total_recharged: number;
  total_consumed: number;
  updated_at: string;
}

interface CreditLedgerItem {
  id: number;
  direction: 'credit' | 'debit';
  amount: number;
  balance_after: number;
  source_type: string;
  source_id: string;
  note: string;
  operator_user_id: number | null;
  created_at: string;
}

interface CreditMemberUsageItem {
  user_id: number;
  display_name: string;
  credit_consumed: number;
  usage_count: number;
  last_used_at: string | null;
}

interface CreditMemberUsageDetailItem {
  id: number;
  user_id: number;
  feature_key: string;
  provider: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  credit_cost_final: number;
  source_record_type: string | null;
  source_record_id: number | string | null;
  request_id: string;
  created_at: string;
}

const CREDIT_USAGE_DETAIL_PAGE_SIZE = 5;
const CREDIT_LEDGER_PAGE_SIZE = 5;
const FEATURE_KEY_LABELS: Record<string, string> = {
  lesson_plan_generate: '复习计划生成',
  consultation_ai_parse: '咨询记录解析',
  audio_transcription: '音频转录',
  monthly_plan_generate: '月度计划生成',
};
const SOURCE_RECORD_TYPE_LABELS: Record<string, string> = {
  lesson: '课程记录',
  consultation: '咨询记录',
  monthly_plan: '月度计划',
  draft: '草稿',
};
const LEDGER_SOURCE_TYPE_LABELS: Record<string, string> = {
  ai_usage: 'AI 功能消耗',
  manual_adjustment: '人工充值',
  xhs_order_redeem: '小红书订单兑换',
  consultation_ai_parse: '咨询记录 AI 解析',
  lesson_plan_generate: '复习计划生成',
  audio_transcription: '音频转录',
  monthly_plan_generate: '月度计划生成',
};
const AI_FEATURE_LABELS: Record<string, string> = {
  lesson_plan_generate: '复习计划生成',
  consultation_ai_parse: '咨询记录解析',
  audio_transcription: '音频转录',
  monthly_plan_generate: '月度计划生成',
};

const WorkspaceLoading = ({ label = '正在处理中...' }: { label?: string }) => (
  <div className="flex flex-col items-center justify-center py-12 text-center">
    <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-sky-200 border-t-sky-500" />
    <p className="font-medium text-slate-700 dark:text-slate-200">{label}</p>
  </div>
);

function formatRequestId(requestId: string) {
  return requestId.length > 20 ? `${requestId.slice(0, 10)}...${requestId.slice(-8)}` : requestId;
}

type CreditCenterPageProps = {
  currentUser: CurrentUser;
};

export function CreditCenterPage({ currentUser }: CreditCenterPageProps) {
  const [creditOverview, setCreditOverview] = useState<CreditOverview | null>(null);
  const [creditLedger, setCreditLedger] = useState<CreditLedgerItem[]>([]);
  const [creditUsage, setCreditUsage] = useState<CreditMemberUsageItem[]>([]);
  const [creditLoading, setCreditLoading] = useState(true);
  const [creditError, setCreditError] = useState('');
  const [redeemOrderId, setRedeemOrderId] = useState('');
  const [redeemPhoneSuffix, setRedeemPhoneSuffix] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);
  const [redeemMessage, setRedeemMessage] = useState('');
  const [selectedUsageUser, setSelectedUsageUser] = useState<CreditMemberUsageItem | null>(null);
  const selectedUsageUserIdRef = useRef<number | null>(null);
  const [usageDetailItems, setUsageDetailItems] = useState<CreditMemberUsageDetailItem[]>([]);
  const [usageDetailLoading, setUsageDetailLoading] = useState(false);
  const [usageDetailError, setUsageDetailError] = useState('');
  const [usageDetailPage, setUsageDetailPage] = useState(1);
  const [ledgerFilter, setLedgerFilter] = useState<'all' | 'credit' | 'debit'>('all');
  const [ledgerPage, setLedgerPage] = useState(1);
  const canSeeSensitiveUsageMeta = currentUser.role === 'super_owner';

  const loadSelectedUsageDetail = useCallback(async (userId: number) => {
    setUsageDetailLoading(true);
    setUsageDetailError('');
    try {
      const payload = await apiFetch<{ items: CreditMemberUsageDetailItem[] }>(`/api/credits/member-usage/${userId}`);
      setUsageDetailItems(payload.items);
    } catch (err) {
      setUsageDetailItems([]);
      setUsageDetailError(err instanceof Error ? err.message : '成员明细加载失败');
    } finally {
      setUsageDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    selectedUsageUserIdRef.current = selectedUsageUser?.user_id ?? null;
  }, [selectedUsageUser]);

  const loadCredits = useCallback(async () => {
    setCreditLoading(true);
    setCreditError('');
    try {
      const [overview, ledgerPayload, usagePayload] = await Promise.all([
        apiFetch<CreditOverview>('/api/credits/overview'),
        apiFetch<{ items: CreditLedgerItem[] }>('/api/credits/ledger?limit=100'),
        apiFetch<{ items: CreditMemberUsageItem[] }>('/api/credits/member-usage'),
      ]);
      setCreditOverview(overview);
      setCreditLedger(ledgerPayload.items);
      setCreditUsage(usagePayload.items);

      if (selectedUsageUserIdRef.current !== null) {
        const refreshedSelectedUsageUser = usagePayload.items.find((item) => item.user_id === selectedUsageUserIdRef.current) ?? null;
        setSelectedUsageUser(refreshedSelectedUsageUser);
        if (refreshedSelectedUsageUser) {
          await loadSelectedUsageDetail(refreshedSelectedUsageUser.user_id);
        } else {
          setUsageDetailItems([]);
          setUsageDetailError('');
        }
      }
    } catch (err) {
      setCreditError(err instanceof Error ? err.message : '积分中心加载失败');
    } finally {
      setCreditLoading(false);
    }
  }, [loadSelectedUsageDetail]);

  useEffect(() => {
    void loadCredits();
  }, [loadCredits]);

  useEffect(() => {
    setUsageDetailPage(1);
  }, [selectedUsageUser, usageDetailItems]);

  useEffect(() => {
    setLedgerPage(1);
  }, [ledgerFilter, creditLedger]);

  const handleRedeemSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setRedeemLoading(true);
    setRedeemMessage('');
    setCreditError('');
    try {
      const payload = await apiFetch<{ overview: CreditOverview }>('/api/credits/redeem/xhs', {
        method: 'POST',
        body: JSON.stringify({
          platform_order_id: redeemOrderId,
          phone_suffix: redeemPhoneSuffix,
        }),
      });
      setCreditOverview(payload.overview);
      setRedeemOrderId('');
      setRedeemPhoneSuffix('');
      setRedeemMessage('兑换成功，积分余额已更新。');
      await loadCredits();
    } catch (err) {
      setCreditError(err instanceof Error ? err.message : '订单兑换失败');
    } finally {
      setRedeemLoading(false);
    }
  };

  const handleSelectUsageUser = (item: CreditMemberUsageItem) => {
    setSelectedUsageUser(item);
    void loadSelectedUsageDetail(item.user_id);
  };

  const totalUsageDetailPages = Math.max(1, Math.ceil(usageDetailItems.length / CREDIT_USAGE_DETAIL_PAGE_SIZE));
  const currentUsageDetailPage = Math.min(usageDetailPage, totalUsageDetailPages);
  const paginatedUsageDetailItems = usageDetailItems.slice(
    (currentUsageDetailPage - 1) * CREDIT_USAGE_DETAIL_PAGE_SIZE,
    currentUsageDetailPage * CREDIT_USAGE_DETAIL_PAGE_SIZE,
  );
  const filteredLedger = creditLedger.filter((item) => ledgerFilter === 'all' || item.direction === ledgerFilter);
  const totalLedgerPages = Math.max(1, Math.ceil(filteredLedger.length / CREDIT_LEDGER_PAGE_SIZE));
  const currentLedgerPage = Math.min(ledgerPage, totalLedgerPages);
  const paginatedLedger = filteredLedger.slice((currentLedgerPage - 1) * CREDIT_LEDGER_PAGE_SIZE, currentLedgerPage * CREDIT_LEDGER_PAGE_SIZE);

  return (
    <div className={`${workspacePageClass} mx-auto max-w-6xl space-y-8`}>
      <section className={`${workspaceCardClass} overflow-hidden p-6`}>
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-sky-600">Credit Workspace</p>
            <h3 className={`${workspaceSectionTitleClass} mt-3`}>积分中心</h3>
            <p className={`${workspaceSectionTextClass} mt-2`}>
              管理 {currentUser.organization_name} 的积分余额、订单兑换、成员消耗和 AI 扣费流水。
            </p>
          </div>
          <button onClick={() => void loadCredits()} className={workspaceSecondaryButtonClass} type="button">
            刷新积分
          </button>
        </div>
      </section>

      {creditError && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
          {creditError}
        </div>
      )}

      {redeemMessage && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-300">
          {redeemMessage}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-3">
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">当前余额</p>
          <p className="mt-2 text-3xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.credit_balance ?? 0}</p>
        </div>
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">累计充值</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.total_recharged ?? 0}</p>
        </div>
        <div className={`${workspaceCardClass} p-5`}>
          <p className="text-sm text-slate-500 dark:text-slate-400">累计消耗</p>
          <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-white">{creditLoading ? '--' : creditOverview?.total_consumed ?? 0}</p>
        </div>
      </section>

      <section className={`${workspaceCardClass} space-y-4 p-6`}>
        <div>
          <p className="font-medium text-slate-900 dark:text-white">小红书订单兑换</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">输入订单号和手机号后四位，将有效订单兑换到当前机构积分池。</p>
        </div>
        <form className="grid gap-3 md:grid-cols-[1fr_180px_auto]" onSubmit={handleRedeemSubmit}>
          <input
            value={redeemOrderId}
            onChange={(event) => setRedeemOrderId(event.target.value)}
            placeholder="小红书订单号"
            className={`${workspaceFieldClass} w-full`}
          />
          <input
            value={redeemPhoneSuffix}
            onChange={(event) => setRedeemPhoneSuffix(event.target.value.replace(/\D/g, '').slice(0, 4))}
            placeholder="手机号后四位"
            className={`${workspaceFieldClass} w-full`}
          />
          <button type="submit" disabled={redeemLoading} className={workspacePrimaryButtonClass}>
            {redeemLoading ? '兑换中...' : '兑换积分'}
          </button>
        </form>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className="space-y-6">
          <div className={`${workspaceCardClass} space-y-4 p-6`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">成员用量</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按成员汇总 AI 功能的积分消耗，点击可查看成员明细。</p>
              </div>
              <span className="shrink-0 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-300">
                {creditUsage.length} 人
              </span>
            </div>
            <div className="space-y-3">
              {creditUsage.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">暂无成员用量记录。</p>
              ) : (
                creditUsage.map((item) => {
                  const selected = selectedUsageUser?.user_id === item.user_id;
                  return (
                    <button
                      key={item.user_id}
                      type="button"
                      onClick={() => handleSelectUsageUser(item)}
                      className={cn(
                        'flex w-full items-center justify-between rounded-2xl border px-4 py-4 text-left transition-all',
                        selected
                          ? 'border-sky-300 bg-sky-50/90 shadow-[0_18px_40px_rgba(47,128,237,0.12)] dark:border-sky-500/30 dark:bg-sky-500/10'
                          : 'border-slate-200/70 bg-white/70 hover:border-sky-200 hover:bg-sky-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:border-white/15 dark:hover:bg-white/10',
                      )}
                    >
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{item.display_name}</p>
                        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                          调用 {item.usage_count} 次 · 最近使用 {item.last_used_at ? new Date(item.last_used_at).toLocaleString('zh-CN') : '暂无'}
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold text-slate-900 dark:text-white">-{item.credit_consumed}</p>
                        <p className="mt-1 text-xs text-sky-600 dark:text-sky-300">查看明细</p>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className={`${workspaceCardClass} space-y-4 p-6`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-medium text-slate-900 dark:text-white">成员明细</p>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">查看某位成员的 AI 使用与积分扣费细项。</p>
              </div>
              {selectedUsageUser && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedUsageUser(null);
                    setUsageDetailItems([]);
                    setUsageDetailError('');
                  }}
                  className={workspaceSecondaryButtonClass}
                >
                  清空选择
                </button>
              )}
            </div>

            {!selectedUsageUser ? (
              <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
                先从上方成员列表选择一位成员，再查看成员明细。
              </div>
            ) : (
              <div className="space-y-4">
                <div className={`${workspaceSoftCardClass} grid gap-4 p-5 md:grid-cols-3`}>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">成员</p>
                    <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">{selectedUsageUser.display_name}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">累计消耗</p>
                    <p className="mt-2 text-base font-semibold text-slate-900 dark:text-white">-{selectedUsageUser.credit_consumed}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">最近使用</p>
                    <p className="mt-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                      {selectedUsageUser.last_used_at ? new Date(selectedUsageUser.last_used_at).toLocaleString('zh-CN') : '暂无'}
                    </p>
                  </div>
                </div>

                {usageDetailError && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-300">
                    {usageDetailError}
                  </div>
                )}

                {usageDetailLoading ? (
                  <div className={`${workspaceSoftCardClass} p-5`}>
                    <WorkspaceLoading label="正在加载成员明细..." />
                  </div>
                ) : usageDetailItems.length === 0 ? (
                  <div className={`${workspaceSoftCardClass} p-5 text-sm text-slate-500 dark:text-slate-400`}>
                    该成员目前没有可展示的使用明细。
                  </div>
                ) : (
                  <div className="space-y-3">
                    {paginatedUsageDetailItems.map((item) => {
                      const featureLabel = FEATURE_KEY_LABELS[item.feature_key] ?? item.feature_key;
                      const sourceTypeLabel = item.source_record_type
                        ? (SOURCE_RECORD_TYPE_LABELS[item.source_record_type] ?? item.source_record_type)
                        : '未知';
                      const providerLabel = item.provider || 'AI';
                      return (
                        <div key={item.id} className={`${workspaceSoftCardClass} space-y-3 p-4`}>
                          <div className="flex items-start justify-between gap-4">
                            <div>
                              <p className="font-medium text-slate-900 dark:text-white">{featureLabel}</p>
                              {canSeeSensitiveUsageMeta && (
                                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                  {providerLabel}{item.model ? ` · ${item.model}` : ''} · 请求编号 {formatRequestId(item.request_id)}
                                </p>
                              )}
                            </div>
                            <p className="text-sm font-semibold text-rose-600 dark:text-rose-300">-{item.credit_cost_final}</p>
                          </div>
                          <div className="grid gap-3 text-xs text-slate-500 dark:text-slate-400 md:grid-cols-3">
                            {canSeeSensitiveUsageMeta ? (
                              <p>来源：{sourceTypeLabel} #{item.source_record_id ?? '-'}</p>
                            ) : (
                              <p>来源：{sourceTypeLabel}</p>
                            )}
                            <p>Tokens：{item.total_tokens ?? 0}（输入 {item.input_tokens ?? 0} / 输出 {item.output_tokens ?? 0}）</p>
                            <p>时间：{new Date(item.created_at).toLocaleString('zh-CN')}</p>
                          </div>
                        </div>
                      );
                    })}
                    {totalUsageDetailPages > 1 && (
                      <div className="flex items-center justify-between border-t border-sky-100/80 pt-3 text-sm dark:border-white/10">
                        <button
                          type="button"
                          onClick={() => setUsageDetailPage((page) => Math.max(1, page - 1))}
                          disabled={currentUsageDetailPage === 1}
                          className={workspaceSecondaryButtonClass}
                        >
                          上一页
                        </button>
                        <span className="text-slate-500 dark:text-slate-400">
                          第 {currentUsageDetailPage} / {totalUsageDetailPages} 页
                        </span>
                        <button
                          type="button"
                          onClick={() => setUsageDetailPage((page) => Math.min(totalUsageDetailPages, page + 1))}
                          disabled={currentUsageDetailPage === totalUsageDetailPages}
                          className={workspaceSecondaryButtonClass}
                        >
                          下一页
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className={`${workspaceCardClass} space-y-4 p-6`}>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-medium text-slate-900 dark:text-white">最近流水</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">最近 100 条积分变动记录，支持按类型筛选。</p>
            </div>
            <label className="space-y-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">
              流水筛选
              <select value={ledgerFilter} onChange={(event) => setLedgerFilter(event.target.value as 'all' | 'credit' | 'debit')} className={`${workspaceFieldClass} w-full`}>
                <option value="all">全部</option>
                <option value="credit">仅充值</option>
                <option value="debit">仅消耗</option>
              </select>
            </label>
          </div>

          <div className="space-y-3">
            {filteredLedger.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400">当前筛选条件下暂无积分流水。</p>
            ) : (
              paginatedLedger.map((item) => {
                const sourceLabel = LEDGER_SOURCE_TYPE_LABELS[item.source_type] ?? item.source_type;
                const rawNote = item.note || '';
                const isManualTopup = /^manual_topup/.test(rawNote);
                const noteLabel = isManualTopup ? '人工充值' : (rawNote || undefined);
                const featureLabel = item.source_type === 'ai_usage' ? (AI_FEATURE_LABELS[rawNote] ?? rawNote) : undefined;
                const displayTitle = featureLabel ?? sourceLabel;
                const displayNote = featureLabel ? undefined : noteLabel;
                return (
                  <div key={item.id} className="flex items-center justify-between rounded-2xl border border-slate-200/70 bg-white/70 px-4 py-4 text-sm dark:border-white/10 dark:bg-white/5">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">{displayTitle}</p>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {[displayNote, `余额 ${item.balance_after}`, new Date(item.created_at).toLocaleString('zh-CN')].filter(Boolean).join(' · ')}
                      </p>
                    </div>
                    <p className={item.direction === 'credit' ? 'font-semibold text-emerald-600 dark:text-emerald-300' : 'font-semibold text-rose-600 dark:text-rose-300'}>
                      {item.direction === 'credit' ? '+' : '-'}{item.amount}
                    </p>
                  </div>
                );
              })
            )}
          </div>

          {totalLedgerPages > 1 && (
            <div className="flex items-center justify-between border-t border-sky-100/80 pt-3 text-sm dark:border-white/10">
              <button
                type="button"
                onClick={() => setLedgerPage((page) => Math.max(1, page - 1))}
                disabled={currentLedgerPage === 1}
                className={workspaceSecondaryButtonClass}
              >
                上一页
              </button>
              <span className="text-slate-500 dark:text-slate-400">
                第 {currentLedgerPage} / {totalLedgerPages} 页
              </span>
              <button
                type="button"
                onClick={() => setLedgerPage((page) => Math.min(totalLedgerPages, page + 1))}
                disabled={currentLedgerPage === totalLedgerPages}
                className={workspaceSecondaryButtonClass}
              >
                下一页
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
