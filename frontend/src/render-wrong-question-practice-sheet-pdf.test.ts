import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDocumentMarkup,
  resolveChromiumLaunchOptions,
} from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup renders one merged writing card without extra preview labels', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 1,
        wrong_question_record_id: 'wechat-1',
        is_geometry: false,
        question_text_snapshot: '计算 \\(x^2 + 1\\) 并化简：\\[\\frac{x^2+1}{2}\\]。',
        child_reason_text_snapshot: '我把乘法放到了最后',
        ai_hint: '',
        reason_blank_prompt: '小标题：为什么会漏掉关键知识点？\n这题我没做好，是因为我漏掉了 ______、没有想清 ______，相关知识点其实是 ______。',
        improvement_summary_prompt: '小标题：接下来怎么补这块知识点？\n接下来我准备先补 ______，再练 ______，做题前还要提醒自己 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /AI 提示/);
  assert.doesNotMatch(markup, /公式预览/);
  assert.doesNotMatch(markup, /预览正常/);
  assert.doesNotMatch(markup, /小标题/);
  assert.match(markup, /这题我没做好，是因为我漏掉了/);
  assert.match(markup, /接下来我准备先补/);
  assert.match(markup, /blank-gap/);
  assert.equal((markup.match(/class="writing-card"/g) || []).length, 1);
  assert.match(markup, /redo-work-area/);
  assert.match(markup, /redo-line/);
  assert.match(markup, /重做这题/);
  assert.doesNotMatch(markup, /可选/);
  assert.match(markup, /katex/);
  assert.doesNotMatch(markup, /\\frac/);
  assert.match(markup, /xr-latex-preview/);
});

test('buildDocumentMarkup normalizes literal newline escapes in question and prompt text', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 4,
        wrong_question_record_id: 'wechat-2',
        is_geometry: false,
        question_text_snapshot: '已知函数 $f(x)=(x-1)e^x-ax$。\\n\\n(2) 若 $a > e$，证明 $f(x) \\neq 1$。',
        reason_blank_prompt: '先梳理错因\\n这道题涉及 ______ 知识点。',
        improvement_summary_prompt: '再写你的想法\\n接下来我准备先补 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /\\n\\n\(2\)|\\n这道题|\\n接下来/);
  assert.match(markup, /\(2\) 若/);
  assert.match(markup, /这道题涉及/);
  assert.match(markup, /接下来我准备先补/);
});

test('buildDocumentMarkup keeps non-empty question blocks for bare latex and geometry practice records', async () => {
  const markup = await buildDocumentMarkup({
    studentName: 'Alice',
    className: '六年级 1 班',
    teacherName: '平台管理员',
    title: 'Alice 错题练习',
    items: [
      {
        question_order: 2,
        wrong_question_record_id: 'wechat-2',
        is_geometry: false,
        question_text_snapshot: '向量 ' + String.raw`\overrightarrow{AB}` + ' 长度为 ' + String.raw`\sqrt{16}` + '，且 $x^2+1>0$。',
      },
      {
        question_order: 3,
        wrong_question_record_id: 'wechat-3',
        is_geometry: true,
        image_data_url: 'data:image/png;base64,ZmFrZQ==',
      },
      {
        question_order: 4,
        wrong_question_record_id: 'wechat-4',
        is_geometry: true,
      },
    ],
  });

  assert.equal((markup.match(/class="question-latex-card"/g) || []).length, 1);
  assert.equal((markup.match(/class="geometry-card"/g) || []).length, 2);
  assert.match(markup, /向量 AB 长度为 √\(16\)/);
  assert.match(markup, /class="katex"/);
  assert.match(markup, /src="data:image\/png;base64,ZmFrZQ=="/);
  assert.match(markup, /图片暂时无法载入，已保留原图记录。/);
  assert.doesNotMatch(markup, /\\overrightarrow|undefined/);
});

test('resolveChromiumLaunchOptions adds hardened chromium flags on linux', async () => {
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
