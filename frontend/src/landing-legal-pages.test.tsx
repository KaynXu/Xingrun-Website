import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('landing page renders Starain hero branding and approved messaging', () => {
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

  assert.match(markup, /Starain/);
  assert.match(markup, /AI Edu Platform/);
  assert.match(markup, /教育工作流终于被 AI 重新组织好了/);
  assert.match(markup, /查看平台方案/);
  assert.match(markup, /href="#features"/);
  assert.match(markup, /申请试用/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});

test('landing page tells the validated workflow story', () => {
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

  assert.match(markup, /从课堂素材到复习交付/);
  assert.match(markup, /把错误沉淀成可追踪资产/);
  assert.match(markup, /把题目沉淀成可调用的题库系统/);
  assert.match(markup, /把课程目标转化为讲义与教研交付/);
  assert.match(markup, /教学素材进入平台/);
  assert.match(markup, /AI 完成结构化处理/);
  assert.match(markup, /输出到复习与教学协同/);
  assert.match(markup, /关于 Starain/);
  assert.match(markup, /不是从 PPT 里想出来的/);
});

test('legal pages use Starain branding in the chrome', () => {
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingLegalPage, 'function');

  const markup = renderToStaticMarkup(
    <LandingLegalPage documentKey="privacy" />,
  );

  assert.match(markup, /Starain/);
  assert.match(markup, /AI Edu Platform/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});

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
