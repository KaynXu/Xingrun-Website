import { Info } from 'lucide-react';
import { FloatingOverviewFilter, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import {
  workspaceSectionTitleClass,
} from '../../workspaceShared';
import type { ClassBindingTarget, CurrentUser } from './model';
import {
  studentCenterMutedSurfaceClass,
  studentCenterSecondaryButtonClass,
  studentCenterSurfaceClass,
} from './ui';

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
    <section className={`${studentCenterSurfaceClass} space-y-5 p-6`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="relative flex flex-wrap items-center gap-2">
            <h3 className={workspaceSectionTitleClass}>校区总览</h3>
            <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
              {currentUser.organization_name}
            </span>
            <div
              className="relative"
              onMouseEnter={onHelpEnter}
              onMouseLeave={onHelpLeave}
            >
              <button
                type="button"
                onClick={onHelpToggle}
                className="inline-flex h-8 w-8 items-center justify-center text-slate-400 transition hover:text-slate-700 dark:text-slate-500 dark:hover:text-slate-200"
                aria-label="查看校区总览说明"
              >
                <Info size={16} />
              </button>
              {activeHelpKey === 'overview' && (
                <div className="absolute left-0 top-10 z-20 w-[min(24rem,calc(100vw-3rem))] rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-500 shadow-none dark:border-white/10 dark:bg-slate-950 dark:text-slate-300">
                  <p className="font-semibold text-slate-900 dark:text-white">校区总览说明</p>
                  <p className="mt-2">查看 {currentUser.organization_name} 的教师、学员、班级和小课数量，可按科目、教师、学段、年级筛选。</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <FloatingOverviewFilter
          label="全校区"
          selectedSummary={selectedSummary}
          defaultSummary="全校区"
          open={open}
          items={items}
          activeKey={activeKey}
          options={options}
          tone="slate"
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
        <div className="flex flex-col gap-3 rounded-2xl border border-amber-200 bg-amber-50/80 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-amber-400/20 dark:bg-amber-400/10">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700 dark:text-amber-200">绑定班级</p>
            <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">目标老师：{classBindingTarget?.teacherName}</p>
          </div>
          {onClearClassBindingTarget && (
            <button
              type="button"
              onClick={onClearClassBindingTarget}
              className={studentCenterSecondaryButtonClass}
            >
              清除目标
            </button>
          )}
        </div>
      )}

      <div className={`${studentCenterMutedSurfaceClass} overflow-hidden p-0`}>
        <div className="grid grid-cols-2 divide-x divide-y divide-slate-200 xl:grid-cols-4 xl:divide-y-0 dark:divide-white/10">
          {summaryItems.map((item) => (
            <div key={item.label} className="p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 dark:text-slate-500">{item.label}</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
