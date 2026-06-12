import React, { useEffect, useState } from 'react';
import { Home, Moon, ShieldCheck, Sun } from 'lucide-react';

export type LandingLegalDocumentKey = 'privacy' | 'terms';

const landingLegalDocuments: Record<
  LandingLegalDocumentKey,
  {
    title: string;
    summary: string;
    updatedAt: string;
    sections: Array<{ title: string; paragraphs: string[] }>;
  }
> = {
  privacy: {
    title: '隐私政策',
    summary: '本政策说明 Starain 在账号申请、课堂材料上传、AI 处理与教学交付过程中如何收集、使用、保存与保护相关信息。',
    updatedAt: '2026-03-27',
    sections: [
      {
        title: '我们如何收集和使用信息',
        paragraphs: [
          '当你申请注册、登录或使用机构账号时，我们会收集并使用你主动提交的账号信息、姓名、机构名称以及必要的身份校验信息，用于完成账号开通、权限管理与服务支持。',
          '当你使用产品处理教学内容时，我们可能处理课堂录音、笔记、PDF、课程主题、题目素材以及对应的 AI 生成结果，用于生成课后复习资料、题库内容、讲义草稿和相关教学交付材料。',
        ],
      },
      {
        title: 'AI 处理与第三方服务',
        paragraphs: [
          '在你启用相关 AI 能力时，系统可能会将完成处理所必需的教学材料发送给当前配置的模型服务提供方，用于生成摘要、题目或结构化内容。',
        ],
      },
    ],
  },
  terms: {
    title: '服务条款',
    summary: '本条款说明 Starain 账号、平台能力与 AI 教学支持服务的使用边界、责任分工与争议处理规则。',
    updatedAt: '2026-03-27',
    sections: [
      {
        title: '账号注册与使用',
        paragraphs: [
          '你应保证注册信息真实、完整，并妥善保管账号与密码，不得向未授权人员共享平台访问权限。',
        ],
      },
      {
        title: 'AI 生成内容说明',
        paragraphs: [
          'AI 生成结果仅作为教学支持与效率工具，不当然构成专业、准确或适用于所有场景的最终结论。你应结合课程目标、学生情况和人工审阅进行必要校对后再对外使用。',
        ],
      },
      {
        title: '争议解决',
        paragraphs: [
          '本条款的订立、履行与解释适用中华人民共和国相关法律法规。如因使用本服务发生争议，双方应优先友好协商。',
        ],
      },
    ],
  },
};

export function getLandingLegalPageFromHash(hash: string): LandingLegalDocumentKey | null {
  if (hash === '#privacy-policy') {
    return 'privacy';
  }
  if (hash === '#terms-of-service') {
    return 'terms';
  }
  return null;
}

export function LandingLegalPage({ documentKey }: { documentKey: LandingLegalDocumentKey }) {
  const document = landingLegalDocuments[documentKey];

  return (
    <div className="min-h-screen bg-[#F6FBFF] text-slate-900 selection:bg-sky-200/70 dark:bg-[#0d1220] dark:text-slate-100">
      <nav className="sticky top-0 z-50 border-b border-sky-100/80 bg-white/80 backdrop-blur-xl dark:border-white/8 dark:bg-[#0d1220]/95">
        <div className="mx-auto flex h-20 max-w-5xl items-center justify-between gap-4 px-6">
          <div className="flex items-center gap-3 min-w-0">
            <img src="/logo.png" alt="Starain logo" className="h-11 w-11 object-contain" />
            <div className="min-w-0">
              <p className="truncate text-lg font-bold tracking-tight dark:text-white">Starain</p>
              <p className="text-xs tracking-[0.28em] text-sky-700">学习全流程 AI 平台</p>
            </div>
          </div>
          <a
            href="#"
            className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition-colors hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
          >
            <Home size={16} />
            返回首页
          </a>
        </div>
      </nav>

      <main className="relative z-10 mx-auto max-w-5xl px-6 py-16 md:py-24">
        <div className="rounded-[2rem] border border-sky-100 bg-white/85 p-8 shadow-[0_30px_90px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-800/80 md:p-12">
          <div className="flex flex-col gap-5 border-b border-sky-100 pb-8 dark:border-white/10">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-xs font-semibold tracking-[0.24em] text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">
              <ShieldCheck size={14} />
              法律文件
            </div>
            <div className="space-y-4">
              <h1 className="text-4xl font-black tracking-tight dark:text-white md:text-5xl">{document.title}</h1>
              <p className="max-w-3xl text-base leading-8 text-slate-600 dark:text-slate-300 md:text-lg">{document.summary}</p>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400">最近更新：{document.updatedAt}</p>
          </div>

          <div className="mt-10 space-y-8">
            {document.sections.map((section) => (
              <section
                key={section.title}
                className="rounded-[1.5rem] border border-sky-100 bg-white/90 p-6 shadow-[0_16px_48px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-slate-800/75 md:p-7"
              >
                <h2 className="text-2xl font-bold tracking-tight dark:text-white">{section.title}</h2>
                <div className="mt-4 space-y-4 text-sm leading-8 text-slate-600 dark:text-slate-300 md:text-base">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </main>

      <footer className="border-t border-sky-100/80 py-20 dark:border-white/8">
        <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-5 px-6 text-sm text-slate-500 dark:text-slate-400 md:flex-row">
          <p>© 2026 Starain. 保留所有权利。</p>
          <div className="flex items-center gap-6">
            <a href="#privacy-policy" className="transition-colors hover:text-slate-900 dark:hover:text-white">隐私政策</a>
            <a href="#terms-of-service" className="transition-colors hover:text-slate-900 dark:hover:text-white">服务条款</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

type LandingPageProps = {
  onLogin: () => void;
  onRegister?: () => void;
  onApplyOrganization?: () => void;
  onJoinOrganization?: () => void;
  activeLegalPage?: LandingLegalDocumentKey | null;
  isDark?: boolean;
  onToggleDarkMode?: () => void;
};

const landingFeatureCards = [
  {
    title: '复习资料生成',
    text: '把课程目标转化为讲义与教研交付，围绕课堂录音、笔记与教学内容进入平台后形成更稳定的复盘链路。',
    tone: 'dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]',
  },
  {
    title: '错题跟进与复习安排',
    text: '把错误整理成可持续跟进记录，帮助老师逐步安排错题跟进与复习安排。',
    tone: 'dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(30,41,59,0.88)_100%)]',
  },
  {
    title: '教师协作交付',
    text: '把课程目标、课堂分析、复习资料生成与教学交付串到同一条协作链路。',
    tone: 'dark:bg-slate-900/88',
  },
];

export function LandingPage({
  onLogin,
  onRegister,
  onApplyOrganization,
  onJoinOrganization,
  activeLegalPage,
  isDark = false,
  onToggleDarkMode,
}: LandingPageProps) {
  const [hashLegalPage, setHashLegalPage] = useState<LandingLegalDocumentKey | null>(() =>
    typeof window === 'undefined' ? null : getLandingLegalPageFromHash(window.location.hash),
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }
    const syncHash = () => setHashLegalPage(getLandingLegalPageFromHash(window.location.hash));
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  const legalPage = activeLegalPage ?? hashLegalPage;
  if (legalPage) {
    return <LandingLegalPage documentKey={legalPage} />;
  }

  const handleRegister = onApplyOrganization ?? onRegister ?? (() => undefined);
  const handleJoin = onJoinOrganization ?? (() => undefined);

  return (
    <div
      className="min-h-screen bg-[#F6FBFF] text-slate-900 dark:bg-[#0d1220] dark:text-slate-100"
      data-background="grainient"
      data-grainient-palette="sky-cyan"
      data-grainient-motion="pronounced"
      data-grainient-style="flow-bands"
    >
      <header className="border-b border-sky-100/80 dark:border-white/8">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-5">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Starain logo" className="h-11 w-11 object-contain" />
            <div>
              <p className="text-lg font-bold tracking-tight">Starain</p>
              <p className="text-xs tracking-[0.28em] text-sky-700">学习全流程 AI 平台</p>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm text-slate-500 dark:text-slate-400">
            <a href="#features">查看平台方案</a>
            <a href="#about">关于 Starain</a>
            <button
              type="button"
              aria-label="切换夜间模式"
              onClick={onToggleDarkMode}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-sky-200 bg-white text-slate-700 transition hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-200 dark:hover:bg-white/10"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-16 md:py-24">
        <section className="grid gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)] lg:items-center">
          <div className="space-y-6">
            <p className="inline-flex w-fit rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-xs font-semibold tracking-[0.24em] text-sky-700 dark:border-sky-500/30 dark:bg-slate-950/35 dark:text-sky-200">
              用ai创造教育
            </p>
            <div className="space-y-4">
              <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">服务学校与机构的 AI 教育平台</p>
              <h1 className="max-w-4xl text-5xl font-black tracking-tight text-slate-900 dark:text-white md:text-6xl">
                Starain 正在把日常教学里最常重复的工作整理进同一套平台流程
              </h1>
              <p className="max-w-3xl text-lg leading-8 text-slate-600 dark:text-slate-300">
                面向学习全流程的 AI 教育平台，从课堂素材到复习交付，把课程目标转化为讲义与教研交付。
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <button type="button" onClick={handleRegister} className="rounded-full bg-sky-600 px-6 py-3 text-sm font-semibold text-white shadow-[0_16px_40px_rgba(34,199,232,0.24)] transition hover:bg-sky-500">
                申请开通机构
              </button>
              <button type="button" onClick={onLogin} className="rounded-full border border-sky-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10">
                机构登录
              </button>
              <button type="button" onClick={handleJoin} className="rounded-full border border-sky-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-sky-50 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10">
                加入机构
              </button>
            </div>
          </div>

          <div className="rounded-[2rem] border border-sky-100 bg-white/90 p-6 shadow-[0_30px_80px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-900/88">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-sky-700 dark:text-sky-300">平台概览</p>
            <div className="mt-6 grid gap-4">
              <div className="rounded-[1.5rem] border border-sky-100 bg-white p-5 shadow-[0_16px_40px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">复习资料</p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">课堂分析、复习资料生成、教学交付。</p>
              </div>
              <div className="rounded-[1.5rem] border border-sky-100 bg-white p-5 shadow-[0_16px_40px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(30,41,59,0.88)_100%)]">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">错题跟进</p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">把错误整理成可持续跟进记录，安排后续复习。</p>
              </div>
              <div className="rounded-[1.5rem] border border-sky-100 bg-white p-5 shadow-[0_16px_40px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-slate-900/88">
                <p className="text-sm font-semibold text-slate-900 dark:text-white">教学交付</p>
                <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">把题目整理成可复用的教学素材，支持教师协作交付。</p>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="mt-20 grid gap-6 md:grid-cols-3">
          {landingFeatureCards.map((card) => (
            <article
              key={card.title}
              className={`rounded-[1.75rem] border border-sky-100 bg-white/92 p-6 shadow-[0_18px_44px_rgba(47,128,237,0.06)] ${card.tone}`}
            >
              <h2 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">{card.title}</h2>
              <p className="mt-3 text-sm leading-7 text-slate-600 dark:text-slate-300">{card.text}</p>
            </article>
          ))}
        </section>

        <section className="mt-20 grid gap-8 rounded-[2rem] border border-sky-100 bg-white/92 p-8 shadow-[0_24px_54px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.42)_0%,rgba(15,23,42,0.7)_100%)] lg:grid-cols-2">
          <div className="space-y-4">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-slate-500 dark:text-slate-400">从课堂素材到复习交付</p>
            <h2 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">课堂录音、笔记与教学内容进入平台后</h2>
            <p className="text-base leading-8 text-slate-600 dark:text-slate-300">
              把课程目标转化为讲义与教研交付，围绕课堂练习、作业和错题记录，帮助老师逐步整理出更稳定的讲义与练习素材。
            </p>
          </div>
          <div className="space-y-4 rounded-[1.5rem] border border-sky-100 bg-white/90 p-6 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)]">
            <p className="text-sm font-semibold text-slate-900 dark:text-white">课堂分析</p>
            <p className="text-sm text-slate-600 dark:text-slate-300">复习资料生成</p>
            <p className="text-sm text-slate-600 dark:text-slate-300">教学交付</p>
            <p className="text-sm text-slate-600 dark:text-slate-300">题目整理</p>
          </div>
        </section>

        <section id="about" className="border-t border-sky-100/80 py-24 dark:border-white/8">
          <div className="grid gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div className="space-y-4">
              <p className="text-sm font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">ABOUT STARAIN</p>
              <a href="#about" className="text-sky-700 underline-offset-4 hover:underline dark:text-sky-300">关于 Starain</a>
            </div>
            <div className="space-y-4">
              <p className="text-lg font-semibold text-slate-900 dark:text-white">不是从 PPT 里想出来的</p>
              <p className="text-base leading-8 text-slate-600 dark:text-slate-300">
                Starain 不是从 PPT 里想出来的，而是从老师真实的课堂复盘、题目整理与复习交付流程里一点点长出来的。
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-sky-100/80 py-20 dark:border-white/8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-6 text-sm text-slate-500 dark:text-slate-400 md:flex-row">
          <div className="space-y-2">
            <p>© 2026 Starain.</p>
            <p>保留所有权利</p>
          </div>
          <div className="flex flex-wrap items-center gap-5">
            <a href="#privacy-policy">隐私政策</a>
            <a href="#terms-of-service">服务条款</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
