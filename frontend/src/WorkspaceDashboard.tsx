import React from 'react';
import { ArrowRight, Library, PlusCircle } from 'lucide-react';

type WorkspaceRole = 'super_owner' | 'owner' | 'admin' | 'member';
type WorkspacePage = 'dashboard' | 'review-generation' | 'class-feedback-generation' | 'consultation' | 'calendar' | 'smartWrongQuestions' | 'classes' | 'accounts' | 'credit' | 'settings';
type WorkspaceStyles = {
  pageClass: string;
  cardClass: string;
  primaryButtonClass: string;
  secondaryButtonClass: string;
};

type WorkspaceDashboardProps = {
  currentUser: {
    display_name: string;
    role: WorkspaceRole;
  };
  setActivePage: (page: WorkspacePage) => void;
  styles: WorkspaceStyles;
};

function getDashboardCopy(role: WorkspaceRole): {
  eyebrow: string;
  title: string;
  description: string;
  panelTitle: string;
  panelBody: string;
} {
  if (role === 'super_owner') {
    return {
      eyebrow: 'Platform command',
      title: '平台总览',
      description: '集中查看跨机构运行状态与关键工作入口。',
      panelTitle: '平台总览',
      panelBody: '这里会承接平台级指标、审批与配置入口。',
    };
  }

  if (role === 'admin' || role === 'owner') {
    return {
      eyebrow: 'Operations focus',
      title: '机构运营概览',
      description: '优先处理机构日常运营、排课协同与教学跟进。',
      panelTitle: '机构运营概览',
      panelBody: '这里会承接机构级经营看板与运营动作。',
    };
  }

  return {
    eyebrow: 'Teaching flow',
    title: '快速开始',
    description: '从最常用的教学动作开始，不显示管理侧待办。',
    panelTitle: '快速开始',
    panelBody: '这里会优先放置复习生成、课堂反馈和错题跟进入口。',
  };
}

export function WorkspaceDashboard({ currentUser, setActivePage, styles }: WorkspaceDashboardProps) {
  const copy = getDashboardCopy(currentUser.role);

  return (
    <div className={`${styles.pageClass} space-y-6`}>
      <section className="rounded-[2rem] border border-sky-100 bg-[radial-gradient(circle_at_top_left,_rgba(34,199,232,0.18),_transparent_32%),linear-gradient(135deg,_rgba(255,255,255,0.98)_0%,_rgba(236,246,255,0.92)_52%,_rgba(223,241,255,0.96)_100%)] p-6 shadow-[0_24px_72px_rgba(47,128,237,0.08)] dark:border-white/10 dark:bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.15),_transparent_30%),linear-gradient(135deg,_rgba(15,23,42,0.98)_0%,_rgba(17,24,39,0.95)_52%,_rgba(30,41,59,0.96)_100%)] dark:shadow-[0_28px_80px_rgba(2,6,23,0.36)] md:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.28em] text-sky-600">{copy.eyebrow}</p>
        <div className="mt-4 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="space-y-3">
            <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">{copy.title}</h3>
            <p className="max-w-2xl text-sm leading-relaxed text-slate-500 dark:text-slate-400">
              欢迎回来，{currentUser.display_name}。{copy.description}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => setActivePage('review-generation')} className={styles.primaryButtonClass}>
              <PlusCircle size={18} />
              新建复习文档
            </button>
            <button type="button" onClick={() => setActivePage('review-generation')} className={styles.secondaryButtonClass}>
              <Library size={18} />
              查看历史文档
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)]">
        <div className={`${styles.cardClass} p-6`}>
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{copy.panelTitle}</p>
              <p className="mt-2 text-sm leading-relaxed text-slate-500 dark:text-slate-400">{copy.panelBody}</p>
            </div>
            <ArrowRight size={18} className="shrink-0 text-sky-500 dark:text-sky-400" />
          </div>
        </div>

        <div className={`${styles.cardClass} p-6`}>
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">当前身份</p>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{currentUser.role}</p>
        </div>
      </section>
    </div>
  );
}