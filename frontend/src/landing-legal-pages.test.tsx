import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('landing page footer exposes standalone legal page links', () => {
  const LandingPage = (AppModule as {
    LandingPage?: React.ComponentType<{
      onLogin: () => void;
      onRegister: () => void;
    }>;
  }).LandingPage;

  assert.equal(typeof LandingPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );

  assert.match(markup, /href="#privacy-policy"/);
  assert.match(markup, /href="#terms-of-service"/);
});

test('privacy policy page renders privacy-specific sections', () => {
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingLegalPage documentKey="privacy" />,
  );

  assert.match(markup, /隐私政策/);
  assert.match(markup, /我们如何收集和使用信息/);
  assert.match(markup, /课堂录音、笔记、PDF/);
});

test('terms page renders service-boundary sections', () => {
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingLegalPage documentKey="terms" />,
  );

  assert.match(markup, /服务条款/);
  assert.match(markup, /账号注册与使用/);
  assert.match(markup, /AI 生成内容说明/);
  assert.match(markup, /争议解决/);
});

test('landing app hash helper maps legal hashes to standalone pages', () => {
  const getLandingLegalPageFromHash = (AppModule as {
    getLandingLegalPageFromHash?: (
      hash: string,
    ) => 'privacy' | 'terms' | null;
  }).getLandingLegalPageFromHash;

  assert.equal(typeof getLandingLegalPageFromHash, 'function');
  assert.equal(getLandingLegalPageFromHash('#privacy-policy'), 'privacy');
  assert.equal(getLandingLegalPageFromHash('#terms-of-service'), 'terms');
  assert.equal(getLandingLegalPageFromHash('#features'), null);
});
