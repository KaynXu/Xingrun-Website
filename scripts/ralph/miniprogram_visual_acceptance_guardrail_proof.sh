#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VISUAL_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_visual_polish_proof.sh"
UPLOAD_PROOF="$ROOT_DIR/scripts/ralph/miniprogram_upload_stability_proof.sh"
PRD_JSON="$ROOT_DIR/scripts/ralph/prd.json"

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "missing file: ${path#$ROOT_DIR/}"
    exit 1
  fi
  echo "ok file: ${path#$ROOT_DIR/}"
}

require_executable() {
  local path="$1"
  if [[ ! -x "$path" ]]; then
    echo "missing executable: ${path#$ROOT_DIR/}"
    exit 1
  fi
  echo "ok executable: ${path#$ROOT_DIR/}"
}

run() {
  echo
  echo ">>> $*"
  "$@"
}

cd "$ROOT_DIR"

require_file "$PRD_JSON"
require_executable "$VISUAL_PROOF"
require_executable "$UPLOAD_PROOF"

echo
echo ">>> final visual acceptance contracts"
node <<'NODE'
const childProcess = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = process.cwd();
const miniRoot = path.join(root, 'miniprogram/miniprogram');
const prd = JSON.parse(fs.readFileSync(path.join(root, 'scripts/ralph/prd.json'), 'utf8'));
const allowCurrentPending = process.env.XR_RALPH_ALLOW_CURRENT_STORY_PENDING === '1';

let failures = 0;

function read(relativePath) {
  return fs.readFileSync(path.join(miniRoot, relativePath), 'utf8');
}

const pages = {
  home: read('pages/parent-home/index.wxml'),
  bind: read('pages/parent-bind/index.wxml'),
  upload: read('pages/parent-upload/index.wxml'),
  wrongbook: read('pages/parent-wrongbook/index.wxml'),
};
const pageStyles = {
  home: read('pages/parent-home/index.wxss'),
  bind: read('pages/parent-bind/index.wxss'),
  upload: read('pages/parent-upload/index.wxss'),
  wrongbook: read('pages/parent-wrongbook/index.wxss'),
};
const appStyles = read('app.wxss');

function check(label, assertion) {
  try {
    assertion();
    console.log(`ok - ${label}`);
  } catch (error) {
    failures += 1;
    console.error(`visual acceptance failed: ${label}`);
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
    throw new Error(`could not locate block from ${startNeedle}`);
  }
  return text.slice(start, end);
}

function countNeedle(text, needle) {
  return text.split(needle).length - 1;
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

function expectRule(styles, selector, declaration) {
  const body = selectorBody(styles, selector);
  if (!body) {
    throw new Error(`missing selector: ${selector}`);
  }
  if (!body.includes(declaration)) {
    throw new Error(`${selector} missing declaration: ${declaration}`);
  }
}

function expectOnePrimaryInBlock(pageText, startNeedle, endNeedle, label) {
  const block = blockBetween(pageText, startNeedle, endNeedle);
  const count = countNeedle(block, 'primary-btn');
  if (count !== 1) {
    throw new Error(`${label} expected one primary action, found ${count}`);
  }
}

check('PRD pass gate is complete or only MP-VISUAL-010 is pending in pre-completion mode', () => {
  const stories = prd.userStories || [];
  const pending = stories.filter((story) => story.passes !== true).map((story) => story.id || '<missing id>');
  if (pending.length === 0) {
    console.log(`ok PRD pass gate: all ${stories.length} stories are passes=true`);
    return;
  }
  if (allowCurrentPending && pending.length === 1 && pending[0] === 'MP-VISUAL-010') {
    console.log('ok PRD pass gate: MP-VISUAL-010 is the only pending story in pre-completion mode');
    return;
  }
  throw new Error(`pending stories: ${pending.join(', ')}`);
});

check('current story did not modify website frontend, website backend, or bridge files', () => {
  const watchedPaths = [
    'frontend',
    'app.py',
    'lesson_manager.py',
    'ai_processor.py',
    'smart_wrong_questions.py',
    'wrong_question_upload_worker.py',
    'config_runtime.py',
    'requirements.txt',
    'tests',
    'miniprogram/backend',
  ];
  const status = childProcess.execFileSync('git', ['status', '--porcelain', '--', ...watchedPaths], {
    encoding: 'utf8',
  });
  const meaningfulStatus = status
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.includes('__pycache__/') && !line.endsWith('.pyc'));
  if (meaningfulStatus.length) {
    throw new Error(`unexpected website/backend/bridge working tree changes:\n${meaningfulStatus.join('\n')}`);
  }
});

check('shared visual system is present for finished parent pages', () => {
  expectRule(appStyles, '.parent-page', 'background: linear-gradient(180deg, #f6fbff 0%, #eef6ff 100%);');
  expectRule(appStyles, '.hero-card', 'border-radius: 28rpx;');
  expectRule(appStyles, '.panel-card', 'box-shadow: 0 16rpx 48rpx rgba(45, 87, 140, 0.08);');
  expectRule(appStyles, '.primary-btn', 'background: #2375d8;');
  expectRule(appStyles, '.ghost-btn', 'background: #eef5ff;');
  expectRule(appStyles, '.danger-btn', 'background: #fff1f0;');
  expectRule(appStyles, '.state-marker', 'border-radius: 999rpx;');
  expectRule(appStyles, '.bottom-action-bar', 'padding-bottom: calc(24rpx + env(safe-area-inset-bottom));');
  expectRule(appStyles, '.parent-page', 'max-width: 100vw;');
  expectRule(appStyles, '.wrongbook-page', 'max-width: 100vw;');
});

check('parent-home uses finished entry hierarchy and one primary action per child section', () => {
  expectIncludes(pages.home, '星润家长端');
  expectIncludes(pages.home, 'class="hero-card"');
  expectIncludes(pages.home, 'class="state-card empty-card"');
  expectIncludes(pages.home, '<button class="primary-btn" bindtap="goBindMore">去绑定孩子</button>');
  expectIncludes(pages.home, 'class="binding-actions"');
  expectIncludes(pages.home, '<button class="primary-btn mini-btn"');
  expectIncludes(pages.home, '<button class="ghost-btn mini-btn"');
  expectOrder(pages.home, '上传错题', '查看错题本');
  expectOnePrimaryInBlock(pages.home, '<view class="binding-actions">', '</view>', 'parent-home child action group');
  expectRule(pageStyles.home, '.binding-actions', 'flex-direction: column;');
  expectRule(pageStyles.home, '.mini-btn', 'white-space: nowrap;');
});

check('parent-bind keeps lookup and bind confirmation actions scoped to their cards', () => {
  expectIncludes(pages.bind, 'class="panel-card invite-panel"');
  expectIncludes(pages.bind, '<button class="primary-btn lookup-btn"');
  expectIncludes(pages.bind, 'class="bound-child-card"');
  expectIncludes(pages.bind, 'class="student-card"');
  expectIncludes(pages.bind, '绑定这个孩子');
  expectOnePrimaryInBlock(pages.bind, '<view wx:if="{{preview}}" class="panel-card class-result">', '<view wx:else class="state-card empty-card empty-student-card">', 'parent-bind class result');
  expectRule(pageStyles.bind, '.lookup-btn', 'width: 100%;');
  expectRule(pageStyles.bind, '.student-card', 'flex-direction: column;');
  expectRule(pageStyles.bind, '.mini-btn', 'white-space: nowrap;');
});

check('parent-upload keeps photo, box, reason, progress, and submit hierarchy separated', () => {
  expectIncludes(pages.upload, 'class="upload-section upload-image-section"');
  expectIncludes(pages.upload, 'class="upload-section upload-box-section"');
  expectIncludes(pages.upload, 'class="reason-card upload-section upload-reason-section"');
  expectIncludes(pages.upload, 'class="state-card upload-stage upload-progress-card');
  expectIncludes(pages.upload, 'class="bottom-action-bar"');
  expectOrder(pages.upload, 'class="upload-section upload-image-section"', 'class="upload-section upload-box-section"');
  expectOrder(pages.upload, 'class="box-action-group"', 'class="reason-card upload-section upload-reason-section"');
  expectOrder(pages.upload, 'class="state-card upload-stage upload-progress-card', 'class="primary-btn submit-btn"');
  expectOnePrimaryInBlock(pages.upload, '<view class="bottom-action-bar">', '</view>', 'parent-upload bottom submit area');
  expectRule(pageStyles.upload, '.submit-panel', 'flex-direction: column;');
  expectRule(pageStyles.upload, '.submit-btn', 'white-space: nowrap;');
});

check('parent-upload separates destructive box action from primary submit and tool row', () => {
  const toolBlock = blockBetween(pages.upload, '<view class="box-tool-row">', '</view>');
  expectNotIncludes(toolBlock, 'removeActiveBox');
  expectIncludes(pages.upload, 'class="box-danger-row"');
  expectIncludes(pages.upload, 'class="danger-btn delete-box-btn"');
  expectOrder(pages.upload, '顺时针旋转', '删除当前题框');
  expectOrder(pages.upload, '删除当前题框', '统一提交所有错题');
  expectRule(pageStyles.upload, '.box-action-group', 'flex-direction: column;');
  expectRule(pageStyles.upload, '.box-danger-row', 'justify-content: flex-end;');
  expectRule(pageStyles.upload, '.delete-box-btn', 'white-space: nowrap;');
});

check('parent-upload success state makes wrongbook progress primary and home secondary', () => {
  expectIncludes(pages.upload, 'class="success-actions"');
  expectIncludes(pages.upload, '<button class="primary-btn success-action-btn" bindtap="openChildWrongbook">查看错题本 / 刷新进度</button>');
  expectIncludes(pages.upload, '<button class="ghost-btn success-action-btn" bindtap="backHome">返回家长主页</button>');
  expectOnePrimaryInBlock(pages.upload, '<view class="success-actions">', '</view>', 'parent-upload success action group');
  expectOrder(pages.upload, 'openChildWrongbook', 'backHome');
  expectRule(pageStyles.upload, '.success-action-btn', 'white-space: nowrap;');
});

check('parent-wrongbook keeps PDF entry, filters, cards, and topic actions in clear hierarchy', () => {
  expectIncludes(pages.wrongbook, '星润错题本');
  expectIncludes(pages.wrongbook, 'class="hero-card wrongbook-hero"');
  expectIncludes(pages.wrongbook, 'class="library-card"');
  expectIncludes(pages.wrongbook, 'class="primary-btn library-btn"');
  expectIncludes(pages.wrongbook, 'class="ghost-btn library-btn library-btn-pending"');
  expectIncludes(pages.wrongbook, 'class="panel-card filter-panel"');
  expectIncludes(pages.wrongbook, 'class="item-card"');
  expectIncludes(pages.wrongbook, 'class="topic-edit-actions"');
  expectOnePrimaryInBlock(pages.wrongbook, '<view class="library-actions">', '</view>', 'parent-wrongbook PDF action group');
  expectOnePrimaryInBlock(pages.wrongbook, '<view class="topic-edit-actions">', '</view>', 'parent-wrongbook topic edit action group');
  expectRule(pageStyles.wrongbook, '.library-actions', 'flex-direction: column;');
  expectRule(pageStyles.wrongbook, '.library-btn', 'white-space: nowrap;');
  expectRule(pageStyles.wrongbook, '.item-question', 'word-break: break-all;');
});

check('active mini program pages do not present prototype, demo, temporary, debug, or internal test UI', () => {
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
  const pagesDir = path.join(miniRoot, 'pages');
  for (const pageDir of fs.readdirSync(pagesDir)) {
    const wxmlPath = path.join(pagesDir, pageDir, 'index.wxml');
    if (!fs.existsSync(wxmlPath)) {
      continue;
    }
    const text = fs.readFileSync(wxmlPath, 'utf8');
    for (const pattern of forbidden) {
      if (pattern.test(text)) {
        throw new Error(`${path.relative(root, wxmlPath)} contains ${pattern}`);
      }
    }
  }
});

if (failures > 0) {
  process.exit(1);
}

console.log('final mini program visual acceptance contracts passed');
NODE

run "$VISUAL_PROOF"
run "$UPLOAD_PROOF"

if [[ "${XR_RALPH_ALLOW_CURRENT_STORY_PENDING:-}" == "1" ]]; then
  echo
  echo "mini program visual acceptance guardrail passed in pre-completion mode"
else
  echo
  echo "mini program visual acceptance guardrail passed"
fi
