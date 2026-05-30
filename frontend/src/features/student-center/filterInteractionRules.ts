export type FilterCloseTimerRef = {
  current: number | null;
};

export type OverviewFilterLayer = 'subject' | 'teacher' | 'stage' | 'grade';

type OverviewFilterLayerState = {
  activeLayer: OverviewFilterLayer | null;
  clickedLayer: OverviewFilterLayer | null;
};

export function cancelFilterCloseTimer(
  timerRef: FilterCloseTimerRef,
  clearTimeoutFn: (timerId: number) => void,
) {
  if (timerRef.current === null) {
    return;
  }
  clearTimeoutFn(timerRef.current);
  timerRef.current = null;
}

export function scheduleFilterClose(
  timerRef: FilterCloseTimerRef,
  {
    onClose,
    clearTimeoutFn,
    setTimeoutFn,
    delay = 120,
  }: {
    onClose: () => void;
    clearTimeoutFn: (timerId: number) => void;
    setTimeoutFn: (callback: () => void, delay: number) => number;
    delay?: number;
  },
) {
  cancelFilterCloseTimer(timerRef, clearTimeoutFn);
  timerRef.current = setTimeoutFn(() => {
    onClose();
    timerRef.current = null;
  }, delay);
}

export function resolveOverviewFilterTriggerClick({
  open,
}: {
  open: boolean;
  activeLayer: OverviewFilterLayer | null;
  clickedLayer: OverviewFilterLayer | null;
}): { open: boolean } & OverviewFilterLayerState {
  if (open) {
    return {
      open: false,
      activeLayer: null,
      clickedLayer: null,
    };
  }
  return {
    open: true,
    activeLayer: null,
    clickedLayer: null,
  };
}

export function resolveOverviewFilterItemHover(
  targetLayer: OverviewFilterLayer,
): OverviewFilterLayerState {
  return {
    activeLayer: targetLayer,
    clickedLayer: null,
  };
}

export function resolveOverviewFilterItemClick({
  activeLayer,
  targetLayer,
}: {
  activeLayer: OverviewFilterLayer | null;
  clickedLayer: OverviewFilterLayer | null;
  targetLayer: OverviewFilterLayer;
}): OverviewFilterLayerState {
  if (activeLayer === targetLayer) {
    return {
      activeLayer: null,
      clickedLayer: null,
    };
  }
  return {
    activeLayer: targetLayer,
    clickedLayer: targetLayer,
  };
}
