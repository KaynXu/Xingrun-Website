import { Info } from 'lucide-react';
import { FloatingOverviewFilter, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import {
  workspaceCardClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';
import type { ClassBindingTarget, CurrentUser } from './model';

export type CampusOverviewFilterLayer = 'subject' | 'teacher' | 'stage' | 'grade';

type CampusOverviewFilterItem = {
  key: CampusOverviewFilterLayer;
  label: string;
  selected: boolean;
};

type CampusOverviewSummaryItem = {
  label: string;
  value: string | number;
};

type CampusOverviewProps = {
  currentUser: CurrentUser;
  classBindingTarget?: ClassBindingTarget | null;
  onClearClassBindingTarget?: () => void;
  activeHelpKey: 'overview' | null;
  onHelpEnter: () => void;
  onHelpLeave: () => void;
  onHelpToggle: () => void;
  selectedSummary: string;
  open: boolean;
  items: CampusOverviewFilterItem[];
  activeKey: CampusOverviewFilterLayer | null;
  options: FloatingFilterOption[];
  summaryItems: CampusOverviewSummaryItem[];
  onAreaEnter: () => void;
  onAreaLeave: () => void;
  onTriggerClick: () => void;
  onLayerEnter: () => void;
  onLayerLeave: () => void;
  onHoverItem: (key: CampusOverviewFilterLayer) => void;
  onClickItem: (key: CampusOverviewFilterLayer) => void;
  onClear: () => void;
  onSelect: (value: string | number) => void;
};

export function CampusOverview({
  currentUser,
  classBindingTarget,
  onClearClassBindingTarget,
  activeHelpKey,
  onHelpEnter,
  onHelpLeave,
  onHelpToggle,
  selectedSummary,
  open,
  items,
  activeKey,
  options,
  summaryItems,
  onAreaEnter,
  onAreaLeave,
  onTriggerClick,
  onLayerEnter,
  onLayerLeave,
  onHoverItem,
  onClickItem,
  onClear,
  onSelect,
}: CampusOverviewProps) {
  return (
    <section className={`${workspaceCardClass} space-y-4 p-6`}>
      <p className="text-sm uppercase tracking-[0.25em] text-sky-600">Class Workspace</p>
      <div className="relative flex flex-wrap items-center gap-2">
        <h3 className="text-2xl font-bold text-slate-900 dark:text-white">校区总览</h3>
        <div
          className="relative"
          onMouseEnter={onHelpEnter}
          onMouseLeave={onHelpLeave}
        >
          <button
            type="button"
            onClick={onHelpToggle}
            className="inline-flex h-8 w-8 items-center justify-center text-sky-600 transition hover:text-sky-700 dark:text-sky-300 dark:hover:text-sky-200"
            aria-label="查看校区总览说明"
          >
            <Info size={16} />
          </button>
          {activeHelpKey === 'overview' && (
            <div className="absolute left-0 top-10 z-20 w-[min(24rem,calc(100vw-3rem))] rounded-2xl border border-sky-100 bg-white p-4 text-sm text-slate-500 shadow-[0_18px_40px_rgba(14,165,233,0.12)] dark:border-white/10 dark:bg-slate-900 dark:text-slate-300">
              <p className="font-semibold text-slate-900 dark:text-white">校区总览说明</p>
              <p className="mt-2">这里汇总 {currentUser.organization_name} 的教师、学员、班级和小课数量，可按科目、教师、学段和年级查看不同范围。</p>
            </div>
          )}
        </div>
        <FloatingOverviewFilter
          label="全校区"
          selectedSummary={selectedSummary}
          defaultSummary="全校区"
          open={open}
          items={items}
          activeKey={activeKey}
          options={options}
          onAreaEnter={onAreaEnter}
          onAreaLeave={onAreaLeave}
          onTriggerClick={onTriggerClick}
          onLayerEnter={onLayerEnter}
          onLayerLeave={onLayerLeave}
          onHoverItem={onHoverItem}
          onClickItem={onClickItem}
          onClear={onClear}
          onSelect={onSelect}
        />
      </div>
      {classBindingTarget && (
        <div className="flex flex-col gap-3 rounded-2xl border border-sky-200 bg-sky-50/80 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-sky-500/30 dark:bg-sky-500/10">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-sky-600 dark:text-sky-300">绑定班级</p>
            <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">目标老师：{classBindingTarget?.teacherName}</p>
          </div>
          {onClearClassBindingTarget && (
            <button
              type="button"
              onClick={onClearClassBindingTarget}
              className={workspaceSecondaryButtonClass}
            >
              清除目标
            </button>
          )}
        </div>
      )}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {summaryItems.map((item) => (
          <div key={item.label} className={`${workspaceSoftCardClass} p-4`}>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">{item.label}</p>
            <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{item.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
