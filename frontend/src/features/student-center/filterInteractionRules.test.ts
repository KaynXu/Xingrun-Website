import assert from 'node:assert/strict';
import test from 'node:test';
import {
  cancelFilterCloseTimer,
  resolveOverviewFilterItemClick,
  resolveOverviewFilterItemHover,
  resolveOverviewFilterTriggerClick,
  scheduleFilterClose,
  type FilterCloseTimerRef,
} from './filterInteractionRules';

test('cancelFilterCloseTimer clears an existing close timer and resets the ref', () => {
  const ref: FilterCloseTimerRef = { current: 42 };
  const clearedTimers: number[] = [];

  cancelFilterCloseTimer(ref, (timerId) => {
    clearedTimers.push(timerId);
  });

  assert.deepEqual(clearedTimers, [42]);
  assert.equal(ref.current, null);
});

test('scheduleFilterClose replaces stale timers and clears itself after running', () => {
  const ref: FilterCloseTimerRef = { current: 7 };
  const clearedTimers: number[] = [];
  const scheduledDelays: number[] = [];
  let scheduledCallback: (() => void) | null = null;
  let closed = false;

  scheduleFilterClose(ref, {
    onClose: () => {
      closed = true;
    },
    clearTimeoutFn: (timerId) => {
      clearedTimers.push(timerId);
    },
    setTimeoutFn: (callback, delay) => {
      scheduledCallback = callback;
      scheduledDelays.push(delay);
      return 99;
    },
  });

  assert.deepEqual(clearedTimers, [7]);
  assert.deepEqual(scheduledDelays, [120]);
  assert.equal(ref.current, 99);
  assert.equal(closed, false);

  scheduledCallback?.();

  assert.equal(closed, true);
  assert.equal(ref.current, null);
});

test('resolveOverviewFilterTriggerClick toggles the overview popover and clears layers when closing', () => {
  assert.deepEqual(resolveOverviewFilterTriggerClick({
    open: false,
    activeLayer: null,
    clickedLayer: null,
  }), {
    open: true,
    activeLayer: null,
    clickedLayer: null,
  });

  assert.deepEqual(resolveOverviewFilterTriggerClick({
    open: true,
    activeLayer: 'teacher',
    clickedLayer: 'teacher',
  }), {
    open: false,
    activeLayer: null,
    clickedLayer: null,
  });
});

test('resolveOverviewFilterItemHover opens a layer without pinning it as clicked', () => {
  assert.deepEqual(resolveOverviewFilterItemHover('subject'), {
    activeLayer: 'subject',
    clickedLayer: null,
  });
});

test('resolveOverviewFilterItemClick toggles the clicked overview layer', () => {
  assert.deepEqual(resolveOverviewFilterItemClick({
    activeLayer: 'subject',
    clickedLayer: null,
    targetLayer: 'subject',
  }), {
    activeLayer: null,
    clickedLayer: null,
  });

  assert.deepEqual(resolveOverviewFilterItemClick({
    activeLayer: 'subject',
    clickedLayer: null,
    targetLayer: 'teacher',
  }), {
    activeLayer: 'teacher',
    clickedLayer: 'teacher',
  });
});
