import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  StudentTodayTasksContent,
  buildStudentTaskPdfPreviewPath,
  type StudentReviewTask,
} from './StudentTodayTasksPage';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

const sampleTask: StudentReviewTask = {
  lesson_id: 70,
  lesson_date: '2026-06-02',
  lesson_subject: '数学',
  lesson_topic: '二次函数最值',
  class_name: '华老师小课',
  review_label: '课后第1天复习 (2026-06-03)',
  estimated_time: '10-20分钟',
  steps: ['复习目标: 回忆二次函数最值问题的整体框架', '完成填空主任务'],
  pdf_url: '/api/pdf/70',
  pdf_download_url: '/api/pdf/download/70',
  pdf_filename: '二次函数最值-70.pdf',
  pdf_available: true,
  pdf_page: 2,
  pdf_page_estimated: true,
};

test('student task pdf preview path keeps auth query before page fragment', () => {
  const previewPath = buildStudentTaskPdfPreviewPath(sampleTask, (path) => `${path}?token=abc`);

  assert.equal(previewPath, '/api/pdf/70?token=abc#page=2');
});

test('student today tasks content renders a polished today-only pdf focused page', () => {
  const markup = renderToStaticMarkup(
    <StudentTodayTasksContent
      today="2026-06-03"
      selectedStudentName="袁玲轩"
      students={[
        {
          id: 178,
          name: '袁玲轩',
          class_names: ['华老师小课'],
        },
      ]}
      selectedStudentId={178}
      loading={false}
      taskLoading={false}
      error=""
      tasks={[sampleTask]}
      activeTask={sampleTask}
      onStudentChange={() => undefined}
      onTaskSelect={() => undefined}
      buildAuthedPath={(path) => path}
    />,
  );

  assert.match(markup, /今日复习/);
  assert.match(markup, /袁玲轩/);
  assert.match(markup, /2026-06-03/);
  assert.match(markup, /二次函数最值/);
  assert.match(markup, /PDF 第 2 页/);
  assert.match(markup, /iframe/);
  assert.match(markup, /复习目标: 回忆二次函数最值问题的整体框架/);
  assert.doesNotMatch(markup, /2026-06-04/);
});

test('workspace source wires student tasks into navigation and page switch', () => {
  assert.match(appSource, /'student-tasks'/);
  assert.match(appSource, /label: '学生端'/);
  assert.match(appSource, /student-tasks': '学生端今日任务'/);
  assert.match(appSource, /activeWorkspacePage === 'student-tasks'[\s\S]*<StudentTodayTasksPage/);
});
