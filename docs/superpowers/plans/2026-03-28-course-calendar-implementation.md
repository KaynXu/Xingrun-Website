# Course Calendar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `题库浏览` workspace tab with a bright Starain-style `课程日历` weekly calendar page, while keeping the first version demo-grade and ready for later linkage to `添加课程`.

**Architecture:** Execute this plan in a fresh worktree created from the current `feat/workspace-shell-starain` branch, because the existing checkout is already dirty with unrelated runtime files and in-progress workspace shell changes. Keep the backend untouched and derive the calendar page entirely from the existing `GET /api/classes` and `GET /api/lessons` responses. Split pure calendar shaping logic into a focused helper module so the new view can be tested with `node:test` without forcing more logic into the already large `frontend/src/App.tsx`.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind v4 utility classes, `motion/react`, Node `node:test`, `tsx`.

---

## File Structure

- Create: `frontend/src/courseCalendarData.ts`
  - Pure functions for week date generation, lesson/class joining, calendar band assignment, teacher load summaries, and status rail data.
- Create: `frontend/src/course-calendar-data.test.ts`
  - `node:test` coverage for the pure calendar shaping helpers.
- Create: `frontend/src/CourseCalendarPage.tsx`
  - Presentational calendar page component and a thin container that consumes `classes` and `lessons`.
- Create: `frontend/src/course-calendar.test.tsx`
  - Static render tests for the page shell, labels, and “no class creation CTA on this page” requirement.
- Create: `frontend/src/workspace-navigation.test.ts`
  - Source-level regression check that the workspace wiring uses `课程日历` and removes the old `题库浏览` tab.
- Modify: `frontend/src/App.tsx`
  - Replace the `questions` page with the new `calendar` page wiring and update the dashboard stat card copy to align with the new navigation.
- Modify: `frontend/package.json`
  - Add a frontend test script so the new and existing `node:test` files can be run consistently.

## Task 1: Create the calendar data model with test coverage

**Files:**
- Create: `frontend/src/courseCalendarData.ts`
- Create: `frontend/src/course-calendar-data.test.ts`
- Modify: `frontend/package.json`
- Test: `frontend/src/course-calendar-data.test.ts`

- [ ] **Step 1: Write the failing data-model test**

Create `frontend/src/course-calendar-data.test.ts`:

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCourseCalendarModel,
  getWeekRangeLabel,
} from './courseCalendarData';

const classes = [
  {
    id: 11,
    name: 'G11-A',
    subject: 'AP Math',
    grade: 'G11',
    teacher_name: 'Alice',
    teacher_email: 'alice@example.com',
    lesson_count: 2,
  },
  {
    id: 22,
    name: 'G10-B',
    subject: 'Physics',
    grade: 'G10',
    teacher_name: 'Luna',
    teacher_email: 'luna@example.com',
    lesson_count: 1,
  },
];

const lessons = [
  {
    id: 101,
    date: '2026-03-30',
    subject: 'AP Math',
    grade: 'G11',
    topic: 'Limits Review',
    summary: '',
    weak_points: '',
    pdf_path: '',
    class_id: 11,
    created_at: '2026-03-30 10:00:00',
  },
  {
    id: 102,
    date: '2026-03-31',
    subject: 'Physics',
    grade: 'G10',
    topic: 'Force Practice',
    summary: '',
    weak_points: '',
    pdf_path: '',
    class_id: 22,
    created_at: '2026-03-31 18:00:00',
  },
];

test('buildCourseCalendarModel builds a 7-day weekly grid with support summaries', () => {
  const model = buildCourseCalendarModel({
    anchorDate: '2026-04-01',
    classes,
    lessons,
  });

  assert.equal(model.days.length, 7);
  assert.equal(model.days[0]?.date, '2026-03-30');
  assert.equal(model.days[0]?.bands.上午.length, 1);
  assert.equal(model.days[1]?.bands.晚间.length, 1);
  assert.equal(model.teacherLoad[0]?.teacherName, 'Alice');
  assert.equal(model.teacherLoad[0]?.count, 1);
  assert.match(model.pendingRecords[0]?.label ?? '', /待补录/);
  assert.equal(model.classStatus.length, 2);
});

test('getWeekRangeLabel formats the visible week for the top control bar', () => {
  assert.equal(getWeekRangeLabel('2026-04-01'), '2026.03.30 - 2026.04.05');
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/course-calendar-data.test.ts
```

Expected: FAIL because `./courseCalendarData` does not exist yet.

- [ ] **Step 3: Add the minimal implementation and test script**

Create `frontend/src/courseCalendarData.ts`:

```ts
export type CalendarBand = '上午' | '下午' | '晚间';

export interface CalendarClassRecord {
  id: number;
  name: string;
  subject: string;
  grade: string;
  teacher_name?: string;
  teacher_email?: string;
  lesson_count?: number;
}

export interface CalendarLessonRecord {
  id: number;
  date: string;
  subject: string;
  grade: string;
  topic: string;
  class_id: number | null;
}

export interface CalendarLessonCard {
  id: number;
  date: string;
  band: CalendarBand;
  title: string;
  teacherName: string;
  className: string;
  subject: string;
}

export interface CourseCalendarModel {
  days: Array<{
    date: string;
    dayLabel: string;
    shortLabel: string;
    bands: Record<CalendarBand, CalendarLessonCard[]>;
  }>;
  teacherLoad: Array<{ teacherName: string; count: number }>;
  pendingRecords: Array<{ label: string }>;
  classStatus: Array<{ className: string; status: string }>;
}

const DAY_LABELS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'] as const;
const BANDS: CalendarBand[] = ['上午', '下午', '晚间'];

function parseIsoDate(dateString: string): Date {
  return new Date(`${dateString}T12:00:00`);
}

function formatIsoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function getMonday(anchorDate: string): Date {
  const base = parseIsoDate(anchorDate);
  const day = base.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(base);
  monday.setDate(base.getDate() + diff);
  return monday;
}

function inferBand(index: number): CalendarBand {
  return BANDS[index % BANDS.length];
}

export function getWeekRangeLabel(anchorDate: string): string {
  const monday = getMonday(anchorDate);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const start = formatIsoDate(monday).replace(/-/g, '.');
  const end = formatIsoDate(sunday).replace(/-/g, '.');
  return `${start} - ${end}`;
}

export function buildCourseCalendarModel(input: {
  anchorDate: string;
  classes: CalendarClassRecord[];
  lessons: CalendarLessonRecord[];
}): CourseCalendarModel {
  const monday = getMonday(input.anchorDate);
  const classesById = new Map(input.classes.map((item) => [item.id, item]));

  const days = Array.from({ length: 7 }, (_, index) => {
    const current = new Date(monday);
    current.setDate(monday.getDate() + index);
    return {
      date: formatIsoDate(current),
      dayLabel: DAY_LABELS[index],
      shortLabel: formatIsoDate(current).slice(5),
      bands: {
        上午: [],
        下午: [],
        晚间: [],
      } satisfies Record<CalendarBand, CalendarLessonCard[]>,
    };
  });

  days.forEach((day, dayIndex) => {
    const dayLessons = input.lessons.filter((lesson) => lesson.date === day.date);
    dayLessons.forEach((lesson, lessonIndex) => {
      const classRecord = lesson.class_id ? classesById.get(lesson.class_id) : undefined;
      const band = inferBand(dayIndex + lessonIndex);
      day.bands[band].push({
        id: lesson.id,
        date: lesson.date,
        band,
        title: lesson.topic || classRecord?.subject || lesson.subject || '课程记录',
        teacherName: classRecord?.teacher_name || '待分配老师',
        className: classRecord?.name || '未关联班级',
        subject: classRecord?.subject || lesson.subject || '课程',
      });
    });
  });

  const teacherLoadMap = new Map<string, number>();
  days.forEach((day) => {
    BANDS.forEach((band) => {
      day.bands[band].forEach((card) => {
        teacherLoadMap.set(card.teacherName, (teacherLoadMap.get(card.teacherName) ?? 0) + 1);
      });
    });
  });

  return {
    days,
    teacherLoad: Array.from(teacherLoadMap.entries())
      .map(([teacherName, count]) => ({ teacherName, count }))
      .sort((left, right) => right.count - left.count),
    pendingRecords: input.classes
      .filter((classRecord) => !input.lessons.some((lesson) => lesson.class_id === classRecord.id))
      .map((classRecord) => ({ label: `${classRecord.subject || classRecord.name} / 待补录` })),
    classStatus: input.classes.map((classRecord) => ({
      className: classRecord.name,
      status: input.lessons.some((lesson) => lesson.class_id === classRecord.id) ? '已同步' : '待处理',
    })),
  };
}
```

Modify `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite --port=3000 --host=0.0.0.0",
    "build": "vite build",
    "preview": "vite preview",
    "clean": "rm -rf dist",
    "lint": "tsc --noEmit",
    "test": "node --import tsx --test src/*.test.ts src/*.test.tsx"
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/course-calendar-data.test.ts
```

Expected: PASS with 2 passing tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/package.json frontend/src/courseCalendarData.ts frontend/src/course-calendar-data.test.ts
git commit -m "test: add course calendar data model coverage"
```

## Task 2: Build the demo-grade `课程日历` page component

**Files:**
- Create: `frontend/src/CourseCalendarPage.tsx`
- Create: `frontend/src/course-calendar.test.tsx`
- Test: `frontend/src/course-calendar.test.tsx`

- [ ] **Step 1: Write the failing page render test**

Create `frontend/src/course-calendar.test.tsx`:

```tsx
import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import { CourseCalendarPage } from './CourseCalendarPage';

const classes = [
  {
    id: 11,
    name: 'G11-A',
    subject: 'AP Math',
    grade: 'G11',
    teacher_name: 'Alice',
    teacher_email: 'alice@example.com',
    lesson_count: 2,
  },
];

const lessons = [
  {
    id: 101,
    date: '2026-03-30',
    subject: 'AP Math',
    grade: 'G11',
    topic: 'Limits Review',
    summary: '',
    weak_points: '',
    pdf_path: '',
    class_id: 11,
    created_at: '2026-03-30 10:00:00',
  },
];

test('course calendar page renders the approved weekly calendar shell', () => {
  const markup = renderToStaticMarkup(
    <CourseCalendarPage
      anchorDate="2026-04-01"
      classes={classes}
      lessons={lessons}
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/course-calendar.test.tsx
```

Expected: FAIL because `./CourseCalendarPage` does not exist yet.

- [ ] **Step 3: Add the page component**

Create `frontend/src/CourseCalendarPage.tsx`:

```tsx
import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

import {
  buildCourseCalendarModel,
  getWeekRangeLabel,
  type CalendarClassRecord,
  type CalendarLessonRecord,
} from './courseCalendarData';

const bands = ['上午', '下午', '晚间'] as const;

export function CourseCalendarPage({
  anchorDate,
  classes,
  lessons,
  onPreviousWeek,
  onNextWeek,
}: {
  anchorDate: string;
  classes: CalendarClassRecord[];
  lessons: CalendarLessonRecord[];
  onPreviousWeek: () => void;
  onNextWeek: () => void;
}) {
  const model = buildCourseCalendarModel({ anchorDate, classes, lessons });

  return (
    <div className="px-6 py-6 md:px-8 md:py-8 xl:px-10 xl:py-10">
      <div className="space-y-6">
        <section className="rounded-[1.75rem] border border-sky-100/90 bg-white/88 p-6 shadow-[0_22px_54px_rgba(47,128,237,0.08)]">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">Calendar View</p>
              <h3 className="mt-3 text-3xl font-bold tracking-tight text-slate-900">课程日历</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">机构视角查看本周课程分布与待补录状态。</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={onPreviousWeek} className="inline-flex items-center gap-2 rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-sky-50">
                <ChevronLeft size={16} />
                上一周
              </button>
              <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-2.5 text-sm font-medium text-slate-700">
                {getWeekRangeLabel(anchorDate)}
              </div>
              <button onClick={onNextWeek} className="inline-flex items-center gap-2 rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-sky-50">
                下一周
                <ChevronRight size={16} />
              </button>
              <div className="rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm text-slate-500">老师筛选</div>
              <div className="rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm text-slate-500">班级筛选</div>
            </div>
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.78fr)]">
          <section className="overflow-hidden rounded-[1.75rem] border border-sky-100/90 bg-white/92 shadow-[0_22px_54px_rgba(47,128,237,0.08)]">
            <div className="grid grid-cols-[88px_repeat(7,minmax(0,1fr))] border-b border-sky-100 bg-slate-50/80">
              <div />
              {model.days.map((day) => (
                <div key={day.date} className="border-l border-sky-100 px-3 py-4 text-center">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-600">{day.dayLabel}</p>
                  <p className="mt-2 text-base font-semibold text-slate-900">{day.shortLabel}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-[88px_repeat(7,minmax(0,1fr))]">
              <div className="grid grid-rows-3 bg-slate-50/70">
                {bands.map((band) => (
                  <div key={band} className="border-t border-sky-100 px-4 py-6 text-sm font-semibold text-slate-500 first:border-t-0">
                    {band}
                  </div>
                ))}
              </div>

              {model.days.map((day) => (
                <div key={day.date} className="grid grid-rows-3 border-l border-sky-100">
                  {bands.map((band) => (
                    <div key={`${day.date}-${band}`} className="min-h-32 border-t border-sky-100 p-3 first:border-t-0">
                      <div className="space-y-2">
                        {day.bands[band].map((card) => (
                          <article key={card.id} className="rounded-2xl border border-sky-100 bg-[linear-gradient(180deg,#ffffff_0%,#eef6ff_100%)] p-3 shadow-sm">
                            <p className="text-sm font-semibold text-slate-900">{card.title}</p>
                            <p className="mt-1 text-xs text-slate-500">{card.teacherName} · {card.className}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-[1.5rem] border border-sky-100 bg-white/88 p-5 shadow-[0_14px_36px_rgba(47,128,237,0.05)]">
              <h4 className="text-lg font-semibold text-slate-900">本周老师负载</h4>
              <div className="mt-4 space-y-2">
                {model.teacherLoad.map((item) => (
                  <div key={item.teacherName} className="rounded-xl bg-sky-50 px-4 py-3 text-sm text-slate-700">
                    {item.teacherName}
                    <span className="float-right text-sky-600">{item.count} 节</span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-[1.5rem] border border-sky-100 bg-white/88 p-5 shadow-[0_14px_36px_rgba(47,128,237,0.05)]">
              <h4 className="text-lg font-semibold text-slate-900">待补录课程</h4>
              <div className="mt-4 space-y-2">
                {model.pendingRecords.map((item) => (
                  <div key={item.label} className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-slate-700">{item.label}</div>
                ))}
              </div>
            </section>

            <section className="rounded-[1.5rem] border border-sky-100 bg-white/88 p-5 shadow-[0_14px_36px_rgba(47,128,237,0.05)]">
              <h4 className="text-lg font-semibold text-slate-900">班级状态</h4>
              <div className="mt-4 space-y-2">
                {model.classStatus.map((item) => (
                  <div key={item.className} className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700">
                    {item.className}
                    <span className="float-right text-slate-500">{item.status}</span>
                  </div>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/course-calendar.test.tsx
```

Expected: PASS with 1 passing test.

- [ ] **Step 5: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/CourseCalendarPage.tsx frontend/src/course-calendar.test.tsx
git commit -m "feat: add course calendar page component"
```

## Task 3: Wire the new page into the workspace and align dashboard copy

**Files:**
- Create: `frontend/src/workspace-navigation.test.ts`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/workspace-navigation.test.ts`

- [ ] **Step 1: Write the failing navigation regression test**

Create `frontend/src/workspace-navigation.test.ts`:

```ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('workspace navigation replaces the old quiz tab with 课程日历', () => {
  const source = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

  assert.match(source, /type Page = 'dashboard' \| 'input' \| 'library' \| 'calendar' \| 'accounts' \| 'settings'/);
  assert.match(source, /label: '课程日历'/);
  assert.match(source, /calendar: '课程日历'/);
  assert.doesNotMatch(source, /questions: '题库浏览'/);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/workspace-navigation.test.ts
```

Expected: FAIL because `App.tsx` still uses the old page name and labels.

- [ ] **Step 3: Wire the page into `App.tsx` and update the dashboard stat**

Modify `frontend/src/App.tsx` with these focused changes:

```tsx
import { CourseCalendarPage } from './CourseCalendarPage';
```

```tsx
type Page = 'dashboard' | 'input' | 'library' | 'calendar' | 'accounts' | 'settings';
```

Expand the class shape so the new page can use teacher metadata from `/api/classes`:

```tsx
interface ClassItem {
  id: number;
  name: string;
  subject: string;
  grade: string;
  teacher_name?: string;
  teacher_email?: string;
  lesson_count?: number;
}
```

Remove the obsolete quiz-only types and component from `App.tsx`:

```tsx
// Delete:
// interface Question { ... }
// interface QuizData { ... }
// const QuestionBank = () => { ... }
```

```tsx
const menuItems = [
  { id: 'dashboard', icon: LayoutDashboard, label: '工作台' },
  { id: 'input', icon: PlusCircle, label: '添加课程' },
  { id: 'library', icon: Library, label: '课程列表' },
  { id: 'calendar', icon: Database, label: '课程日历' },
  ...(currentUser.role === 'owner' ? [{ id: 'accounts', icon: User, label: '账号审批' }] : []),
  { id: 'settings', icon: Settings, label: '系统设置' },
];
```

Replace the dashboard stat card copy:

```tsx
const statCards = [
  { label: '本月课程', value: stats?.month_lessons ?? '—', icon: FileText, color: 'text-blue-500' },
  { label: '累计课程', value: stats?.total_lessons ?? '—', icon: Library, color: 'text-green-500' },
  { label: '已生成 PDF', value: stats?.total_pdfs ?? '—', icon: Download, color: 'text-purple-500' },
  { label: '本周排课', value: recentLessons.length, icon: Database, color: 'text-orange-500' },
];
```

Add local week state near `activePage`:

```tsx
const [calendarAnchorDate, setCalendarAnchorDate] = useState(() => new Date().toISOString().slice(0, 10));
```

Add page title:

```tsx
const pageTitle: Record<Page, string> = {
  dashboard: '工作台',
  input: '添加课程',
  library: '课程列表',
  calendar: '课程日历',
  accounts: '账号审批',
  settings: '系统设置',
};
```

Replace the old question-bank render branch:

```tsx
{activePage === 'calendar' && (
  <CourseCalendarPage
    anchorDate={calendarAnchorDate}
    classes={classes}
    lessons={lessons}
    onPreviousWeek={() => {
      const next = new Date(`${calendarAnchorDate}T12:00:00`);
      next.setDate(next.getDate() - 7);
      setCalendarAnchorDate(next.toISOString().slice(0, 10));
    }}
    onNextWeek={() => {
      const next = new Date(`${calendarAnchorDate}T12:00:00`);
      next.setDate(next.getDate() + 7);
      setCalendarAnchorDate(next.toISOString().slice(0, 10));
    }}
  />
)}
```

Also add the minimal shared data loader in `App.tsx` so the calendar can reuse existing APIs without backend changes:

```tsx
const [classes, setClasses] = useState<ClassItem[]>([]);
const [lessons, setLessons] = useState<Lesson[]>([]);

useEffect(() => {
  if (!token) {
    setClasses([]);
    setLessons([]);
    return;
  }

  Promise.all([apiFetch<ClassItem[]>('/api/classes'), apiFetch<Lesson[]>('/api/lessons')])
    .then(([nextClasses, nextLessons]) => {
      setClasses(nextClasses);
      setLessons(nextLessons);
    })
    .catch(console.error);
}, [token]);
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
node --import tsx --test src/workspace-navigation.test.ts
```

Expected: PASS with 1 passing test.

- [ ] **Step 5: Run the frontend verification suite**

Run:

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary/frontend
npm test
npm run lint
npm run build
```

Expected:

- `npm test`: PASS across existing and new `node:test` files
- `npm run lint`: PASS
- `npm run build`: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
git add frontend/src/App.tsx frontend/src/workspace-navigation.test.ts
git commit -m "feat: replace quiz tab with course calendar"
```

## Self-Review Checklist

- Spec coverage:
  - Tab rename and replacement: covered in Task 3.
  - Weekly calendar page: covered in Task 2.
  - Reuse existing APIs and frontend join logic: covered in Task 1 and Task 3.
  - No `新增班级` on the page: enforced in Task 2 test and component.
  - Dashboard semantic alignment: covered in Task 3.

- Placeholder scan:
  - No `TBD`, `TODO`, or “implement later” markers remain in this plan.

- Type consistency:
  - `calendar` is the only replacement page key used throughout.
  - The helper module uses `CalendarClassRecord` and `CalendarLessonRecord` consistently across the tests and the page component.

## Execution Notes

- Use a fresh worktree before starting Task 1 so the implementation does not collide with the already-dirty checkout.
- Keep commits scoped to each task; do not mix runtime files, `data/*.db`, or unrelated docs into implementation commits.

## Suggested Worktree Command

```bash
cd /Users/ark.mini/Desktop/Xingrun-Review/Xingrun-Summary
mkdir -p .worktrees
git worktree add .worktrees/course-calendar -b feat/course-calendar
```
