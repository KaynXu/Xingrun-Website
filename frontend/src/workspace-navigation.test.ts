import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');
const fixedGradeValues = ['涓€骞寸骇', '浜屽勾绾?, '涓夊勾绾?, '鍥涘勾绾?, '浜斿勾绾?, '鍏勾绾?, '鍒濅竴', '鍒濅簩', '鍒濅笁', '楂樹竴', '楂樹簩', '楂樹笁'];
const sharedGradeOptionsPattern = new RegExp(
  `const gradeOptions\\s*=\\s*\\[\\s*${fixedGradeValues.map((value) => `'${value}'`).join('\\s*,\\s*')}\\s*\\];`,
);

test('workspace navigation wires consultation and calendar pages into the shell', () => {
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /id: 'consultation'[\s\S]*label: '鍜ㄨ璁板綍'/);
  assert.match(appSource, /consultation: '鍜ㄨ璁板綍'/);
  assert.match(appSource, /activePage === 'consultation'[\s\S]*<ConsultationPage currentUser=\{currentUser\}/);
  assert.match(appSource, /id: 'calendar'[\s\S]*label: '璇剧▼鏃ュ巻'/);
  assert.match(appSource, /calendar: '璇剧▼鏃ュ巻'/);
  assert.match(appSource, /activePage === 'calendar'[\s\S]*<CourseCalendarPage/);

  assert.doesNotMatch(appSource, /棰樺簱娴忚/);
  assert.doesNotMatch(appSource, /QuestionBank/);
});

test('review generation source replaces separate lesson input and library pages with one review-generation workspace page', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock[0], /id: 'review-generation'[\s\S]*label: '澶嶄範鐢熸垚'/);
  assert.doesNotMatch(sidebarBlock[0], /id: 'input'[\s\S]*label: '娣诲姞璇剧▼'/);
  assert.doesNotMatch(sidebarBlock[0], /id: 'library'[\s\S]*label: '璇剧▼鍒楄〃'/);
  assert.match(appSource, /'review-generation': '澶嶄範鐢熸垚'/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage onSuccess=\{handleReviewGenerationSuccess\} currentUser=\{currentUser\} \/>/);
  assert.doesNotMatch(appSource, /activePage === 'input'/);
  assert.doesNotMatch(appSource, /activePage === 'library'/);
});

test('review generation source defaults to 鍘嗗彶鏂囨。 and expands 鐢熸垚澶嶄範鏂囨。 from 鏂板缓澶嶄範鏂囨。 CTA', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess, currentUser \}: \{ onSuccess: \(\) => void; currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const \[composerOpen, setComposerOpen\] = useState\(false\);/);
  assert.match(reviewGenerationBlock[0], /<h3 className=\{workspaceSectionTitleClass\}>鍘嗗彶鏂囨。<\/h3>/);
  assert.match(reviewGenerationBlock[0], /鏂板缓澶嶄範鏂囨。/);
  assert.match(reviewGenerationBlock[0], /鐢熸垚澶嶄範鏂囨。/);
  assert.match(reviewGenerationBlock[0], /<ReviewDocumentHistory refreshToken=\{historyRefreshToken\} \/>/);
});

test('review generation source collapses the inline composer after successful generation', () => {
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess, currentUser \}: \{ onSuccess: \(\) => void; currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.ok(reviewGenerationBlock);
  assert.match(reviewGenerationBlock[0], /const handleComposerSuccess = \(\) => \{\s*setComposerOpen\(false\);\s*onSuccess\(\);\s*\};/);
  assert.doesNotMatch(reviewGenerationBlock[0], /setActivePage\('library'\)/);
});

test('lesson input source keeps subject class and date controls in a fluid grid without fixed width clashes', () => {
  const lessonInputBlock = appSource.match(/const LessonInput = \(\{ onSuccess, currentUser \}: \{ onSuccess: \(\) => void; currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);
  const subjectComboboxBlock = appSource.match(/const SubjectCombobox = \([\s\S]*?\n};/);

  assert.ok(lessonInputBlock);
  assert.ok(subjectComboboxBlock);
  assert.match(lessonInputBlock[0], /className="grid gap-3 md:grid-cols-\[minmax\(0,1\.4fr\)_minmax\(0,1fr\)_minmax\(0,0\.9fr\)\]"/);
  assert.match(lessonInputBlock[0], /className=\{`\$\{workspaceFieldClass\} w-full`\}/);
  assert.doesNotMatch(lessonInputBlock[0], /sm:w-40/);
  assert.doesNotMatch(subjectComboboxBlock[0], /sm:w-32/);
});

test('review generation source requires class selection before generation and carries currentUser into LessonInput', () => {
  const lessonInputBlock = appSource.match(/const LessonInput = \(\{ onSuccess, currentUser \}: \{ onSuccess: \(\) => void; currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);
  const reviewGenerationBlock = appSource.match(/const ReviewGenerationPage = \(\{ onSuccess, currentUser \}: \{ onSuccess: \(\) => void; currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.ok(lessonInputBlock);
  assert.ok(reviewGenerationBlock);
  assert.match(lessonInputBlock[0], /if \(!classId\) \{\s*setError\('请选择班级后再生成复习记录'\);\s*return;\s*\}/);
  assert.match(reviewGenerationBlock[0], /<LessonInput onSuccess=\{handleFormSuccess\} currentUser=\{currentUser\} \/>/);
  assert.match(appSource, /activePage === 'review-generation'[\s\S]*<ReviewGenerationPage onSuccess=\{handleReviewGenerationSuccess\} currentUser=\{currentUser\} \/>/);
});

test('review generation source appends auth token to lesson pdf links', () => {
  assert.match(appSource, /function buildAuthedPath\(path: string\): string \{/);
  assert.match(appSource, /const token = getToken\(\);/);
  assert.match(appSource, /href=\{buildAuthedPath\(`\/api\/pdf\/\$\{lesson\.id\}`\)\}/);
  assert.match(appSource, /href=\{buildAuthedPath\(`\/api\/pdf\/download\/\$\{lesson\.id\}`\)\}/);
});

test('workspace navigation wires smart wrong questions into every authenticated role shell', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(appSource, /function canAccessSmartWrongQuestions\(role: Role\): boolean \{/);
  assert.match(appSource, /return hasStaffAccess\(role\) \|\| role === 'member';/);
  assert.match(sidebarBlock[0], /canAccessSmartWrongQuestions\(currentUser\.role\)[\s\S]*\{ id: 'smartWrongQuestions', icon: Cpu, label: '鏅鸿兘閿欓' \}/);
  assert.match(appSource, /smartWrongQuestions: '鏅鸿兘閿欓'/);
  assert.match(appSource, /activePage === 'smartWrongQuestions'[\s\S]*canAccessSmartWrongQuestions\(currentUser\.role\)[\s\S]*<SmartWrongQuestionsPage currentUser=\{currentUser\} \/>/);
});

test('workspace navigation wires master data mappings into the owner shell only', () => {
  const sidebarBlock = appSource.match(/const menuItems = \[[\s\S]*?\n  \];/);

  assert.ok(sidebarBlock);
  assert.match(appSource, /type Page = 'dashboard' \| 'review-generation' \| 'consultation' \| 'calendar' \| 'smartWrongQuestions' \| 'masterDataMappings' \| 'classes' \| 'accounts' \| 'settings';/);
  assert.match(sidebarBlock[0], /hasOwnerAccess\(currentUser\.role\)[\s\S]*\{ id: 'masterDataMappings', icon: Database, label: '老师与班级匹配' \}/);
  assert.match(appSource, /masterDataMappings: '老师与班级匹配'/);
  assert.match(appSource, /activePage === 'masterDataMappings'[\s\S]*hasOwnerAccess\(currentUser\.role\)[\s\S]*<MasterDataMappingsPage currentUser=\{currentUser\} focusUserId=\{masterDataFocusUserId\} \/>/);
  assert.match(appSource, /activePage === 'accounts'[\s\S]*<ApprovalPage currentUser=\{currentUser\} onStartBinding=\{handleStartMemberBinding\} \/>/);
});

test('workspace navigation source reserves classes management for owner and admin shells', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, /type Page = [^;]*'classes'[^;]*;/);
  assert.match(appSource, /hasStaffAccess\(currentUser\.role\)/);
  assert.match(appSource, /id: 'classes'[\s\S]*label: '鐝骇绠＄悊'/);
  assert.match(appSource, /classes: '鐝骇绠＄悊'/);
  assert.match(appSource, /activePage === 'classes'[\s\S]*<ClassManagementPage currentUser=\{currentUser\}/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<ClassItem\[]>\('\/api\/classes'\)/);
  assert.match(appSource, /const ClassManagementPage = \(\{ currentUser \}: \{ currentUser: CurrentUser \}\) => \{[\s\S]*?apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(classManagementBlock[0], /鍦ㄨ繖閲岀粺涓€绠＄悊 \{currentUser\.organization_name\} 鐨勭彮绾т俊鎭笌璐熻矗鑰佸笀瀹夋帓銆?);
  assert.match(classManagementBlock[0], /璐熻矗鑰佸笀/);
  assert.doesNotMatch(classManagementBlock[0], /鐝骇鑰佸笀鍒嗛厤/);
  assert.doesNotMatch(classManagementBlock[0], /鎴愬憳鐝骇鍒嗛厤/);
  assert.doesNotMatch(appSource, /const ClassManagementPage = [\s\S]*鍗囦负绠＄悊鍛?);
});

test('workspace navigation source exposes explicit super owner hierarchy for account controls', () => {
  assert.match(appSource, /type Role = 'super_owner' \| 'owner' \| 'admin' \| 'member';/);
  assert.match(appSource, /if \(role === 'super_owner'\) return '瓒呯骇绠＄悊鍛?;/);
  assert.match(appSource, /if \(role === 'owner'\) return '鏈烘瀯璐熻矗浜?;/);
  assert.match(appSource, /function hasOwnerAccess\(role: Role\): boolean \{/);
  assert.match(appSource, /function canManageOwnerRole\(role: Role\): boolean \{/);
  assert.match(appSource, /超级管理员可以设置或撤销机构负责人；机构负责人只可切换管理员与普通成员权限/);
});

test('class management source guards selection and refresh during class save delete locks', () => {
  assert.match(appSource, /const classInteractionLocked = saving \|\| deleting;/);
  assert.match(appSource, /const classCardInteractionLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(appSource, /const pageRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(appSource, /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(appSource, /const \[formByClassId, setFormByClassId\] = useState<Record<string, ClassFormValues>>/);
  assert.match(appSource, /const handleToggleExpandedClass = \(classId: number \| 'new'\) => \{\s*if \(classCardInteractionLocked\) \{\s*return;\s*\}\s*setExpandedClassId\(\(current\) => current === classId \? null : classId\);\s*setFormError\(''\);\s*setAssignmentError\(''\);\s*\};/);
  assert.match(appSource, /onClick=\{\(\) => loadPage\(expandedClassId\)\.catch\(\(\) => undefined\)\}\s+disabled=\{pageRefreshLocked\}\s+className=\{workspaceSecondaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleToggleExpandedClass\('new'\)\}\s+disabled=\{classCardInteractionLocked\}\s+className=\{workspacePrimaryButtonClass\}/);
  assert.match(appSource, /onClick=\{\(\) => handleToggleExpandedClass\(item\.id\)\}[\s\S]*disabled=\{classCardInteractionLocked\}/);
});

test('class management source adds a specific grade filter and renders filtered classes only', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[selectedGradeFilter, setSelectedGradeFilter\] = useState<string>\('鍏ㄩ儴'\)/);
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\['鍏ㄩ儴'\s*,\s*\.\.\.gradeOptions\s*\];/);
  assert.match(classManagementBlock[0], /const filteredClasses = classes\.filter\(\(item\) => \{/);
  assert.match(classManagementBlock[0], /if \(selectedGradeFilter === '鍏ㄩ儴'\) \{\s*return true;\s*\}/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.length === 0 \?/);
  assert.match(classManagementBlock[0], /\{filteredClasses\.map\(\(item\) => \{/);
});

test('class management source reuses fixed grade options for form selection', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /const gradeFilterOptions\s*=\s*\[\s*'鍏ㄩ儴'\s*,\s*\.\.\.gradeOptions\s*\];/);
  assert.match(classManagementBlock[0], /<select[\s\S]*?value=\{newClassForm\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\('new', 'grade', e\.target\.value\)\}/);
  assert.match(classManagementBlock[0], /<select[\s\S]*?value=\{formState\.grade\}[\s\S]*?onChange=\{\(e\) => handleFieldChange\(item\.id, 'grade', e\.target\.value\)\}/);
  assert.doesNotMatch(classManagementBlock[0], /<input[\s\S]*?value=\{newClassForm\.grade\}[\s\S]*?placeholder="濡傦細鍏勾绾?/);
  assert.doesNotMatch(classManagementBlock[0], /<input[\s\S]*?value=\{formState\.grade\}[\s\S]*?placeholder="濡傦細鍏勾绾?/);
});

test('class management source validates saves against the shared fixed grade options', () => {
  assert.match(appSource, sharedGradeOptionsPattern);
  assert.match(appSource, /gradeOptions\.includes\(\s*[^)]*grade[^)]*\)/);
  assert.match(appSource, /璇烽€夋嫨骞寸骇/);
});

test('class management source uses class-centric teacher binding instead of user checkbox matrices', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /apiFetch<\{ teacher_bindings: Record<number, number \| null> \}>\('\/api\/classes\/teacher-bindings'\)/);
  assert.match(classManagementBlock[0], /const \[teacherBindingByClassId, setTeacherBindingByClassId\] = useState<Record<number, number \| null>>\(\{\}\);/);
  assert.match(classManagementBlock[0], /const \[teacherBindingSavingByClassId, setTeacherBindingSavingByClassId\] = useState<Record<number, boolean>>\(\{\}\);/);
  assert.match(classManagementBlock[0], /const handleSelectTeacherForClass = async \(classId: number, teacherUserId: number\) => \{/);
  assert.match(classManagementBlock[0], /apiFetch\(`\/api\/classes\/\$\{classId\}\/teacher`, \{/);
  assert.doesNotMatch(classManagementBlock[0], /apiFetch<\{ class_ids: number\[\] \}>\(`\/api\/admin\/users\/\$\{userId\}\/classes`\)/);
  assert.doesNotMatch(classManagementBlock[0], /type="checkbox"/);
  assert.match(classManagementBlock[0], /type="radio"/);
});

test('class management source keeps interaction locks while switching to single-teacher binding saves', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const hasTeacherBindingSavingRows = Object\.values\(teacherBindingSavingByClassId\)\.some\(Boolean\);/);
  assert.match(classManagementBlock[0], /const classCardInteractionLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const pageRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /const assignmentRefreshLocked = classInteractionLocked \|\| hasTeacherBindingSavingRows;/);
  assert.match(classManagementBlock[0], /if \(classInteractionLocked \|\| teacherBindingSavingByClassId\[classId\]\) \{\s*return;\s*\}/);
  assert.match(classManagementBlock[0], /loadPageRequestVersionRef\.current \+= 1;/);
  assert.match(classManagementBlock[0], /if \(classCardInteractionLocked\) \{\s*return;\s*\}[\s\S]*setExpandedClassId\(/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /disabled=\{teacherBindingSaving \|\| classInteractionLocked\}/);
  assert.match(classManagementBlock[0], /disabled=\{assignmentRefreshLocked\}/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*淇濆瓨鐝骇/);
  assert.match(classManagementBlock[0], /disabled=\{classCardInteractionLocked\}[\s\S]*鍒犻櫎褰撳墠鐝骇/);
});

test('class management source keeps refresh reconciliation non-destructive after successful mutations', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(appSource, /type LoadPageResult =/);
  assert.match(classManagementBlock[0], /const preserveStateOnError = options\?\.preserveStateOnError \?\? false;/);
  assert.match(classManagementBlock[0], /return \{ status: 'stale' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'success' \};/);
  assert.match(classManagementBlock[0], /return \{ status: 'refresh-error', error \};/);
  assert.match(classManagementBlock[0], /if \(!preserveStateOnError\) \{[\s\S]*setClasses\(\[\]\);[\s\S]*setUsers\(\[\]\);[\s\S]*setTeacherBindingByClassId\(\{\}\);/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(classId, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /const refreshResult = await loadPage\(created\.id, \{ preserveStateOnError: true \}\);/);
  assert.match(classManagementBlock[0], /if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*鑰佸笀缁戝畾宸蹭繚瀛橈紝浣嗗垪琛ㄥ埛鏂板け璐?);
  assert.match(classManagementBlock[0], /if \(refreshResult\.status === 'refresh-error'\) \{[\s\S]*鐝骇鍜岃礋璐ｈ€佸笀宸蹭繚瀛橈紝浣嗗垪琛ㄥ埛鏂板け璐?);
});

test('class management source adds compact card single-expand state via expandedClassId', () => {
  const classManagementBlock = appSource.match(/const ClassManagementPage = \([\s\S]*?\n};/);

  assert.ok(classManagementBlock);
  assert.match(classManagementBlock[0], /const \[expandedClassId, setExpandedClassId\] = useState<number \| 'new' \| null>/);
  assert.match(classManagementBlock[0], /const isExpanded = expandedClassId === item\.id/);
  assert.match(classManagementBlock[0], /setExpandedClassId\(\(current\) => current === classId \? null : classId\)/);
  assert.match(classManagementBlock[0], /className=\{`\$\{workspaceSoftCardClass\} overflow-hidden p-5`\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\('new'\)\}/);
  assert.match(classManagementBlock[0], /onClick=\{\(\) => handleToggleExpandedClass\(item\.id\)\}/);
  assert.doesNotMatch(classManagementBlock[0], /灞曞紑绠＄悊/);
  assert.doesNotMatch(classManagementBlock[0], /鏀惰捣绠＄悊/);
  assert.doesNotMatch(classManagementBlock[0], /褰撳墠灞曞紑/);
  assert.doesNotMatch(classManagementBlock[0], /姣忔鍙睍寮€涓€涓彮绾у崱鐗囷紝鍦ㄥ崱鐗囧唴閮ㄥ畬鎴愬熀纭€淇℃伅缁存姢鍜岀彮绾ц€佸笀鍒嗛厤銆?);
});

test('class management source guards loadPage responses with a request version ref', () => {
  assert.match(appSource, /const loadPageRequestVersionRef = useRef\(0\);/);
  assert.match(appSource, /const requestVersion = \+\+loadPageRequestVersionRef\.current;/);
  assert.match(appSource, /if \(requestVersion !== loadPageRequestVersionRef\.current\) \{\s*return \{ status: 'stale' \};\s*\}/);
});

test('consultation workspace source uses adaptive layouts instead of horizontal scrolling hacks', () => {
  assert.match(appSource, /mobileNavOpen/);
  assert.match(appSource, /aria-label="鎵撳紑瀵艰埅"/);
  assert.match(appSource, /className="fixed inset-0 z-40 lg:hidden"/);
  assert.match(appSource, /className="grid gap-4 p-4 sm:p-5 lg:grid-cols-2 2xl:hidden"/);
  assert.match(appSource, /className="hidden 2xl:block"/);
  assert.match(appSource, /whitespace-nowrap/);
  assert.doesNotMatch(appSource, /overflow-x-auto/);
});

test('consultation workspace source shows source channel alongside normalized grade-focused metadata', () => {
  assert.match(appSource, /鏉ユ簮娓犻亾/);
  assert.match(appSource, /record\.source_channel \|\| '鏈爣娉ㄦ潵婧愭笭閬?/);
  assert.match(appSource, /record\.consultation_subject \|\| '鏈～鍐欏挩璇㈢鐩?/);
});

test('consultation modal source exposes quick parsing and structured confirmation controls', () => {
  assert.match(appSource, /蹇€熷綍鍏?);
  assert.match(appSource, /鏅鸿兘瑙ｆ瀽/);
  assert.match(appSource, /鏉ユ簮娓犻亾澶囨敞/);
  assert.match(appSource, /apiFetch<ConsultationTeacherOption\[]>\('\/api\/consultation-teachers'\)/);
});

test('consultation workspace source allows admins to edit and delete records and uses the new follow-up status set', () => {
  assert.match(appSource, /const consultationStatusOptions = \['寰呴個绾?, '璺熻繘涓?, '宸叉姤鐝?, '宸插姖閫€'\];/);
  assert.match(appSource, /follow_up_status: '寰呴個绾?,/);
  assert.match(appSource, /function hasStaffAccess\(role: Role\): boolean \{/);
  assert.match(appSource, /\{readOnly && hasStaffAccess\(currentUser\.role\) && \(/);
  assert.match(appSource, /const canManage = hasStaffAccess\(currentUser\.role\);/);
  assert.match(appSource, /\{canManage && \(/);
  assert.match(appSource, /onDelete=\{canManage \? handleDelete : undefined\}/);
});

test('approval page source keeps member role controls separate from class assignment', () => {
  const approvalBlock = appSource.match(/const ApprovalPage = \([\s\S]*?\n\};\n\nconst SettingsPage/);

  assert.ok(approvalBlock);
  assert.match(approvalBlock[0], /鎴愬憳鏉冮檺/);
  assert.match(approvalBlock[0], /apiFetch<UserItem\[]>\('\/api\/admin\/users'\)/);
  assert.match(approvalBlock[0], /`\/api\/admin\/users\/\$\{userId\}\/role`/);
  assert.doesNotMatch(approvalBlock[0], /鎴愬憳鐝骇鍒嗛厤/);
});
