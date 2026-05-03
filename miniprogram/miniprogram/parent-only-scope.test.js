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

test('parent home keeps an entry for binding more children after at least one child is already bound', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');

  assert.equal(homeTemplate.includes('绑定更多孩子'), true);
  assert.match(homeTemplate, /bindtap="goBindMore"/);
});

test('parent home uses upload-only wording after children are already available', () => {
  const homeTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxml'), 'utf8');

  assert.equal(homeTemplate.includes('已绑定孩子'), false);
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
  assert.match(uploadTemplate, /<button class="primary-btn submit-btn" loading="{{submitting}}" disabled="{{submitting \|\| cropExporting}}" bindtap="submitUpload">统一提交所有错题<\/button>/);
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
  assert.match(uploadTemplate, /<button class="primary-btn submit-btn" loading="{{submitting}}" disabled="{{submitting \|\| cropExporting}}" bindtap="submitUpload">统一提交所有错题<\/button>/);
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

test('parent upload and wrongbook pages expose primary topic category controls', () => {
  const uploadSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.js'), 'utf8');
  const uploadTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxml'), 'utf8');
  const wrongbookSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.js'), 'utf8');
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');

  assert.equal(uploadSource.includes('topicCategoryOptions'), true);
  assert.equal(uploadTemplate.includes('专题分类'), true);
  assert.equal(uploadTemplate.includes('handleActiveBoxTopicChange'), true);
  assert.equal(wrongbookSource.includes('updateChildWrongQuestionTopicCategory'), true);
  assert.equal(wrongbookSource.includes('topicSummaries'), true);
  assert.equal(wrongbookTemplate.includes('专题'), true);
  assert.equal(wrongbookTemplate.includes('bindtap="saveTopicCategory"'), true);
});

test('parent mini program pages stack action areas for narrow phone screens', () => {
  const homeStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-home/index.wxss'), 'utf8');
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

  assertRuleIncludes(homeStyles, '.binding-card', 'flex-direction: column;');
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
  assert.match(bindTemplate, /class="state-card empty-student-card"/);

  assert.match(bindStyles, /\.invite-panel\s*\{[^}]*gap:\s*22rpx;/s);
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

  assert.ok(homeActions.indexOf('上传错题') >= 0, 'home child card should include upload action');
  assert.ok(homeActions.indexOf('查看错题本') >= 0, 'home child card should include wrongbook action');
  assert.ok(homeActions.indexOf('上传错题') < homeActions.indexOf('查看错题本'));
  assert.match(successActions, /class="primary-btn success-action-btn"[^>]*bindtap="openChildWrongbook"/);
  assert.match(successActions, /class="ghost-btn success-action-btn"[^>]*bindtap="backHome"/);
  assert.ok(successActions.indexOf('openChildWrongbook') < successActions.indexOf('backHome'));
});
