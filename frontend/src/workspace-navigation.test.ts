import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('workspace navigation wires the calendar page instead of the question bank', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'input' \| 'library' \| 'calendar' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);

  assert.doesNotMatch(appSource, /题库浏览/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});
