import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const modalSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationModal.tsx'), 'utf8');
const statusCardsSource = readFileSync(resolve(process.cwd(), 'src/features/consultation/ConsultationStageStatusCards.tsx'), 'utf8');

test('consultation stage status cards summarize saved process teachers and states', () => {
  assert.match(statusCardsSource, /ConsultationStageStatusCards/);
  assert.match(statusCardsSource, /客服老师/);
  assert.match(statusCardsSource, /负责教师VX/);
  assert.match(statusCardsSource, /沟通教师/);
  assert.match(statusCardsSource, /测试教师/);
  assert.match(statusCardsSource, /试听教师/);
  assert.match(statusCardsSource, /带课教师/);
  assert.match(statusCardsSource, /进班班级/);
  assert.doesNotMatch(statusCardsSource, /label: '客服微信'/);
  assert.doesNotMatch(statusCardsSource, /label: '测试情况'/);
  assert.doesNotMatch(statusCardsSource, /label: '试听情况'/);
  assert.match(statusCardsSource, /CheckCircle2/);
});

test('consultation stage status cards own consistent vertical spacing', () => {
  assert.match(statusCardsSource, /'my-3 grid gap-2 sm:grid-cols-2'/);
  assert.doesNotMatch(modalSource, /<ConsultationStageStatusCards[\s\S]{0,180}className="mt-3"/);
});

test('consultation view and edit modal render the same stage status cards', () => {
  assert.match(modalSource, /import \{ ConsultationStageStatusCards \} from '\.\/ConsultationStageStatusCards';/);
  assert.match(modalSource, /<ConsultationStageStatusCards[\s\S]*section="base"/);
  assert.match(modalSource, /<ConsultationStageStatusCards[\s\S]*section="communication"/);
  assert.match(modalSource, /<ConsultationStageStatusCards[\s\S]*section="trial"/);
  assert.match(modalSource, /<ConsultationStageStatusCards[\s\S]*section="result"/);
});

test('consultation edit status teacher cards are selectable except customer service', () => {
  assert.match(statusCardsSource, /teacherField\?:/);
  assert.match(statusCardsSource, /classField\?: 'success_class_id'/);
  assert.match(statusCardsSource, /onTeacherChange\?:/);
  assert.match(statusCardsSource, /onClassChange\?:/);
  assert.match(statusCardsSource, /teacherOptions\.map/);
  assert.match(statusCardsSource, /客服老师[\s\S]*teacherField: undefined/);
  assert.match(statusCardsSource, /负责教师VX[\s\S]*teacherField: 'teacher_id'/);
  assert.match(statusCardsSource, /沟通教师[\s\S]*teacherField: 'communication_teacher_added'/);
  assert.match(statusCardsSource, /测试教师[\s\S]*teacherField: 'test_teacher'/);
  assert.match(statusCardsSource, /试听教师[\s\S]*teacherField: 'trial_teacher'/);
  assert.match(statusCardsSource, /带课教师[\s\S]*teacherField: 'teaching_teacher'/);
  assert.match(statusCardsSource, /进班班级[\s\S]*classField: 'success_class_id'/);
  assert.match(modalSource, /teacherOptions=\{teacherOptions\}/);
  assert.match(modalSource, /onTeacherChange=\{handleStageStatusTeacherChange\}/);
});

test('consultation result class dropdown follows the selected teaching teacher', () => {
  assert.match(modalSource, /if \(field === 'teaching_teacher'\) \{/);
  assert.match(modalSource, /const nextTeacher = teacherOptions\.find\(\(option\) => option\.display_name === value\);/);
  assert.match(modalSource, /success_class_id: successClassStillMatches \? current\.success_class_id : null/);
  assert.match(modalSource, /const selectedTeachingTeacher = teacherOptions\.find\(\(option\) => option\.display_name === form\.teaching_teacher\);/);
  assert.match(modalSource, /const successClassOptions = selectedTeachingTeacher \? teachingTeacherMatchedClasses : assignableClassOptions;/);
  assert.match(modalSource, /classes=\{successClassOptions\}/);
  assert.match(modalSource, /onClassChange=\{\(classId\) => \{[\s\S]*handleSuccessClassChange\(classId \? String\(classId\) : ''\);[\s\S]*\}\}/);
  assert.match(statusCardsSource, /aria-label=\{`选择\$\{item\.label\}`\}[\s\S]*请选择班级[\s\S]*classes\.map/);
});

test('consultation view modal lets status cards own the base status row without duplicate read-only labels', () => {
  assert.doesNotMatch(modalSource, /<p className=\{compactReadLabelClass\}>客服微信<\/p>/);
  assert.doesNotMatch(modalSource, /<p className=\{compactReadLabelClass\}>教师微信<\/p>/);
  assert.doesNotMatch(modalSource, /<p className=\{compactReadLabelClass\}>咨询教师<\/p>/);
});

test('consultation view modal follows the edit modal section order and compact fields', () => {
  assert.match(modalSource, /sectionStates\.base\), 'min-h-\[14rem\] md:order-1'/);
  assert.match(modalSource, /sectionStates\.trial\), 'min-h-\[14rem\] md:order-2'/);
  assert.match(modalSource, /sectionStates\.communication\), 'min-h-\[14rem\] space-y-2 md:order-3'/);
  assert.match(modalSource, /sectionStates\.result\), 'min-h-\[14rem\] space-y-3 md:order-4'/);
  assert.match(modalSource, /家长微信名[\s\S]*孩子姓名[\s\S]*年级[\s\S]*咨询科目[\s\S]*来源渠道主类[\s\S]*来源渠道备注/);
  assert.match(modalSource, /<p className=\{compactReadLabelClass\}>沟通情况<\/p>[\s\S]*跟进 1[\s\S]*跟进 2[\s\S]*<p className=\{compactReadLabelClass\}>测试情况<\/p>/);
});

test('consultation edit modal keeps quick entry as a compact top bar instead of a separate section card', () => {
  assert.match(modalSource, /lg:grid-cols-2 lg:items-start/);
  assert.match(modalSource, /sm:grid-cols-\[minmax\(13rem,1fr\)_4\.75rem_3\.75rem_auto_auto\] sm:items-center/);
  assert.match(modalSource, /h-10 min-w-0 gap-0 px-1 py-2 text-xs/);
  assert.doesNotMatch(modalSource, /<Cpu size=\{12\} className="absolute left-1\.5" \/>/);
  assert.match(modalSource, /!readOnly && 'hidden'/);
  assert.match(modalSource, /aria-label="快速录入咨询描述"/);
  assert.match(modalSource, /placeholder="快速录入"/);
  assert.doesNotMatch(modalSource, /解析后可确认并保存。/);
  assert.doesNotMatch(modalSource, /先用快速录入整理信息，再确认下方结构化字段。/);
  assert.doesNotMatch(modalSource, /记录详情只读展示，管理员和机构负责人可以在这里进入编辑。/);
  assert.doesNotMatch(modalSource, /编辑弹窗：流程操作先进入草稿，点击底部保存后才会写入记录。/);
  assert.doesNotMatch(modalSource, /当前咨询的完整流程位置。/);
  assert.doesNotMatch(modalSource, /placeholder="快速录入：学生、年级、科目、来源、诉求、接待老师"/);
  assert.doesNotMatch(modalSource, /<h4 className="text-sm font-extrabold text-\[#1F2A44\] dark:text-white">快速录入<\/h4>/);
  assert.doesNotMatch(modalSource, /mb-4 grid gap-3 p-3\.5 lg:grid-cols-\[8rem_minmax\(0,1fr\)_auto\]/);
});

test('consultation edit modal removes customer wechat duplicate control and keeps save icon-only', () => {
  assert.doesNotMatch(modalSource, /客服微信：\{customerWechatDone \? '已添加' : '未添加'\}/);
  assert.doesNotMatch(modalSource, /const customerWechatDone =/);
  assert.match(modalSource, /aria-label="保存咨询记录"/);
  assert.match(modalSource, /<Save size=\{20\} strokeWidth=\{2\.5\} className="shrink-0" \/>/);
  assert.doesNotMatch(modalSource, /<Save size=\{15\} \/>\\s*\{saveButtonLabel\}/);
});

test('consultation edit modal does not render a second responsible teacher selector below status cards', () => {
  assert.doesNotMatch(modalSource, /aria-label="选择负责老师"/);
  assert.doesNotMatch(modalSource, /compactStatusClass\(teacherWechatDone\)/);
  assert.doesNotMatch(modalSource, /const teacherWechatDone =/);
});

test('consultation edit base info does not expose a manual date field', () => {
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>日期<\/span>/);
  assert.doesNotMatch(modalSource, /<input type="date" value=\{form\.date\}/);
});

test('consultation edit base info keeps six detail fields in one paired grid', () => {
  assert.match(
    modalSource,
    /<div className=\{`\$\{compactFieldGridClass\} mt-3`\}>[\s\S]*家长微信名[\s\S]*孩子姓名[\s\S]*年级[\s\S]*咨询科目[\s\S]*来源渠道主类[\s\S]*来源渠道备注[\s\S]*<\/div>\s*<\/section>/,
  );
  const baseInfoFieldsStart = modalSource.indexOf('<span className={compactEditLabelClass}>家长微信名</span>');
  const baseInfoFieldsEnd = modalSource.indexOf('</section>', baseInfoFieldsStart);
  const baseInfoFieldsSource = modalSource.slice(baseInfoFieldsStart, baseInfoFieldsEnd);
  assert.equal((baseInfoFieldsSource.match(/compactFieldGridClass/g) || []).length, 0);
});

test('consultation result panels use ended time wording from the sketch', () => {
  assert.match(modalSource, />结束时间</);
  assert.doesNotMatch(modalSource, />最后更新</);
});

test('consultation edit communication card uses split notes and image grid controls', () => {
  assert.match(modalSource, /沟通情况/);
  assert.match(modalSource, /跟进 1/);
  assert.match(modalSource, /跟进 2/);
  assert.match(modalSource, /测试情况/);
  assert.match(modalSource, /const testImagePages = useMemo/);
  assert.match(modalSource, /const pageSize = 4;/);
  assert.match(modalSource, /snap-x snap-mandatory overflow-x-auto/);
  assert.match(modalSource, /grid h-full min-w-full snap-start grid-cols-2 grid-rows-2 gap-2/);
  assert.match(modalSource, /aria-label="添加测试情况图片"/);
  assert.match(modalSource, /aria-label=\{`删除测试情况图片 \$\{tile\.index \+ 1\}`\}/);
  assert.match(modalSource, /\/api\/consultations\/\$\{record\.id\}\/test-images\/\$\{index\}/);
  assert.match(modalSource, /test_images: current\.test_images\.filter\(\(_, imageIndex\) => imageIndex !== index\)/);
  assert.match(modalSource, /event\.preventDefault\(\);[\s\S]*event\.stopPropagation\(\);[\s\S]*void handleDeleteTestImage\(tile\.index\);/);
  assert.match(modalSource, /disabled=\{deletingTestImageIndex === tile\.index\}/);
  assert.match(modalSource, /已先从当前编辑中移除，点击保存后写入记录。/);
  assert.doesNotMatch(modalSource, />查看图片 \{index \+ 1\}</);
});

test('consultation test images open an in-modal gallery with close and navigation controls', () => {
  assert.match(modalSource, /const \[previewImageIndex, setPreviewImageIndex\] = useState<number \| null>\(null\)/);
  assert.match(modalSource, /aria-label=\{`查看测试情况图片 \$\{index \+ 1\}`\}/);
  assert.match(modalSource, /aria-label=\{`查看测试情况图片 \$\{tile\.index \+ 1\}`\}/);
  assert.match(modalSource, /aria-label="关闭图片预览"/);
  assert.match(modalSource, /aria-label="上一张测试情况图片"/);
  assert.match(modalSource, /aria-label="下一张测试情况图片"/);
  assert.match(modalSource, /event\.key === 'Escape'/);
  assert.match(modalSource, /event\.key === 'ArrowLeft'/);
  assert.match(modalSource, /event\.key === 'ArrowRight'/);
  assert.doesNotMatch(modalSource, /href=\{image\.url\}/);
  assert.doesNotMatch(modalSource, /href=\{tile\.image\.url\}/);
});

test('consultation edit modal places trial before communication in the two-column grid', () => {
  assert.match(modalSource, /sectionStates\.base\), 'min-h-\[14rem\] scroll-mt-6 md:order-1'/);
  assert.match(modalSource, /sectionStates\.trial\), 'min-h-\[14rem\] scroll-mt-6 md:order-2'/);
  assert.match(modalSource, /sectionStates\.communication\), 'min-h-\[14rem\] scroll-mt-6 space-y-2 md:order-3'/);
  assert.match(modalSource, /sectionStates\.result\), 'min-h-\[14rem\] scroll-mt-6 space-y-3 md:order-4'/);
  assert.match(modalSource, /<span className=\{compactEditLabelClass\}>对应班课<\/span>[\s\S]*\{assignableClassOptions\.map\(\(item\) => \(/);
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>班级<\/span>/);
  assert.doesNotMatch(modalSource, /successUsesManualClass/);
});

test('consultation edit cards remove crossed-out detail controls from sketch feedback', () => {
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>是否测试<\/span>/);
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>是否试听<\/span>/);
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>试听教师<\/span>/);
  assert.doesNotMatch(modalSource, /<span className=\{compactEditLabelClass\}>跟进备注（内部）<\/span>/);
});

test('consultation edit communication card stacks follow-up rows and aligns test heading with communication heading', () => {
  assert.match(modalSource, /sectionStates\.communication\), 'min-h-\[14rem\] scroll-mt-6 space-y-2 md:order-3'/);
  assert.match(modalSource, /section="communication"[\s\S]*<div className="mt-2 grid items-stretch gap-2 sm:grid-cols-2">/);
  assert.match(modalSource, /<div className=\{cn\(sectionBoxClass, 'flex h-full flex-col space-y-2'\)\}>/);
  assert.doesNotMatch(modalSource, /lg:grid-cols-\[minmax\(0,1\.05fr\)_minmax\(13rem,0\.95fr\)\]/);
  assert.doesNotMatch(modalSource, /xl:grid-cols-\[minmax\(0,1\.05fr\)_minmax\(15rem,0\.95fr\)\]/);
  assert.match(modalSource, /<label className="flex min-h-0 flex-1 scroll-mt-6 flex-col space-y-2 text-sm">[\s\S]*className=\{`\$\{fieldClass\} min-h-\[8rem\] flex-1 resize-none`\}/);
  assert.match(modalSource, /<div className="grid shrink-0 gap-2">\s*<label className="space-y-2 text-sm">\s*<span className=\{compactEditLabelClass\}>跟进 1<\/span>/);
  assert.doesNotMatch(modalSource, /<div className="grid gap-2 sm:grid-cols-2">\s*<label className="space-y-2 text-sm">\s*<span className=\{compactEditLabelClass\}>跟进 1<\/span>/);
  assert.match(modalSource, /<div ref=\{testSectionRef\} className=\{cn\(sectionBoxClass, 'scroll-mt-6'/);
  assert.match(modalSource, /<div className="flex h-full flex-col space-y-2 text-sm">\s*<span className=\{compactEditLabelClass\}>测试情况<\/span>\s*<div className="min-h-0 flex-1 overflow-hidden">/);
  assert.doesNotMatch(modalSource, /<p className=\{compactEditLabelClass\}>测试情况<\/p>/);
  assert.doesNotMatch(modalSource, /<div className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-3">/);
  assert.doesNotMatch(modalSource, /<div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-3">/);
  assert.doesNotMatch(modalSource, /<h5 className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">测试情况<\/h5>/);
});
