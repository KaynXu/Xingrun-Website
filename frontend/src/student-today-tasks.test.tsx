import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import {
  StudentPortalPage,
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
  pdf_url: '/api/student/pdf/70',
  pdf_download_url: '/api/student/pdf/download/70',
  pdf_filename: '二次函数最值-70.pdf',
  pdf_available: true,
  pdf_page: 2,
  pdf_page_estimated: true,
};

test('student task pdf preview path keeps auth query before page fragment', () => {
  const previewPath = buildStudentTaskPdfPreviewPath(sampleTask, (path) => `${path}?token=abc`);

  assert.equal(previewPath, '/api/student/pdf/70?token=abc#page=2');
});

test('student today tasks content renders a flat task list and pdf-only preview', () => {
  const markup = renderToStaticMarkup(
    <StudentTodayTasksContent
      today="2026-06-03"
      student={
        {
          id: 178,
          name: '袁玲轩',
          class_names: ['华老师小课'],
        }
      }
      loading={false}
      taskLoading={false}
      error=""
      tasks={[sampleTask]}
      activeTask={sampleTask}
      onTaskSelect={() => undefined}
      buildAuthedPath={(path) => path}
    />,
  );

  assert.match(markup, /今日复习/);
  assert.match(markup, /今日任务/);
  assert.match(markup, /二次函数最值/);
  assert.match(markup, /iframe/);
  assert.doesNotMatch(markup, /袁玲轩/);
  assert.doesNotMatch(markup, /华老师小课/);
  assert.doesNotMatch(markup, /学生端/);
  assert.doesNotMatch(markup, /2026-06-03/);
  assert.doesNotMatch(markup, /下载/);
  assert.doesNotMatch(markup, /完成清单/);
  assert.doesNotMatch(markup, /复习目标: 回忆二次函数最值问题的整体框架/);
  assert.doesNotMatch(markup, /1 项/);
  assert.doesNotMatch(markup, /选择学生/);
  assert.doesNotMatch(markup, /2026-06-04/);
});

test('workspace source exposes student portal outside teacher navigation', () => {
  assert.match(appSource, /StudentPortalPage/);
  assert.match(appSource, /window\.location\.pathname\.startsWith\('\/student'\)/);
  assert.match(appSource, /<StudentPortalPage today=\{getTodayIsoDate\(\)\}/);
  assert.doesNotMatch(appSource, /id: 'student-tasks'/);
  assert.doesNotMatch(appSource, /activeWorkspacePage === 'student-tasks'/);
});

test('student portal login page omits the dark intro panel', () => {
  const markup = renderToStaticMarkup(<StudentPortalPage today="2026-06-03" />);

  assert.match(markup, /学生端登录/);
  assert.match(markup, /登录学生端/);
  assert.doesNotMatch(markup, /Xingrun Student/);
  assert.doesNotMatch(markup, /权限/);
  assert.doesNotMatch(markup, /PDF 页面/);
});
