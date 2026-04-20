import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDocumentMarkup,
  resolveChromiumLaunchOptions,
} from '../scripts/renderWrongQuestionLibraryPdf.mjs';

test('buildDocumentMarkup renders child reason and note blocks for each wrong question record', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherTitle: '平台管理员',
    records: [
      {
        created_at: '2026-04-09 10:00:00',
        is_geometry: false,
        question_text: '计算 $2+3\\times4$ 的结果。',
        child_reason_text: '我把乘法放到最后算了',
        cause_note: '运算顺序放错了位置',
      },
    ],
  });

  assert.match(markup, /孩子自述错因/);
  assert.match(markup, /我把乘法放到最后算了/);
  assert.match(markup, /补充备注/);
  assert.match(markup, /运算顺序放错了位置/);
});

test('resolveChromiumLaunchOptions prefers explicit environment paths', async () => {
  const launchOptions = await resolveChromiumLaunchOptions({
    env: {
      XR_PLAYWRIGHT_EXECUTABLE_PATH: '/custom/chrome',
    },
    platform: 'linux',
    pathExists: async () => false,
  });

  assert.deepEqual(launchOptions, {
    executablePath: '/custom/chrome',
    args: ['--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox'],
  });
});

test('resolveChromiumLaunchOptions falls back to common linux chromium paths', async () => {
  const launchOptions = await resolveChromiumLaunchOptions({
    env: {},
    platform: 'linux',
    pathExists: async (candidate) => candidate === '/snap/bin/chromium',
  });

  assert.deepEqual(launchOptions, {
    executablePath: '/snap/bin/chromium',
    args: ['--disable-dev-shm-usage', '--no-sandbox', '--disable-setuid-sandbox'],
  });
});
