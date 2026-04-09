import test from 'node:test';
import assert from 'node:assert/strict';

import {
  assignLessonCardsToPeriods,
  buildClassStatusRailData,
  getWeekDates,
  getWeekRangeLabel,
  joinClassesAndLessons,
  summarizePendingRecords,
  summarizeTeacherLoad,
} from './courseCalendarData';

test('course calendar data helpers build a weekly demo view from classes and lessons', () => {
  const classes = [
    {
      id: 1,
      name: '高一数学A班',
      subject: '数学',
      grade: '高一',
      teacher_name: 'Alice',
      teacher_email: 'alice@example.com',
      lesson_count: 1,
    },
    {
      id: 2,
      name: '高一英语B班',
      subject: '英语',
      grade: '高一',
      teacher_name: 'Bob',
      teacher_email: 'bob@example.com',
      lesson_count: 1,
    },
  ];

  const lessons = [
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
    },
    {
      id: 102,
      class_id: 2,
      date: '2026-03-31',
      subject: '英语',
      grade: '高一',
      topic: '阅读理解',
      summary: '篇章阅读',
      weak_points: '',
      pdf_path: '',
      created_at: '2026-03-31 19:00:00',
      session: '晚间',
      record_status: 'pending',
    },
    {
      id: 103,
      class_id: 1,
      date: '2026-04-01',
      subject: '数学',
      grade: '高一',
      topic: '错题复盘',
      summary: '整理失败重试',
      weak_points: '',
      pdf_path: '',
      created_at: '2026-04-01 20:00:00',
      session: '晚间',
      record_status: 'failed',
      generation_error: 'AI 生成失败，请稍后重试',
    },
  ];

  const weekDates = getWeekDates('2026-04-01');

  assert.equal(weekDates.length, 7);
  assert.equal(weekDates[0], '2026-03-30');
  assert.equal(getWeekRangeLabel('2026-04-01'), '2026.03.30 - 2026.04.05');

  const joined = joinClassesAndLessons(classes, lessons);
  const firstDayCards = joined.filter((card) => card.date === weekDates[0]);
  const secondDayCards = joined.filter((card) => card.date === weekDates[1]);
  const failedCard = joined.find((card) => card.id === 103);

  const firstDayPeriods = assignLessonCardsToPeriods(firstDayCards);
  const secondDayPeriods = assignLessonCardsToPeriods(secondDayCards);

  assert.equal(firstDayPeriods.上午.length, 1);
  assert.equal(secondDayPeriods.晚间.length, 1);
  assert.equal(failedCard?.failed, true);
  assert.equal(failedCard?.pending, false);

  const teacherLoad = summarizeTeacherLoad(joined);
  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.count, 2);

  const pendingRecords = summarizePendingRecords(lessons);
  assert.match(pendingRecords[0]?.label ?? '', /待补录/);
  assert.equal(pendingRecords[0]?.count, 1);

  const classStatus = buildClassStatusRailData(classes, lessons);
  assert.equal(classStatus.length, 2);
});

test('teacher load summarizes scheduled lessons instead of teacher-owned classes', () => {
  const classes = [
    {
      id: 1,
      name: '高一数学A班',
      subject: '数学',
      grade: '高一',
      teacher_name: 'Alice',
      teacher_email: 'alice@example.com',
      lesson_count: 1,
    },
    {
      id: 2,
      name: '高一英语B班',
      subject: '英语',
      grade: '高一',
      teacher_name: 'Bob',
      teacher_email: 'bob@example.com',
      lesson_count: 1,
    },
    {
      id: 3,
      name: '高一数学C班',
      subject: '数学',
      grade: '高一',
      teacher_name: 'Alice',
      teacher_email: 'alice@example.com',
      lesson_count: 0,
    },
  ];

  const lessons = [
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
    },
    {
      id: 102,
      class_id: 2,
      date: '2026-03-31',
      subject: '英语',
      grade: '高一',
      topic: '阅读理解',
      summary: '篇章阅读',
      weak_points: '',
      pdf_path: '',
      created_at: '2026-03-31 19:00:00',
      session: '晚间',
      record_status: 'pending',
    },
  ];

  const joined = joinClassesAndLessons(classes, lessons);
  const teacherLoad = summarizeTeacherLoad(joined);

  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.count, 1);
  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.classCount, 1);
});
