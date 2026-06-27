import { workspaceCardClass, workspacePageClass } from '../../workspaceShared';
import type { CurrentUser } from '../../appTypes';

type ClassFeedbackGenerationPageProps = {
  currentUser: CurrentUser;
};

export function ClassFeedbackGenerationPage({ currentUser: _currentUser }: ClassFeedbackGenerationPageProps) {
  return (
    <div className={`${workspacePageClass} space-y-6`}>
      <section className={`${workspaceCardClass} p-6`}>
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500">Class Feedback</p>
        <h3 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">课堂反馈</h3>
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">重新设计中</p>
      </section>
    </div>
  );
}
