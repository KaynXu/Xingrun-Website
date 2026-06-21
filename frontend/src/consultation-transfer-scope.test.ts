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

test('consultation page exposes member history mode and ownership filters', () => {
  assert.match(pageSource, /consultationScope/);
  assert.match(pageSource, /历史咨询/);
  assert.match(pageSource, /自创咨询/);
  assert.match(pageSource, /咨询转接/);
  assert.match(pageSource, /scope=\$\{consultationScope\}/);
  assert.match(pageSource, /ownership=\$\{consultationOwnership\}/);
  assert.match(pageSource, /currentUser\.role === 'member'/);
});

test('consultation page prioritizes member server-side filter empty state before global empty state', () => {
  assert.match(pageSource, /hasMemberServerFilter/);
  assert.match(pageSource, /当前筛选暂无咨询记录/);

  const memberFilteredEmptyIndex = pageSource.indexOf('hasMemberServerFilter && records.length === 0');
  const globalEmptyIndex = pageSource.indexOf('records.length === 0');

  assert.notEqual(memberFilteredEmptyIndex, -1);
  assert.notEqual(globalEmptyIndex, -1);
  assert.ok(memberFilteredEmptyIndex < globalEmptyIndex);
});

test('consultation page renders member history as a separate view with return action', () => {
  assert.match(pageSource, /isHistoryConsultationView/);
  assert.match(pageSource, /历史咨询档案/);
  assert.match(pageSource, /返回咨询主页/);
  assert.match(pageSource, /setConsultationScope\('current'\)/);
  assert.match(pageSource, /!isHistoryConsultationView && consultationFilterGroups\.map/);
});
