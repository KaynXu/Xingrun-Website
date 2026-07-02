import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  canMakeReviewPlanVersionCurrent,
  type ReviewPlanDetailRecord,
  type ReviewPlanVersionRecord,
} from './features/review-generation/reviewPlanVersions';

const reviewGenerationSource = readFileSync(new URL('./features/review-generation/ReviewGenerationPage.tsx', import.meta.url), 'utf8');
const reviewPlanRegenerateDialogSource = readFileSync(new URL('./features/review-generation/ReviewPlanRegenerateDialog.tsx', import.meta.url), 'utf8');
const reviewPlanGenerationOptionsSource = readFileSync(new URL('./features/review-generation/reviewPlanGenerationOptions.ts', import.meta.url), 'utf8');
const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const workspacePageContentSource = readFileSync(new URL('./features/navigation/WorkspacePageContent.tsx', import.meta.url), 'utf8');
const lessonInputSource = readFileSync(new URL('./features/review-generation/LessonInput.tsx', import.meta.url), 'utf8');

test('review history source polls review plans while pending lessons exist', () => {
  assert.match(reviewGenerationSource, /const hasPendingLesson = lessons\.some\(isReviewLessonPending\);/);
  assert.match(reviewGenerationSource, /const timer = window\.setInterval\(\(\) => \{\s*void load\(true\);\s*\}, 3000\);/);
  assert.match(reviewGenerationSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review history source normalizes malformed task polling responses', () => {
  assert.match(reviewGenerationSource, /apiFetch<unknown>\('\/api\/review-plans'\)/);
  assert.match(reviewGenerationSource, /const nextLessons = normalizeReviewLessonsResponse\(payload\);/);
  assert.match(reviewGenerationSource, /setLessons\(nextLessons\);/);
  assert.match(reviewGenerationSource, /onLessonsChange\(nextLessons\);/);
});

test('review history source exposes regenerate action and immediate progress feedback', () => {
  assert.match(reviewGenerationSource, /\/api\/review-plans\/\$\{lesson\.id\}\/regenerate/);
  assert.match(reviewGenerationSource, /<ReviewPlanRegenerateDialog/);
  assert.match(reviewPlanRegenerateDialogSource, /重新生成设置/);
  assert.match(reviewPlanRegenerateDialogSource, /<ReviewPlanGenerationOptionsFields/);
  assert.match(reviewGenerationSource, /generation_options: buildGenerationOptionsPayload\(options\)/);
  assert.match(reviewGenerationSource, /openRegenerateDialog\(lesson\)/);
  assert.match(reviewGenerationSource, /onTaskStarted\(lesson\.id, startedAtMs\);/);
  assert.match(reviewGenerationSource, /onFloatingNotice\(\{ type: 'info', text: `《\$\{getLessonTitle\(lesson\)\}》已开始重新生成。` \}\);/);
  assert.match(reviewGenerationSource, /has_version_generating: true/);
  assert.match(reviewGenerationSource, /active_version_status: nextStatus/);
  assert.match(reviewGenerationSource, /title="重新生成"/);
  assert.doesNotMatch(reviewGenerationSource, /确定重新生成《/);
});

test('regenerate dialog keeps source reuse copy terse', () => {
  assert.match(reviewPlanRegenerateDialogSource, /复用原课堂材料/);
  assert.doesNotMatch(reviewPlanRegenerateDialogSource, /重新上传|重新转录|原始逐字稿会/);
});

test('review history opens lightweight version detail view', () => {
  assert.match(reviewGenerationSource, /selectedDetailLessonId/);
  assert.match(reviewGenerationSource, /<ReviewPlanDetailView/);
  assert.match(reviewGenerationSource, /title="详情"/);
  assert.match(reviewGenerationSource, /onBack=\{\(\) => setSelectedDetailLessonId\(null\)\}/);
});

test('review plan detail source fetches versions and can make a ready version current', () => {
  const detailSource = readFileSync(new URL('./features/review-generation/ReviewPlanDetailView.tsx', import.meta.url), 'utf8');
  assert.match(detailSource, /apiFetch<unknown>\(`\/api\/review-plans\/\$\{lessonId\}`\)/);
  assert.match(detailSource, /\/api\/review-plans\/\$\{lessonId\}\/versions\/\$\{version\.id\}\/make-current/);
  assert.match(detailSource, /current_pdf_url/);
  assert.match(detailSource, /版本历史/);
  assert.match(detailSource, /iframe/);
  assert.match(detailSource, /detail\?\.has_version_generating/);
  assert.match(detailSource, /const timer = window\.setInterval\(\(\) => \{\s*void loadDetail\(true\);\s*\}, 3000\);/);
  assert.match(detailSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review plan version helper requires a ready version with an available PDF before make-current', () => {
  const detail: ReviewPlanDetailRecord = {
    id: 12,
    date: '2026-05-02',
    subject: '数学',
    grade: '七年级',
    topic: '整式',
    summary: '',
    weak_points: '',
    created_at: '2026-05-02T12:00:00',
    current_version_id: 31,
    current_version_no: 1,
    current_generated_at: '2026-05-02T12:20:00',
    current_pdf_url: '/api/review-plans/12/versions/31/pdf',
    current_download_url: '/api/review-plans/12/versions/31/download',
    current_status: 'ready',
    has_version_generating: false,
    active_version_status: '',
    latest_generation_error: '',
    review_generation_options: null,
    review_generation_summary: '',
    versions: [],
  };
  const baseVersion: ReviewPlanVersionRecord = {
    id: 32,
    lesson_id: 12,
    version_no: 2,
    status: 'ready',
    pdf_available: true,
    pdf_url: '/api/review-plans/12/versions/32/pdf',
    download_url: '/api/review-plans/12/versions/32/download',
    generation_error: '',
    generation_options: null,
    generation_summary: '',
    created_at: '2026-05-02T12:30:00',
    updated_at: '2026-05-02T12:30:00',
    completed_at: '2026-05-02T12:35:00',
  };

  assert.equal(canMakeReviewPlanVersionCurrent(detail, baseVersion), true);
  assert.equal(canMakeReviewPlanVersionCurrent(detail, { ...baseVersion, id: 31 }), false);
  assert.equal(canMakeReviewPlanVersionCurrent(detail, { ...baseVersion, pdf_available: false }), false);
  assert.equal(canMakeReviewPlanVersionCurrent(detail, { ...baseVersion, status: 'failed' }), false);
});

test('review generation source keeps progress feedback in a dismissible floating dock', () => {
  assert.match(reviewGenerationSource, /function ReviewGenerationTaskDock\(/);
  assert.match(reviewGenerationSource, /createPortal\(dock, document\.body\)/);
  assert.match(reviewGenerationSource, /fixed bottom-5 right-5/);
  assert.match(reviewGenerationSource, /aria-label=\"关闭生成状态浮层\"/);
  assert.match(reviewGenerationSource, /复习计划生成/);
  assert.match(reviewGenerationSource, /dotClassName: 'bg-amber-500'/);
  assert.match(reviewGenerationSource, /return state === 'pending' \|\| state === 'failed';/);
  assert.match(workspacePageContentSource, /return state === 'pending' \|\| state === 'failed';/);
  assert.match(workspacePageContentSource, /reviewTaskDockDismissed/);
  assert.match(workspacePageContentSource, /setReviewTaskDockDismissed\(false\);/);
  assert.match(workspacePageContentSource, /setReviewTaskDockDismissed\(true\);/);
  assert.match(workspacePageContentSource, /const hasReviewDockContent = Boolean\(reviewFloatingNotice\) \|\| hasReviewFloatingTask;/);
  assert.match(workspacePageContentSource, /onReviewTaskDockAvailableChange\(hasReviewDockContent\);/);
  assert.match(workspacePageContentSource, /<ReviewGenerationTaskDock[\s\S]*lessons=\{reviewLatestLessons\}[\s\S]*notice=\{reviewFloatingNotice\}/);
  assert.match(workspacePageContentSource, /setReviewProgressNow\(Date\.now\(\)\);/);
  assert.match(workspacePageContentSource, /activeWorkspacePage === 'review-generation' \? 6000 : 3000/);
  assert.doesNotMatch(reviewGenerationSource, /border-emerald-200 bg-emerald-50/);
  assert.doesNotMatch(reviewGenerationSource, /bg-amber-50(?:\s|["'`/])/);
});

test('review generation source synchronizes member class selection against accessible classes', () => {
  assert.match(lessonInputSource, /function syncMemberScopedClassSelection\(/);
  assert.match(lessonInputSource, /if \(role !== 'member'\) \{\s*return selectedClassId;/);
  assert.match(lessonInputSource, /if \(classes.length === 1\) \{\s*return classes\[0\]\?\.id \?\? null;/);
  assert.match(lessonInputSource, /setClassId\(\(current\) => syncMemberScopedClassSelection\(currentUser\.role, classes, current\)\);/);
  assert.match(appSource, /import \{ WorkspacePageContent \} from '\.\/features\/navigation\/WorkspacePageContent';/);
  assert.match(workspacePageContentSource, /import \{ LessonInput \} from '\.\.\/review-generation\/LessonInput';/);
});

test('review generation validates custom review days before creating or regenerating', () => {
  assert.match(reviewPlanGenerationOptionsSource, /export function parseCustomReviewDays/);
  assert.match(reviewPlanGenerationOptionsSource, /replace\(\/，\/g, ','\)/);
  assert.match(reviewPlanGenerationOptionsSource, /export function getGenerationOptionsValidationError/);
  assert.match(reviewPlanGenerationOptionsSource, /请输入日期点/);
  assert.match(reviewPlanGenerationOptionsSource, /日期点格式错误/);
  assert.match(reviewPlanGenerationOptionsSource, /review_days: parseCustomReviewDays\(value\.customDays\)/);
  assert.match(lessonInputSource, /getGenerationOptionsValidationError\(generationOptions\)/);
  assert.match(lessonInputSource, /setError\(generationOptionsError\);/);
  assert.match(reviewPlanRegenerateDialogSource, /const validationError = getGenerationOptionsValidationError\(value\);/);
  assert.match(reviewPlanRegenerateDialogSource, /disabled=\{submitting \|\| Boolean\(validationError\)\}/);
  assert.match(reviewGenerationSource, /getGenerationOptionsValidationError\(options\)/);
  assert.match(reviewGenerationSource, /onFloatingNotice\(\{ type: 'error', text: generationOptionsError \}\);/);
});

test('review generation schedule mode labels show concrete day counts', () => {
  const optionsFieldsSource = readFileSync(new URL('./features/review-generation/ReviewPlanGenerationOptionsFields.tsx', import.meta.url), 'utf8');

  for (const label of ['5次间隔', '1天集中', '每日连续', '自定义日期']) {
    assert.match(lessonInputSource, new RegExp(label));
    assert.match(optionsFieldsSource, new RegExp(label));
  }
  assert.match(reviewPlanGenerationOptionsSource, /return '1天集中复习';/);
  assert.match(reviewPlanGenerationOptionsSource, /return `每日连续 \$\{value\.dailyCount\} 天`;/);
  assert.match(reviewPlanGenerationOptionsSource, /return `自定义日期 \$\{value\.customDays\.trim\(\) \|\| '未填写'\}`;/);
  assert.match(reviewPlanGenerationOptionsSource, /return '5次间隔复习';/);
  assert.doesNotMatch(lessonInputSource, /label: '压缩'/);
  assert.doesNotMatch(optionsFieldsSource, /label: '压缩'/);
});

test('review generation places generation settings directly under top class metadata', () => {
  const optionsIndex = lessonInputSource.indexOf('title="生成设置"');
  const noClassWarningIndex = lessonInputSource.indexOf('{hasNoAssignableClasses &&');
  const materialSectionIndex = lessonInputSource.indexOf('title="课堂材料"');

  assert.notEqual(optionsIndex, -1);
  assert.ok(optionsIndex < noClassWarningIndex);
  assert.ok(optionsIndex < materialSectionIndex);
});

test('review generation composer uses compact single-column layout', () => {
  assert.match(reviewGenerationSource, /新建复习文档/);
  assert.match(reviewGenerationSource, /max-w-\[720px\]/);
  assert.match(lessonInputSource, /function SectionHeader\(/);
  assert.match(lessonInputSource, /title="基本信息"/);
  assert.match(lessonInputSource, /title="生成设置"/);
  assert.match(lessonInputSource, /title="课堂材料"/);
  assert.match(lessonInputSource, /const \[supplementOpen, setSupplementOpen\] = useState\(false\);/);
  assert.match(lessonInputSource, /title="补充信息" optional/);
  assert.match(lessonInputSource, /formStatusText/);
  assert.match(lessonInputSource, /disabled=\{!canGenerate\}/);
  assert.doesNotMatch(lessonInputSource, /生成前检查/);
  assert.doesNotMatch(lessonInputSource, /xl:grid-cols-\[minmax\(0,1\.35fr\)_280px\]/);
});

test('review generation material upload supports drag and drop', () => {
  assert.match(lessonInputSource, /const \[isMaterialDragActive, setIsMaterialDragActive\] = useState\(false\);/);
  assert.match(lessonInputSource, /const handleMaterialFileDrop = \(event: React\.DragEvent<HTMLDivElement>\)/);
  assert.match(lessonInputSource, /event\.dataTransfer\.dropEffect = 'copy';/);
  assert.match(lessonInputSource, /onDrop=\{handleMaterialFileDrop\}/);
  assert.match(lessonInputSource, /handleMaterialFileSelect\(event\.dataTransfer\.files\?\.\[0\] \?\? null\)/);
  assert.match(lessonInputSource, /onChange=\{\(e\) => handleMaterialFileSelect\(e\.target\.files\?\.\[0\] \?\? null\)\}/);
});
