import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMarkup } from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup renders reflection and prevention blocks for each wrong question practice item', async () => {
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
        ai_hint: '下次做这类题，先看清运算顺序，算完再检查一步。',
        reason_blank_prompt: '这题我错在 ______，因为我把 ______ 看错了。',
        improvement_summary_prompt: '以后遇到同类题，我会先 ______，做完再 ______。',
      },
    ],
  });

  assert.doesNotMatch(markup, /AI 提示/);
  assert.match(markup, /下次提醒/);
  assert.match(markup, /下次做这类题，先看清运算顺序，算完再检查一步。/);
  assert.match(markup, /把错因补完整/);
  assert.match(markup, /这题我错在/);
  assert.match(markup, /写一写以后怎么做/);
  assert.match(markup, /以后遇到同类题/);
});
