import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMarkup } from '../scripts/renderWrongQuestionPracticeSheetPdf.mjs';

test('buildDocumentMarkup renders hint and reflection blocks for each wrong question practice item', async () => {
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
        ai_hint: '先回忆运算顺序，再检查自己是不是跳步了。',
        reason_blank_prompt: '这题我错在 ______，因为我忽略了 ______。',
        improvement_summary_prompt: '以后遇到同类题，我会先 ______，再 ______，避免 ______。',
      },
    ],
  });

  assert.match(markup, /AI 提示/);
  assert.match(markup, /先回忆运算顺序，再检查自己是不是跳步了。/);
  assert.match(markup, /错题挖空/);
  assert.match(markup, /这题我错在/);
  assert.match(markup, /改正与避免总结/);
  assert.match(markup, /以后遇到同类题/);
});
