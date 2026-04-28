import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { CourseCalendarPage } from './CourseCalendarPage';

test('course calendar page renders the approved weekly dashboard shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-03-31"
      today="2026-04-02"
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
        { id: 201, title: '教研会', time_range: '19:00-20:00', note: '带资料', visibility: 'private' },
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
        },
      ]}
      pageStepDays={6}
      onPageStepDaysChange={() => undefined}
      onPreviousPage={() => undefined}
      onNextPage={() => undefined}
      onScheduleClass={() => undefined}
      onScheduleCustomItem={() => undefined}
      onCreateCustomItem={() => Promise.resolve({ id: 999, title: '事项', time_range: '19:00-20:00', note: '', visibility: 'private' })}
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
  assert.match(markup, /08:15 开始/);
  assert.match(markup, /08:15-10:15/);
  assert.match(markup, /拖动课程到此/);
  assert.match(markup, /添加自定义事项/);
  assert.match(markup, /翻动/);
  assert.doesNotMatch(markup, /第 1 页/);
  assert.doesNotMatch(markup, /天数/);
  assert.match(markup, /draggable="true"/);
  assert.match(markup, /课程卡片/);
  assert.match(markup, /自定义事项/);
  assert.match(markup, /教研会/);
  assert.doesNotMatch(markup, /待补录课程/);
  assert.doesNotMatch(markup, /新增班级/);
  assert.doesNotMatch(markup, /函数入门/);
});

test('course calendar page avoids a nested min-h-screen container inside the workspace shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-03-31"
      today="2026-04-02"
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
      onDeleteSchedule={() => undefined}
      onDeleteCustomSchedule={() => undefined}
    />,
  );

  assert.doesNotMatch(markup, /min-h-screen/);
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
  assert.match(source, /lg:hidden/);
  assert.match(source, /lg:block/);
});
