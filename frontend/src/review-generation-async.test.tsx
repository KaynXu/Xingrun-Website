import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

test('review generation source tracks async lesson status fields', () => {
  assert.match(appSource, /record_status\?: string;/);
  assert.match(appSource, /generation_error\?: string;/);
});

test('review history source polls review plans while pending lessons exist', () => {
  assert.match(appSource, /const hasPendingLesson = lessons\.some\(\(lesson\) => lesson\.record_status === 'pending'\);/);
  assert.match(appSource, /const timer = window\.setInterval\(\(\) => \{\s*void load\(true\);\s*\}, 3000\);/);
  assert.match(appSource, /return \(\) => window\.clearInterval\(timer\);/);
});

test('review history source renders pending and failed status copy', () => {
  assert.match(appSource, /lesson\.record_status === 'pending'\s*\?\s*'生成中'/);
  assert.match(appSource, /lesson\.record_status === 'failed'/);
  assert.match(appSource, /'生成失败'/);
  assert.match(appSource, /lesson\.generation_error/);
  assert.match(appSource, /可离开页面，完成后会出现在列表中/);
});

test('review generation page closes composer after async creation succeeds', () => {
  assert.match(appSource, /const handleFormSuccess = \(\) => \{\s*setComposerOpen\(false\);/);
});
