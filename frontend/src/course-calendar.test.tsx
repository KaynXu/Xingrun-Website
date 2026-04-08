import test from 'node:test';
import assert from 'node:assert/strict';
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
      lessons={[
        {
          id: 101,
          class_id: 1,
          date: '2026-03-30',
          subject: '数学',
          grade: '高一',
          topic: '函数入门',
          summary: '函数概念',
          weak_points: '',
          pdf_path: '',
          created_at: '2026-03-30 10:00:00',
          session: '上午',
          record_status: 'pending',
        },
      ]}
      onPreviousWeek={() => undefined}
      onNextWeek={() => undefined}
    />,
  );

  assert.match(markup, /课程日历/);
  assert.match(markup, /上午/);
  assert.match(markup, /下午/);
  assert.match(markup, /晚间/);
  assert.match(markup, /本周老师负载/);
  assert.match(markup, /待补录课程/);
  assert.match(markup, /班级状态/);
  assert.doesNotMatch(markup, /新增班级/);
});

test('course calendar page avoids a nested min-h-screen container inside the workspace shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-04-01"
      classes={[]}
      lessons={[]}
      onPreviousWeek={() => undefined}
      onNextWeek={() => undefined}
    />,
  );

  assert.doesNotMatch(markup, /min-h-screen/);
});
