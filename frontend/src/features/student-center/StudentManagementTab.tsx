import { Search } from 'lucide-react';
import { FloatingFilterBar, type FloatingFilterItem, type FloatingFilterOption } from '../../components/FloatingFilterBar';
import {
  workspaceCardClass,
  workspaceFieldClass,
  workspaceSecondaryButtonClass,
  workspaceSoftCardClass,
} from '../../workspaceShared';
import type { ClassItem, UserItem } from './model';

export type StudentManagementFilterLayer = 'subject' | 'teacher' | 'stage' | 'grade' | 'class';

export type StudentManagementRow = {
  id: number;
  name: string;
  classItem: ClassItem;
  teacherUserId: number | null;
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
  onStudentFilterAreaEnter: () => void;
  onStudentFilterAreaLeave: () => void;
  onActivateStudentFilter: (key: StudentManagementFilterLayer) => void;
  onClearStudentFilter: (key: StudentManagementFilterLayer) => void;
  onSelectStudentFilterOption: (value: string | number) => void;
  onStudentNameFilterChange: (value: string) => void;
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
  onStudentFilterAreaEnter,
  onStudentFilterAreaLeave,
  onActivateStudentFilter,
  onClearStudentFilter,
  onSelectStudentFilterOption,
  onStudentNameFilterChange,
  getClassDisplayName,
}: StudentManagementTabProps) {
  return (
    <section className={`${workspaceCardClass} space-y-5 p-6`}>
      <div>
        <h4 className="text-xl font-semibold text-slate-900 dark:text-white">学员管理</h4>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">默认展示全部学员，可按教师、科目、学段、年级、班级筛选，并查询学员姓名。</p>
      </div>
      <FloatingFilterBar
        items={studentFilterItems}
        activeKey={activeStudentFilterLayer}
        options={activeStudentFilterOptions}
        scopeLabel={studentScopeLabel}
        summary={activeStudentFilterSummary}
        summaryText="未筛选时默认按年级、班级和姓名排序。"
        onAreaEnter={onStudentFilterAreaEnter}
        onAreaLeave={onStudentFilterAreaLeave}
        onActivate={onActivateStudentFilter}
        onClear={onClearStudentFilter}
        onSelect={onSelectStudentFilterOption}
        extraControls={(
          <label className="relative w-full sm:ml-2 sm:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-sky-500 dark:text-sky-300" size={16} />
            <input
              value={studentNameFilter}
              onChange={(event) => onStudentNameFilterChange(event.target.value)}
              placeholder="学员姓名查询"
              className={`${workspaceFieldClass} h-10 rounded-full bg-white py-2 pl-9 pr-9 text-sm dark:bg-slate-900/60`}
            />
            {studentNameFilter.trim() ? (
              <button
                type="button"
                onClick={() => onStudentNameFilterChange('')}
                className="absolute right-3 top-1/2 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-400 transition hover:bg-sky-100 hover:text-sky-600 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-sky-400/20 dark:hover:text-sky-100"
                aria-label="清空学员姓名查询"
              >
                ×
              </button>
            ) : null}
          </label>
        )}
      />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filteredStudentRows.length ? filteredStudentRows.map((item) => {
          const teacher = item.teacherUserId == null ? undefined : users.find((user) => user.id === item.teacherUserId);
          return (
            <div key={`${item.classItem.id}-${item.id}`} className={`${workspaceSoftCardClass} p-4`}>
              <p className="text-lg font-semibold text-slate-900 dark:text-white">{item.name}</p>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{getClassDisplayName(item.classItem)}</p>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{[item.classItem.stage, item.classItem.current_grade || item.classItem.grade, teacher?.name || item.classItem.teacher_name || '未分配老师'].filter(Boolean).join(' · ')}</p>
              <button type="button" className={`${workspaceSecondaryButtonClass} mt-4 h-9 px-3 py-2 text-sm`}>班级进出历史</button>
            </div>
          );
        }) : (
          <div className="rounded-2xl border border-dashed border-sky-200 p-10 text-center text-slate-500 dark:border-white/10 dark:text-slate-400">当前筛选下暂无学员。</div>
        )}
      </div>
    </section>
  );
}
