import test from 'node:test';
import assert from 'node:assert/strict';
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
  assert.match(markup, /教学工作平台/);
  assert.match(markup, /老师工作里的 AI 工具/);
  assert.match(markup, /帮老师整理复习资料、记录错题、准备讲义。/);
  assert.match(markup, /申请试用/);
  assert.match(markup, /href="#privacy-policy"/);
  assert.match(markup, /href="#terms-of-service"/);
  assert.doesNotMatch(markup, /学习全流程 AI 平台/);
  assert.doesNotMatch(markup, /data-background="grainient"/);
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

  assert.match(markup, /复习计划生成/);
  assert.match(markup, /课堂材料/);
  assert.match(markup, /课堂录音/);
  assert.match(markup, /补充笔记/);
  assert.match(markup, /生成复习计划/);
  assert.match(markup, /讲义大纲/);
  assert.match(markup, /课后练习/);
  assert.doesNotMatch(markup, /服务学校与机构的 AI 教育平台/);
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

  assert.match(markup, /课堂内容整理成复习资料/);
  assert.match(markup, /错题记录集中保存/);
  assert.match(markup, /题目和讲义继续整理/);
  assert.match(markup, /讲义和教研材料放在一起/);
  assert.match(markup, /关于 Starain/);
  assert.match(markup, /复习资料、错题跟进、讲义整理和教师协作，集中放在同一套工作流里。/);
  assert.doesNotMatch(markup, /不是从 PPT 里想出来的/);
  assert.doesNotMatch(markup, /AP、A-Level、IB/);
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
  assert.match(markup, /教学工作平台/);
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
  assert.match(landingMarkup, /bg-white/);
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
  assert.match(markup, /账号与使用边界/);
  assert.match(markup, /AI 结果与责任分工/);
  assert.match(markup, /服务调整与争议处理/);
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

  assert.match(markup, /id="about"/);
  assert.doesNotMatch(markup, /href="#about"/);
  assert.match(markup, /aria-label="切换夜间模式"/);
  assert.match(markup, /dark:bg-slate-950/);
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
  assert.match(markup, /关于 Starain/);
  assert.match(markup, /教学工作平台/);
  assert.match(markup, /面向学校、机构和教学团队的教学工作平台。/);
  assert.match(markup, /dark:text-white/);
  assert.match(markup, /<footer class="border-t border-sky-100\/80 py-20 dark:border-white\/8"/);
  assert.match(markup, /保留所有权利/);
});

test('landing page markup does not contain stray navbar characters after the brand block', () => {
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

  assert.doesNotMatch(markup, /<\/div>˜/);
  assert.doesNotMatch(markup, /˜/);
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
