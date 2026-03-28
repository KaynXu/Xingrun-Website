import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'input' \| 'library' \| 'consultation' \| 'calendar' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'consultation'[\s\S]*label: '咨询记录'/);
  assert.match(appSource, /consultation: '咨询记录'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(appSource, /id: 'calendar'[\s\S]*label: '课程日历'/);
  assert.match(appSource, /calendar: '课程日历'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);

  assert.doesNotMatch(appSource, /题库浏览/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});

test('consultation workspace source uses adaptive layouts instead of horizontal scrolling hacks', () => {
  assert.match(appSource, /mobileNavOpen/);
  assert.match(appSource, /aria-label="打开导航"/);
  assert.match(appSource, /className="fixed inset-0 z-40 lg:hidden"/);
  assert.match(appSource, /className="grid gap-4 p-4 sm:p-5 lg:grid-cols-2 2xl:hidden"/);
  assert.match(appSource, /className="hidden 2xl:block"/);
  assert.match(appSource, /whitespace-nowrap/);
  assert.doesNotMatch(appSource, /overflow-x-auto/);
});
