import {
  getAcademicGradeRank,
  getAcademicStageFromGrade,
  normalizeAcademicGradeLabel,
} from '../../domain/classNaming';
import type { FloatingFilterItem, FloatingFilterOption } from '../../components/FloatingFilterBar';
import type { ClassManagementFilterLayer } from './ClassManagementTab';
import type { ClassItem, UserItem } from './model';

export type ClassTeacherFilter = number | 'all';

export type ClassFilterState = {
  subjectFilter: string;
  teacherFilter: ClassTeacherFilter;
  stageFilter: string;
  gradeFilter: string;
};

type ClassRuleBase = {
  classes: ClassItem[];
  subjectLookupClasses?: ClassItem[];
  teacherBindingByClassId: Record<number, number | null>;
  subjectOptions: string[];
};

type ClassOptionArgs = ClassRuleBase & {
  users: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
  gradeGroups: Record<string, string[]>;
  filters: ClassFilterState;
};

export function getClassTeacherUserId(
  item: ClassItem,
  teacherBindingByClassId: Record<number, number | null>,
): number | null {
  return teacherBindingByClassId[item.id] ?? item.teacher_user_id ?? null;
}

function buildSubjectLookup(
  classes: ClassItem[],
  teacherBindingByClassId: Record<number, number | null>,
  subjectOptions: string[],
): {
  subjectByTeacherUserId: Map<number, string>;
  subjectByTeacherName: Map<string, string>;
} {
  const subjectByTeacherUserId = new Map<number, string>();
  const subjectByTeacherName = new Map<string, string>();

  classes.forEach((item) => {
    const subject = item.subject && subjectOptions.includes(item.subject) ? item.subject : '';
    if (!subject) {
      return;
    }
    const teacherUserId = getClassTeacherUserId(item, teacherBindingByClassId);
    if (teacherUserId != null && !subjectByTeacherUserId.has(teacherUserId)) {
      subjectByTeacherUserId.set(teacherUserId, subject);
    }
    if (item.teacher_name && !subjectByTeacherName.has(item.teacher_name)) {
      subjectByTeacherName.set(item.teacher_name, subject);
    }
  });

  return { subjectByTeacherUserId, subjectByTeacherName };
}

export function getClassEffectiveSubject(
  item: ClassItem,
  classes: ClassItem[],
  teacherBindingByClassId: Record<number, number | null>,
  subjectOptions: string[],
): string {
  if (item.subject && subjectOptions.includes(item.subject)) {
    return item.subject;
  }
  const { subjectByTeacherUserId, subjectByTeacherName } = buildSubjectLookup(classes, teacherBindingByClassId, subjectOptions);
  const teacherUserId = getClassTeacherUserId(item, teacherBindingByClassId);
  if (teacherUserId != null) {
    const subjectByUserId = subjectByTeacherUserId.get(teacherUserId);
    if (subjectByUserId) {
      return subjectByUserId;
    }
  }
  return item.teacher_name ? subjectByTeacherName.get(item.teacher_name) || '' : '';
}

export function classMatchesFilters({
  item,
  classes,
  subjectLookupClasses,
  teacherBindingByClassId,
  subjectOptions,
  filters,
  except,
}: ClassRuleBase & {
  item: ClassItem;
  filters: ClassFilterState;
  except?: ClassManagementFilterLayer | null;
}): boolean {
  if (
    except !== 'subject'
    && filters.subjectFilter !== '全部学科'
    && getClassEffectiveSubject(item, subjectLookupClasses || classes, teacherBindingByClassId, subjectOptions) !== filters.subjectFilter
  ) {
    return false;
  }
  const itemTeacherUserId = getClassTeacherUserId(item, teacherBindingByClassId);
  if (except !== 'teacher' && filters.teacherFilter !== 'all' && itemTeacherUserId !== filters.teacherFilter) {
    return false;
  }
  const itemStage = item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '');
  if (except !== 'stage' && filters.stageFilter !== '全部学段' && itemStage !== filters.stageFilter) {
    return false;
  }
  const itemGrade = normalizeAcademicGradeLabel(item.current_grade || item.grade || '');
  if (except !== 'grade' && filters.gradeFilter !== '全部' && itemGrade !== filters.gradeFilter) {
    return false;
  }
  return true;
}

function getClassFilterOptionBase(args: ClassOptionArgs, layer: ClassManagementFilterLayer): ClassItem[] {
  return args.classes.filter((item) => classMatchesFilters({ ...args, item, except: layer }));
}

export function resolveClassFilterOptions(args: ClassOptionArgs): {
  subjectOptions: string[];
  teacherOptions: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
} {
  return {
    subjectOptions: args.subjectOptions,
    teacherOptions: args.users.filter((user) => getClassFilterOptionBase(args, 'teacher').some((item) => (
      getClassTeacherUserId(item, args.teacherBindingByClassId) === user.id
    ))),
    stageOptions: args.stageOptions.filter((stage) => getClassFilterOptionBase(args, 'stage').some((item) => (
      (item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '')) === stage
    ))),
    gradeOptions: args.gradeOptions.filter((grade) => {
      if (args.filters.stageFilter !== '全部学段' && !args.gradeGroups[args.filters.stageFilter]?.includes(grade)) {
        return false;
      }
      return getClassFilterOptionBase(args, 'grade').some((item) => (
        normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === grade
      ));
    }),
  };
}

export function buildClassFilterSummary(filters: ClassFilterState, users: UserItem[]): string {
  return [
    filters.teacherFilter !== 'all' ? users.find((user) => user.id === filters.teacherFilter)?.name || '指定教师' : '',
    filters.subjectFilter !== '全部学科' ? filters.subjectFilter : '',
    filters.stageFilter !== '全部学段' ? filters.stageFilter : '',
    filters.gradeFilter !== '全部' ? filters.gradeFilter : '',
  ].filter(Boolean).join(' / ') || '全部';
}

export function buildClassFilterItems(
  filters: ClassFilterState,
  users: UserItem[],
): Array<FloatingFilterItem<ClassManagementFilterLayer>> {
  return [
    {
      key: 'subject',
      defaultLabel: '科目',
      label: filters.subjectFilter === '全部学科' ? '科目' : `科目：${filters.subjectFilter}`,
      selected: filters.subjectFilter !== '全部学科',
    },
    {
      key: 'teacher',
      defaultLabel: '教师',
      label: filters.teacherFilter === 'all' ? '教师' : users.find((user) => user.id === filters.teacherFilter)?.name || '指定教师',
      selected: filters.teacherFilter !== 'all',
    },
    {
      key: 'stage',
      defaultLabel: '学段',
      label: filters.stageFilter === '全部学段' ? '学段' : filters.stageFilter,
      selected: filters.stageFilter !== '全部学段',
    },
    {
      key: 'grade',
      defaultLabel: '年级',
      label: filters.gradeFilter === '全部' ? '年级' : filters.gradeFilter,
      selected: filters.gradeFilter !== '全部',
    },
  ];
}

export function resolveActiveClassFilterOptions(
  activeLayer: ClassManagementFilterLayer | null,
  filters: ClassFilterState,
  options: {
    subjectOptions: string[];
    teacherOptions: UserItem[];
    stageOptions: string[];
    gradeOptions: string[];
  },
): FloatingFilterOption[] {
  if (!activeLayer) {
    return [];
  }
  if (activeLayer === 'subject') {
    return options.subjectOptions.map((option) => ({ id: option, label: option, selected: filters.subjectFilter === option }));
  }
  if (activeLayer === 'teacher') {
    return options.teacherOptions.map((teacher) => ({ id: teacher.id, label: teacher.name, selected: filters.teacherFilter === teacher.id }));
  }
  if (activeLayer === 'stage') {
    return options.stageOptions.map((stage) => ({ id: stage, label: stage, selected: filters.stageFilter === stage }));
  }
  return options.gradeOptions.map((grade) => ({ id: grade, label: grade, selected: filters.gradeFilter === grade }));
}

export function getClassInfoIssues(
  item: ClassItem,
  teacherBindingByClassId: Record<number, number | null>,
  subjectOptions: string[],
): string[] {
  const grade = normalizeAcademicGradeLabel(item.current_grade || item.grade || '');
  const requiresClassNumber = !item.class_type || item.class_type === 'group';
  return [
    (!item.subject || !subjectOptions.includes(item.subject)) ? '缺科目' : '',
    !(item.stage || getAcademicStageFromGrade(grade)) ? '缺学段' : '',
    !grade ? '缺年级' : '',
    requiresClassNumber && !item.class_number ? '缺班号' : '',
    getClassTeacherUserId(item, teacherBindingByClassId) == null ? '缺负责教师' : '',
  ].filter(Boolean);
}

export function isClassInfoIncomplete(
  item: ClassItem,
  teacherBindingByClassId: Record<number, number | null>,
  subjectOptions: string[],
): boolean {
  return getClassInfoIssues(item, teacherBindingByClassId, subjectOptions).length > 0;
}

function getClassTypeRank(item: ClassItem): number {
  return item.class_type && item.class_type !== 'group' ? 0 : 1;
}

export function resolveFilteredClasses(args: ClassRuleBase & {
  filters: ClassFilterState;
}): ClassItem[] {
  return args.classes.filter((item) => classMatchesFilters({ ...args, item })).sort((left, right) => {
    const incompleteDelta = Number(isClassInfoIncomplete(right, args.teacherBindingByClassId, args.subjectOptions)) - Number(isClassInfoIncomplete(left, args.teacherBindingByClassId, args.subjectOptions));
    const classTypeDelta = getClassTypeRank(left) - getClassTypeRank(right);
    const gradeDelta = getAcademicGradeRank(left.current_grade || left.grade || '') - getAcademicGradeRank(right.current_grade || right.grade || '');
    const leftSubject = getClassEffectiveSubject(left, args.subjectLookupClasses || args.classes, args.teacherBindingByClassId, args.subjectOptions);
    const rightSubject = getClassEffectiveSubject(right, args.subjectLookupClasses || args.classes, args.teacherBindingByClassId, args.subjectOptions);
    return incompleteDelta || classTypeDelta || gradeDelta || `${leftSubject}${left.name}`.localeCompare(`${rightSubject}${right.name}`, 'zh-CN') || left.id - right.id;
  });
}
