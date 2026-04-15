import test from 'node:test';
import assert from 'node:assert/strict';

import { buildDocumentMarkup } from '../scripts/renderWrongQuestionLibraryPdf.mjs';

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
