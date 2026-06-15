import { workspaceFieldClass } from '../../workspaceShared';

export const studentCenterSurfaceClass =
  'rounded-[1.5rem] border border-slate-200 bg-white dark:border-white/10 dark:bg-slate-950';

export const studentCenterMutedSurfaceClass =
  'rounded-[1.25rem] border border-slate-200 bg-slate-50/70 dark:border-white/10 dark:bg-white/[0.04]';

export const studentCenterPrimaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-slate-950 px-4 py-2.5 font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200';

export const studentCenterSecondaryButtonClass =
  'inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-100 dark:hover:bg-white/[0.08]';

export const studentCenterFieldClass =
  `${workspaceFieldClass} border-slate-200 bg-white text-slate-700 shadow-none focus:border-slate-400 focus:ring-slate-100 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-white/20 dark:focus:ring-white/10`;

export const studentCenterBadgeClass =
  'inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:bg-white/[0.08] dark:text-slate-300';

export function getStudentCenterSubjectBadgeClass(subject: string | null | undefined): string {
  if (subject === '数学') {
    return 'inline-flex items-center rounded-full bg-[#d7dee5] px-2.5 py-1 text-xs font-semibold text-[#5a6773] dark:bg-[#4b5966]/35 dark:text-[#d7dee5]';
  }
  if (subject === '物理') {
    return 'inline-flex items-center rounded-full bg-[#d9dfd3] px-2.5 py-1 text-xs font-semibold text-[#66705e] dark:bg-[#55614f]/35 dark:text-[#dde4d7]';
  }
  if (subject === '国际数学') {
    return 'inline-flex items-center rounded-full bg-[#dfd6d9] px-2.5 py-1 text-xs font-semibold text-[#74656a] dark:bg-[#67575d]/35 dark:text-[#e6dde0]';
  }
  return studentCenterBadgeClass;
}
