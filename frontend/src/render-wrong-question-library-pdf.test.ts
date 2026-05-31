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

test('buildDocumentMarkup renders structured reason analysis blocks', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherTitle: '平台管理员',
    records: [
      {
        created_at: '2026-05-04 11:34:06',
        is_geometry: false,
        question_text: '已知定义在 $[m-4,3m]$ 上的偶函数。',
        child_reason_text: '我当时只说自己没有看懂绝对值和定义域。',
        core_issue: '没有把偶函数定义域关于原点对称和单调区间限制合在一起判断。',
        key_omission: '漏掉了先由定义域对称求出 m，再检查两个自变量是否落在单调区间内。',
        next_step: '下次先写定义域约束，再把比较函数值转成比较绝对值或对应区间上的自变量。',
      },
    ],
  });

  assert.match(markup, /AI 错因分析/);
  assert.match(markup, /核心错因/);
  assert.match(markup, /关键遗漏/);
  assert.match(markup, /后续操作/);
  assert.match(markup, /没有把偶函数定义域关于原点对称/);
  assert.match(markup, /先由定义域对称求出 m/);
  assert.match(markup, /比较函数值转成比较绝对值/);
});

test('buildDocumentMarkup keeps non-empty question blocks for missing notes and geometry records', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherTitle: '平台管理员',
    records: [
      {
        created_at: '2026-04-09 10:00:00',
        is_geometry: false,
        question_text: '向量 ' + String.raw`\overrightarrow{AB}` + ' 长度为 ' + String.raw`\sqrt{16}` + '，且 $x^2+1>0$。',
      },
      {
        created_at: '2026-04-09 10:10:00',
        is_geometry: true,
        image_data_url: 'data:image/png;base64,ZmFrZQ==',
      },
      {
        created_at: '2026-04-09 10:20:00',
        is_geometry: true,
      },
    ],
  });

  assert.equal((markup.match(/class="question-text-block"/g) || []).length, 1);
  assert.equal((markup.match(/class="geometry-card"/g) || []).length, 2);
  assert.match(markup, /向量 AB 长度为 √\(16\)/);
  assert.match(markup, /class="katex"/);
  assert.match(markup, /src="data:image\/png;base64,ZmFrZQ=="/);
  assert.match(markup, /图片暂时无法载入，已保留原图记录。/);
  assert.doesNotMatch(markup, /\\overrightarrow|undefined/);
});

test('buildDocumentMarkup renders generated diagram with its recognized question text', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherTitle: '平台管理员',
    records: [
      {
        created_at: '2026-04-09 10:10:00',
        is_geometry: true,
        question_text: '如图，数轴上点 A 表示 -5，点 B 表示 15。',
        diagram_type: 'number_line',
        image_data_url: 'data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=',
      },
    ],
  });

  assert.match(markup, /如图，数轴上点 A 表示 -5/);
  assert.match(markup, /生成图像/);
  assert.match(markup, /src="data:image\/svg\+xml;base64,PHN2Zz48L3N2Zz4="/);
  assert.doesNotMatch(markup, /保留原图入库/);
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
