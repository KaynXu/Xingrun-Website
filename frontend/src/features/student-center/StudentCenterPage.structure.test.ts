import assert from 'node:assert/strict';
import test from 'node:test';
import { existsSync, readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('../../App.tsx', import.meta.url), 'utf8');
const studentCenterPageUrl = new URL('./StudentCenterPage.tsx', import.meta.url);
const campusOverviewUrl = new URL('./CampusOverview.tsx', import.meta.url);
const classManagementTabUrl = new URL('./ClassManagementTab.tsx', import.meta.url);
const studentManagementTabUrl = new URL('./StudentManagementTab.tsx', import.meta.url);
const classEditorModalUrl = new URL('./ClassEditorModal.tsx', import.meta.url);
const classEditorModalActionsUrl = new URL('./useClassEditorModalActions.ts', import.meta.url);
const classEditorModalStateUrl = new URL('./classEditorModalState.ts', import.meta.url);

test('student center page is extracted from App shell', () => {
  assert.ok(existsSync(studentCenterPageUrl), 'StudentCenterPage.tsx should exist');
  assert.match(appSource, /import \{ StudentCenterPage \} from '\.\/features\/student-center\/StudentCenterPage';/);
  assert.match(appSource, /<StudentCenterPage currentUser=\{currentUser\} classBindingTarget=\{classBindingTarget\} onClearClassBindingTarget=\{\(\) => setClassBindingTarget\(null\)\} \/>/);
  assert.doesNotMatch(appSource, /const ClassManagementPage = \(/);

  const studentCenterSource = readFileSync(studentCenterPageUrl, 'utf8');
  assert.match(studentCenterSource, /export function StudentCenterPage/);
  assert.match(studentCenterSource, /const studentCenterPermissions = getStudentCenterPermissions\(currentUser\);/);
});

test('campus overview is extracted from the student center page', () => {
  assert.ok(existsSync(campusOverviewUrl), 'CampusOverview.tsx should exist');

  const studentCenterSource = readFileSync(studentCenterPageUrl, 'utf8');
  const campusOverviewSource = readFileSync(campusOverviewUrl, 'utf8');

  assert.match(studentCenterSource, /import \{ CampusOverview \} from '\.\/CampusOverview';/);
  assert.match(studentCenterSource, /<CampusOverview[\s\S]*summaryItems=\{classSummaryItems\}/);
  assert.doesNotMatch(studentCenterSource, /<h3 className="text-2xl font-bold text-slate-900 dark:text-white">校区总览<\/h3>/);

  assert.match(campusOverviewSource, /export function CampusOverview/);
  assert.match(campusOverviewSource, /<FloatingOverviewFilter/);
  assert.match(campusOverviewSource, /校区总览说明/);
});

test('class management tab display is extracted from the student center page', () => {
  assert.ok(existsSync(classManagementTabUrl), 'ClassManagementTab.tsx should exist');

  const studentCenterSource = readFileSync(studentCenterPageUrl, 'utf8');
  const classManagementTabSource = readFileSync(classManagementTabUrl, 'utf8');

  assert.match(studentCenterSource, /import \{ ClassManagementTab \} from '\.\/ClassManagementTab';/);
  assert.match(studentCenterSource, /<ClassManagementTab[\s\S]*filteredClasses=\{filteredClasses\}/);
  assert.doesNotMatch(studentCenterSource, /<h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级卡片<\/h4>/);

  assert.match(classManagementTabSource, /export function ClassManagementTab/);
  assert.match(classManagementTabSource, /<FloatingFilterBar/);
  assert.match(classManagementTabSource, /班级卡片/);
});

test('student management tab display is extracted from the student center page', () => {
  assert.ok(existsSync(studentManagementTabUrl), 'StudentManagementTab.tsx should exist');

  const studentCenterSource = readFileSync(studentCenterPageUrl, 'utf8');
  const studentManagementTabSource = readFileSync(studentManagementTabUrl, 'utf8');

  assert.match(studentCenterSource, /import \{ StudentManagementTab \} from '\.\/StudentManagementTab';/);
  assert.match(studentCenterSource, /<StudentManagementTab[\s\S]*filteredStudentRows=\{filteredStudentRows\}/);
  assert.match(studentCenterSource, /<StudentManagementTab[\s\S]*getClassDisplayName=\{getClassDisplayName\}/);
  assert.doesNotMatch(studentCenterSource, /<StudentManagementTab[\s\S]*getClassDisplayName=\{getCurrentClassDisplayName\}/);
  assert.doesNotMatch(studentCenterSource, /<h4 className="text-xl font-semibold text-slate-900 dark:text-white">学员管理<\/h4>/);

  assert.match(studentManagementTabSource, /export function StudentManagementTab/);
  assert.match(studentManagementTabSource, /<FloatingFilterBar/);
  assert.match(studentManagementTabSource, /学员姓名查询/);
});

test('class editor modal display is extracted from the student center page', () => {
  assert.ok(existsSync(classEditorModalUrl), 'ClassEditorModal.tsx should exist');
  assert.ok(existsSync(classEditorModalActionsUrl), 'useClassEditorModalActions.ts should exist');
  assert.ok(existsSync(classEditorModalStateUrl), 'classEditorModalState.ts should exist');

  const studentCenterSource = readFileSync(studentCenterPageUrl, 'utf8');
  const classEditorModalSource = readFileSync(classEditorModalUrl, 'utf8');
  const classEditorModalActionsSource = readFileSync(classEditorModalActionsUrl, 'utf8');

  assert.match(studentCenterSource, /import \{ ClassEditorModal \} from '\.\/ClassEditorModal';/);
  assert.match(studentCenterSource, /import \{ useClassEditorModalActions \} from '\.\/useClassEditorModalActions';/);
  assert.match(studentCenterSource, /import \{ buildClassEditorModalState \} from '\.\/classEditorModalState';/);
  assert.match(studentCenterSource, /const classEditorActions = useClassEditorModalActions\(/);
  assert.match(studentCenterSource, /const classEditorModalState = buildClassEditorModalState\(\{/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*mode=\{classEditorMode\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*locks=\{classEditorLocks\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*errors=\{classEditorErrors\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*options=\{classEditorOptions\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*newClass=\{classEditorNewClass\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*editing=\{classEditorEditing\}/);
  assert.match(studentCenterSource, /<ClassEditorModal[\s\S]*actions=\{classEditorActions\}/);
  assert.doesNotMatch(studentCenterSource, /<ClassEditorModal[\s\S]*locks=\{\{/);
  assert.doesNotMatch(studentCenterSource, /<ClassEditorModal[\s\S]*errors=\{\{/);
  assert.doesNotMatch(studentCenterSource, /<ClassEditorModal[\s\S]*options=\{\{/);
  assert.doesNotMatch(studentCenterSource, /<ClassEditorModal[\s\S]*actions=\{\{/);
  assert.doesNotMatch(studentCenterSource, /<ClassEditorModal[\s\S]*newClassExpanded=\{newClassExpanded\}/);
  assert.doesNotMatch(studentCenterSource, /<AnimatePresence>/);

  assert.match(classEditorModalActionsSource, /export function useClassEditorModalActions/);
  assert.match(classEditorModalActionsSource, /onNewClassBridgeChange/);
  assert.match(classEditorModalActionsSource, /onRefreshAssignment/);
  assert.match(classEditorModalActionsSource, /onSelectTeacherForClass/);
  assert.match(classEditorModalSource, /export type ClassEditorModalMode =/);
  assert.match(classEditorModalSource, /export type ClassEditorModalLocks =/);
  assert.match(classEditorModalSource, /export type ClassEditorModalErrors =/);
  assert.match(classEditorModalSource, /export type ClassEditorModalOptions =/);
  assert.match(classEditorModalSource, /export type ClassEditorNewClassState =/);
  assert.match(classEditorModalSource, /export type ClassEditorEditingState =/);
  assert.match(classEditorModalSource, /export type ClassEditorActions =/);
  assert.match(classEditorModalSource, /export function ClassEditorModal/);
  assert.match(classEditorModalSource, /<AnimatePresence>/);
  assert.match(classEditorModalSource, /家长绑定邀请码/);
  assert.match(classEditorModalSource, /编辑学生/);
});
