import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const pageSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationPage.tsx'), 'utf8');

test('consultation page distinguishes transferred cards and current responsibility', () => {
  assert.match(pageSource, /getConsultationTransferBadge/);
  assert.match(pageSource, /record\.is_transferred_consultation/);
  assert.match(pageSource, /record\.transfer_marker \|\| '咨询转接'/);
  assert.match(pageSource, /record\.current_responsibility/);
  assert.match(pageSource, /record\.assignment_note/);
});

test('consultation page gates member edit actions by per-record transfer scope', () => {
  assert.match(pageSource, /canEditConsultationRecord/);
  assert.match(pageSource, /record\.can_edit_consultation/);
  assert.match(pageSource, /canEditConsultationStage/);
  assert.match(pageSource, /consultationProcessStages\.indexOf\(record\.assigned_stage\)/);
  assert.match(pageSource, /转接咨询只能编辑当前转接阶段及之后的流程/);
});
