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
      anchorDate="2026-04-01"
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
          date: '2026-03-30',
          time_block: '08:00-10:00',
        },
      ]}
      onPreviousWeek={() => undefined}
      onNextWeek={() => undefined}
      onScheduleClass={() => undefined}
      onDeleteSchedule={() => undefined}
    />,
  );

  assert.match(markup, /课程日历/);
  assert.match(markup, /08:00-10:00/);
  assert.match(markup, /10:00-12:00/);
  assert.match(markup, /13:00-15:00/);
  assert.match(markup, /15:00-17:00/);
  assert.match(markup, /17:00-19:00/);
  assert.match(markup, /19:00-21:00/);
  assert.match(markup, /拖动班级到时间板块/);
  assert.match(markup, /draggable="true"/);
  assert.match(markup, /本周老师负载/);
  assert.doesNotMatch(markup, /待补录课程/);
  assert.match(markup, /班级状态/);
  assert.doesNotMatch(markup, /新增班级/);
  assert.doesNotMatch(markup, /函数入门/);
});

test('course calendar page avoids a nested min-h-screen container inside the workspace shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-04-01"
      classes={[]}
      schedules={[]}
      onPreviousWeek={() => undefined}
      onNextWeek={() => undefined}
      onScheduleClass={() => undefined}
      onDeleteSchedule={() => undefined}
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
  assert.doesNotMatch(calendarEffect[0], /\/api\/review-plans/);
  assert.match(appSource, /apiFetch<\{ item: CourseCalendarScheduleRecord \}>\('\/api\/course-calendar\/schedules'/);
});
