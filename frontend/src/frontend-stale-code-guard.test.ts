import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { extname, join, relative, resolve } from 'node:path';
import { tmpdir } from 'node:os';

type DeprecatedFrontendGuard = {
  term: string;
  pattern: RegExp;
  reason: string;
};

const ACTIVE_SOURCE_ROOTS = [resolve(process.cwd(), 'src')];
const ACTIVE_SOURCE_EXTENSIONS = new Set(['.css', '.js', '.jsx', '.ts', '.tsx']);
const IGNORED_SOURCE_PATTERNS = [/\.test\.[cm]?[jt]sx?$/, /\.d\.ts$/];
const REQUIRED_GUARDED_TERMS = [
  '欢迎回来',
  '直接进入真实可用的教学动作',
  '不伪造任务列表',
  '首页聚焦已经可用的机构管理入口',
  '保留真实概览壳层',
  '当前首页只保留真实入口说明',
  'AI 会整理成统一的复习资料与后续教学素材',
  '系统会帮你',
  '让 AI 只做解析和预览',
  '还没有草稿。先粘贴原始文本，再点击“开始解析”。',
  '先这样再那样',
  '老师这里只保留是否掌握的勾选',
  '保存失败时会保留当前草稿，便于继续修改后重试',
  '把当前题目按错题库文档方式展开',
  '查看这个孩子当前记录，并直接保存跟进内容',
  'downloadWrongQuestionSummary(filters)',
  '导出汇总',
  '只看待教师跟进',
  'onlyPendingReview',
  'buildWrongQuestionSummaryExportPath',
  'downloadWrongQuestionSummary',
  'summary/export',
];

const DEPRECATED_FRONTEND_GUARDS: DeprecatedFrontendGuard[] = [
  {
    term: '欢迎回来',
    pattern: /欢迎回来/,
    reason: 'handoff: workspace conversational copy was removed',
  },
  {
    term: '直接进入真实可用的教学动作',
    pattern: /直接进入真实可用的教学动作/,
    reason: 'existing dashboard test: placeholder narration was removed',
  },
  {
    term: '不伪造任务列表',
    pattern: /不伪造任务列表/,
    reason: 'existing dashboard test: placeholder narration was removed',
  },
  {
    term: '首页聚焦已经可用的机构管理入口',
    pattern: /首页聚焦已经可用的机构管理入口/,
    reason: 'existing dashboard test: placeholder narration was removed',
  },
  {
    term: '保留真实概览壳层',
    pattern: /保留真实概览壳层/,
    reason: 'existing dashboard test: placeholder narration was removed',
  },
  {
    term: '当前首页只保留真实入口说明',
    pattern: /当前首页只保留真实入口说明/,
    reason: 'existing dashboard test: placeholder narration was removed',
  },
  {
    term: 'AI 会整理成统一的复习资料与后续教学素材',
    pattern: /AI 会整理成统一的复习资料与后续教学素材/,
    reason: 'existing dashboard test: assistant-style copy was removed',
  },
  {
    term: '系统会帮你',
    pattern: /系统会(?:先)?帮你/,
    reason: 'handoff: assistant-style field narration was removed',
  },
  {
    term: '让 AI 只做解析和预览',
    pattern: /让 AI 只做解析和预览/,
    reason: 'existing dashboard test: assistant-style copy was removed',
  },
  {
    term: '还没有草稿。先粘贴原始文本，再点击“开始解析”。',
    pattern: /还没有草稿。先粘贴原始文本，再点击“开始解析”。/,
    reason: 'existing dashboard test: step-by-step placeholder copy was removed',
  },
  {
    term: '先这样再那样',
    pattern: /先这样再那样/,
    reason: 'handoff: assistant-style step narration was removed',
  },
  {
    term: '老师这里只保留是否掌握的勾选',
    pattern: /老师这里只保留是否掌握的勾选/,
    reason: 'existing smart-wrong-question test: conversational guidance was removed',
  },
  {
    term: '保存失败时会保留当前草稿，便于继续修改后重试',
    pattern: /保存失败时会保留当前草稿，便于继续修改后重试/,
    reason: 'existing smart-wrong-question test: conversational guidance was removed',
  },
  {
    term: '把当前题目按错题库文档方式展开',
    pattern: /把当前题目按错题库文档方式展开/,
    reason: 'existing smart-wrong-question test: conversational guidance was removed',
  },
  {
    term: '查看这个孩子当前记录，并直接保存跟进内容',
    pattern: /查看这个孩子当前记录，并直接保存跟进内容/,
    reason: 'existing smart-wrong-question test: conversational guidance was removed',
  },
  {
    term: 'downloadWrongQuestionSummary(filters)',
    pattern: /downloadWrongQuestionSummary\(filters\)/,
    reason: 'existing smart-wrong-question test: removed summary export action',
  },
  {
    term: '导出汇总',
    pattern: /导出汇总/,
    reason: 'handoff: old smart-wrong-question summary export UI was removed',
  },
  {
    term: '只看待教师跟进',
    pattern: /只看待教师跟进/,
    reason: 'handoff: old pending-review filter UI was removed',
  },
  {
    term: 'onlyPendingReview',
    pattern: /onlyPendingReview/,
    reason: 'handoff: old pending-review query path was removed',
  },
  {
    term: 'buildWrongQuestionSummaryExportPath',
    pattern: /buildWrongQuestionSummaryExportPath/,
    reason: 'existing smart-wrong-question test: removed summary export helper',
  },
  {
    term: 'downloadWrongQuestionSummary',
    pattern: /downloadWrongQuestionSummary/,
    reason: 'existing smart-wrong-question test: removed summary export helper',
  },
  {
    term: 'summary/export',
    pattern: /summary\/export/,
    reason: 'existing smart-wrong-question test: removed summary export endpoint path',
  },
];

function isActiveSourceFile(filePath: string): boolean {
  return ACTIVE_SOURCE_EXTENSIONS.has(extname(filePath)) && !IGNORED_SOURCE_PATTERNS.some((pattern) => pattern.test(filePath));
}

function collectSourceFiles(root: string): string[] {
  const entries = readdirSync(root).sort();
  const files: string[] = [];

  for (const entry of entries) {
    const entryPath = join(root, entry);
    const stats = statSync(entryPath);

    if (stats.isDirectory()) {
      files.push(...collectSourceFiles(entryPath));
      continue;
    }

    if (stats.isFile() && isActiveSourceFile(entryPath)) {
      files.push(entryPath);
    }
  }

  return files;
}

function collectDeprecatedFrontendMatches(sourceRoots: string[]): string[] {
  const matches: string[] = [];

  for (const sourceRoot of sourceRoots) {
    for (const filePath of collectSourceFiles(sourceRoot)) {
      const source = readFileSync(filePath, 'utf8');

      for (const guard of DEPRECATED_FRONTEND_GUARDS) {
        if (guard.pattern.test(source)) {
          matches.push(`${relative(process.cwd(), filePath)}: ${guard.term} (${guard.reason})`);
        }
      }
    }
  }

  return matches;
}

test('frontend stale-code guard tracks the documented deprecated website UI terms', () => {
  assert.deepEqual(
    DEPRECATED_FRONTEND_GUARDS.map((guard) => guard.term),
    REQUIRED_GUARDED_TERMS,
  );
});

test('frontend stale-code guard detects deprecated terms in active source files only', () => {
  const tempRoot = mkdtempSync(join(tmpdir(), 'frontend-stale-code-guard-'));
  const sourceRoot = join(tempRoot, 'src');

  try {
    mkdirSync(sourceRoot);
    writeFileSync(join(sourceRoot, 'ActivePanel.tsx'), '<button>欢迎回来</button>');
    writeFileSync(join(sourceRoot, 'ActivePanel.test.tsx'), '<button>导出汇总</button>');

    assert.deepEqual(collectDeprecatedFrontendMatches([sourceRoot]), [
      `${relative(process.cwd(), join(sourceRoot, 'ActivePanel.tsx'))}: 欢迎回来 (handoff: workspace conversational copy was removed)`,
    ]);
  } finally {
    rmSync(tempRoot, { recursive: true, force: true });
  }
});

test('active website frontend source keeps removed copy and dead paths out', () => {
  assert.deepEqual(collectDeprecatedFrontendMatches(ACTIVE_SOURCE_ROOTS), []);
});
