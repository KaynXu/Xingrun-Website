import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { JSDOM } from 'jsdom';

import { CourseCalendarPage, type CourseCalendarPageProps } from './CourseCalendarPage';

type GlobalKey = keyof typeof globalThis;

function setGlobalValue<T>(key: GlobalKey, value: T): () => void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, key);
  Object.defineProperty(globalThis, key, {
    configurable: true,
    writable: true,
    value,
  });

  return () => {
    if (descriptor) {
      Object.defineProperty(globalThis, key, descriptor);
      return;
    }

    delete (globalThis as Record<string, unknown>)[key];
  };
}

function setupDomEnvironment(): {
  cleanup: () => void;
  container: HTMLDivElement;
  event: typeof Event;
  mouseEvent: typeof MouseEvent;
} {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });
  const restoreCallbacks = [
    setGlobalValue('window', dom.window),
    setGlobalValue('document', dom.window.document),
    setGlobalValue('navigator', dom.window.navigator),
    setGlobalValue('HTMLElement', dom.window.HTMLElement),
    setGlobalValue('HTMLSelectElement', dom.window.HTMLSelectElement),
    setGlobalValue('Node', dom.window.Node),
    setGlobalValue('Event', dom.window.Event),
    setGlobalValue('MouseEvent', dom.window.MouseEvent),
    setGlobalValue('IS_REACT_ACT_ENVIRONMENT' as GlobalKey, true),
  ];
  const container = dom.window.document.createElement('div');
  dom.window.document.body.appendChild(container);

  return {
    cleanup: () => {
      dom.window.document.body.removeChild(container);
      for (const restore of restoreCallbacks.reverse()) {
        restore();
      }
      dom.window.close();
    },
    container,
    event: dom.window.Event,
    mouseEvent: dom.window.MouseEvent,
  };
}

function buildCalendarProps(overrides: Partial<CourseCalendarPageProps> = {}): CourseCalendarPageProps {
  return {
    anchorDate: '2026-03-31',
    today: '2026-04-02',
    currentUserId: 1,
    currentUserRole: 'owner',
    classes: [],
    schedules: [],
    customItems: [],
    customSchedules: [],
    pageStepDays: 6,
    onPageStepDaysChange: () => undefined,
    onPreviousPage: () => undefined,
    onNextPage: () => undefined,
    onScheduleClass: () => undefined,
    onScheduleCustomItem: () => undefined,
    onCreateCustomItem: () => Promise.resolve({ id: 999, title: '事项', time_range: '19:00-20:00', note: '', visibility: 'private' }),
    onDeleteCustomItem: () => undefined,
    onDeleteSchedule: () => undefined,
    onDeleteCustomSchedule: () => undefined,
    ...overrides,
  };
}

function dispatchCalendarDrop(
  domEnvironment: { event: typeof Event },
  target: Element,
  payload: Record<string, string>,
) {
  const dropEvent = new domEnvironment.event('drop', { bubbles: true, cancelable: true });
  Object.defineProperty(dropEvent, 'dataTransfer', {
    configurable: true,
    value: {
      getData: (type: string) => payload[type] ?? '',
    },
  });
  target.dispatchEvent(dropEvent);
}

test('course calendar page renders the approved weekly dashboard shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-03-31"
      today="2026-04-02"
      currentUserId={1}
      currentUserRole="owner"
      classes={[
        {
          id: 1,
          name: '高一数学A班',
          subject: '数学',
          grade: '高一',
          teacher_name: 'Alice',
          teacher_email: 'alice@example.com',
          lesson_count: 1,
        },
      ]}
      schedules={[
        {
          id: 101,
          class_id: 1,
          date: '2026-03-31',
          time_block: '08:00-10:00',
          start_offset_minutes: 15,
        },
      ]}
      customItems={[
        { id: 201, title: '教研会', time_range: '19:00-20:00', note: '带资料', visibility: 'private', created_by: 1 },
      ]}
      customSchedules={[
        {
          id: 301,
          custom_item_id: 201,
          date: '2026-04-02',
          time_block: '20:00-22:00',
          title: '教研会',
          time_range: '19:00-20:00',
          note: '带资料',
          visibility: 'organization',
        },
      ]}
      pageStepDays={6}
      onPageStepDaysChange={() => undefined}
      onPreviousPage={() => undefined}
      onNextPage={() => undefined}
      onScheduleClass={() => undefined}
      onScheduleCustomItem={() => undefined}
      onCreateCustomItem={() => Promise.resolve({ id: 999, title: '事项', time_range: '19:00-20:00', note: '', visibility: 'private' })}
      onDeleteCustomItem={() => undefined}
      onDeleteSchedule={() => undefined}
      onDeleteCustomSchedule={() => undefined}
    />,
  );

  assert.match(markup, /课程日历/);
  assert.match(markup, /08:00-10:00/);
  assert.match(markup, /10:00-12:00/);
  assert.match(markup, /14:00-16:00/);
  assert.match(markup, /16:00-18:00/);
  assert.match(markup, /18:00-20:00/);
  assert.match(markup, /20:00-22:00/);
  assert.match(markup, /08:15-10:15/);
  assert.match(markup, /拖动课程到此/);
  assert.match(markup, /添加自定义事项/);
  assert.match(markup, /翻动/);
  assert.match(markup, /全部学科/);
  assert.match(markup, /数学/);
  assert.match(markup, /物理/);
  assert.doesNotMatch(markup, /管理教师筛选/);
  assert.doesNotMatch(markup, /第 1 页/);
  assert.doesNotMatch(markup, /天数/);
  assert.match(markup, /draggable="true"/);
  assert.match(markup, /课程卡片/);
  assert.match(markup, /自定义事项/);
  assert.match(markup, /教研会/);
  assert.match(markup, /管理员发布/);
  assert.doesNotMatch(markup, /待补录课程/);
  assert.doesNotMatch(markup, /新增班级/);
  assert.doesNotMatch(markup, /函数入门/);
});

test('course calendar page avoids a nested min-h-screen container inside the workspace shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-03-31"
      today="2026-04-02"
      currentUserId={2}
      currentUserRole="member"
      classes={[]}
      schedules={[]}
      customItems={[]}
      customSchedules={[]}
      pageStepDays={6}
      onPageStepDaysChange={() => undefined}
      onPreviousPage={() => undefined}
      onNextPage={() => undefined}
      onScheduleClass={() => undefined}
      onScheduleCustomItem={() => undefined}
      onCreateCustomItem={() => Promise.resolve({ id: 999, title: '事项', time_range: '19:00-20:00', note: '', visibility: 'private' })}
      onDeleteCustomItem={() => undefined}
      onDeleteSchedule={() => undefined}
      onDeleteCustomSchedule={() => undefined}
    />,
  );

  assert.doesNotMatch(markup, /min-h-screen/);
});

test('course calendar page renders empty schedules and missing teacher or subject fields without broken labels', () => {
  const emptyMarkup = renderToStaticMarkup(
    <CourseCalendarPage
      {...buildCalendarProps({
        classes: [],
        schedules: [],
        customItems: [],
        customSchedules: [],
      })}
    />,
  );

  assert.match(emptyMarkup, /拖动课程到此/);
  assert.match(emptyMarkup, /暂无可拖拽课程/);
  assert.doesNotMatch(emptyMarkup, /undefined/);

  const missingFieldMarkup = renderToStaticMarkup(
    <CourseCalendarPage
      {...buildCalendarProps({
        classes: [
          {
            id: 1,
            name: '七年级课后巩固班',
            lesson_count: 1,
          },
        ],
        schedules: [
          {
            id: 101,
            class_id: 1,
            date: '2026-03-31',
            time_block: '08:00-10:00',
          },
        ],
      })}
    />,
  );

  assert.match(missingFieldMarkup, /七年级课后巩固班/);
  assert.match(missingFieldMarkup, /未分配教师/);
  assert.match(missingFieldMarkup, /08:00 开始/);
  assert.doesNotMatch(missingFieldMarkup, /undefined/);
});

test('course calendar draggable cards constrain long class names', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/CourseCalendarPage.tsx'), 'utf8');
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      {...buildCalendarProps({
        classes: [
          {
            id: 1,
            name: '这是一个非常非常非常长的七年级数学强化课程名称用于验证右侧拖拽卡片不会撑破布局',
            subject: '数学',
            grade: '七年级',
            teacher_name: 'Alice',
            lesson_count: 1,
          },
        ],
      })}
    />,
  );

  assert.match(markup, /这是一个非常非常非常长的七年级数学强化课程名称用于验证右侧拖拽卡片不会撑破布局/);
  assert.match(source, /<div className="min-w-0 flex-1">[\s\S]*<p className=\{cn\('truncate font-semibold'/);
});

test('course calendar filters can show an empty draggable course result without hiding the page', async () => {
  const domEnvironment = setupDomEnvironment();
  let root: Root | null = null;

  try {
    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        <CourseCalendarPage
          {...buildCalendarProps({
            classes: [
              {
                id: 1,
                name: '七年级数学班',
                subject: '数学',
                grade: '七年级',
                teacher_name: 'Alice',
              },
              {
                id: 2,
                name: '八年级物理班',
                subject: '物理',
                grade: '八年级',
                teacher_name: 'Bob',
              },
            ],
          })}
        />,
      );
    });

    const [teacherSelect, subjectSelect] = Array.from(domEnvironment.container.querySelectorAll('select')) as HTMLSelectElement[];
    assert.ok(teacherSelect);
    assert.ok(subjectSelect);

    await act(async () => {
      teacherSelect.value = 'Alice';
      teacherSelect.dispatchEvent(new domEnvironment.event('change', { bubbles: true }));
      subjectSelect.value = '物理';
      subjectSelect.dispatchEvent(new domEnvironment.event('change', { bubbles: true }));
    });

    assert.match(domEnvironment.container.textContent ?? '', /暂无可拖拽课程/);
    assert.equal(domEnvironment.container.querySelectorAll('[data-course-class-id]').length, 0);
    assert.match(domEnvironment.container.textContent ?? '', /课程日历/);
  } finally {
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    domEnvironment.cleanup();
  }
});

test('course calendar clears pending drop after canceling adjustment or failed schedule callbacks', async () => {
  const domEnvironment = setupDomEnvironment();
  let root: Root | null = null;
  const classScheduleCalls: number[] = [];
  const customScheduleCalls: number[] = [];
  const loggedErrors: unknown[] = [];
  const originalConsoleError = console.error;
  const classPayload = { 'application/x-course-class-id': '1', 'text/plain': '1' };
  const customPayload = { 'application/x-course-custom-item-id': '201', 'text/plain': '201' };
  console.error = (...args: unknown[]) => {
    loggedErrors.push(args[0]);
  };

  try {
    root = createRoot(domEnvironment.container);
    await act(async () => {
      root?.render(
        <CourseCalendarPage
          {...buildCalendarProps({
            classes: [
              {
                id: 1,
                name: '七年级数学班',
                subject: '数学',
                grade: '七年级',
                teacher_name: 'Alice',
              },
            ],
            customItems: [
              {
                id: 201,
                title: '家长会',
                time_range: '19:00-20:00',
                note: '带资料',
                visibility: 'private',
                created_by: 1,
              },
            ],
            onScheduleClass: () => {
              classScheduleCalls.push(1);
              return Promise.reject(new Error('API unavailable'));
            },
            onScheduleCustomItem: () => {
              customScheduleCalls.push(201);
              return Promise.reject(new Error('API unavailable'));
            },
          })}
        />,
      );
    });

    const slot = domEnvironment.container.querySelector('[data-calendar-slot="2026-03-31-08:00-10:00"]');
    assert.ok(slot);

    await act(async () => {
      dispatchCalendarDrop(domEnvironment, slot, classPayload);
    });
    assert.match(domEnvironment.container.textContent ?? '', /微调启动时间/);

    const cancelButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('取消'));
    assert.ok(cancelButton);
    await act(async () => {
      cancelButton.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
    });
    assert.doesNotMatch(domEnvironment.container.textContent ?? '', /微调启动时间/);

    await act(async () => {
      dispatchCalendarDrop(domEnvironment, slot, classPayload);
    });
    const classConfirmButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('按 08:00 开始 排课'));
    assert.ok(classConfirmButton);
    await act(async () => {
      classConfirmButton.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
      await Promise.resolve();
    });
    assert.equal(classScheduleCalls.length, 1);
    assert.doesNotMatch(domEnvironment.container.textContent ?? '', /微调启动时间/);

    await act(async () => {
      dispatchCalendarDrop(domEnvironment, slot, customPayload);
    });
    const customConfirmButton = Array.from(domEnvironment.container.querySelectorAll('button')).find((button) => button.textContent?.includes('按 08:00 开始 排课'));
    assert.ok(customConfirmButton);
    await act(async () => {
      customConfirmButton.dispatchEvent(new domEnvironment.mouseEvent('click', { bubbles: true }));
      await Promise.resolve();
    });
    assert.equal(customScheduleCalls.length, 1);
    assert.doesNotMatch(domEnvironment.container.textContent ?? '', /微调启动时间/);
    assert.equal(loggedErrors.length, 2);
  } finally {
    console.error = originalConsoleError;
    if (root) {
      await act(async () => {
        root?.unmount();
      });
    }
    domEnvironment.cleanup();
  }
});

test('app loads course calendar schedules separately from review plans', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const calendarEffect = appSource.match(/setCalendarLoading\(true\);[\s\S]*?return \(\) => \{\s*cancelled = true;\s*\};/);

  assert.ok(calendarEffect);
  assert.match(calendarEffect[0], /apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(calendarEffect[0], /apiFetch<\{ items: CourseCalendarScheduleRecord\[] \}>\('\/api\/course-calendar\/schedules/);
  assert.match(calendarEffect[0], /apiFetch<\{ items: CourseCalendarCustomItemRecord\[] \}>\('\/api\/course-calendar\/custom-items/);
  assert.match(calendarEffect[0], /apiFetch<\{ items: CourseCalendarCustomScheduleRecord\[] \}>\('\/api\/course-calendar\/custom-schedules/);
  assert.doesNotMatch(calendarEffect[0], /\/api\/review-plans/);
  assert.match(appSource, /apiFetch<\{ item: CourseCalendarScheduleRecord \}>\('\/api\/course-calendar\/schedules'/);
  assert.match(appSource, /apiFetch<\{ item: CourseCalendarCustomItemRecord \}>\('\/api\/course-calendar\/custom-items'/);
  assert.match(appSource, /apiFetch<\{ item: CourseCalendarCustomScheduleRecord \}>\('\/api\/course-calendar\/custom-schedules'/);
  assert.match(appSource, /window\.alert\(error instanceof Error \? error\.message : '删除自定义事项失败'\)/);
});

test('app exposes a recoverable course calendar list-load failure path', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const calendarEffect = appSource.match(/setCalendarLoading\(true\);[\s\S]*?return \(\) => \{\s*cancelled = true;\s*\};/);
  const calendarRender = appSource.match(/\{activeWorkspacePage === 'calendar' &&[\s\S]*?\{activeWorkspacePage === 'smartWrongQuestions'/);

  assert.ok(calendarEffect);
  assert.ok(calendarRender);
  assert.match(appSource, /const \[calendarError, setCalendarError\] = useState\(''\);/);
  assert.match(calendarEffect[0], /setCalendarError\(''\);/);
  assert.match(
    calendarEffect[0],
    /setCalendarError\(error instanceof Error \? error\.message : '课程日历加载失败，请刷新重试。'\);/,
  );
  assert.match(calendarEffect[0], /setCalendarLoading\(false\);/);
  assert.match(calendarRender[0], /calendarError/);
  assert.match(calendarRender[0], /课程日历加载失败/);
});

test('app shows a user-facing error when course calendar schedule saves fail', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const scheduleClassBlock = appSource.match(/const handleScheduleCalendarClass =[\s\S]*?const handleDeleteCalendarSchedule =/);
  const scheduleCustomBlock = appSource.match(/const handleScheduleCalendarCustomItem =[\s\S]*?const handleDeleteCalendarCustomSchedule =/);

  assert.ok(scheduleClassBlock);
  assert.ok(scheduleCustomBlock);
  assert.match(
    scheduleClassBlock[0],
    /window\.alert\(error instanceof Error \? error\.message : '新增课程排期失败'\)/,
  );
  assert.match(
    scheduleCustomBlock[0],
    /window\.alert\(error instanceof Error \? error\.message : '新增自定义事项排期失败'\)/,
  );
});

test('app shows a user-facing error when course calendar delete or refresh actions fail', () => {
  const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8');
  const deleteScheduleBlock = appSource.match(/const handleDeleteCalendarSchedule =[\s\S]*?const handleCreateCalendarCustomItem =/);
  const deleteCustomItemBlock = appSource.match(/const handleDeleteCalendarCustomItem =[\s\S]*?const handleScheduleCalendarCustomItem =/);
  const deleteCustomScheduleBlock = appSource.match(/const handleDeleteCalendarCustomSchedule =[\s\S]*?const pageTitle:/);

  assert.ok(deleteScheduleBlock);
  assert.ok(deleteCustomItemBlock);
  assert.ok(deleteCustomScheduleBlock);
  assert.match(
    deleteScheduleBlock[0],
    /window\.alert\(error instanceof Error \? error\.message : '删除课程排期失败'\)/,
  );
  assert.match(
    deleteCustomItemBlock[0],
    /window\.alert\(error instanceof Error \? error\.message : '删除自定义事项失败'\)/,
  );
  assert.match(
    deleteCustomScheduleBlock[0],
    /window\.alert\(error instanceof Error \? error\.message : '删除自定义事项排期失败'\)/,
  );
});

test('course calendar source opens time adjustment after dropping a class', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/CourseCalendarPage.tsx'), 'utf8');

  assert.match(source, /setPendingDrop\(\{ itemType: 'class', itemId: classId, date, timeBlock \}\)/);
  assert.match(source, /setPendingDrop\(\{ itemType: 'custom', itemId: customItemId, date, timeBlock \}\)/);
  assert.match(source, /提前 15 分钟/);
  assert.match(source, /提前半小时/);
  assert.match(source, /晚 15 分钟/);
  assert.match(source, /晚半小时/);
  assert.match(source, /自定义微调/);
  assert.match(source, /buildCourseScheduleTimeRange\(pendingDrop\.timeBlock, selectedOffsetMinutes\)/);
  assert.match(source, /const visibleDayCount = 6/);
  assert.match(source, /onPreviousPage\(normalizedPageStepDays\)/);
  assert.match(source, /onNextPage\(normalizedPageStepDays\)/);
  assert.match(source, /gridTemplateColumns: '82px repeat\(6, minmax\(0, 1fr\)\)'/);
  assert.match(source, /overflow-hidden rounded-xl border px-2 py-2 transition/);
  assert.match(source, /h-\[calc\(\(100vh-250px\)\/6\)\] min-h-\[72px\]/);
  assert.match(source, /max-h-full space-y-2 overflow-hidden/);
  assert.match(source, /isCalendarExpanded/);
  assert.match(source, /Maximize2/);
  assert.match(source, /Minimize2/);
  assert.match(source, /const SUBJECT_FILTER_OPTIONS = \['数学', '物理'\]/);
  assert.match(source, /getTeacherOptions\(classes\)/);
  assert.doesNotMatch(source, /setTeacherEditorOpen\(true\)/);
  assert.doesNotMatch(source, /handleAddTeacherOption/);
  assert.doesNotMatch(source, /handleRemoveTeacherOption/);
  assert.match(source, /function getClassGradeRank/);
  assert.match(source, /getClassGradeRank\(b\) - getClassGradeRank\(a\)/);
  assert.match(source, /max-h-\[320px\] space-y-2 overflow-y-auto overscroll-contain/);
  assert.match(source, /max-h-\[320px\] space-y-3 overflow-y-auto overscroll-contain/);
  assert.match(source, /xl:grid-cols-\[minmax\(0,1fr\)_240px\]/);
  assert.match(source, /isCalendarExpanded \? 'overflow-visible' : 'overflow-hidden backdrop-blur-sm'/);
  assert.match(source, /fixed inset-3 z-50 overflow-hidden/);
  assert.doesNotMatch(source, /fixed inset-3 z-50 overflow-y-auto/);
  assert.match(source, /xl:items-end/);
  assert.match(source, /时间板块，快速完成当前页排课。/);
  assert.match(source, /xl:justify-center/);
  assert.match(source, /xl:whitespace-nowrap/);
  assert.match(source, /const canDeleteCustomItem = item\.can_delete \?\? item\.created_by === currentUserId/);
  assert.match(source, /draggable=\{false\}/);
  assert.match(source, /onMouseDown=\{\(event\) => event\.stopPropagation\(\)\}/);
  assert.match(source, /onDeleteCustomItem\(item\.id\)/);
  assert.match(source, /OpenedCourseScheduleModal/);
  assert.match(source, /onOpenSchedule=\{setOpenedCourseSchedule\}/);
  assert.match(source, /visibility: schedule\.visibility \?\? 'private'/);
  assert.match(source, /isOrganizationVisible \? '管理员发布' : '自定义事项'/);
  assert.doesNotMatch(source, /Trash2/);
  assert.match(source, /schedule\.className[\s\S]*schedule\.displayRange/);
  assert.match(source, /lg:hidden/);
  assert.match(source, /lg:block/);
});
