import type {
  ClassCommentaryLearningTrend,
  ClassCommentaryObservedLearningState,
} from '../../classCommentary';

export const studentLearningStateLabels: Record<ClassCommentaryObservedLearningState, string> = {
  unknown: '持续观察',
  weak: '需要巩固',
  developing: '正在发展',
  secure: '已经掌握',
  mastered: '熟练掌握',
};

export const studentLearningTrendLabels: Record<ClassCommentaryLearningTrend, string> = {
  new_observation: '新观察',
  regressed: '需要关注',
  stable: '保持稳定',
  improved: '有所进步',
};

export function formatStudentLearningGraphTime(value: string): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
