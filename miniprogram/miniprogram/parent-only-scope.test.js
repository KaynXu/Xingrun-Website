const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const MINIPROGRAM_DIR = path.resolve(__dirname);

test('mini program keeps only the parent upload flow pages and deletes legacy page files', () => {
  const appConfigPath = path.join(MINIPROGRAM_DIR, 'app.json');
  const appConfig = JSON.parse(fs.readFileSync(appConfigPath, 'utf8'));

  assert.deepEqual(appConfig.pages, [
    'pages/index/index',
    'pages/parent-home/index',
    'pages/parent-bind/index',
    'pages/parent-upload/index',
    'pages/parent-wrongbook/index',
  ]);

  for (const page of [
    'pages/chat',
    'pages/crop',
    'pages/wrongbook',
  ]) {
    assert.equal(fs.existsSync(path.join(MINIPROGRAM_DIR, page)), false, `${page} should be removed`);
  }
});

test('parent mini program exposes my and photo upload as the only bottom tabs', () => {
  const appConfigPath = path.join(MINIPROGRAM_DIR, 'app.json');
  const appConfig = JSON.parse(fs.readFileSync(appConfigPath, 'utf8'));

  assert.deepEqual(appConfig.tabBar.list.map((item) => ({
    pagePath: item.pagePath,
    text: item.text,
  })), [
    { pagePath: 'pages/parent-home/index', text: '我的' },
    { pagePath: 'pages/parent-upload/index', text: '拍照上传' },
  ]);
});

test('parent home keeps an entry for binding more children after at least one child is already bound', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');

  assert.equal(homeTemplate.includes('绑定更多孩子'), true);
  assert.match(homeTemplate, /bindtap="goBindMore"/);
});

test('parent home is the my section and no longer exposes upload actions inside child cards', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');

  assert.equal(homeTemplate.includes('我的孩子'), true);
  assert.equal(homeTemplate.includes('设置当前上传孩子'), true);
  assert.equal(homeTemplate.includes('上传错题'), false);
  assert.equal(homeTemplate.includes('查看错题本'), true);
});

test('tab page navigation returns to the my section with switchTab', () => {
  const bindSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.js'), 'utf8');
  const bindTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.wxml'), 'utf8');
  const uploadSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.js'), 'utf8');

  assert.match(bindSource, /wx\.switchTab\(\{\s*url:\s*'\/pages\/parent-home\/index'\s*\}\)/);
  assert.equal(bindTemplate.includes('去我的'), true);
  assert.match(uploadSource, /backHome\(\)\s*\{[\s\S]*wx\.switchTab\(\{\s*url:\s*'\/pages\/parent-home\/index'\s*\}\)/);
});

test('active mini program flow avoids optional chaining syntax for better devtools compatibility', () => {
  for (const relativePath of [
    'utils/parentApi.js',
    'pages/index/index.js',
    'pages/parent-bind/index.js',
    'pages/parent-home/index.js',
    'pages/parent-upload/index.js',
  ]) {
    const source = fs.readFileSync(path.join(MINIPROGRAM_DIR, relativePath), 'utf8');
    assert.equal(source.includes('?.'), false, `${relativePath} should not use optional chaining`);
    assert.equal(source.includes('??'), false, `${relativePath} should not use nullish coalescing`);
  }
});

test('mini program serverUrl uses the production HTTPS domain instead of a raw IP', () => {
  const appSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'app.js'), 'utf8');

  assert.match(appSource, /serverUrl:\s*'https:\/\/xingrun\.online'/);
  assert.equal(appSource.includes('http://49.234.185.86:3001'), false);
});

test('parent upload page exposes crop-first multi-image controls', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');

  assert.equal(uploadTemplate.includes('class="panel-card upload-flow-panel"'), true);
  assert.equal(uploadTemplate.includes('class="upload-section upload-image-section"'), true);
  assert.equal(uploadTemplate.includes('class="upload-section upload-box-section"'), true);
  assert.equal(uploadTemplate.includes('class="reason-card upload-section upload-reason-section"'), true);
  assert.equal(uploadTemplate.includes('AI 框选'), false);
  assert.equal(uploadTemplate.includes('补加框'), true);
  assert.equal(uploadTemplate.includes('删除当前'), true);
  assert.equal(uploadTemplate.includes('顺时针旋转'), true);
  assert.equal(uploadTemplate.includes('拍照或从相册里选一张图片'), false);
});

test('parent upload box tools keep stable hierarchy on narrow screens', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const uploadStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxss'), 'utf8');

  const toolRow = uploadTemplate.slice(
    uploadTemplate.indexOf('<view class="box-tool-row">'),
    uploadTemplate.indexOf('</view>', uploadTemplate.indexOf('<view class="box-tool-row">')),
  );
  assert.equal(toolRow.includes('addManualBox'), true);
  assert.equal(toolRow.includes('rotateCurrentImageClockwise'), true);
  assert.equal(toolRow.includes('removeActiveBox'), false);
  assert.match(uploadTemplate, /<button class="danger-btn delete-box-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="removeActiveBox">删除当前题框<\/button>/);
  assert.match(uploadStyles, /\.box-action-group\s*\{[^}]*display:\s*flex;/s);
  assert.match(uploadStyles, /\.box-action-group\s*\{[^}]*flex-direction:\s*column;/s);
  assert.match(uploadStyles, /\.box-tool-row\s*\{[^}]*display:\s*flex;/s);
  assert.match(uploadStyles, /\.box-tool-row\s*\{[^}]*align-items:\s*stretch;/s);
  assert.match(uploadStyles, /\.tool-btn\s*\{[^}]*flex:\s*1/s);
  assert.match(uploadStyles, /\.tool-btn\s*\{[^}]*height:\s*72rpx;/s);
  assert.match(uploadStyles, /\.tool-btn\s*\{[^}]*line-height:\s*72rpx;/s);
  assert.match(uploadStyles, /\.tool-btn\s*\{[^}]*white-space:\s*nowrap;/s);
  assert.match(uploadStyles, /\.box-danger-row\s*\{[^}]*justify-content:\s*flex-end;/s);
  assert.match(uploadStyles, /\.delete-box-btn\s*\{[^}]*white-space:\s*nowrap;/s);
});

test('parent upload image picker button stays readable on narrow screens', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const uploadStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxss'), 'utf8');

  assert.match(uploadTemplate, /<button class="ghost-btn picker-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="chooseImages">/);
  assert.match(uploadStyles, /\.picker-btn\s*\{[^}]*width:\s*100%;/s);
  assert.match(uploadStyles, /\.picker-btn\s*\{[^}]*white-space:\s*nowrap;/s);
  assert.match(uploadStyles, /\.picker-btn\s*\{[^}]*box-sizing:\s*border-box;/s);
});

test('parent upload submit button stays on one line on narrow screens', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const uploadStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxss'), 'utf8');

  assert.equal(uploadTemplate.includes('class="submit-panel"'), true);
  assert.equal(uploadTemplate.includes('class="submit-title"'), true);
  assert.equal(uploadTemplate.includes('class="submit-desc"'), true);
  assert.match(uploadTemplate, /<button class="primary-btn submit-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="submitUpload">统一提交所有错题<\/button>/);
  assert.equal(uploadTemplate.includes('loading="{{submitting}}"'), false);
  assert.match(uploadStyles, /\.bottom-action-bar\s*\{[^}]*padding:\s*0 30rpx calc\(30rpx \+ env\(safe-area-inset-bottom\)\);/s);
  assert.match(uploadStyles, /\.submit-panel\s*\{[^}]*display:\s*flex;/s);
  assert.match(uploadStyles, /\.submit-panel\s*\{[^}]*flex-direction:\s*column;/s);
  assert.match(uploadStyles, /\.submit-btn\s*\{[^}]*width:\s*100%;/s);
  assert.match(uploadStyles, /\.submit-btn\s*\{[^}]*white-space:\s*nowrap;/s);
  assert.match(uploadStyles, /\.submit-btn\s*\{[^}]*box-sizing:\s*border-box;/s);
  assert.match(uploadStyles, /\.submit-title\s*\{[^}]*white-space:\s*nowrap;/s);
  assert.match(uploadStyles, /\.submit-desc\s*\{[^}]*word-break:\s*break-all;/s);
});

test('parent upload controls that mutate the draft are disabled during submission stages', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');

  assert.match(uploadTemplate, /<button class="ghost-btn picker-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="chooseImages">/);
  assert.match(uploadTemplate, /<button class="ghost-btn tool-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="addManualBox">补加框<\/button>/);
  assert.match(uploadTemplate, /<button class="danger-btn delete-box-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="removeActiveBox">删除当前题框<\/button>/);
  assert.match(uploadTemplate, /<button class="ghost-btn tool-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="rotateCurrentImageClockwise">顺时针旋转<\/button>/);
  assert.match(uploadTemplate, /<button[^>]*disabled="{{submitting \|\| cropExporting}}"[^>]*bindtap="switchActiveBoxReasonMode"[\s\S]*文字输入[\s\S]*<\/button>/);
  assert.match(uploadTemplate, /<button[^>]*disabled="{{submitting \|\| cropExporting}}"[^>]*bindtap="switchActiveBoxReasonMode"[\s\S]*语音说明[\s\S]*<\/button>/);
  assert.match(uploadTemplate, /<button class="ghost-btn voice-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="toggleActiveBoxVoiceRecording">/);
  assert.match(uploadTemplate, /<button class="primary-btn submit-btn" disabled="{{submitting \|\| cropExporting}}" bindtap="submitUpload">统一提交所有错题<\/button>/);
});

test('parent upload voice mode prompts children to explain structured reasons', () => {
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');

  assert.match(uploadTemplate, /讲清这题的核心错因/);
  assert.match(uploadTemplate, /说出自己漏掉的条件、定义或检查步骤/);
  assert.match(uploadTemplate, /下次做这类题准备先做什么/);
});

test('parent wrongbook page exposes question text and a pdf entry button', () => {
  const wrongbookSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.js'), 'utf8');
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');

  assert.equal(wrongbookSource.includes('fetchChildWrongQuestionLibrary'), true);
  assert.equal(wrongbookSource.includes('normalizeWrongQuestionLatexPreviewText'), true);
  assert.equal(wrongbookTemplate.includes('查看 PDF'), true);
  assert.equal(wrongbookTemplate.includes('item.questionPreviewText'), true);
});

test('parent wrongbook page uses a finished learning-record hierarchy', () => {
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');
  const wrongbookStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxss'), 'utf8');

  assert.match(wrongbookTemplate, /class="hero-card wrongbook-hero"/);
  assert.match(wrongbookTemplate, /class="hero-badge">星润错题本<\/text>/);
  assert.match(wrongbookTemplate, /class="hero-stat-row"/);
  assert.match(wrongbookTemplate, /class="library-state-tag/);
  assert.match(wrongbookTemplate, /class="library-actions"/);
  assert.match(wrongbookTemplate, /class="primary-btn library-btn"[^>]*wx:if="{{libraryPdfReady}}"/);
  assert.match(wrongbookTemplate, /class="ghost-btn library-btn library-btn-pending"[^>]*wx:else/);
  assert.match(wrongbookTemplate, /class="panel-card filter-panel"/);
  assert.match(wrongbookTemplate, /class="item-card-head"/);
  assert.match(wrongbookTemplate, /class="item-section-label">题目预览<\/text>/);
  assert.match(wrongbookTemplate, /class="item-section-label">错因简述<\/text>/);
  assert.match(wrongbookTemplate, /class="item-status-card /);
  assert.match(wrongbookTemplate, /class="state-card loading-card"/);
  assert.match(wrongbookTemplate, /class="state-card empty-card"/);
  assert.match(wrongbookTemplate, /class="ghost-btn state-action-btn" bindtap="onShow">重新加载<\/button>/);

  assert.match(wrongbookStyles, /\.wrongbook-hero\s*\{[^}]*display:\s*flex;/s);
  assert.match(wrongbookStyles, /\.hero-stat-row\s*\{[^}]*flex-wrap:\s*wrap;/s);
  assert.match(wrongbookStyles, /\.library-actions\s*\{[^}]*flex-direction:\s*column;/s);
  assert.match(wrongbookStyles, /\.library-btn-pending\s*\{[^}]*background:\s*#eef5ff;/s);
  assert.match(wrongbookStyles, /\.filter-panel\s*\{[^}]*padding:\s*24rpx;/s);
  assert.match(wrongbookStyles, /\.item-card\s*\{[^}]*flex-direction:\s*column;/s);
  assert.match(wrongbookStyles, /\.item-section\s*\{[^}]*min-width:\s*0;/s);
  assert.match(wrongbookStyles, /\.item-section-label\s*\{[^}]*letter-spacing:\s*0;/s);
  assert.match(wrongbookStyles, /\.item-status-card\s*\{[^}]*white-space:\s*pre-wrap;/s);
});

test('parent pages use unified state card anatomy for non-happy paths', () => {
  const appStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'app.wxss'), 'utf8');
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');
  const bindTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.wxml'), 'utf8');
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');

  assert.match(appStyles, /\.state-marker\s*\{[^}]*border-radius:\s*999rpx;/s);
  assert.match(appStyles, /\.state-marker-loading\s*\{[^}]*background:\s*#e9f5ff;/s);
  assert.match(appStyles, /\.state-marker-empty\s*\{[^}]*background:\s*#e9f5ff;/s);
  assert.match(appStyles, /\.state-marker-processing\s*\{[^}]*background:\s*#fff7e6;/s);
  assert.match(appStyles, /\.state-marker-success\s*\{[^}]*background:\s*#e8faf0;/s);
  assert.match(appStyles, /\.state-marker-error\s*\{[^}]*background:\s*#fff1f0;/s);

  assert.match(homeTemplate, /class="state-card loading-card"[\s\S]*class="state-marker state-marker-loading"/);
  assert.match(homeTemplate, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  assert.match(homeTemplate, /class="ghost-btn state-action-btn" bindtap="onShow">重新加载<\/button>/);
  assert.match(homeTemplate, /class="state-card empty-card"[\s\S]*class="state-marker state-marker-empty"/);

  assert.match(bindTemplate, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  assert.match(bindTemplate, /class="state-card empty-card empty-student-card"[\s\S]*class="state-marker state-marker-empty"/);

  assert.match(uploadTemplate, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  assert.match(uploadTemplate, /wx:if="\{\{uploadStageText && !successTaskIds\.length\}\}" class="state-card upload-stage upload-progress-card/);
  assert.match(uploadTemplate, /class="state-marker {{uploadStage === 'failed' \|\| uploadStage === 'partial_failed' \? 'state-marker-error' : uploadStage === 'ready' \? 'state-marker-success' : 'state-marker-processing'}}"/);
  assert.match(uploadTemplate, /class="state-card upload-result-card/);
  assert.match(uploadTemplate, /class="state-marker {{uploadTaskSummary.state === 'failed' \|\| uploadTaskSummary.state === 'partial_failed' \? 'state-marker-error' : uploadTaskSummary.state === 'ready' \? 'state-marker-success' : 'state-marker-processing'}}"/);

  assert.match(wrongbookTemplate, /class="state-card upload-status-card/);
  assert.match(wrongbookTemplate, /class="state-marker {{uploadTaskSummary.state === 'failed' \|\| uploadTaskSummary.state === 'partial_failed' \? 'state-marker-error' : 'state-marker-processing'}}"/);
  assert.match(wrongbookTemplate, /class="state-card loading-card"[\s\S]*class="state-marker state-marker-loading"/);
  assert.match(wrongbookTemplate, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  assert.match(wrongbookTemplate, /class="state-card empty-card"[\s\S]*class="state-marker state-marker-empty"/);
  assert.match(wrongbookTemplate, /class="item-status-card {{item.recognitionStatus === 'failed' \? 'item-status-error' : 'item-status-processing'}}"[\s\S]*class="state-marker item-status-marker {{item.recognitionStatus === 'failed' \? 'state-marker-error' : 'state-marker-processing'}}"/);
});

test('parent upload and wrongbook pages expose primary topic category controls', () => {
  const uploadSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.js'), 'utf8');
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const wrongbookSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.js'), 'utf8');
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');

  assert.equal(uploadSource.includes('topicCategoryOptions'), true);
  assert.equal(uploadSource.includes('showPrimaryTopicCategory'), true);
  assert.equal(uploadTemplate.includes('专题分类'), true);
  assert.match(uploadTemplate, /wx:if="{{showPrimaryTopicCategory}}"[\s\S]*专题分类/);
  assert.equal(uploadTemplate.includes('handleActiveBoxTopicChange'), true);
  assert.equal(wrongbookSource.includes('updateChildWrongQuestionTopicCategory'), true);
  assert.equal(wrongbookSource.includes('topicSummaries'), true);
  assert.equal(wrongbookSource.includes('showPrimaryTopicCategory'), true);
  assert.equal(wrongbookTemplate.includes('专题'), true);
  assert.match(wrongbookTemplate, /wx:if="{{showPrimaryTopicCategory}}"[\s\S]*专题筛选/);
  assert.match(wrongbookTemplate, /wx:if="{{showPrimaryTopicCategory}}"[\s\S]*修改专题/);
  assert.equal(wrongbookTemplate.includes('bindtap="saveTopicCategory"'), true);
});

test('parent mini program pages keep action areas stable for narrow phone screens', () => {
  const homeStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxss'), 'utf8');
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');
  const bindStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.wxss'), 'utf8');
  const wrongbookStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxss'), 'utf8');
  const assertRuleIncludes = (styles, selector, declaration) => {
    assert.equal(
      styles
        .split('}')
        .some((rule) => {
          const [selectors, body = ''] = rule.split('{');
          return selectors.includes(selector) && body.includes(declaration);
        }),
      true,
      `${selector} should include ${declaration}`,
    );
  };

  assert.equal(homeTemplate.includes('上传后可在错题本查看整理进度。'), false);
  assert.match(homeTemplate, /class="binding-info"[\s\S]*class="binding-actions"/);
  assertRuleIncludes(homeStyles, '.binding-card', 'flex-direction: column;');
  assertRuleIncludes(homeStyles, '.binding-card', 'align-items: stretch;');
  assertRuleIncludes(homeStyles, '.binding-info', 'flex: 1;');
  assertRuleIncludes(homeStyles, '.binding-actions', 'width: 100%;');
  assertRuleIncludes(homeStyles, '.mini-btn', 'width: 100%;');
  assertRuleIncludes(homeStyles, '.mini-btn', 'white-space: nowrap;');

  assertRuleIncludes(bindStyles, '.student-card', 'flex-direction: column;');
  assertRuleIncludes(bindStyles, '.section-head', 'flex-direction: column;');
  assertRuleIncludes(bindStyles, '.mini-btn', 'width: 100%;');
  assertRuleIncludes(bindStyles, '.mini-btn', 'white-space: nowrap;');

  assertRuleIncludes(wrongbookStyles, '.library-card', 'flex-direction: column;');
  assertRuleIncludes(wrongbookStyles, '.library-btn', 'width: 100%;');
  assertRuleIncludes(wrongbookStyles, '.library-btn', 'white-space: nowrap;');
});

test('parent mini program pages include WeChat narrow runtime guardrails', () => {
  const appStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'app.wxss'), 'utf8');
  const uploadStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxss'), 'utf8');

  const assertRuleIncludes = (styles, selector, declaration) => {
    assert.equal(
      styles
        .split('}')
        .some((rule) => {
          const [selectors, body = ''] = rule.split('{');
          return selectors.includes(selector) && body.includes(declaration);
        }),
      true,
      `${selector} should include ${declaration}`,
    );
  };

  assertRuleIncludes(appStyles, 'page', 'max-width: 100vw;');
  assertRuleIncludes(appStyles, 'page', 'overflow-x: hidden;');
  assertRuleIncludes(appStyles, '.parent-page', 'max-width: 100vw;');
  assertRuleIncludes(appStyles, '.parent-page', 'padding-bottom: calc(28rpx + constant(safe-area-inset-bottom));');
  assertRuleIncludes(appStyles, '.parent-page', 'padding-bottom: calc(28rpx + env(safe-area-inset-bottom));');
  assertRuleIncludes(appStyles, '.wrongbook-page', 'max-width: 100vw;');
  assertRuleIncludes(appStyles, '.wrongbook-page', 'padding-bottom: calc(28rpx + constant(safe-area-inset-bottom));');
  assertRuleIncludes(appStyles, '.wrongbook-page', 'padding-bottom: calc(28rpx + env(safe-area-inset-bottom));');
  assertRuleIncludes(appStyles, '.primary-btn', 'min-width: 0;');
  assertRuleIncludes(appStyles, '.primary-btn', 'max-width: 100%;');
  assertRuleIncludes(appStyles, '.primary-btn', 'text-overflow: clip;');
  assertRuleIncludes(appStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + constant(safe-area-inset-bottom));');
  assertRuleIncludes(uploadStyles, '.bottom-action-bar', 'padding: 0 30rpx calc(30rpx + constant(safe-area-inset-bottom));');
});

test('parent bind page uses official card hierarchy for lookup, existing children, and bind confirmation', () => {
  const bindTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.wxml'), 'utf8');
  const bindStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-bind/index.wxss'), 'utf8');

  assert.match(bindTemplate, /<view class="panel-card invite-panel">/);
  assert.match(bindTemplate, /class="field-group"/);
  assert.match(bindTemplate, /class="primary-btn lookup-btn" loading="{{loading}}" bindtap="previewInvite">查看班级和学生<\/button>/);
  assert.match(bindTemplate, /class="bound-child-card"/);
  assert.match(bindTemplate, /class="bound-child-name"/);
  assert.match(bindTemplate, /class="bound-child-meta"/);
  assert.match(bindTemplate, /class="panel-card class-result"/);
  assert.match(bindTemplate, /class="class-result-title"/);
  assert.match(bindTemplate, /class="student-info"/);
  assert.match(bindTemplate, /class="state-card empty-card empty-student-card"/);

  assert.match(bindStyles, /\.invite-panel\s*\{[^}]*gap:\s*22rpx;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*display:\s*block;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*width:\s*100%;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*height:\s*88rpx;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*min-height:\s*88rpx;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*line-height:\s*88rpx;/s);
  assert.match(bindStyles, /\.field-input\s*\{[^}]*padding:\s*0\s+24rpx;/s);
  assert.match(bindStyles, /\.lookup-btn\s*\{[^}]*width:\s*100%;/s);
  assert.match(bindStyles, /\.bound-child-card,\s*\.student-card\s*\{[^}]*display:\s*flex;/s);
  assert.match(bindStyles, /\.bound-child-card,\s*\.student-card\s*\{[^}]*flex-direction:\s*column;/s);
  assert.match(bindStyles, /\.bound-child-name,\s*\.bound-child-meta,\s*\.class-result-title,\s*\.student-name,\s*\.student-meta\s*\{[^}]*word-break:\s*break-all;/s);
  assert.match(bindStyles, /\.student-info\s*\{[^}]*min-width:\s*0;/s);
  assert.match(bindStyles, /\.empty-student-card\s*\{[^}]*background:\s*#f8fbff;/s);
});

test('parent-facing primary actions appear before nearby secondary follow-up actions', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const homeActions = homeTemplate.slice(
    homeTemplate.indexOf('class="binding-actions"'),
    homeTemplate.indexOf('</view>', homeTemplate.indexOf('class="binding-actions"')),
  );
  const successActions = uploadTemplate.slice(
    uploadTemplate.indexOf('<view class="success-actions">'),
    uploadTemplate.indexOf('</view>', uploadTemplate.indexOf('<view class="success-actions">')),
  );

  assert.ok(homeActions.indexOf('设置当前上传孩子') >= 0, 'home child card should include current child action');
  assert.ok(homeActions.indexOf('查看错题本') >= 0, 'home child card should include wrongbook action');
  assert.ok(homeActions.indexOf('设置当前上传孩子') < homeActions.indexOf('查看错题本'));
  assert.match(successActions, /class="primary-btn success-action-btn"[^>]*bindtap="openChildWrongbook"/);
  assert.match(successActions, /class="ghost-btn success-action-btn"[^>]*bindtap="backHome"/);
  assert.ok(successActions.indexOf('openChildWrongbook') < successActions.indexOf('backHome'));
});
