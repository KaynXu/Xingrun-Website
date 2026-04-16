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

  assert.equal(uploadTemplate.includes('AI 框选'), true);
  assert.equal(uploadTemplate.includes('补加框'), true);
  assert.equal(uploadTemplate.includes('删除当前'), true);
  assert.equal(uploadTemplate.includes('拍照或从相册里选一张图片'), false);
});

test('parent upload action buttons keep a stable single-row layout on narrow screens', () => {
  const uploadStyles = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-upload/index.wxss'), 'utf8');

  assert.match(uploadStyles, /\.action-row\s*\{[^}]*display:\s*flex;/s);
  assert.match(uploadStyles, /\.action-row\s*\{[^}]*align-items:\s*stretch;/s);
  assert.match(uploadStyles, /\.compact-btn\s*\{[^}]*flex:\s*1/s);
  assert.match(uploadStyles, /\.compact-btn\s*\{[^}]*height:\s*72rpx;/s);
  assert.match(uploadStyles, /\.compact-btn\s*\{[^}]*line-height:\s*72rpx;/s);
  assert.match(uploadStyles, /\.compact-btn\s*\{[^}]*white-space:\s*nowrap;/s);
});

test('parent wrongbook page exposes question text and a pdf entry button', () => {
  const wrongbookSource = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.js'), 'utf8');
  const wrongbookTemplate = fs.readFileSync(path.join(MINIPROGRAM_DIR, 'pages/parent-wrongbook/index.wxml'), 'utf8');

  assert.equal(wrongbookSource.includes('fetchChildWrongQuestionLibrary'), true);
  assert.equal(wrongbookTemplate.includes('查看 PDF'), true);
  assert.equal(wrongbookTemplate.includes('item.questionText'), true);
});
