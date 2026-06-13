import { useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Database,
  FileText,
  Home,
  Moon,
  ShieldCheck,
  Sun,
} from 'lucide-react';
import { motion } from 'motion/react';

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
          '我们会尽量控制处理范围，仅在完成对应功能所需的最小范围内进行传输和存储。',
        ],
      },
      {
        title: '数据保存与安全',
        paragraphs: [
          '平台会结合账号权限、机构边界和运行日志对数据访问进行控制，并采取合理的技术与管理措施降低未授权访问、披露或丢失风险。',
          '如你需要更正、删除相关信息或咨询数据处理方式，可通过平台提供的机构管理与服务支持渠道联系我们。',
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
        title: '账号与使用边界',
        paragraphs: [
          '机构账号、成员账号及其对应权限由平台和机构管理员共同维护。你应确保提交的信息真实、准确，并妥善保管登录凭证。',
          '未经授权，你不得干扰平台运行、绕过权限控制、非法获取其他机构数据，或将平台用于违反法律法规及教学伦理的场景。',
        ],
      },
      {
        title: 'AI 结果与责任分工',
        paragraphs: [
          '平台提供的 AI 生成结果用于辅助教学、整理资料与提升协作效率，不应被视为对教学判断的完全替代。',
          '机构和使用者应根据自身教学要求对生成内容进行必要复核，并对最终对外交付或教学使用结果负责。',
        ],
      },
      {
        title: '服务调整与争议处理',
        paragraphs: [
          '我们可在必要时对平台功能、接口和运营规则进行更新，并通过适当方式通知受影响的用户或机构。',
          '如因使用本服务发生争议，双方应优先友好协商；协商不成的，按适用法律法规和约定规则处理。',
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
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-12%] left-[-8%] h-[28rem] w-[28rem] rounded-full bg-sky-200/45 blur-[120px]" />
        <div className="absolute right-[-10%] top-[10%] h-[24rem] w-[24rem] rounded-full bg-cyan-200/40 blur-[110px]" />
        <div className="absolute bottom-[-12%] left-[18%] h-[22rem] w-[22rem] rounded-full bg-blue-100/70 blur-[120px]" />
      </div>

      <nav className="sticky top-0 z-50 border-b border-sky-100/80 bg-white/80 backdrop-blur-xl dark:border-white/8 dark:bg-[#0d1220]/95">
        <div className="mx-auto flex h-20 max-w-5xl items-center justify-between gap-4 px-6">
          <div className="flex min-w-0 items-center gap-3">
            <img src="/logo.png" alt="Starain logo" className="h-11 w-11 object-contain" />
            <div className="min-w-0">
              <p className="truncate text-lg font-bold tracking-tight dark:text-white">Starain</p>
              <p className="text-xs tracking-[0.28em] text-sky-700 dark:text-sky-300">教学工作平台</p>
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
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="rounded-[2rem] border border-sky-100 bg-white/85 p-8 shadow-[0_30px_90px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-800/80 md:p-12"
        >
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
        </motion.div>
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

export function LandingPage({
  onLogin,
  onRegister,
  onApplyOrganization,
  onJoinOrganization: _onJoinOrganization,
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

    const syncLandingLegalPage = () => {
      setHashLegalPage(getLandingLegalPageFromHash(window.location.hash));
    };

    syncLandingLegalPage();
    window.addEventListener('hashchange', syncLandingLegalPage);
    return () => window.removeEventListener('hashchange', syncLandingLegalPage);
  }, []);

  const legalPage = activeLegalPage ?? hashLegalPage;

  if (legalPage) {
    return <LandingLegalPage documentKey={legalPage} />;
  }

  const handleRegister = onApplyOrganization ?? onRegister ?? (() => undefined);
  const previewActions = [
    '生成复习计划',
    '生成讲义',
    '生成小测',
    '讲评错题',
    '整理白板',
    '调整难度',
  ];
  const previewOutputs = [
    { title: '复习计划', tone: 'bg-[#315c72]' },
    { title: '讲义大纲', tone: 'bg-[#516d43]' },
    { title: '课堂小测', tone: 'bg-[#6d2f4f]' },
    { title: '错题讲评', tone: 'bg-[#2e5971]' },
    { title: '复习清单', tone: 'bg-[#7b6a32]' },
    { title: '课后练习', tone: 'bg-[#5c3b67]' },
  ];
  const [activePreviewIndex, setActivePreviewIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActivePreviewIndex((current) => (current + 1) % previewActions.length);
    }, 2400);

    return () => window.clearInterval(timer);
  }, [previewActions.length]);

  return (
    <div className="min-h-screen bg-white text-slate-900 selection:bg-sky-200/70 dark:bg-slate-950 dark:text-slate-100">
      <nav className="fixed top-0 z-50 w-full border-b border-slate-200 bg-white/92 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/96">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Starain logo" className="h-12 w-12 object-contain" />
            <span className="text-xl font-bold tracking-tight">星润Starain</span>
            <span className="hidden text-xs font-semibold uppercase tracking-[0.32em] text-sky-600 sm:block">
              教学工作平台
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onToggleDarkMode}
              className="rounded-full p-2.5 text-slate-500 transition-colors hover:bg-sky-50 dark:text-slate-400 dark:hover:bg-white/10"
              aria-label="切换夜间模式"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              onClick={onLogin}
              className="rounded-full bg-sky-600 px-6 py-2.5 text-sm font-bold text-white shadow-[0_16px_40px_rgba(34,199,232,0.28)] transition-all hover:bg-sky-500 active:scale-95"
            >
              立即登录
            </button>
          </div>
        </div>
      </nav>

      <section className="border-b border-slate-200 bg-white dark:border-white/10 dark:bg-slate-950">
        <div className="mx-auto flex min-h-[calc(100vh-80px)] max-w-7xl items-center px-6 py-16 md:py-20">
          <div className="grid w-full gap-10 lg:grid-cols-[minmax(0,0.74fr)_minmax(0,1.26fr)] lg:items-center">
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
              className="max-w-2xl"
            >
              <div className="inline-flex items-center rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold tracking-[0.22em] text-slate-500 dark:border-white/10 dark:text-slate-400">
                STARAIN WORKSPACE
              </div>
              <h1 className="mt-7 max-w-4xl text-4xl font-black leading-[1.05] tracking-tight text-slate-950 dark:text-white sm:text-5xl md:text-6xl">
                给教学团队用的 AI 工具
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-slate-600 dark:text-slate-300 md:text-lg">
                帮老师整理复习资料、记录错题、准备讲义。
              </p>

              <div className="mt-10 flex flex-col gap-3 sm:flex-row">
                <button
                  onClick={onLogin}
                  className="inline-flex items-center justify-center rounded-full bg-sky-600 px-8 py-3.5 text-base font-bold text-white transition-all hover:bg-sky-500 active:scale-95"
                >
                  立即登录
                </button>
                <button
                  onClick={handleRegister}
                  className="inline-flex items-center justify-center rounded-full border border-sky-200 bg-white px-8 py-3.5 text-base font-bold text-slate-800 transition-all hover:bg-sky-50 active:scale-95 dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10"
                >
                  申请试用
                </button>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 36 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12, duration: 0.78, ease: [0.16, 1, 0.3, 1] }}
              className="w-full lg:ml-auto lg:max-w-[780px]"
            >
              <div
                data-hero-preview="review-plans"
                className="overflow-hidden rounded-[1.75rem] border border-slate-200/80 bg-white shadow-[0_16px_40px_rgba(15,23,42,0.05)] ring-1 ring-slate-100/80 dark:border-white/10 dark:bg-slate-900 dark:ring-white/5"
              >
                <div className="flex items-center justify-between border-b border-slate-200/80 bg-slate-50/70 px-4 py-3 dark:border-white/10 dark:bg-white/[0.02]">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-300" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-white px-3 py-1 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200/70 dark:bg-white/5 dark:text-slate-400 dark:ring-white/10">
                      Review Plans
                    </span>
                    <span className="rounded-full border border-slate-200/80 px-3 py-1 text-[11px] font-medium text-slate-500 dark:border-white/10 dark:text-slate-400">
                      复习计划生成
                    </span>
                  </div>
                </div>

                <div className="p-3.5">
                  <div className="p-1">
                    <div className="grid gap-3 lg:grid-cols-[128px_22px_minmax(0,1fr)] lg:items-center">
                      <div>
                        <div className="rounded-[1.1rem] border border-slate-200/80 bg-white p-2.5 shadow-[0_8px_18px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-slate-900">
                          <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-slate-400">Source Material</p>
                          <div className="mt-2.5 space-y-2">
                            <div className="h-1.5 w-4/5 rounded-full bg-[#9fe7dc]" />
                            <div className="h-1.5 w-full rounded-full bg-[#c9f1ea]" />
                            <div className="h-1.5 w-3/5 rounded-full bg-[#d7f4ef]" />
                          </div>
                          <div className="mt-3 space-y-1.5">
                            {['课堂录音', '补充笔记', '例题讲义'].map((item, index) => (
                              <div key={item} className="flex items-center gap-2">
                                <span className={`h-1.5 rounded-full ${index === 0 ? 'w-16 bg-[#8cded1]' : index === 1 ? 'w-12 bg-slate-200 dark:bg-white/10' : 'w-10 bg-slate-200 dark:bg-white/10'}`} />
                                <span className="whitespace-nowrap text-[10px] text-slate-400">{item}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="relative hidden h-full lg:block">
                        <svg viewBox="0 0 32 248" className="h-full w-full">
                          <path
                            d="M2 124 C10 124, 12 62, 30 48"
                            fill="none"
                            stroke="#4f7392"
                            strokeWidth="1.25"
                            strokeDasharray="4 4"
                          />
                          <path
                            d="M2 124 C10 124, 12 124, 30 124"
                            fill="none"
                            stroke="#4f7392"
                            strokeWidth="1.25"
                            strokeDasharray="4 4"
                          />
                          <path
                            d="M2 124 C10 124, 12 186, 30 202"
                            fill="none"
                            stroke="#4f7392"
                            strokeWidth="1.25"
                            strokeDasharray="4 4"
                          />
                        </svg>
                      </div>

                      <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-3">
                        {previewOutputs.map((output, index) => {
                          const isActive = index === activePreviewIndex;
                          return (
                            <motion.div
                              key={output.title}
                              animate={{
                                y: isActive ? -3 : 0,
                                scale: isActive ? 1.015 : 1,
                                opacity: isActive ? 1 : 0.88,
                              }}
                              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                              className={`overflow-hidden rounded-[0.95rem] border ${
                                isActive
                                  ? 'border-slate-300/90 bg-white shadow-[0_12px_26px_rgba(15,23,42,0.07)] ring-1 ring-slate-200/60 dark:border-white/15 dark:bg-slate-900'
                                  : 'border-slate-200/80 bg-white/92 shadow-[0_4px_12px_rgba(15,23,42,0.03)] dark:border-white/10 dark:bg-slate-900/88'
                              }`}
                            >
                              <div className={`h-3 ${output.tone}`} />
                              <div className="space-y-1.5 p-2.5">
                                <p className="text-[11px] font-semibold text-slate-800 dark:text-slate-100">{output.title}</p>
                                <div className="space-y-1">
                                  <div className="h-1.5 w-4/5 rounded-full bg-slate-200 dark:bg-white/10" />
                                  <div className="h-1.5 w-3/5 rounded-full bg-slate-100 dark:bg-white/5" />
                                </div>
                              </div>
                            </motion.div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2 xl:grid-cols-6">
                    {previewActions.map((action, index) => {
                      const isActive = index === activePreviewIndex;
                      return (
                        <button
                          key={action}
                          type="button"
                          onMouseEnter={() => setActivePreviewIndex(index)}
                          className={`rounded-2xl border px-2.5 py-2 text-left text-xs font-medium transition-all ${
                            isActive
                              ? 'border-slate-300 bg-white text-slate-900 shadow-[0_10px_18px_rgba(15,23,42,0.05)] ring-1 ring-slate-200/50 dark:border-sky-400/20 dark:bg-slate-900 dark:text-white'
                              : 'border-transparent bg-slate-50/80 text-slate-400 dark:bg-white/[0.03] dark:text-slate-500'
                          }`}
                        >
                          {action}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section id="features" className="border-t border-sky-100/80 py-24 dark:border-white/8">
        <div className="mx-auto max-w-7xl px-6">
          <motion.div
            className="mb-16"
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <h2 className="mb-4 text-4xl font-bold dark:text-white md:text-5xl">先把复习、错题、讲义这几件事做顺</h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">少一点重复整理，少一点来回找材料。</p>
          </motion.div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="group relative overflow-hidden rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 shadow-[0_24px_70px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] md:col-span-2 md:p-10"
            >
              <div className="absolute right-0 top-0 p-8 opacity-10 transition-opacity group-hover:opacity-20">
                <FileText size={200} />
              </div>
              <div className="relative z-10 flex h-full flex-col justify-between">
                <div>
                  <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600 text-white">
                    <FileText size={24} />
                  </div>
                  <h3 className="mb-4 text-3xl font-bold text-slate-900 dark:text-white">上完课，复习资料能很快出来</h3>
                  <p className="max-w-2xl text-lg text-slate-600 dark:text-slate-300">
                    课堂录音、笔记和讲义放进来，学生要用的复习材料和老师后续要补的内容会先整理出来。
                  </p>
                </div>
                <div className="mt-12 flex flex-wrap gap-4">
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">课堂记录</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">复习资料</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">讲义整理</div>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.92)_0%,_rgba(239,248,255,0.92)_100%)] p-6 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] md:p-10"
            >
              <div>
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500 text-white">
                  <AlertCircle size={24} />
                </div>
                <h3 className="mb-4 text-2xl font-bold text-slate-900 dark:text-white">错题记录不会散</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  错因、薄弱点和后续安排都会留下来，下次回看不用重新翻记录。
                </p>
              </div>
              <div className="mt-8 flex flex-wrap gap-2">
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">错因</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">薄弱点</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">后续安排</span>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col justify-between rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] md:p-10"
            >
              <div>
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-500 text-white">
                  <Database size={24} />
                </div>
                <h3 className="mb-4 text-2xl font-bold text-slate-900 dark:text-white">题目和讲义能反复用</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  课堂练习、作业和错题会慢慢沉淀成讲义和练习素材。
                </p>
              </div>
              <div className="mt-8 flex items-center gap-2 text-sm font-bold text-blue-600 dark:text-blue-400">
                <span>题目整理</span>
                <ArrowRight size={14} />
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 32 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="flex flex-col items-center gap-10 rounded-[2.5rem] border border-sky-100 bg-white/85 p-6 shadow-[0_24px_70px_rgba(47,128,237,0.06)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.96)_0%,rgba(15,23,42,0.9)_100%)] md:col-span-2 md:flex-row md:p-10"
            >
              <div className="flex-1">
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800 text-white">
                  <FileText size={24} />
                </div>
                <h3 className="mb-4 text-3xl font-bold text-slate-900 dark:text-white">讲义和教研材料可以顺手整理</h3>
                <p className="text-lg text-slate-600 dark:text-slate-300">
                  同一节课里的课程目标、讲义和提纲放在一起，老师不用来回拼。
                </p>
              </div>
              <div className="flex w-full flex-col gap-3 rounded-3xl border border-sky-100 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96)_0%,_rgba(234,245,255,0.96)_100%)] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.92)_0%,rgba(30,41,59,0.88)_100%)] md:w-72">
                {[
                  { label: '讲义大纲', tone: 'bg-orange-500', width: '72%' },
                  { label: '课堂提纲', tone: 'bg-orange-400', width: '58%' },
                  { label: '教研材料', tone: 'bg-orange-300', width: '33%' },
                ].map((item, index) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, y: 14 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.55, delay: 0.15 + index * 0.12, ease: [0.16, 1, 0.3, 1] }}
                    className="rounded-2xl border border-sky-100 bg-white/90 p-4 shadow-[0_14px_34px_rgba(47,128,237,0.07)] dark:border-white/10 dark:bg-slate-900/88"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-sm font-medium text-slate-900 dark:text-white">{item.label}</span>
                      <span className="rounded-full border border-sky-100 bg-sky-50 px-2 py-1 text-[10px] text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/50 dark:text-sky-300">
                        草稿
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="h-2 overflow-hidden rounded-full bg-sky-100 dark:bg-slate-600">
                        <motion.div
                          initial={{ width: '0%' }}
                          whileInView={{ width: item.width }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.9, delay: 0.35 + index * 0.15, ease: [0.16, 1, 0.3, 1] }}
                          className={`h-full ${item.tone}`}
                        />
                      </div>
                      <div className="h-2 w-3/4 rounded-full bg-sky-100 dark:bg-slate-600" />
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      <section id="about" className="border-t border-sky-100/80 py-24 dark:border-white/8">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid grid-cols-1 items-start gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <motion.div
              className="space-y-6"
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            >
              <span className="inline-flex items-center rounded-full border border-slate-200 bg-white/80 px-4 py-1.5 text-xs font-semibold tracking-[0.28em] text-slate-500 dark:border-white/10 dark:bg-white/5 dark:text-slate-400">
                关于 Starain
              </span>
              <div>
                <h2 className="mb-4 text-4xl font-bold text-slate-900 dark:text-white md:text-5xl">关于 Starain</h2>
                <p className="max-w-2xl text-lg leading-relaxed text-slate-600 dark:text-slate-300">
                  这套产品先给我们自己的教学团队用。
                </p>
              </div>
              <p className="max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400 md:text-base">
                我们先拿它处理复习资料、错题跟进、讲义整理和教师协作。哪里费时间，哪里容易断，就先改哪里。
              </p>
            </motion.div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-1">
              {[
                {
                  title: '已验证流程',
                  body: '课堂素材到复习资料，这条线我们一直在自己用。',
                },
                {
                  title: '能力模块化',
                  body: '复习、错题、讲义拆开能用，放在一起也顺。',
                },
                {
                  title: '服务对象',
                  body: '学校、培训机构、国际课程团队和教研运营团队都能用。',
                },
              ].map((item, index) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
                  className="rounded-[2rem] border border-sky-100 bg-white/85 p-6 shadow-[0_20px_60px_rgba(47,128,237,0.05)] dark:border-white/10 dark:bg-slate-800/80"
                >
                  <p className="mb-2 text-sm font-semibold text-slate-900 dark:text-white">{item.title}</p>
                  <p className="text-sm leading-relaxed text-slate-500 dark:text-slate-400">{item.body}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-sky-100/80 py-20 dark:border-white/8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-8 px-6 md:flex-row">
          <div className="flex flex-col items-center gap-3 md:items-start">
            <div className="flex items-center gap-3">
              <img src="/logo.png" alt="Starain logo" className="h-10 w-10 object-contain" />
              <span className="text-lg font-bold tracking-tight dark:text-white">星润Starain</span>
              <span className="text-xs font-semibold uppercase tracking-[0.32em] text-sky-600">
                教学工作平台
              </span>
            </div>
            <p className="max-w-md text-center text-sm text-gray-500 dark:text-slate-400 md:text-left">
              给学校、机构和教学团队用，主要处理复习、错题和讲义整理。
            </p>
          </div>
          <div className="flex flex-col items-center gap-2 text-sm text-slate-500 dark:text-slate-400 md:items-start">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">法律</p>
            <a href="#privacy-policy" className="transition-colors hover:text-slate-900 dark:hover:text-white">隐私政策</a>
            <a href="#terms-of-service" className="transition-colors hover:text-slate-900 dark:hover:text-white">服务条款</a>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400">© 2026 Starain. 保留所有权利。</p>
        </div>
      </footer>
    </div>
  );
}
