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
  expectIncludes(pages.home.wxml, 'class="state-card"');
  expectIncludes(pages.home.wxml, 'class="state-card empty-card"');
  expectIncludes(pages.home.wxml, 'class="empty-kicker"');
  expectIncludes(pages.home.wxml, '<button class="primary-btn" bindtap="goBindMore">去绑定孩子</button>');
  expectIncludes(pages.home.wxml, 'class="panel-copy"');
  expectIncludes(pages.home.wxml, '已绑定 {{bindings.length}} 个孩子');
  expectIncludes(pages.home.wxml, 'class="binding-info"');
  expectIncludes(pages.home.wxml, 'class="binding-meta-stack"');
  expectIncludes(pages.home.wxml, '任课老师：{{item.teacherName || \'任课老师待补充\'}}');
  expectIncludes(pages.home.wxml, 'class="binding-hint"');
  expectIncludes(pages.home.wxml, 'class="binding-actions"');
  expectIncludes(pages.home.wxml, 'class="ghost-btn mini-btn"');
  expectIncludes(pages.home.wxml, 'class="primary-btn mini-btn"');
  expectOrderWithinBlock(pages.home.wxml, 'class="binding-actions"', '</view>', '上传错题', '查看错题本');
  expectRule(pages.home.wxss, '.empty-card', 'border: 2rpx solid rgba(35, 117, 216, 0.12);');
  expectRule(pages.home.wxss, '.empty-kicker', 'border-radius: 999rpx;');
  expectRule(pages.home.wxss, '.panel-copy', 'min-width: 0;');
  expectRule(pages.home.wxss, '.binding-info', 'min-width: 0;');
  expectRule(pages.home.wxss, '.binding-meta-stack', 'gap: 6rpx;');
  expectRule(pages.home.wxss, '.binding-hint', 'word-break: break-all;');
  expectRule(pages.home.wxss, '.binding-name', 'word-break: break-all;');
  expectRule(pages.home.wxss, '.binding-meta', 'word-break: break-all;');
  expectRule(pages.home.wxss, '.binding-actions', 'flex-direction: column;');
  expectRule(pages.home.wxss, '.binding-actions', 'width: 100%;');
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
  expectIncludes(pages.bind.wxml, 'class="state-card empty-student-card"');
  expectIncludes(pages.bind.wxml, '绑定这个孩子');
  expectRule(pages.bind.wxss, '.invite-panel', 'gap: 22rpx;');
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
  expectIncludes(pages.upload.wxml, 'class="ghost-btn picker-btn"');
  expectIncludes(pages.upload.wxml, 'bindtap="chooseImages"');
  expectIncludes(pages.upload.wxml, 'class="crop-stage-shell"');
  expectIncludes(pages.upload.wxml, 'class="box-action-group"');
  expectIncludes(pages.upload.wxml, 'class="box-tool-row"');
  expectIncludes(pages.upload.wxml, 'class="box-danger-row"');
  expectIncludes(pages.upload.wxml, '补加框');
  expectIncludes(pages.upload.wxml, '删除当前题框');
  expectIncludes(pages.upload.wxml, '顺时针旋转');
  expectIncludes(pages.upload.wxml, 'class="reason-card"');
  expectIncludes(pages.upload.wxml, 'class="upload-stage {{uploadStage');
  expectIncludes(pages.upload.wxml, 'class="bottom-action-bar"');
  expectIncludes(pages.upload.wxml, 'class="primary-btn submit-btn"');
  expectOrder(pages.upload.wxml, 'class="ghost-btn picker-btn"', 'class="box-action-group"');
  expectOrder(pages.upload.wxml, 'class="box-action-group"', 'class="reason-card"');
  expectOrder(pages.upload.wxml, 'class="upload-stage {{uploadStage', 'class="primary-btn submit-btn"');
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

check('parent-upload: bottom submit area has narrow-screen and safe-area spacing rules', () => {
  const uploadStyles = combinedStyles(pages.upload);
  expectRule(uploadStyles, '.parent-page', 'padding: 28rpx;');
  expectRule(uploadStyles, '.parent-page', 'box-sizing: border-box;');
  expectRule(uploadStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + env(safe-area-inset-bottom));');
  expectRule(pages.upload.wxss, '.submit-btn', 'width: 100%;');
  expectRule(pages.upload.wxss, '.submit-btn', 'line-height: 84rpx;');
  expectRule(pages.upload.wxss, '.submit-btn', 'white-space: nowrap;');
  expectRule(pages.upload.wxss, '.submit-btn', 'box-sizing: border-box;');
  expectRule(pages.upload.wxss, '.picker-btn', 'width: 100%;');
  expectRule(pages.upload.wxss, '.picker-btn', 'white-space: nowrap;');
});

check('parent-wrongbook: PDF entry, status, filters, and cards have clear hierarchy', () => {
  expectIncludes(pages.wrongbook.wxml, 'class="upload-status-card');
  expectIncludes(pages.wrongbook.wxml, 'class="library-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="primary-btn library-btn"');
  expectIncludes(pages.wrongbook.wxml, '查看 PDF');
  expectIncludes(pages.wrongbook.wxml, 'PDF 暂未就绪');
  expectIncludes(pages.wrongbook.wxml, 'class="state-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="topic-chip');
  expectIncludes(pages.wrongbook.wxml, 'class="item-card"');
  expectIncludes(pages.wrongbook.wxml, 'class="edit-topic-btn"');
  expectIncludes(pages.wrongbook.wxml, 'class="item-question"');
  expectRule(pages.wrongbook.wxss, '.library-card', 'flex-direction: column;');
  expectRule(pages.wrongbook.wxss, '.library-btn', 'width: 100%;');
  expectRule(pages.wrongbook.wxss, '.library-btn', 'white-space: nowrap;');
  expectRule(pages.wrongbook.wxss, '.item-top', 'flex-wrap: wrap;');
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
