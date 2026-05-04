#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

run() {
  echo
  echo ">>> $*"
  "$@"
}

cd "$ROOT_DIR"

run node --test miniprogram/miniprogram/parent-only-scope.test.js

echo
echo ">>> mini program visual structure contracts"
node <<'NODE'
const fs = require('node:fs');
const path = require('node:path');

const root = process.cwd();
const miniRoot = path.join(root, 'miniprogram/miniprogram');

const pages = {
  home: {
    name: 'parent-home',
    wxml: read('pages/parent-home/index.wxml'),
    wxss: read('pages/parent-home/index.wxss'),
  },
  bind: {
    name: 'parent-bind',
    wxml: read('pages/parent-bind/index.wxml'),
    wxss: read('pages/parent-bind/index.wxss'),
  },
  upload: {
    name: 'parent-upload',
    wxml: read('pages/parent-upload/index.wxml'),
    wxss: read('pages/parent-upload/index.wxss'),
  },
  wrongbook: {
    name: 'parent-wrongbook',
    wxml: read('pages/parent-wrongbook/index.wxml'),
    wxss: read('pages/parent-wrongbook/index.wxss'),
  },
};
const sharedStyles = read('app.wxss');

let failures = 0;

function read(relativePath) {
  return fs.readFileSync(path.join(miniRoot, relativePath), 'utf8');
}

function check(label, assertion) {
  try {
    assertion();
    console.log(`ok - ${label}`);
  } catch (error) {
    failures += 1;
    console.error(`visual contract failed: ${label}`);
    console.error(`  ${error.message}`);
  }
}

function expectIncludes(text, needle) {
  if (!text.includes(needle)) {
    throw new Error(`missing text: ${needle}`);
  }
}

function expectNotIncludes(text, needle) {
  if (text.includes(needle)) {
    throw new Error(`unexpected text: ${needle}`);
  }
}

function expectMatch(text, pattern) {
  if (!pattern.test(text)) {
    throw new Error(`missing pattern: ${pattern}`);
  }
}

function expectOrder(text, before, after) {
  const beforeIndex = text.indexOf(before);
  const afterIndex = text.indexOf(after);
  if (beforeIndex === -1) {
    throw new Error(`missing ordered text: ${before}`);
  }
  if (afterIndex === -1) {
    throw new Error(`missing ordered text: ${after}`);
  }
  if (beforeIndex >= afterIndex) {
    throw new Error(`expected "${before}" before "${after}"`);
  }
}

function blockBetween(text, startNeedle, endNeedle) {
  const start = text.indexOf(startNeedle);
  const end = text.indexOf(endNeedle, start);
  if (start === -1 || end === -1 || end <= start) {
    throw new Error(`could not locate block ${startNeedle}`);
  }
  return text.slice(start, end);
}

function expectOrderWithinBlock(text, startNeedle, endNeedle, before, after) {
  expectOrder(blockBetween(text, startNeedle, endNeedle), before, after);
}

function selectorBody(styles, selector) {
  const bodies = [];
  const rulePattern = /([^{}]+)\{([^{}]*)\}/g;
  let match;
  while ((match = rulePattern.exec(styles)) !== null) {
    const selectors = match[1].split(',').map((item) => item.trim());
    if (selectors.includes(selector)) {
      bodies.push(match[2]);
    }
  }
  return bodies.join('\n');
}

function combinedStyles(page) {
  return `${sharedStyles}\n${page.wxss}`;
}

function expectRule(styles, selector, declaration) {
  const body = selectorBody(styles, selector);
  if (!body) {
    throw new Error(`missing selector: ${selector}`);
  }
  if (!body.includes(declaration)) {
    throw new Error(`${selector} missing declaration: ${declaration}`);
  }
}

function expectNoSharedButtonRule(styles, selector) {
  const body = selectorBody(styles, selector);
  if (body) {
    throw new Error(`${selector} should be defined by app.wxss, not by page wxss`);
  }
}

function expectNoPrimaryInBlock(text, startNeedle, endNeedle) {
  const block = blockBetween(text, startNeedle, endNeedle);
  if (block.includes('primary-btn')) {
    throw new Error(`${startNeedle} should not contain a primary button`);
  }
}

function checkPageShell(page) {
  check(`${page.name}: page shell and card primitives`, () => {
    const styles = combinedStyles(page);
    expectRule(styles, page.name === 'parent-wrongbook' ? '.wrongbook-page' : '.parent-page', 'min-height: 100vh;');
    expectRule(styles, page.name === 'parent-wrongbook' ? '.wrongbook-page' : '.parent-page', 'padding: 28rpx;');
    expectRule(styles, page.name === 'parent-wrongbook' ? '.wrongbook-page' : '.parent-page', 'box-sizing: border-box;');
    expectMatch(styles, /border-radius:\s*(24|28|32)rpx;/);
    expectMatch(styles, /box-shadow:\s*0\s+\d+rpx\s+\d+rpx\s+rgba/);
  });
}

for (const page of Object.values(pages)) {
  checkPageShell(page);
}

check('shared visual system: primitives live in app.wxss', () => {
  expectRule(sharedStyles, '.parent-page', 'background: linear-gradient(180deg, #f6fbff 0%, #eef6ff 100%);');
  expectRule(sharedStyles, '.hero-card', 'border-radius: 28rpx;');
  expectRule(sharedStyles, '.state-card', 'box-shadow: 0 16rpx 48rpx rgba(45, 87, 140, 0.08);');
  expectRule(sharedStyles, '.section-title', 'color: #10233f;');
  expectRule(sharedStyles, '.primary-btn', 'background: #2375d8;');
  expectRule(sharedStyles, '.ghost-btn', 'background: #eef5ff;');
  expectRule(sharedStyles, '.danger-btn', 'background: #fff1f0;');
  expectRule(sharedStyles, '.icon-btn', 'width: 72rpx;');
  expectRule(sharedStyles, '.tag', 'border-radius: 999rpx;');
  expectRule(sharedStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + env(safe-area-inset-bottom));');
});

check('shared visual system: primary and secondary button colors are not scattered in page wxss', () => {
  for (const page of Object.values(pages)) {
    expectNoSharedButtonRule(page.wxss, '.primary-btn');
    expectNoSharedButtonRule(page.wxss, '.ghost-btn');
  }
});

check('parent-home: primary and secondary actions are grouped by child card', () => {
  expectIncludes(pages.home.wxml, 'class="hero-card"');
  expectIncludes(pages.home.wxml, 'class="hero-badge"');
  expectIncludes(pages.home.wxml, '星润家长端');
  expectIncludes(pages.home.wxml, '孩子错题与上传入口');
  expectMatch(pages.home.wxml, /class="state-card /);
  expectIncludes(pages.home.wxml, 'class="state-card empty-card"');
  expectIncludes(pages.home.wxml, 'class="state-marker state-marker-empty"');
  expectIncludes(pages.home.wxml, '<button class="primary-btn" bindtap="goBindMore">去绑定孩子</button>');
  expectIncludes(pages.home.wxml, 'class="panel-copy"');
  expectIncludes(pages.home.wxml, '已绑定 {{bindings.length}} 个孩子');
  expectIncludes(pages.home.wxml, 'class="binding-info"');
  expectIncludes(pages.home.wxml, 'class="binding-meta-stack"');
  expectIncludes(pages.home.wxml, '任课老师：{{item.teacherName || \'任课老师待补充\'}}');
  expectNotIncludes(pages.home.wxml, '上传后可在错题本查看整理进度。');
  expectIncludes(pages.home.wxml, 'class="binding-actions"');
  expectIncludes(pages.home.wxml, 'class="ghost-btn mini-btn"');
  expectIncludes(pages.home.wxml, 'class="primary-btn mini-btn"');
  expectOrderWithinBlock(pages.home.wxml, 'class="binding-actions"', '</view>', '上传错题', '查看错题本');
  expectRule(pages.home.wxss, '.empty-card', 'border: 2rpx solid rgba(35, 117, 216, 0.12);');
  expectRule(pages.home.wxss, '.panel-copy', 'min-width: 0;');
  expectRule(pages.home.wxss, '.binding-info', 'min-width: 0;');
  expectRule(pages.home.wxss, '.binding-info', 'flex: 1;');
  expectRule(pages.home.wxss, '.binding-card', 'flex-direction: row;');
  expectRule(pages.home.wxss, '.binding-card', 'align-items: center;');
  expectRule(pages.home.wxss, '.binding-meta-stack', 'gap: 6rpx;');
  expectRule(pages.home.wxss, '.binding-name', 'word-break: break-all;');
  expectRule(pages.home.wxss, '.binding-meta', 'word-break: break-all;');
  expectRule(pages.home.wxss, '.binding-actions', 'flex-direction: column;');
  expectRule(pages.home.wxss, '.binding-actions', 'width: 190rpx;');
  expectRule(pages.home.wxss, '.mini-btn', 'width: 100%;');
  expectRule(pages.home.wxss, '.mini-btn', 'white-space: nowrap;');
});

check('parent-bind: lookup, existing binding, and bind confirmation hierarchy', () => {
  expectIncludes(pages.bind.wxml, 'class="panel-card invite-panel"');
  expectIncludes(pages.bind.wxml, 'class="field-group"');
  expectIncludes(pages.bind.wxml, 'class="field-input"');
  expectIncludes(pages.bind.wxml, '<button class="primary-btn lookup-btn" loading="{{loading}}" bindtap="previewInvite">查看班级和学生</button>');
  expectIncludes(pages.bind.wxml, 'class="section-head"');
  expectIncludes(pages.bind.wxml, '<button class="ghost-btn" size="mini" bindtap="goHome">去上传</button>');
  expectIncludes(pages.bind.wxml, 'class="bound-child-card"');
  expectIncludes(pages.bind.wxml, 'class="bound-child-name"');
  expectIncludes(pages.bind.wxml, 'class="bound-child-meta"');
  expectIncludes(pages.bind.wxml, 'class="panel-card class-result"');
  expectIncludes(pages.bind.wxml, 'class="class-result-title"');
  expectIncludes(pages.bind.wxml, 'class="student-card"');
  expectIncludes(pages.bind.wxml, 'class="student-info"');
  expectIncludes(pages.bind.wxml, 'class="primary-btn mini-btn"');
  expectIncludes(pages.bind.wxml, 'class="state-card empty-card empty-student-card"');
  expectIncludes(pages.bind.wxml, '绑定这个孩子');
  expectRule(pages.bind.wxss, '.invite-panel', 'gap: 22rpx;');
  expectRule(pages.bind.wxss, '.field-input', 'display: block;');
  expectRule(pages.bind.wxss, '.field-input', 'height: 88rpx;');
  expectRule(pages.bind.wxss, '.field-input', 'line-height: 88rpx;');
  expectRule(pages.bind.wxss, '.lookup-btn', 'width: 100%;');
  expectRule(pages.bind.wxss, '.section-head', 'flex-direction: column;');
  expectRule(pages.bind.wxss, '.bound-child-card', 'flex-direction: column;');
  expectRule(pages.bind.wxss, '.student-card', 'flex-direction: column;');
  expectRule(pages.bind.wxss, '.student-info', 'min-width: 0;');
  expectRule(pages.bind.wxss, '.bound-child-name', 'word-break: break-all;');
  expectRule(pages.bind.wxss, '.bound-child-meta', 'word-break: break-all;');
  expectRule(pages.bind.wxss, '.class-result-title', 'word-break: break-all;');
  expectRule(pages.bind.wxss, '.student-name', 'word-break: break-all;');
  expectRule(pages.bind.wxss, '.student-meta', 'word-break: break-all;');
  expectRule(pages.bind.wxss, '.empty-student-card', 'background: #f8fbff;');
  expectRule(pages.bind.wxss, '.mini-btn', 'width: 100%;');
  expectRule(pages.bind.wxss, '.mini-btn', 'white-space: nowrap;');
});

check('parent-upload: photo, box, reason, progress, and submit sections stay distinct', () => {
  expectIncludes(pages.upload.wxml, 'class="panel-card upload-flow-panel"');
  expectIncludes(pages.upload.wxml, 'class="upload-section upload-image-section"');
  expectIncludes(pages.upload.wxml, 'class="upload-section upload-box-section"');
  expectIncludes(pages.upload.wxml, 'class="selected-image-context"');
  expectIncludes(pages.upload.wxml, 'class="reason-card upload-section upload-reason-section"');
  expectIncludes(pages.upload.wxml, 'class="state-card upload-stage upload-progress-card');
  expectIncludes(pages.upload.wxml, 'class="submit-panel"');
  expectIncludes(pages.upload.wxml, 'class="ghost-btn picker-btn"');
  expectIncludes(pages.upload.wxml, 'bindtap="chooseImages"');
  expectIncludes(pages.upload.wxml, 'class="crop-stage-shell"');
  expectIncludes(pages.upload.wxml, 'class="box-action-group"');
  expectIncludes(pages.upload.wxml, 'class="box-tool-row"');
  expectIncludes(pages.upload.wxml, 'class="box-danger-row"');
  expectIncludes(pages.upload.wxml, '补加框');
  expectIncludes(pages.upload.wxml, '删除当前题框');
  expectIncludes(pages.upload.wxml, '顺时针旋转');
  expectIncludes(pages.upload.wxml, 'class="reason-card upload-section upload-reason-section"');
  expectIncludes(pages.upload.wxml, 'class="state-card upload-stage upload-progress-card {{uploadStage');
  expectIncludes(pages.upload.wxml, 'class="bottom-action-bar"');
  expectIncludes(pages.upload.wxml, 'class="primary-btn submit-btn"');
  expectOrder(pages.upload.wxml, 'class="upload-section upload-image-section"', 'class="upload-section upload-box-section"');
  expectOrder(pages.upload.wxml, 'class="ghost-btn picker-btn"', 'class="box-action-group"');
  expectOrder(pages.upload.wxml, 'class="box-action-group"', 'class="reason-card upload-section upload-reason-section"');
  expectOrder(pages.upload.wxml, 'class="reason-card upload-section upload-reason-section"', 'class="state-card upload-stage upload-progress-card');
  expectOrder(pages.upload.wxml, 'class="state-card upload-stage upload-progress-card', 'class="primary-btn submit-btn"');
  expectRule(pages.upload.wxss, '.upload-flow-panel', 'padding: 0;');
  expectRule(pages.upload.wxss, '.upload-section', 'padding: 30rpx;');
  expectRule(pages.upload.wxss, '.upload-section-head', 'display: flex;');
  expectRule(pages.upload.wxss, '.selected-image-context', 'display: flex;');
  expectRule(pages.upload.wxss, '.upload-progress-card', 'margin: 0 30rpx 22rpx;');
  expectRule(pages.upload.wxss, '.submit-panel', 'display: flex;');
  expectRule(pages.upload.wxss, '.submit-panel', 'flex-direction: column;');
});

check('parent-upload: destructive box action is visually separated from final submit', () => {
  const toolBlock = blockBetween(pages.upload.wxml, '<view class="box-tool-row">', '</view>');
  if (toolBlock.includes('removeActiveBox')) {
    throw new Error('delete action should not be inside the main box tool row');
  }
  expectMatch(toolBlock, /<button class="ghost-btn tool-btn"[^>]*bindtap="addManualBox">补加框<\/button>/);
  expectMatch(toolBlock, /<button class="ghost-btn tool-btn"[^>]*bindtap="rotateCurrentImageClockwise">顺时针旋转<\/button>/);
  expectMatch(pages.upload.wxml, /<view class="box-danger-row">[\s\S]*<button class="danger-btn delete-box-btn"[^>]*bindtap="removeActiveBox">删除当前题框<\/button>[\s\S]*<\/view>/);
  expectMatch(pages.upload.wxml, /<button class="primary-btn submit-btn"[^>]*bindtap="submitUpload">统一提交所有错题<\/button>/);
  expectNoPrimaryInBlock(pages.upload.wxml, '<view class="box-action-group">', '<view wx:if="{{activeBox}}"');
  expectOrder(pages.upload.wxml, '顺时针旋转', '删除当前题框');
  expectOrder(pages.upload.wxml, '删除当前题框', '统一提交所有错题');
  expectRule(pages.upload.wxss, '.box-action-group', 'display: flex;');
  expectRule(pages.upload.wxss, '.box-action-group', 'flex-direction: column;');
  expectRule(pages.upload.wxss, '.box-tool-row', 'display: flex;');
  expectRule(pages.upload.wxss, '.box-tool-row', 'align-items: stretch;');
  expectRule(pages.upload.wxss, '.tool-btn', 'flex: 1;');
  expectRule(pages.upload.wxss, '.tool-btn', 'min-width: 0;');
  expectRule(pages.upload.wxss, '.tool-btn', 'white-space: nowrap;');
  expectRule(pages.upload.wxss, '.box-danger-row', 'display: flex;');
  expectRule(pages.upload.wxss, '.box-danger-row', 'justify-content: flex-end;');
  expectRule(pages.upload.wxss, '.delete-box-btn', 'white-space: nowrap;');
});

check('parent-upload: success actions make progress or wrongbook the primary next step', () => {
  expectIncludes(pages.upload.wxml, 'class="success-actions"');
  expectMatch(pages.upload.wxml, /<button class="primary-btn success-action-btn"[^>]*bindtap="openChildWrongbook">查看错题本 \/ 刷新进度<\/button>/);
  expectMatch(pages.upload.wxml, /<button class="ghost-btn success-action-btn"[^>]*bindtap="backHome">返回家长主页<\/button>/);
  expectOrderWithinBlock(pages.upload.wxml, '<view class="success-actions">', '</view>', 'openChildWrongbook', 'backHome');
  expectRule(pages.upload.wxss, '.success-actions', 'display: flex;');
  expectRule(pages.upload.wxss, '.success-actions', 'flex-direction: column;');
  expectRule(pages.upload.wxss, '.success-action-btn', 'width: 100%;');
  expectRule(pages.upload.wxss, '.success-action-btn', 'white-space: nowrap;');
});

check('parent-facing pages: unified state card anatomy for loading, empty, processing, success, and error', () => {
  expectRule(sharedStyles, '.state-marker', 'border-radius: 999rpx;');
  expectRule(sharedStyles, '.state-marker-loading', 'background: #e9f5ff;');
  expectRule(sharedStyles, '.state-marker-empty', 'background: #e9f5ff;');
  expectRule(sharedStyles, '.state-marker-processing', 'background: #fff7e6;');
  expectRule(sharedStyles, '.state-marker-success', 'background: #e8faf0;');
  expectRule(sharedStyles, '.state-marker-error', 'background: #fff1f0;');
  expectRule(sharedStyles, '.state-action-btn', 'white-space: nowrap;');

  expectMatch(pages.home.wxml, /class="state-card loading-card"[\s\S]*class="state-marker state-marker-loading"/);
  expectMatch(pages.home.wxml, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  expectMatch(pages.home.wxml, /class="ghost-btn state-action-btn" bindtap="onShow">重新加载<\/button>/);
  expectMatch(pages.home.wxml, /class="state-card empty-card"[\s\S]*class="state-marker state-marker-empty"/);

  expectMatch(pages.bind.wxml, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  expectMatch(pages.bind.wxml, /class="state-card empty-card empty-student-card"[\s\S]*class="state-marker state-marker-empty"/);

  expectMatch(pages.upload.wxml, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  expectIncludes(pages.upload.wxml, 'class="state-card upload-stage upload-progress-card');
  expectIncludes(pages.upload.wxml, "class=\"state-marker {{uploadStage === 'failed' || uploadStage === 'partial_failed' ? 'state-marker-error' : uploadStage === 'ready' ? 'state-marker-success' : 'state-marker-processing'}}\"");
  expectIncludes(pages.upload.wxml, 'class="state-card upload-result-card');
  expectIncludes(pages.upload.wxml, "class=\"state-marker {{uploadTaskSummary.state === 'failed' || uploadTaskSummary.state === 'partial_failed' ? 'state-marker-error' : uploadTaskSummary.state === 'ready' ? 'state-marker-success' : 'state-marker-processing'}}\"");

  expectIncludes(pages.wrongbook.wxml, 'class="state-card upload-status-card');
  expectIncludes(pages.wrongbook.wxml, "class=\"state-marker {{uploadTaskSummary.state === 'failed' || uploadTaskSummary.state === 'partial_failed' ? 'state-marker-error' : 'state-marker-processing'}}\"");
  expectMatch(pages.wrongbook.wxml, /class="state-card loading-card"[\s\S]*class="state-marker state-marker-loading"/);
  expectMatch(pages.wrongbook.wxml, /class="state-card error-card"[\s\S]*class="state-marker state-marker-error"/);
  expectMatch(pages.wrongbook.wxml, /class="state-card empty-card"[\s\S]*class="state-marker state-marker-empty"/);
  expectIncludes(pages.wrongbook.wxml, "class=\"state-marker item-status-marker {{item.recognitionStatus === 'failed' ? 'state-marker-error' : 'state-marker-processing'}}\"");
});

check('parent-upload: bottom submit area has narrow-screen and safe-area spacing rules', () => {
  const uploadStyles = combinedStyles(pages.upload);
  expectRule(uploadStyles, '.parent-page', 'padding: 28rpx;');
  expectRule(uploadStyles, '.parent-page', 'box-sizing: border-box;');
  expectRule(sharedStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + constant(safe-area-inset-bottom));');
  expectRule(uploadStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + env(safe-area-inset-bottom));');
  expectRule(pages.upload.wxss, '.bottom-action-bar', 'padding: 0 30rpx calc(30rpx + constant(safe-area-inset-bottom));');
  expectRule(pages.upload.wxss, '.bottom-action-bar', 'padding: 0 30rpx calc(30rpx + env(safe-area-inset-bottom));');
  expectRule(pages.upload.wxss, '.submit-btn', 'width: 100%;');
  expectRule(pages.upload.wxss, '.submit-btn', 'line-height: 84rpx;');
  expectRule(pages.upload.wxss, '.submit-btn', 'white-space: nowrap;');
  expectRule(pages.upload.wxss, '.submit-btn', 'box-sizing: border-box;');
  expectRule(pages.upload.wxss, '.picker-btn', 'width: 100%;');
  expectRule(pages.upload.wxss, '.picker-btn', 'white-space: nowrap;');
  expectRule(pages.upload.wxss, '.submit-title', 'white-space: nowrap;');
  expectRule(pages.upload.wxss, '.submit-desc', 'word-break: break-all;');
});

check('parent-facing pages: WeChat narrow runtime width and clipping guardrails', () => {
  expectRule(sharedStyles, 'page', 'max-width: 100vw;');
  expectRule(sharedStyles, 'page', 'overflow-x: hidden;');
  expectRule(sharedStyles, '.parent-page', 'width: 100%;');
  expectRule(sharedStyles, '.parent-page', 'max-width: 100vw;');
  expectRule(sharedStyles, '.parent-page', 'overflow-x: hidden;');
  expectRule(sharedStyles, '.parent-page', 'padding-bottom: calc(28rpx + constant(safe-area-inset-bottom));');
  expectRule(sharedStyles, '.parent-page', 'padding-bottom: calc(28rpx + env(safe-area-inset-bottom));');
  expectRule(sharedStyles, '.wrongbook-page', 'width: 100%;');
  expectRule(sharedStyles, '.wrongbook-page', 'max-width: 100vw;');
  expectRule(sharedStyles, '.wrongbook-page', 'overflow-x: hidden;');
  expectRule(sharedStyles, '.wrongbook-page', 'padding-bottom: calc(28rpx + constant(safe-area-inset-bottom));');
  expectRule(sharedStyles, '.wrongbook-page', 'padding-bottom: calc(28rpx + env(safe-area-inset-bottom));');
  expectRule(sharedStyles, '.primary-btn', 'min-width: 0;');
  expectRule(sharedStyles, '.primary-btn', 'max-width: 100%;');
  expectRule(sharedStyles, '.primary-btn', 'text-overflow: clip;');
  expectRule(sharedStyles, '.ghost-btn', 'min-width: 0;');
  expectRule(sharedStyles, '.danger-btn', 'min-width: 0;');

  for (const page of Object.values(pages)) {
    const styles = combinedStyles(page);
    for (const selector of ['.primary-btn', '.submit-btn', '.lookup-btn', '.library-btn', '.success-action-btn']) {
      const body = selectorBody(styles, selector);
      if (/(^|[;\s])(?:width|min-width):\s*\d+rpx\b/.test(body)) {
        throw new Error(`${page.name} ${selector} uses a fixed rpx width`);
      }
    }
  }
});

check('parent-wrongbook: PDF entry, status, filters, and cards have clear hierarchy', () => {
  expectIncludes(pages.wrongbook.wxml, 'class="hero-card wrongbook-hero"');
  expectIncludes(pages.wrongbook.wxml, '星润错题本');
  expectIncludes(pages.wrongbook.wxml, 'class="hero-stat-row"');
  expectIncludes(pages.wrongbook.wxml, 'class="state-card upload-status-card');
  expectIncludes(pages.wrongbook.wxml, 'class="library-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="primary-btn library-btn"');
  expectIncludes(pages.wrongbook.wxml, 'class="ghost-btn library-btn library-btn-pending"');
  expectIncludes(pages.wrongbook.wxml, 'class="library-state-tag');
  expectIncludes(pages.wrongbook.wxml, 'class="library-actions"');
  expectIncludes(pages.wrongbook.wxml, '查看 PDF');
  expectIncludes(pages.wrongbook.wxml, 'PDF 暂未就绪');
  expectIncludes(pages.wrongbook.wxml, 'class="panel-card filter-panel"');
  expectIncludes(pages.wrongbook.wxml, 'class="state-card loading-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="state-card error-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="state-card empty-card"');
  expectIncludes(pages.wrongbook.wxml, '重新加载');
  expectIncludes(pages.wrongbook.wxml, 'class="topic-scroll"');
  expectNotIncludes(pages.wrongbook.wxml, 'scroll-x="true"');
  expectIncludes(pages.wrongbook.wxml, 'class="topic-chip');
  expectIncludes(pages.wrongbook.wxml, 'class="item-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="item-card-head"');
  expectIncludes(pages.wrongbook.wxml, 'class="item-section-label">题目预览</text>');
  expectIncludes(pages.wrongbook.wxml, 'class="item-section-label">错因简述</text>');
  expectIncludes(pages.wrongbook.wxml, 'class="item-status-card ');
  expectIncludes(pages.wrongbook.wxml, 'class="edit-topic-btn"');
  expectIncludes(pages.wrongbook.wxml, 'class="item-question"');
  expectRule(pages.wrongbook.wxss, '.wrongbook-hero', 'display: flex;');
  expectRule(pages.wrongbook.wxss, '.hero-stat-row', 'flex-wrap: wrap;');
  expectRule(pages.wrongbook.wxss, '.library-actions', 'flex-direction: column;');
  expectRule(pages.wrongbook.wxss, '.library-card', 'flex-direction: column;');
  expectRule(pages.wrongbook.wxss, '.library-btn', 'width: 100%;');
  expectRule(pages.wrongbook.wxss, '.library-btn', 'white-space: nowrap;');
  expectRule(pages.wrongbook.wxss, '.library-btn-pending', 'background: #eef5ff;');
  expectRule(pages.wrongbook.wxss, '.filter-panel', 'padding: 24rpx;');
  expectRule(pages.wrongbook.wxss, '.topic-scroll', 'display: flex;');
  expectRule(pages.wrongbook.wxss, '.topic-scroll', 'width: 100%;');
  expectRule(pages.wrongbook.wxss, '.topic-chip', 'flex: 1 1 calc(50% - 6rpx);');
  expectRule(pages.wrongbook.wxss, '.topic-chip', 'min-width: 0;');
  expectRule(pages.wrongbook.wxss, '.item-card', 'flex-direction: column;');
  expectRule(pages.wrongbook.wxss, '.item-top', 'flex-wrap: wrap;');
  expectRule(pages.wrongbook.wxss, '.item-section', 'min-width: 0;');
  expectRule(pages.wrongbook.wxss, '.item-section-label', 'letter-spacing: 0;');
  expectRule(pages.wrongbook.wxss, '.item-status-card', 'white-space: pre-wrap;');
  expectRule(pages.wrongbook.wxss, '.item-question', 'white-space: pre-wrap;');
  expectRule(pages.wrongbook.wxss, '.item-question', 'word-break: break-all;');
});

check('parent-wrongbook: topic edit actions keep secondary and save actions grouped', () => {
  expectIncludes(pages.wrongbook.wxml, 'class="topic-edit-actions"');
  expectIncludes(pages.wrongbook.wxml, 'class="topic-action-btn"');
  expectIncludes(pages.wrongbook.wxml, 'class="primary-btn topic-action-btn topic-save-btn"');
  expectOrder(pages.wrongbook.wxml, 'cancelEditTopicCategory', 'saveTopicCategory');
  expectRule(pages.wrongbook.wxss, '.topic-edit-actions', 'display: flex;');
  expectRule(pages.wrongbook.wxss, '.topic-action-btn', 'flex: 1;');
});

check('parent-facing templates avoid prototype-only wording', () => {
  const forbidden = [
    /原型/,
    /prototype/i,
    /\bdemo\b/i,
    /调试/,
    /\bdebug\b/i,
    /内部测试/,
    /测试页面/,
    /临时页面/,
    /占位/,
    /TODO/,
    /FIXME/,
  ];
  for (const page of Object.values(pages)) {
    for (const pattern of forbidden) {
      if (pattern.test(page.wxml)) {
        throw new Error(`${page.name} template contains prototype-only wording: ${pattern}`);
      }
    }
  }
  expectNotIncludes(pages.upload.wxml, 'AI 框选');
});

if (failures > 0) {
  process.exit(1);
}

console.log('mini program visual structure contracts passed');
NODE

echo
echo "mini program visual polish proof passed"
