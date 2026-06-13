import type { ClassItem } from './appTypes';
import { formatClassDisplayName } from './domain/classNaming';

export function getCurrentClassDisplayName(item: ClassItem | null | undefined, showCohortYear = false): string {
  return formatClassDisplayName(item, { showCohortYear });
}

export function getCurrentClassDisplayNameById(
  classes: ClassItem[],
  classId: number | null | undefined,
  fallbackName?: string | null,
  showCohortYear = false,
): string {
  const classItem = classId == null ? undefined : classes.find((item) => item.id === classId);
  return getCurrentClassDisplayName(classItem, showCohortYear) || fallbackName?.trim() || '';
}
