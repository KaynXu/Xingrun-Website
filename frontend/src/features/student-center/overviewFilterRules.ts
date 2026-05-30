import {
  getAcademicStageFromGrade,
  normalizeAcademicGradeLabel,
} from '../../domain/classNaming';
import type { ClassItem, CurrentUser, UserItem } from './model';
import type { CampusOverviewFilterLayer } from './CampusOverview';

export type OverviewTeacherFilter = number | 'all';

export type OverviewFilterState = {
  subjectFilter: string;
  teacherFilter: OverviewTeacherFilter;
  stageFilter: string;
  gradeFilter: string;
};

type OverviewRuleBase = {
  classes: ClassItem[];
  subjectLookupClasses?: ClassItem[];
  teacherBindingByClassId: Record<number, number | null>;
  subjectOptions: string[];
};

type OverviewOptionArgs = OverviewRuleBase & {
  users: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
  gradeGroups: Record<string, string[]>;
  filters: OverviewFilterState;
};

export function getOverviewClassTeacherUserId(
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
    const teacherUserId = getOverviewClassTeacherUserId(item, teacherBindingByClassId);
    if (teacherUserId != null && !subjectByTeacherUserId.has(teacherUserId)) {
      subjectByTeacherUserId.set(teacherUserId, subject);
    }
    if (item.teacher_name && !subjectByTeacherName.has(item.teacher_name)) {
      subjectByTeacherName.set(item.teacher_name, subject);
    }
  });

  return { subjectByTeacherUserId, subjectByTeacherName };
}

export function getOverviewClassEffectiveSubject(
  item: ClassItem,
  classes: ClassItem[],
  teacherBindingByClassId: Record<number, number | null>,
  subjectOptions: string[],
): string {
  if (item.subject && subjectOptions.includes(item.subject)) {
    return item.subject;
  }
  const { subjectByTeacherUserId, subjectByTeacherName } = buildSubjectLookup(classes, teacherBindingByClassId, subjectOptions);
  const teacherUserId = getOverviewClassTeacherUserId(item, teacherBindingByClassId);
  if (teacherUserId != null) {
    const subjectByUserId = subjectByTeacherUserId.get(teacherUserId);
    if (subjectByUserId) {
      return subjectByUserId;
    }
  }
  return item.teacher_name ? subjectByTeacherName.get(item.teacher_name) || '' : '';
}

export function overviewClassMatchesFilters({
  item,
  classes,
  subjectLookupClasses,
  teacherBindingByClassId,
  subjectOptions,
  filters,
  except,
}: OverviewRuleBase & {
  item: ClassItem;
  filters: OverviewFilterState;
  except?: CampusOverviewFilterLayer | null;
}): boolean {
  if (
    except !== 'subject'
    && filters.subjectFilter !== '全部学科'
    && getOverviewClassEffectiveSubject(item, subjectLookupClasses || classes, teacherBindingByClassId, subjectOptions) !== filters.subjectFilter
  ) {
    return false;
  }
  const itemTeacherUserId = getOverviewClassTeacherUserId(item, teacherBindingByClassId);
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

export function resolveOverviewFilteredClasses(args: OverviewRuleBase & {
  filters: OverviewFilterState;
}): ClassItem[] {
  return args.classes.filter((item) => overviewClassMatchesFilters({ ...args, item }));
}

function getOverviewFilterOptionBase(args: OverviewOptionArgs, layer: CampusOverviewFilterLayer): ClassItem[] {
  return args.classes.filter((item) => overviewClassMatchesFilters({ ...args, item, except: layer }));
}

export function resolveOverviewFilterOptions(args: OverviewOptionArgs): {
  subjectOptions: string[];
  teacherOptions: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
} {
  return {
    subjectOptions: args.subjectOptions,
    teacherOptions: args.users.filter((user) => getOverviewFilterOptionBase(args, 'teacher').some((item) => (
      getOverviewClassTeacherUserId(item, args.teacherBindingByClassId) === user.id
    ))),
    stageOptions: args.stageOptions.filter((stage) => getOverviewFilterOptionBase(args, 'stage').some((item) => (
      (item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '')) === stage
    ))),
    gradeOptions: args.gradeOptions.filter((grade) => {
      if (args.filters.stageFilter !== '全部学段' && !args.gradeGroups[args.filters.stageFilter]?.includes(grade)) {
        return false;
      }
      return getOverviewFilterOptionBase(args, 'grade').some((item) => (
        normalizeAcademicGradeLabel(item.current_grade || item.grade || '') === grade
      ));
    }),
  };
}

export function buildOverviewFilterSummary(filters: OverviewFilterState, users: UserItem[]): string {
  return [
    filters.teacherFilter !== 'all' ? `教师：${users.find((user) => user.id === filters.teacherFilter)?.name || '指定教师'}` : '',
    filters.subjectFilter !== '全部学科' ? `科目：${filters.subjectFilter}` : '',
    filters.stageFilter !== '全部学段' ? `学段：${filters.stageFilter}` : '',
    filters.gradeFilter !== '全部' ? `年级：${filters.gradeFilter}` : '',
  ].filter(Boolean).join(' / ') || '全校区';
}

export function buildOverviewFilterItems(
  filters: OverviewFilterState,
  canUseOrganizationScope: boolean,
): Array<{ key: CampusOverviewFilterLayer; label: string; selected: boolean }> {
  return [
    {
      key: 'subject',
      label: '科目',
      selected: filters.subjectFilter !== '全部学科',
    },
    ...(canUseOrganizationScope ? [{
      key: 'teacher' as const,
      label: '教师',
      selected: filters.teacherFilter !== 'all',
    }] : []),
    {
      key: 'stage',
      label: '学段',
      selected: filters.stageFilter !== '全部学段',
    },
    {
      key: 'grade',
      label: '年级',
      selected: filters.gradeFilter !== '全部',
    },
  ];
}

export function resolveOverviewSummaryItems({
  filteredClasses,
  currentUser,
  canUseOrganizationScope,
  teacherBindingByClassId,
}: {
  filteredClasses: ClassItem[];
  currentUser: CurrentUser;
  canUseOrganizationScope: boolean;
  teacherBindingByClassId: Record<number, number | null>;
}): Array<{ label: string; value: string | number }> {
  const classSummaryTeacherKeys = new Set(filteredClasses.map((item) => {
    const teacherUserId = getOverviewClassTeacherUserId(item, teacherBindingByClassId);
    return teacherUserId == null
      ? (item.teacher_name ? `name:${item.teacher_name}` : null)
      : `id:${teacherUserId}`;
  }).filter(Boolean));
  const studentCount = filteredClasses.reduce((total, item) => total + Number(item.student_count || 0), 0);
  const lessonCount = filteredClasses.reduce((total, item) => total + Number(item.lesson_count || 0), 0);

  if (canUseOrganizationScope) {
    return [
      { label: '教师人数', value: classSummaryTeacherKeys.size },
      { label: '学员人数', value: studentCount },
      { label: '班级数量', value: filteredClasses.length },
      { label: '小课数量', value: lessonCount },
    ];
  }

  return [
    { label: '主讲教师', value: currentUser.display_name || currentUser.username },
    { label: '学员人数', value: studentCount },
    { label: '班级数量', value: filteredClasses.length },
    { label: '小课数量', value: lessonCount },
  ];
}
