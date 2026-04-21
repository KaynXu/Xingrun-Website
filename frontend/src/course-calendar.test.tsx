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
          start_offset_minutes: 15,
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
  assert.match(markup, /14:00-16:00/);
  assert.match(markup, /16:00-18:00/);
  assert.match(markup, /18:00-20:00/);
  assert.match(markup, /20:00-22:00/);
  assert.match(markup, /08:15 开始/);
  assert.match(markup, /08:15-10:15/);
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

test('course calendar source opens time adjustment after dropping a class', () => {
  const source = readFileSync(resolve(process.cwd(), 'src/CourseCalendarPage.tsx'), 'utf8');

  assert.match(source, /setPendingDrop\(\{ classId, date, timeBlock \}\)/);
  assert.match(source, /提前 15 分钟/);
  assert.match(source, /提前半小时/);
  assert.match(source, /晚 15 分钟/);
  assert.match(source, /晚半小时/);
  assert.match(source, /自定义微调/);
  assert.match(source, /buildCourseScheduleTimeRange\(pendingDrop\.timeBlock, selectedOffsetMinutes\)/);
  assert.match(source, /lg:hidden/);
  assert.match(source, /lg:block/);
});
