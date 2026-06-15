import { Plus, Search } from 'lucide-react';
import { FloatingFilterBar, type FloatingFilterItem, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import type { ClassItem, UserItem } from './model';
import type { StudentScheduleStatusFilter } from './studentFilterRules';
import {
  studentCenterFieldClass,
  studentCenterPrimaryButtonClass,
  studentCenterSecondaryButtonClass,
  studentCenterSurfaceClass,
} from './ui';

export type StudentManagementFilterLayer = 'subject' | 'teacher' | 'stage' | 'grade' | 'class';

export type StudentManagementRow = {
  id: number;
  name: string;
  classItem: ClassItem | null;
  teacherUserId: number | null;
  scheduled: boolean;
};

type StudentManagementTabProps = {
  filteredStudentRows: StudentManagementRow[];
  users: UserItem[];
  studentFilterItems: Array<FloatingFilterItem<StudentManagementFilterLayer>>;
  activeStudentFilterLayer: StudentManagementFilterLayer | null;
  activeStudentFilterOptions: FloatingFilterOption[];
  studentScopeLabel: string;
  activeStudentFilterSummary: string;
  studentNameFilter: string;
  scheduleStatusFilter: StudentScheduleStatusFilter;
  canManageStudents: boolean;
  onStudentFilterAreaEnter: () => void;
  onStudentFilterAreaLeave: () => void;
  onActivateStudentFilter: (key: StudentManagementFilterLayer) => void;
  onClearStudentFilter: (key: StudentManagementFilterLayer) => void;
  onSelectStudentFilterOption: (value: string | number) => void;
  onStudentNameFilterChange: (value: string) => void;
  onScheduleStatusFilterChange: (value: StudentScheduleStatusFilter) => void;
  onCreateStudent: () => void;
  onOpenStudentProfile: (studentId: number) => void;
  getClassDisplayName: (item: ClassItem) => string;
};

export function StudentManagementTab({
  filteredStudentRows,
  users,
  studentFilterItems,
  activeStudentFilterLayer,
  activeStudentFilterOptions,
  studentScopeLabel,
  activeStudentFilterSummary,
  studentNameFilter,
  scheduleStatusFilter,
  canManageStudents,
  onStudentFilterAreaEnter,
  onStudentFilterAreaLeave,
  onActivateStudentFilter,
  onClearStudentFilter,
  onSelectStudentFilterOption,
  onStudentNameFilterChange,
  onScheduleStatusFilterChange,
  onCreateStudent,
  onOpenStudentProfile,
  getClassDisplayName,
}: StudentManagementTabProps) {
  return (
    <section className={`${studentCenterSurfaceClass} space-y-5 p-6`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-xl font-semibold text-slate-900 dark:text-white">学员列表</h4>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">按排课状态和课程范围筛选学员，进入档案继续维护来源、家长联系方式和班级安排。</p>
        </div>
        {canManageStudents ? (
          <button type="button" onClick={onCreateStudent} className={`${studentCenterPrimaryButtonClass} h-10 px-4 py-2 text-sm`}>
            <Plus size={16} />
            新建学员
          </button>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: 'all' as const, label: '全部' },
          { key: 'scheduled' as const, label: '已排课' },
          { key: 'unscheduled' as const, label: '未排课' },
        ].map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onScheduleStatusFilterChange(item.key)}
            className={[
              'h-9 rounded-full px-4 text-sm font-semibold transition',
              scheduleStatusFilter === item.key
                ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
                : 'border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300 dark:hover:bg-white/[0.08]',
            ].join(' ')}
          >
            {item.label}
          </button>
        ))}
      </div>
      {scheduleStatusFilter === 'scheduled' ? (
        <FloatingFilterBar
          items={studentFilterItems}
          activeKey={activeStudentFilterLayer}
          options={activeStudentFilterOptions}
          scopeLabel={studentScopeLabel}
          summary={activeStudentFilterSummary}
          tone="slate"
          onAreaEnter={onStudentFilterAreaEnter}
          onAreaLeave={onStudentFilterAreaLeave}
          onActivate={onActivateStudentFilter}
          onClear={onClearStudentFilter}
          onSelect={onSelectStudentFilterOption}
          extraControls={(
            <label className="relative w-full sm:ml-2 sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={16} />
              <input
                value={studentNameFilter}
                onChange={(event) => onStudentNameFilterChange(event.target.value)}
                placeholder="学员姓名查询"
                className={`${studentCenterFieldClass} h-10 rounded-full py-2 pl-9 pr-9 text-sm`}
              />
              {studentNameFilter.trim() ? (
                <button
                  type="button"
                  onClick={() => onStudentNameFilterChange('')}
                  className="absolute right-3 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-400 transition hover:bg-slate-200 hover:text-slate-700 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-white/15 dark:hover:text-white"
                  aria-label="清空学员姓名查询"
                >
                  ×
                </button>
              ) : null}
            </label>
          )}
        />
      ) : null}
      <div className="overflow-hidden rounded-[1.25rem] border border-slate-200 bg-white dark:border-white/10 dark:bg-slate-950">
        <div className="hidden grid-cols-[minmax(9rem,1.1fr)_minmax(12rem,1.4fr)_minmax(9rem,1fr)_auto] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-bold text-slate-400 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-500 md:grid">
          <span>学员</span>
          <span>课程状态</span>
          <span>负责教师</span>
          <span className="text-right">操作</span>
        </div>
        <div className="divide-y divide-slate-200 dark:divide-white/10">
        {filteredStudentRows.length ? filteredStudentRows.map((item) => {
          const teacher = item.teacherUserId == null ? undefined : users.find((user) => user.id === item.teacherUserId);
          const classLabel = item.classItem ? getClassDisplayName(item.classItem) : '未排课';
          const detailLine = item.classItem
            ? [item.classItem.stage, item.classItem.current_grade || item.classItem.grade].filter(Boolean).join(' · ')
            : '暂无课程安排';
          const teacherLabel = item.classItem ? teacher?.name || item.classItem.teacher_name || '未分配老师' : '-';
          return (
            <div
              key={`${item.classItem?.id || 'unscheduled'}-${item.id}`}
              className="grid gap-3 px-4 py-3 transition hover:bg-slate-50 md:grid-cols-[minmax(9rem,1.1fr)_minmax(12rem,1.4fr)_minmax(9rem,1fr)_auto] md:items-center dark:hover:bg-white/[0.04]"
            >
              <div>
                <p className="text-base font-semibold text-slate-900 dark:text-white">{item.name}</p>
                <p className="mt-1 text-xs text-slate-400 md:hidden dark:text-slate-500">{teacherLabel}</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{classLabel}</p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{detailLine}</p>
              </div>
              <p className="hidden text-sm text-slate-500 md:block dark:text-slate-400">{teacherLabel}</p>
              <button
                type="button"
                onClick={() => onOpenStudentProfile(item.id)}
                className={`${studentCenterSecondaryButtonClass} h-9 justify-self-start px-3 py-2 text-sm md:justify-self-end`}
              >
                学员详情
              </button>
            </div>
          );
        }) : (
          <div className="p-10 text-center text-slate-500 dark:text-slate-400">当前筛选下暂无学员。</div>
        )}
        </div>
      </div>
    </section>
  );
}
