import test from 'node:test';
import assert from 'node:assert/strict';

import {
  COURSE_CALENDAR_TIME_BLOCKS,
  assignScheduleCardsToTimeBlocks,
  buildClassStatusRailData,
  getWeekDates,
  getWeekRangeLabel,
  joinClassesAndSchedules,
  summarizePendingRecords,
  summarizeTeacherLoad,
} from './courseCalendarData';

test('course calendar data helpers build an independent six-block schedule from classes', () => {
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

  const schedules = [
    {
      id: 101,
      class_id: 1,
      date: '2026-03-30',
      time_block: '08:00-10:00',
    },
    {
      id: 102,
      class_id: 2,
      date: '2026-03-31',
      time_block: '19:00-21:00',
    },
  ];

  const weekDates = getWeekDates('2026-04-01');

  assert.equal(weekDates.length, 7);
  assert.equal(weekDates[0], '2026-03-30');
  assert.equal(getWeekRangeLabel('2026-04-01'), '2026.03.30 - 2026.04.05');
  assert.equal(COURSE_CALENDAR_TIME_BLOCKS.length, 6);

  const joined = joinClassesAndSchedules(classes, schedules);
  const firstDayCards = joined.filter((card) => card.date === weekDates[0]);
  const secondDayCards = joined.filter((card) => card.date === weekDates[1]);

  const firstDayBlocks = assignScheduleCardsToTimeBlocks(firstDayCards);
  const secondDayBlocks = assignScheduleCardsToTimeBlocks(secondDayCards);

  assert.equal(firstDayBlocks['08:00-10:00'].length, 1);
  assert.equal(secondDayBlocks['19:00-21:00'].length, 1);
  assert.equal(firstDayCards[0].className, '高一数学A班');

  const teacherLoad = summarizeTeacherLoad(joined);
  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.count, 1);

  const pendingRecords = summarizePendingRecords(schedules);
  assert.equal(pendingRecords.length, 0);

  const classStatus = buildClassStatusRailData(classes, schedules);
  assert.equal(classStatus.length, 2);
});

test('teacher load summarizes scheduled classes instead of teacher-owned classes', () => {
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

  const schedules = [
    {
      id: 101,
      class_id: 1,
      date: '2026-03-30',
      time_block: '08:00-10:00',
    },
    {
      id: 102,
      class_id: 2,
      date: '2026-03-31',
      time_block: '19:00-21:00',
    },
  ];

  const joined = joinClassesAndSchedules(classes, schedules);
  const teacherLoad = summarizeTeacherLoad(joined);

  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.count, 1);
  assert.equal(teacherLoad.find((item) => item.teacherName === 'Alice')?.classCount, 1);
});
