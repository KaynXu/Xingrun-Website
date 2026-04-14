import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

import * as AppModule from './App';

test('landing page renders Starain hero branding and a theme-aware grainient hero background', () => {
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
  assert.match(markup, /学习全流程 AI 平台/);
  assert.match(markup, /Starain，用 AI 赋能教育机构。/);
  assert.match(markup, /Starain 正在把日常教学里最常重复的工作整理进同一套平台流程/);
  assert.match(markup, /查看平台方案/);
  assert.match(markup, /href="#features"/);
  assert.match(markup, /申请开通机构/);
  assert.match(markup, /data-background="grainient"/);
  assert.match(markup, /data-grainient-palette="sky-cyan"/);
  assert.match(markup, /data-grainient-motion="pronounced"/);
  assert.doesNotMatch(markup, /data-stream-src=/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});

test('landing hero uses exhibition-panel copy with a light result preview instead of a white dashboard card', () => {
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

  assert.match(markup, /服务学校与机构的 AI 教育平台/);
  assert.match(markup, /复习资料生成/);
  assert.match(markup, /错题跟进与复习安排/);
  assert.match(markup, /教师协作交付/);
  assert.match(markup, /平台概览/);
  assert.match(markup, /面向学习全流程的 AI 教育平台/);
  assert.match(markup, /复习资料/);
  assert.match(markup, /错题跟进/);
  assert.match(markup, /教学交付/);
  assert.doesNotMatch(markup, /rounded-\[2rem\] border border-sky-100 bg-white\/85 p-5 sm:p-8 md:p-12/);
  assert.doesNotMatch(markup, /题库系统/);
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
  assert.match(markup, /把错误整理成可持续跟进记录/);
  assert.match(markup, /把题目整理成可复用的教学素材/);
  assert.match(markup, /围绕课堂练习、作业和错题记录，帮助老师逐步整理出更稳定的讲义与练习素材。/);
  assert.match(markup, /题目整理/);
  assert.doesNotMatch(markup, /AP、A-Level、IB/);
  assert.doesNotMatch(markup, /AP \/ A-Level \/ IB/);
  assert.match(markup, /把课程目标转化为讲义与教研交付/);
  assert.match(markup, /课堂录音、笔记与教学内容进入平台后/);
  assert.match(markup, /课堂分析/);
  assert.match(markup, /复习资料生成/);
  assert.match(markup, /教学交付/);
  assert.match(markup, /关于 Starain/);
  assert.match(markup, /不是从 PPT 里想出来的/);
  assert.doesNotMatch(markup, /把错误沉淀成可追踪资产/);
  assert.doesNotMatch(markup, /把题目沉淀成可调用的题库系统/);
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
  assert.match(markup, /学习全流程 AI 平台/);
  assert.doesNotMatch(markup, /星润 AI 教育解决方案/);
});

test('landing and legal pages use the bright Starain shell', () => {
  const LandingPage = (AppModule as {
    LandingPage?: React.ComponentType<{
      onLogin: () => void;
      onRegister: () => void;
    }>;
  }).LandingPage;
  const LandingLegalPage = (AppModule as {
    LandingLegalPage?: React.ComponentType<{
      documentKey: 'privacy' | 'terms';
    }>;
  }).LandingLegalPage;

  assert.equal(typeof LandingPage, 'function');
  assert.equal(typeof LandingLegalPage, 'function');

  const landingMarkup = renderToStaticMarkup(
    <LandingPage onLogin={() => undefined} onRegister={() => undefined} />,
  );
  const legalMarkup = renderToStaticMarkup(
    <LandingLegalPage documentKey="terms" />,
  );

  assert.doesNotMatch(landingMarkup, /min-h-screen bg-black text-white/);
  assert.doesNotMatch(legalMarkup, /min-h-screen bg-black text-white/);
  assert.match(landingMarkup, /bg-\[#F6FBFF\]/);
  assert.match(landingMarkup, /text-slate-900/);
  assert.match(legalMarkup, /bg-\[#F6FBFF\]/);
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

test('landing page keeps a single about link per nav group and exposes a dark mode toggle', () => {
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

  assert.equal((markup.match(/href="#about"/g) ?? []).length, 2);
  assert.doesNotMatch(markup, /我们的故事/);
  assert.match(markup, /aria-label="切换夜间模式"/);
  assert.match(markup, /dark:bg-\[#0d1220\]/);
  assert.match(markup, /dark:border-white\/8/);
  assert.match(markup, /dark:text-slate-400/);
});

test('landing page dark mode styles cover the about section and footer shell', () => {
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

  assert.match(markup, /id="about" class="border-t border-sky-100\/80 py-24 dark:border-white\/8"/);
  assert.match(markup, /ABOUT STARAIN/);
  assert.match(markup, /dark:bg-slate-950\/35 dark:text-sky-200/);
  assert.match(markup, /dark:bg-\[linear-gradient\(180deg,rgba\(2,6,23,0\.42\)_0%,rgba\(15,23,42,0\.7\)_100%\)\]/);
  assert.match(markup, /dark:text-white/);
  assert.match(markup, /<footer class="border-t border-sky-100\/80 py-20 dark:border-white\/8"/);
  assert.match(markup, /保留所有权利/);
});

test('landing page source does not contain stray navbar characters after the brand block', () => {
  const appSource = readFileSync(new URL('./App.tsx', import.meta.url), 'utf8');

  assert.doesNotMatch(appSource, /<\/div>˜/);
  assert.doesNotMatch(appSource, /˜/);
});

test('landing feature cards swap to dark-specific surfaces instead of pale demo panels', () => {
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

  assert.match(markup, /dark:border-white\/10 dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.96\)_0%,rgba\(15,23,42,0\.9\)_100%\)\]/);
  assert.match(markup, /dark:bg-\[linear-gradient\(180deg,rgba\(15,23,42,0\.92\)_0%,rgba\(30,41,59,0\.88\)_100%\)\]/);
  assert.match(markup, /dark:bg-slate-900\/88/);
  assert.doesNotMatch(markup, /dark:bg-slate-700\/50/);
  assert.doesNotMatch(markup, /dark:bg-slate-600\/50/);
});
