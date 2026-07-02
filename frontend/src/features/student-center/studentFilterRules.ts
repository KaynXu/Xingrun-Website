import {
  formatClassDisplayName,
  getAcademicStageFromGrade,
  normalizeAcademicGradeLabel,
} from '../../domain/classNaming';
import type { FloatingFilterItem, FloatingFilterOption } from '../../components/FloatingFilterBar';
import type { ClassItem, UserItem } from './model';
import {
  getClassEffectiveSubject,
  getClassTeacherUserId,
  type ClassTeacherFilter,
} from './classFilterRules';
import type { StudentManagementFilterLayer } from './StudentManagementTab';

export type StudentClassFilter = number | 'all';
export type StudentScheduleStatusFilter = 'all' | 'scheduled' | 'unscheduled';

export type StudentFilterState = {
  subjectFilter: string;
  teacherFilter: ClassTeacherFilter;
  stageFilter: string;
  gradeFilter: string;
  classFilter: StudentClassFilter;
  nameFilter: string;
  scheduleStatusFilter: StudentScheduleStatusFilter;
};

export type StudentRow = {
  id: number;
  name: string;
  classItems: Array<{
    classItem: ClassItem;
    teacherUserId: number | null;
  }>;
  classItem: ClassItem | null;
  teacherUserId: number | null;
  scheduled: boolean;
};

type StudentRuleBase = {
  rows: StudentRow[];
  classes: ClassItem[];
  teacherBindingByClassId: Record<number, number | null>;
  subjectOptions: string[];
};

type StudentOptionArgs = StudentRuleBase & {
  scopedClasses: ClassItem[];
  users: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
  gradeGroups: Record<string, string[]>;
  filters: StudentFilterState;
};

export function buildStudentRows(args: {
  classes: ClassItem[];
  studentsByClassId: Record<number, Array<{ id: number; name: string }>>;
  allStudents?: Array<{ id: number; name: string }>;
  teacherBindingByClassId: Record<number, number | null>;
}): StudentRow[] {
  const rowsByStudentId = new Map<number, StudentRow>();
  const ensureRow = (student: { id: number; name: string }): StudentRow => {
    const existing = rowsByStudentId.get(student.id);
    if (existing) {
      if (!existing.name && student.name) {
        existing.name = student.name;
      }
      return existing;
    }
    const row: StudentRow = {
      id: student.id,
      name: student.name,
      classItems: [],
      classItem: null,
      teacherUserId: null,
      scheduled: false,
    };
    rowsByStudentId.set(student.id, row);
    return row;
  };

  (args.allStudents || []).forEach(ensureRow);
  args.classes.forEach((classItem) => {
    (args.studentsByClassId[classItem.id] || []).forEach((student) => {
      const row = ensureRow(student);
      const teacherUserId = getClassTeacherUserId(classItem, args.teacherBindingByClassId);
      if (!row.classItems.some((item) => item.classItem.id === classItem.id)) {
        row.classItems.push({ classItem, teacherUserId });
      }
      row.classItem = row.classItems[0]?.classItem || null;
      row.teacherUserId = row.classItems[0]?.teacherUserId ?? null;
      row.scheduled = row.classItems.length > 0;
    });
  });

  return Array.from(rowsByStudentId.values());
}

function getStudentCourseItems(item: StudentRow): Array<{ classItem: ClassItem; teacherUserId: number | null }> {
  if (item.classItems.length) {
    return item.classItems;
  }
  return item.classItem ? [{ classItem: item.classItem, teacherUserId: item.teacherUserId }] : [];
}

function studentHasMatchingCourse(
  item: StudentRow,
  predicate: (course: { classItem: ClassItem; teacherUserId: number | null }) => boolean,
): boolean {
  return getStudentCourseItems(item).some(predicate);
}

export function studentMatchesFilters({
  item,
  classes,
  teacherBindingByClassId,
  subjectOptions,
  filters,
  except,
}: StudentRuleBase & {
  item: StudentRow;
  filters: StudentFilterState;
  except?: StudentManagementFilterLayer | null;
}): boolean {
  if (filters.scheduleStatusFilter === 'scheduled' && !item.scheduled) {
    return false;
  }
  if (filters.scheduleStatusFilter === 'unscheduled' && item.scheduled) {
    return false;
  }
  if (filters.scheduleStatusFilter !== 'scheduled') {
    return true;
  }
  if (
    except !== 'subject'
    && filters.subjectFilter !== '全部学科'
    && !studentHasMatchingCourse(item, (course) => getClassEffectiveSubject(course.classItem, classes, teacherBindingByClassId, subjectOptions) === filters.subjectFilter)
  ) {
    return false;
  }
  if (except !== 'teacher' && filters.teacherFilter !== 'all' && !studentHasMatchingCourse(item, (course) => course.teacherUserId === filters.teacherFilter)) {
    return false;
  }
  if (except !== 'stage' && filters.stageFilter !== '全部学段' && !studentHasMatchingCourse(item, (course) => (
    (course.classItem.stage || getAcademicStageFromGrade(course.classItem.current_grade || course.classItem.grade || '')) === filters.stageFilter
  ))) {
    return false;
  }
  if (except !== 'grade' && filters.gradeFilter !== '全部' && !studentHasMatchingCourse(item, (course) => (
    normalizeAcademicGradeLabel(course.classItem.current_grade || course.classItem.grade || '') === filters.gradeFilter
  ))) {
    return false;
  }
  if (except !== 'class' && filters.classFilter !== 'all' && !studentHasMatchingCourse(item, (course) => course.classItem.id === filters.classFilter)) {
    return false;
  }
  const keyword = filters.nameFilter.trim();
  if (keyword && !item.name.includes(keyword)) {
    return false;
  }
  return true;
}

function getStudentFilterOptionBase(args: StudentOptionArgs, layer: StudentManagementFilterLayer): StudentRow[] {
  return args.rows.filter((item) => studentMatchesFilters({ ...args, item, except: layer }));
}

export function resolveStudentFilterOptions(args: StudentOptionArgs): {
  subjectOptions: string[];
  teacherOptions: UserItem[];
  stageOptions: string[];
  gradeOptions: string[];
  classOptions: ClassItem[];
} {
  return {
    subjectOptions: args.subjectOptions,
    teacherOptions: args.users.filter((user) => getStudentFilterOptionBase(args, 'teacher').some((item) => (
      studentHasMatchingCourse(item, (course) => course.teacherUserId === user.id)
    ))),
    stageOptions: args.stageOptions.filter((stage) => getStudentFilterOptionBase(args, 'stage').some((item) => (
      studentHasMatchingCourse(item, (course) => (course.classItem.stage || getAcademicStageFromGrade(course.classItem.current_grade || course.classItem.grade || '')) === stage)
    ))),
    gradeOptions: args.gradeOptions.filter((grade) => {
      if (args.filters.stageFilter !== '全部学段' && !args.gradeGroups[args.filters.stageFilter]?.includes(grade)) {
        return false;
      }
      return getStudentFilterOptionBase(args, 'grade').some((item) => (
        studentHasMatchingCourse(item, (course) => normalizeAcademicGradeLabel(course.classItem.current_grade || course.classItem.grade || '') === grade)
      ));
    }),
    classOptions: args.scopedClasses.filter((classItem) => getStudentFilterOptionBase(args, 'class').some((item) => (
      studentHasMatchingCourse(item, (course) => course.classItem.id === classItem.id)
    ))),
  };
}

export function resolveFilteredStudentRows(args: StudentRuleBase & {
  filters: StudentFilterState;
}): StudentRow[] {
  return args.rows.filter((item) => studentMatchesFilters({ ...args, item })).sort((left, right) => {
    return left.name.localeCompare(right.name, 'zh-CN')
      || left.id - right.id
      || formatClassDisplayName(left.classItem).localeCompare(formatClassDisplayName(right.classItem), 'zh-CN');
  });
}

export function buildStudentFilterSummary(
  filters: StudentFilterState,
  users: UserItem[],
  classes: ClassItem[],
): string {
  return [
    filters.teacherFilter !== 'all' ? users.find((user) => user.id === filters.teacherFilter)?.name || '指定教师' : '',
    filters.subjectFilter !== '全部学科' ? filters.subjectFilter : '',
    filters.stageFilter !== '全部学段' ? filters.stageFilter : '',
    filters.gradeFilter !== '全部' ? filters.gradeFilter : '',
    filters.classFilter !== 'all' ? formatClassDisplayName(classes.find((item) => item.id === filters.classFilter)) || '指定班级' : '',
    filters.nameFilter.trim(),
  ].filter(Boolean).join(' / ') || '全部';
}

export function buildStudentFilterItems(
  filters: StudentFilterState,
  users: UserItem[],
  classes: ClassItem[],
): Array<FloatingFilterItem<StudentManagementFilterLayer>> {
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
    {
      key: 'class',
      defaultLabel: '班级',
      label: filters.classFilter === 'all' ? '班级' : formatClassDisplayName(classes.find((item) => item.id === filters.classFilter)) || '指定班级',
      selected: filters.classFilter !== 'all',
    },
  ];
}

export function resolveActiveStudentFilterOptions(
  activeLayer: StudentManagementFilterLayer | null,
  filters: StudentFilterState,
  options: {
    subjectOptions: string[];
    teacherOptions: UserItem[];
    stageOptions: string[];
    gradeOptions: string[];
    classOptions: ClassItem[];
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
  if (activeLayer === 'grade') {
    return options.gradeOptions.map((grade) => ({ id: grade, label: grade, selected: filters.gradeFilter === grade }));
  }
  return options.classOptions.map((classItem) => ({ id: classItem.id, label: formatClassDisplayName(classItem), selected: filters.classFilter === classItem.id }));
}
