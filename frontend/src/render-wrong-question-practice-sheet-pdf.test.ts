import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMarkup } from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup renders practice sections as fill-in only and leaves redo lines at the bottom', async () => {
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
        reason_blank_prompt: '先把缺的知识点补出来\n这题我没做好，是因为我漏掉了 ______、没有想清 ______，相关知识点其实是 ______。',
        improvement_summary_prompt: '再想想怎么把知识点补上\n接下来我准备先补 ______，再练 ______，做题前还要提醒自己 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /AI 提示/);
  assert.doesNotMatch(markup, /下次提醒/);
  assert.doesNotMatch(markup, /把错因补完整/);
  assert.doesNotMatch(markup, /写一写以后怎么做/);
  assert.match(markup, /先把缺的知识点补出来/);
  assert.match(markup, /再想想怎么把知识点补上/);
  assert.match(markup, /blank-gap/);
  assert.doesNotMatch(markup, /writing-lines/);
  assert.match(markup, /redo-work-area/);
  assert.match(markup, /redo-line/);
  assert.match(markup, /katex/);
  assert.doesNotMatch(markup, /\\frac/);
  assert.match(markup, /公式预览/);
  assert.match(markup, /预览正常/);
  assert.match(markup, /xr-latex-preview/);
});
