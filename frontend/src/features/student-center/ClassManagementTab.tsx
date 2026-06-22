import type { KeyboardEvent, MouseEvent } from 'react';
import { ChevronRight, PlusCircle } from 'lucide-react';
import { FloatingFilterBar, type FloatingFilterItem, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import { getAcademicStageFromGrade, normalizeAcademicGradeLabel } from '../../domain/classNaming';
import { buildDiceBearAvatarUrl, cn } from '../../workspaceShared';
import type { ClassItem, UserItem } from './model';
import {
  getStudentCenterSubjectBadgeClass,
  studentCenterMutedSurfaceClass,
  studentCenterPrimaryButtonClass,
  studentCenterSecondaryButtonClass,
  studentCenterSurfaceClass,
} from './ui';

export type ClassManagementFilterLayer = 'subject' | 'teacher' | 'stage' | 'grade';

type ClassManagementTabProps = {
  loading: boolean;
  classes: ClassItem[];
  filteredClasses: ClassItem[];
  users: UserItem[];
  studentsByClassId: Record<number, Array<{ id: number; name: string }>>;
  teacherBindingByClassId: Record<number, number | null>;
  expandedClassId: number | 'new' | null;
  classCardInteractionLocked: boolean;
  pageRefreshLocked: boolean;
  canCreateClass: boolean;
  canEditClassCards: boolean;
  classCardActionLabel: string;
  classScopeLabel: string;
  classFilterItems: Array<FloatingFilterItem<ClassManagementFilterLayer>>;
  activeClassFilterLayer: ClassManagementFilterLayer | null;
  activeClassFilterOptions: FloatingFilterOption[];
  activeClassFilterSummary: string;
  showClassCohortYear: boolean;
  subjectOptions: string[];
  onRefresh: () => void;
  onCreateClass: () => void;
  onClassFilterAreaEnter: () => void;
  onClassFilterAreaLeave: () => void;
  onActivateClassFilter: (key: ClassManagementFilterLayer) => void;
  onClearClassFilter: (key: ClassManagementFilterLayer) => void;
  onSelectClassFilterOption: (value: string | number) => void;
  onShowClassCohortYearChange: (checked: boolean) => void;
  onClassCardClick: (event: MouseEvent<HTMLElement>, classId: number) => void;
  onToggleExpandedClass: (classId: number | 'new') => void;
  getClassEffectiveSubject: (item: ClassItem) => string;
  getClassInfoIssues: (item: ClassItem) => string[];
  getClassDisplayName: (item: ClassItem) => string;
};

export function ClassManagementTab({
  loading,
  classes,
  filteredClasses,
  users,
  studentsByClassId,
  teacherBindingByClassId,
  expandedClassId,
  classCardInteractionLocked,
  pageRefreshLocked,
  canCreateClass,
  canEditClassCards,
  classCardActionLabel,
  classScopeLabel,
  classFilterItems,
  activeClassFilterLayer,
  activeClassFilterOptions,
  activeClassFilterSummary,
  showClassCohortYear,
  subjectOptions,
  onRefresh,
  onCreateClass,
  onClassFilterAreaEnter,
  onClassFilterAreaLeave,
  onActivateClassFilter,
  onClearClassFilter,
  onSelectClassFilterOption,
  onShowClassCohortYearChange,
  onClassCardClick,
  onToggleExpandedClass,
  getClassEffectiveSubject,
  getClassInfoIssues,
  getClassDisplayName,
}: ClassManagementTabProps) {
  return (
    <section className={`${studentCenterSurfaceClass} space-y-5 p-6`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">班级列表</h4>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {canEditClassCards ? '按筛选范围查看班级，逐条进入编辑窗口维护基础信息、老师和学员。' : '查看本人负责班级的基础信息和学员情况。'}
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={onRefresh}
            disabled={pageRefreshLocked}
            className={studentCenterSecondaryButtonClass}
          >
            刷新列表
          </button>
          {canCreateClass && (
            <button
              type="button"
              onClick={onCreateClass}
              disabled={classCardInteractionLocked}
              className={studentCenterPrimaryButtonClass}
            >
              <PlusCircle size={18} />
              新建班级
            </button>
          )}
        </div>
      </div>

      <FloatingFilterBar
        items={classFilterItems}
        activeKey={activeClassFilterLayer}
        options={activeClassFilterOptions}
        scopeLabel={classScopeLabel}
        summary={activeClassFilterSummary}
        summaryText="未筛选时默认按年级从低到高排列。"
        tone="slate"
        onAreaEnter={onClassFilterAreaEnter}
        onAreaLeave={onClassFilterAreaLeave}
        onActivate={onActivateClassFilter}
        onClear={onClearClassFilter}
        onSelect={onSelectClassFilterOption}
        extraControls={(
          <label className="inline-flex min-h-10 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
            <input
              type="checkbox"
              checked={showClassCohortYear}
              onChange={(event) => onShowClassCohortYearChange(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-400"
            />
            入学年份
          </label>
        )}
      />

      {loading ? (
        <div className="rounded-2xl border border-dashed border-slate-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
          正在加载班级数据...
        </div>
      ) : (
        <div className="space-y-3">
          {filteredClasses.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">
              {classes.length === 0 ? '暂无班级，点击右上角“新建班级”开始创建。' : `当前筛选“${activeClassFilterSummary}”下暂无班级。`}
            </div>
          ) : null}

          {filteredClasses.length > 0 ? (
            <div className={`${studentCenterMutedSurfaceClass} overflow-hidden p-0`}>
              <div className="divide-y divide-slate-200 dark:divide-white/10">
                {filteredClasses.map((item) => {
                  const isExpanded = expandedClassId === item.id;
                  const currentTeacherUserId = teacherBindingByClassId[item.id] ?? item.teacher_user_id ?? null;
                  const currentTeacher = currentTeacherUserId == null ? undefined : users.find((user) => user.id === currentTeacherUserId);
                  const teacherSummary = currentTeacher?.name || item.teacher_name || '未分配老师';
                  const teacherAvatarUrl = buildDiceBearAvatarUrl(currentTeacher || { name: teacherSummary });
                  const gradeLabel = normalizeAcademicGradeLabel(item.current_grade || item.grade || '') || item.grade || '未填写年级';
                  const stageLabel = item.stage || getAcademicStageFromGrade(item.current_grade || item.grade || '') || '未填写学段';
                  const classStudents = studentsByClassId[item.id] || [];
                  const studentCount = Math.max(classStudents.length, Number(item.student_count || 0));
                  const visibleStudentNames = classStudents.slice(0, 4).map((student) => student.name);
                  const missingSubject = !item.subject || !subjectOptions.includes(item.subject);
                  const effectiveSubject = getClassEffectiveSubject(item);
                  const displayName = getClassDisplayName(item);
                  const classInfoIssues = getClassInfoIssues(item);
                  const secondaryInfoIssues = missingSubject
                    ? classInfoIssues.filter((issue) => issue !== '缺科目')
                    : classInfoIssues;

                  return (
                    <div
                      key={item.id}
                      role="button"
                      tabIndex={0}
                      onClick={(event) => onClassCardClick(event, item.id)}
                      onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          onToggleExpandedClass(item.id);
                        }
                      }}
                      aria-label={`打开班级 ${displayName}`}
                      className={cn(
                        'transition hover:bg-slate-50/90 dark:hover:bg-white/[0.04]',
                        isExpanded && 'bg-slate-50 dark:bg-white/[0.04]',
                        classCardInteractionLocked ? 'cursor-not-allowed opacity-75' : 'cursor-pointer',
                      )}
                    >
                      <div className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(14rem,1.3fr)_minmax(18rem,1fr)_auto] lg:items-center">
                  <div className="min-w-0">
                    <div className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="truncate text-base font-bold text-slate-900 dark:text-white">{displayName}</span>
                      {missingSubject ? (
                        <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200">
                          需填写科目{effectiveSubject ? ` · 按${effectiveSubject}筛选` : ''}
                        </span>
                      ) : (
                        <span className={getStudentCenterSubjectBadgeClass(item.subject)}>{item.subject}</span>
                      )}
                      {secondaryInfoIssues.length ? (
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300">
                          待补全：{secondaryInfoIssues.join(' / ')}
                        </span>
                      ) : null}
                      {item.is_bridge ? (
                        <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-400/10 dark:text-amber-200">衔接</span>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      <span>{stageLabel}</span>
                      <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
                      <span>{gradeLabel}</span>
                      <span className="h-1 w-1 rounded-full bg-slate-300 dark:bg-slate-600" />
                      <span>{studentCount ? `${studentCount}名学员` : '暂无学员'}</span>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-400 dark:text-slate-500">上课教师</p>
                      <div className="mt-1 flex items-center gap-2">
                        <img
                          src={teacherAvatarUrl}
                          alt={`${teacherSummary} 头像`}
                          className="h-6 w-6 shrink-0 rounded-full bg-slate-100 object-cover dark:bg-white/10"
                        />
                        <p className="truncate font-semibold text-slate-800 dark:text-slate-100">{teacherSummary}</p>
                      </div>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-400 dark:text-slate-500">班号</p>
                      <p className="mt-1 truncate font-semibold text-slate-800 dark:text-slate-100">{item.class_number ? `${item.class_number}班` : '未填写'}</p>
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-400 dark:text-slate-500">学员</p>
                      <p className="mt-1 truncate font-semibold text-slate-800 dark:text-slate-100">
                        {visibleStudentNames.length ? visibleStudentNames.join('、') : (studentCount ? `${studentCount}名学员` : '暂无学员')}
                      </p>
                    </div>
                  </div>
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onToggleExpandedClass(item.id)}
                        disabled={classCardInteractionLocked}
                        className={`${studentCenterPrimaryButtonClass} h-9 px-3 py-2 text-sm`}
                        title={canEditClassCards ? 'Command+S / Ctrl+S' : '查看班级学员'}
                      >
                        {classCardActionLabel}
                    </button>
                    <ChevronRight size={18} className="text-slate-400 dark:text-slate-500" />
                    </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
