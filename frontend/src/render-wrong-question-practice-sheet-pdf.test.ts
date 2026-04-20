import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMarkup } from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup uses ai-generated section titles and avoids a separate reminder block', async () => {
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
        question_text_snapshot: '计算 $2+3\\times4$ 的结果。',
        child_reason_text_snapshot: '我把乘法放到了最后',
        ai_hint: '',
        reason_blank_prompt: '先把真正错因写出来\n我这题错在 ______，因为我当时把 ______ 忽略了。',
        improvement_summary_prompt: '再想想下次怎么避免\n这次如果重来，我会先关注什么？以后我准备怎么提醒自己？',
      },
    ],
  });

  assert.doesNotMatch(markup, /AI 提示/);
  assert.doesNotMatch(markup, /下次提醒/);
  assert.doesNotMatch(markup, /把错因补完整/);
  assert.doesNotMatch(markup, /写一写以后怎么做/);
  assert.match(markup, /先把真正错因写出来/);
  assert.match(markup, /我这题错在/);
  assert.match(markup, /再想想下次怎么避免/);
  assert.match(markup, /这次如果重来，我会先关注什么/);
});
