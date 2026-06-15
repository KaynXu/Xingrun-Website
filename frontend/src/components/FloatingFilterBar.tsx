import type { ReactNode } from 'react';

type FloatingFilterValue = string | number;

export type FloatingFilterItem<Key extends string = string> = {
  key: Key;
  defaultLabel: string;
  label: string;
  selected: boolean;
  icon?: ReactNode;
};

export type FloatingFilterOption = {
  id: FloatingFilterValue;
  label: string;
  selected: boolean;
};

type FloatingFilterBarProps<Key extends string = string> = {
  items: Array<FloatingFilterItem<Key>>;
  activeKey: Key | null;
  options: FloatingFilterOption[];
  scopeLabel?: string;
  summary: string;
  emptyText?: string;
  summaryText?: string;
  extraControls?: ReactNode;
  floatingOptions?: boolean;
  compact?: boolean;
  activateOnHover?: boolean;
  tone?: 'sky' | 'slate';
  onAreaEnter: () => void;
  onAreaLeave: () => void;
  onActivate: (key: Key | null) => void;
  onClear: (key: Key) => void;
  onSelect: (value: FloatingFilterValue) => void;
};

type FloatingOverviewFilterProps<Key extends string = string> = {
  label: string;
  selectedSummary: string;
  defaultSummary: string;
  open: boolean;
  items: Array<Pick<FloatingFilterItem<Key>, 'key' | 'label' | 'selected'>>;
  activeKey: Key | null;
  options: FloatingFilterOption[];
  emptyText?: string;
  tone?: 'sky' | 'slate';
  onAreaEnter: () => void;
  onAreaLeave: () => void;
  onTriggerClick: () => void;
  onLayerEnter: () => void;
  onLayerLeave: () => void;
  onHoverItem: (key: Key) => void;
  onClickItem: (key: Key) => void;
  onClear: () => void;
  onSelect: (value: FloatingFilterValue) => void;
};

function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function resolveFloatingFilterTone(tone: 'sky' | 'slate') {
  if (tone === 'slate') {
    return {
      divider: 'border-slate-200 dark:border-white/10',
      selectedTrigger: 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-950',
      activeTrigger: 'border-slate-300 bg-slate-100 text-slate-900 dark:border-white/15 dark:bg-white/[0.08] dark:text-white',
      idleTrigger: 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/[0.08]',
      clearChip: 'bg-white/20 hover:bg-white/35 dark:bg-slate-950/15 dark:hover:bg-slate-950/30',
      clearFilter: 'bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/15',
      panel: 'rounded-2xl border border-slate-200 bg-white p-3 shadow-none dark:border-white/10 dark:bg-slate-950',
      overviewLayer: 'rounded-2xl border border-slate-200 bg-slate-50/75 p-3 dark:border-white/10 dark:bg-white/[0.04]',
      optionSelected: 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-950',
      optionIdle: 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/[0.08]',
    };
  }

  return {
    divider: 'border-sky-100/80 dark:border-white/10',
    selectedTrigger: 'border-sky-500 bg-sky-500 text-white shadow-sm dark:border-sky-400 dark:bg-sky-400 dark:text-slate-950',
    activeTrigger: 'border-sky-300 bg-sky-50 text-sky-700 shadow-sm dark:border-sky-400/40 dark:bg-sky-400/10 dark:text-sky-100',
    idleTrigger: 'border-sky-100 bg-white/80 text-slate-600 hover:border-sky-200 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
    clearChip: 'bg-white/25 hover:bg-white/40 dark:bg-slate-950/20 dark:hover:bg-slate-950/30',
    clearFilter: 'bg-sky-100 text-sky-600 hover:bg-sky-200 dark:bg-slate-950/20 dark:hover:bg-slate-950/30',
    panel: 'rounded-2xl border border-sky-100 bg-white p-3 shadow-[0_12px_30px_rgba(14,165,233,0.08)] dark:border-white/10 dark:bg-slate-900/70',
    overviewLayer: 'rounded-2xl border border-sky-100 bg-sky-50/70 p-3 dark:border-white/10 dark:bg-white/5',
    optionSelected: 'border-sky-500 bg-sky-500 text-white',
    optionIdle: 'border-sky-100 bg-white text-slate-600 hover:border-sky-300 hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-300 dark:hover:bg-white/10',
  };
}

export function FloatingFilterBar<Key extends string = string>({
  items,
  activeKey,
  options,
  scopeLabel,
  summary,
  emptyText = '当前条件下暂无可选项。',
  summaryText,
  extraControls,
  floatingOptions = false,
  compact = false,
  activateOnHover = true,
  tone = 'sky',
  onAreaEnter,
  onAreaLeave,
  onActivate,
  onClear,
  onSelect,
}: FloatingFilterBarProps<Key>) {
  const activeItem = activeKey ? items.find((item) => item.key === activeKey) : null;
  const toneClasses = resolveFloatingFilterTone(tone);

  return (
    <div
      className={cn(
        'relative',
        compact ? '' : `border-t pt-4 ${toneClasses.divider}`,
        !floatingOptions && !compact && 'space-y-3',
      )}
      onMouseEnter={onAreaEnter}
      onMouseLeave={onAreaLeave}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn('font-semibold text-slate-500 dark:text-slate-400', compact ? 'text-xs' : 'text-sm')}>筛选</span>
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onMouseEnter={() => {
              if (activateOnHover) {
                onActivate(item.key);
              }
            }}
            onClick={() => onActivate(activeKey === item.key ? null : item.key)}
            className={cn(
              'inline-flex min-h-10 items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition',
              compact && 'min-h-9 px-3 py-1.5',
              item.selected
                ? toneClasses.selectedTrigger
                : activeKey === item.key
                  ? toneClasses.activeTrigger
                  : toneClasses.idleTrigger,
            )}
          >
            {item.icon}
            {item.label}
            {item.selected && (
              <span
                role="button"
                tabIndex={0}
                aria-label={`取消${item.defaultLabel}筛选`}
                onClick={(event) => {
                  event.stopPropagation();
                  onClear(item.key);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    event.stopPropagation();
                    onClear(item.key);
                  }
                }}
                className={cn('inline-flex h-5 w-5 items-center justify-center rounded-full text-xs leading-none', toneClasses.clearChip)}
              >
                ×
              </span>
            )}
          </button>
        ))}
        {scopeLabel ? (
          <span className="ml-auto text-xs font-semibold text-slate-400 dark:text-slate-500">
            {scopeLabel}
          </span>
        ) : null}
        {extraControls}
      </div>
      {activeKey && (
        <div className={cn(toneClasses.panel, floatingOptions ? 'absolute left-0 right-0 top-[calc(100%+0.5rem)] z-30' : '')}>
          <p className="mb-2 text-xs font-bold text-slate-400 dark:text-slate-500">
            {activeItem?.defaultLabel || '筛选'}筛选
          </p>
          {options.length === 0 ? (
            <p className="text-sm text-slate-400 dark:text-slate-500">{emptyText}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {options.map((option) => (
                <button
                  key={`${activeKey}-${option.id}`}
                  type="button"
                  onClick={() => onSelect(option.id)}
                  className={cn(
                    'rounded-full border px-3 py-2 text-sm font-semibold transition',
                    option.selected
                      ? toneClasses.optionSelected
                      : toneClasses.optionIdle,
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {summaryText ? (
        <p className="text-xs text-slate-400 dark:text-slate-500">
          当前：{summary}。{summaryText}
        </p>
      ) : null}
    </div>
  );
}

export function FloatingOverviewFilter<Key extends string = string>({
  label,
  selectedSummary,
  defaultSummary,
  open,
  items,
  activeKey,
  options,
  emptyText = '当前条件下暂无可选项。',
  tone = 'sky',
  onAreaEnter,
  onAreaLeave,
  onTriggerClick,
  onLayerEnter,
  onLayerLeave,
  onHoverItem,
  onClickItem,
  onClear,
  onSelect,
}: FloatingOverviewFilterProps<Key>) {
  const hasSelection = selectedSummary !== defaultSummary;
  const toneClasses = resolveFloatingFilterTone(tone);

  return (
    <div
      className="relative"
      onMouseEnter={onAreaEnter}
      onMouseLeave={onAreaLeave}
    >
      <button
        type="button"
        onClick={onTriggerClick}
        className={cn(
          'inline-flex min-h-9 items-center gap-2 rounded-full border px-3 py-2 text-sm font-semibold transition',
          open || hasSelection
            ? toneClasses.activeTrigger
            : toneClasses.idleTrigger,
        )}
      >
        {hasSelection ? `${label}：${selectedSummary}` : label}
        {hasSelection ? (
          <span
            role="button"
            tabIndex={0}
            aria-label="清空校区总览筛选"
            onClick={(event) => {
              event.stopPropagation();
              onClear();
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                event.stopPropagation();
                onClear();
              }
            }}
            className={cn('inline-flex h-5 w-5 items-center justify-center rounded-full text-xs leading-none', toneClasses.clearFilter)}
          >
            ×
          </span>
        ) : null}
      </button>
      {open && (
        <div className={cn('absolute left-0 top-11 z-20 w-[min(28rem,calc(100vw-3rem))] space-y-3', toneClasses.panel)}>
          <div className={toneClasses.overviewLayer}>
            <div className="flex flex-wrap gap-2">
              {items.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onMouseEnter={() => {
                    onLayerEnter();
                    onHoverItem(item.key);
                  }}
                  onMouseLeave={onLayerLeave}
                  onClick={() => {
                    onLayerEnter();
                    onClickItem(item.key);
                  }}
                  className={cn(
                    'rounded-full border px-3 py-2 text-sm font-semibold transition',
                    activeKey === item.key || item.selected
                      ? toneClasses.activeTrigger
                      : toneClasses.optionIdle,
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          {activeKey && (
            <div
              className={toneClasses.overviewLayer}
              onMouseEnter={onLayerEnter}
              onMouseLeave={onLayerLeave}
            >
              {options.length === 0 ? (
                <p className="text-sm text-slate-400 dark:text-slate-500">{emptyText}</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {options.map((option) => (
                    <button
                      key={`${activeKey}-${option.id}`}
                      type="button"
                      onClick={() => onSelect(option.id)}
                      className={cn(
                        'rounded-full border px-3 py-2 text-sm font-semibold transition',
                        option.selected
                          ? toneClasses.optionSelected
                          : toneClasses.optionIdle,
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
