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
              <p className="text-xs tracking-[0.28em] text-sky-700 dark:text-sky-300">学习全流程 AI 平台</p>
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

  return (
    <div className="min-h-screen bg-[#F6FBFF] text-slate-900 selection:bg-sky-200/70 dark:bg-[#0d1220] dark:text-slate-100">
      <nav className="fixed top-0 z-50 w-full border-b border-sky-100/80 bg-white/80 backdrop-blur-xl dark:border-white/8 dark:bg-[#0d1220]/95">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Starain logo" className="h-12 w-12 object-contain" />
            <span className="text-xl font-bold tracking-tight">星润Starain</span>
            <span className="hidden text-xs font-semibold uppercase tracking-[0.32em] text-sky-600 sm:block">
              学习全流程 AI 平台
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

      <section className="relative overflow-hidden border-b border-sky-100/80 bg-[linear-gradient(180deg,#f7fbff_0%,#ffffff_76%)] dark:border-white/8 dark:bg-[linear-gradient(180deg,#0d1220_0%,#111827_78%)]">
        <div className="absolute inset-x-0 top-0 h-64 bg-[radial-gradient(circle_at_top_left,rgba(34,199,232,0.12),transparent_34%),radial-gradient(circle_at_top_right,rgba(47,128,237,0.08),transparent_28%)] dark:bg-[radial-gradient(circle_at_top_left,rgba(34,199,232,0.12),transparent_32%),radial-gradient(circle_at_top_right,rgba(47,128,237,0.1),transparent_28%)]" />
        <div
          className="absolute inset-0 opacity-[0.45] dark:opacity-[0.12]"
          style={{
            backgroundImage:
              'linear-gradient(rgba(148,163,184,0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.12) 1px, transparent 1px)',
            backgroundPosition: 'center top',
            backgroundSize: '48px 48px',
            maskImage: 'linear-gradient(180deg, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.12) 72%, transparent 100%)',
          }}
        />

        <div className="relative z-10 mx-auto max-w-7xl px-6 pb-20 pt-32 md:pb-24 md:pt-36">
          <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
            <motion.div
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
              className="max-w-2xl"
            >
              <div className="inline-flex items-center rounded-full border border-sky-200 bg-white px-4 py-2 text-xs font-semibold tracking-[0.22em] text-sky-700 shadow-sm dark:border-white/10 dark:bg-white/5 dark:text-sky-200">
                面向学校与机构的教学工作台
              </div>
              <h1 className="mt-7 max-w-4xl text-4xl font-black leading-[1.05] tracking-tight text-slate-950 dark:text-white sm:text-5xl md:text-6xl">
                把复习生成、错题跟进和教学交付收进同一套平台
              </h1>
              <p className="mt-6 max-w-xl text-base leading-8 text-slate-600 dark:text-slate-300 md:text-lg">
                Starain 帮老师、教务和机构负责人在同一条工作流里完成课堂整理、复习输出和后续跟进，少切工具，也少重复整理。
              </p>

              <div className="mt-8 flex flex-col gap-3 text-sm text-slate-600 dark:text-slate-300">
                <div className="flex items-start gap-3">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-sky-500" />
                  <p>先完成真实教学任务，再让 AI 补上整理、生成和归档这些重复工作。</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-sky-500" />
                  <p>机构负责人、老师和教务团队看到的是同一套进度和交付结果，不再分散在多个工具里。</p>
                </div>
              </div>

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
              className="overflow-hidden rounded-[2rem] border border-sky-100 bg-white shadow-[0_16px_48px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-slate-950"
            >
              <div className="flex items-center justify-between border-b border-sky-100 px-5 py-4 dark:border-white/10">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400 dark:text-slate-500">Starain workspace</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">今天最值得推进的三件事</p>
                </div>
                <div className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:bg-sky-500/10 dark:text-sky-300">
                  机构工作流
                </div>
              </div>

              <div className="grid gap-0 lg:grid-cols-[220px_minmax(0,1fr)]">
                <div className="border-b border-sky-100 bg-sky-50/70 px-4 py-4 dark:border-white/10 dark:bg-white/5 lg:border-b-0 lg:border-r">
                  <div className="space-y-2">
                    {[
                      ['复习生成', '课堂内容整理'],
                      ['错题跟进', '学生薄弱点'],
                      ['教学交付', '讲义与协作'],
                    ].map(([title, subtitle], index) => (
                      <div
                        key={title}
                        className={`rounded-2xl px-4 py-3 ${
                          index === 0
                            ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-900 dark:text-white'
                            : 'text-slate-500 dark:text-slate-400'
                        }`}
                      >
                        <p className="text-sm font-semibold">{title}</p>
                        <p className="mt-1 text-xs">{subtitle}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="px-5 py-4">
                  <div className="grid gap-0">
                    {[
                      {
                        title: '复习文档待生成',
                        body: '把课堂录音和笔记整理成学生可直接使用的复习材料。',
                        status: '进行中',
                      },
                      {
                        title: '错题跟进待更新',
                        body: '围绕错因、掌握状态和后续练习安排形成连续记录。',
                        status: '今日跟进',
                      },
                      {
                        title: '讲义草稿待确认',
                        body: '把课程目标、教研材料和教师修改意见收进统一交付链路。',
                        status: '待确认',
                      },
                    ].map((item, index) => (
                      <div
                        key={item.title}
                        className={`flex flex-col gap-3 py-4 sm:flex-row sm:items-start sm:justify-between ${
                          index === 0 ? '' : 'border-t border-sky-100 dark:border-white/10'
                        }`}
                      >
                        <div className="max-w-lg">
                          <p className="text-sm font-semibold text-slate-900 dark:text-white">{item.title}</p>
                          <p className="mt-2 text-sm leading-7 text-slate-600 dark:text-slate-300">{item.body}</p>
                        </div>
                        <div className="shrink-0 rounded-full border border-sky-100 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 dark:border-sky-500/20 dark:bg-sky-500/10 dark:text-sky-300">
                          {item.status}
                        </div>
                      </div>
                    ))}
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
            <h2 className="mb-4 text-4xl font-bold dark:text-white md:text-5xl">把真实教学流程整理成可复用的 AI 能力</h2>
            <p className="text-lg text-slate-600 dark:text-slate-300">不是堆叠功能点，而是把一条已经跑通的教育工作流产品化。</p>
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
                  <h3 className="mb-4 text-3xl font-bold text-slate-900 dark:text-white">从课堂素材到复习交付</h3>
                  <p className="max-w-2xl text-lg text-slate-600 dark:text-slate-300">
                    课堂录音、笔记与教学内容进入平台后，被整理成结构化复习资料、练习内容与更稳定的教学交付材料。
                  </p>
                </div>
                <div className="mt-12 flex flex-wrap gap-4">
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">课堂分析</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">复习资料生成</div>
                  <div className="rounded-full border border-sky-100 bg-sky-50 px-4 py-2 text-xs font-mono text-sky-700 dark:border-sky-500/30 dark:bg-sky-900/40 dark:text-sky-300">教学交付</div>
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
                <h3 className="mb-4 text-2xl font-bold text-slate-900 dark:text-white">把错误整理成可持续跟进记录</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  不是一次性纠错，而是持续记录高频错误、薄弱点与个性化复习路径。
                </p>
              </div>
              <div className="mt-8 flex flex-wrap gap-2">
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">错因整理</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">薄弱点追踪</span>
                <span className="rounded-full bg-cyan-50 px-3 py-1 text-[10px] font-bold tracking-widest text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">个性化复习</span>
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
                <h3 className="mb-4 text-2xl font-bold text-slate-900 dark:text-white">把题目整理成可复用的教学素材</h3>
                <p className="text-slate-600 dark:text-slate-300">
                  围绕课堂练习、作业和错题记录，帮助老师逐步整理出更稳定的讲义与练习素材。
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
                <h3 className="mb-4 text-3xl font-bold text-slate-900 dark:text-white">把课程目标转化为讲义与教研交付</h3>
                <p className="text-lg text-slate-600 dark:text-slate-300">
                  从课程目标到讲义、课堂提纲和教研素材，减少教师重复整理工作。
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
                        AI Draft
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
                ABOUT STARAIN
              </span>
              <div>
                <h2 className="mb-4 text-4xl font-bold text-slate-900 dark:text-white md:text-5xl">关于 Starain</h2>
                <p className="max-w-2xl text-lg leading-relaxed text-slate-600 dark:text-slate-300">
                  Starain 不是从 PPT 里想出来的，而是从真实教学现场长出来的。
                </p>
              </div>
              <p className="max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400 md:text-base">
                我们先在自己的教育机构中解决复习资料、错题跟进、讲义整理与教师协作问题，再把这套已经跑通的流程产品化，服务更多同行团队。
              </p>
            </motion.div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-1">
              {[
                {
                  title: '已验证流程',
                  body: '课堂素材到复习交付的链路已经在真实教学里跑通。',
                },
                {
                  title: '能力模块化',
                  body: '错题跟进、复习安排与讲义整理可以在同一条教学链路里持续复用。',
                },
                {
                  title: '服务对象',
                  body: '聚焦学校、培训机构、国际课程团队与教研运营场景。',
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
                学习全流程 AI 平台
              </span>
            </div>
            <p className="max-w-md text-center text-sm text-gray-500 dark:text-slate-400 md:text-left">
              面向学校、机构与教学团队，构建从内容生成到教学交付的 AI 能力底座。
            </p>
          </div>
          <div className="flex flex-col items-center gap-2 text-sm text-slate-500 dark:text-slate-400 md:items-start">
            <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">导航</p>
            <a href="#features" className="transition-colors hover:text-slate-900 dark:hover:text-white">核心方案</a>
            <a href="#about" className="transition-colors hover:text-slate-900 dark:hover:text-white">关于 Starain</a>
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
