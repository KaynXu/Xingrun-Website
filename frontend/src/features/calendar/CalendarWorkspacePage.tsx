import { useEffect, useState } from 'react';
import { AlertCircle } from 'lucide-react';

import { CourseCalendarPage } from '../../CourseCalendarPage';
import {
  getCurrentWeekTuesday,
  type CourseCalendarCustomItemRecord,
  type CourseCalendarCustomScheduleRecord,
  type CourseCalendarScheduleRecord,
  type CourseCalendarTimeBlock,
} from '../../courseCalendarData';
import type { ClassItem, CurrentUser } from '../../appTypes';
import {
  apiFetch,
  getTodayIsoDate,
  workspaceCardClass,
  workspacePageClass,
} from '../../workspaceShared';

function shiftIsoDate(dateString: string, days: number): string {
  const [year, month, day] = dateString.split('-').map((value) => Number(value));
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function CalendarWorkspacePage({ currentUser }: { currentUser: CurrentUser }) {
  const [calendarClasses, setCalendarClasses] = useState<ClassItem[]>([]);
  const [calendarSchedules, setCalendarSchedules] = useState<CourseCalendarScheduleRecord[]>([]);
  const [calendarCustomItems, setCalendarCustomItems] = useState<CourseCalendarCustomItemRecord[]>([]);
  const [calendarCustomSchedules, setCalendarCustomSchedules] = useState<CourseCalendarCustomScheduleRecord[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState('');
  const [calendarAnchorDate, setCalendarAnchorDate] = useState<string>(() => getCurrentWeekTuesday(getTodayIsoDate()));
  const [calendarPageStepDays, setCalendarPageStepDays] = useState(6);

  useEffect(() => {
    let cancelled = false;
    setCalendarLoading(true);
    setCalendarError('');

    Promise.all([
      apiFetch<ClassItem[]>('/api/classes'),
      apiFetch<{ items: CourseCalendarScheduleRecord[] }>('/api/course-calendar/schedules'),
      apiFetch<{ items: CourseCalendarCustomItemRecord[] }>('/api/course-calendar/custom-items'),
      apiFetch<{ items: CourseCalendarCustomScheduleRecord[] }>('/api/course-calendar/custom-schedules'),
    ])
      .then(([classes, schedulePayload, customItemPayload, customSchedulePayload]) => {
        if (cancelled) {
          return;
        }
        setCalendarClasses(classes);
        setCalendarSchedules(schedulePayload.items);
        setCalendarCustomItems(customItemPayload.items);
        setCalendarCustomSchedules(customSchedulePayload.items);
        setCalendarAnchorDate(getCurrentWeekTuesday(getTodayIsoDate()));
      })
      .catch((error) => {
        console.error(error);
        if (!cancelled) {
          setCalendarError(error instanceof Error ? error.message : '课程日历加载失败，请刷新重试。');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCalendarLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [currentUser.id, currentUser.role]);

  const handlePreviousCalendarPage = (dayCount: number) => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, -dayCount));
  };

  const handleNextCalendarPage = (dayCount: number) => {
    setCalendarAnchorDate((current) => shiftIsoDate(current, dayCount));
  };

  const handleCalendarPageStepDaysChange = (dayCount: number) => {
    setCalendarPageStepDays(Math.max(1, Math.min(14, Math.trunc(dayCount) || 6)));
  };

  const handleScheduleCalendarClass = (classId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes = 0) => {
    apiFetch<{ item: CourseCalendarScheduleRecord }>('/api/course-calendar/schedules', {
      method: 'POST',
      body: JSON.stringify({
        class_id: classId,
        date,
        time_block: timeBlock,
        start_offset_minutes: startOffsetMinutes,
      }),
    })
      .then(({ item }) => {
        setCalendarSchedules((current) => [
          ...current.filter(
            (schedule) =>
              schedule.id !== item.id
              && !(schedule.class_id === item.class_id && schedule.date === item.date && schedule.time_block === item.time_block),
          ),
          item,
        ]);
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '新增课程排期失败');
        }
      });
  };

  const handleDeleteCalendarSchedule = (scheduleId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/schedules/${scheduleId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarSchedules((current) => current.filter((schedule) => schedule.id !== scheduleId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除课程排期失败');
        }
      });
  };

  const handleCreateCalendarCustomItem = (item: { title: string; time_range: string; note: string; visibility: 'private' | 'organization' }) => {
    return apiFetch<{ item: CourseCalendarCustomItemRecord }>('/api/course-calendar/custom-items', {
      method: 'POST',
      body: JSON.stringify(item),
    })
      .then(({ item: createdItem }) => {
        setCalendarCustomItems((current) => [createdItem, ...current.filter((existing) => existing.id !== createdItem.id)]);
        return createdItem;
      })
      .catch((error) => {
        console.error(error);
        throw error;
      });
  };

  const handleDeleteCalendarCustomItem = (itemId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/custom-items/${itemId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarCustomItems((current) => current.filter((item) => item.id !== itemId));
        setCalendarCustomSchedules((current) => current.filter((schedule) => schedule.custom_item_id !== itemId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除自定义事项失败');
        }
      });
  };

  const handleScheduleCalendarCustomItem = (customItemId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes = 0) => {
    apiFetch<{ item: CourseCalendarCustomScheduleRecord }>('/api/course-calendar/custom-schedules', {
      method: 'POST',
      body: JSON.stringify({
        custom_item_id: customItemId,
        date,
        time_block: timeBlock,
        start_offset_minutes: startOffsetMinutes,
      }),
    })
      .then(({ item }) => {
        setCalendarCustomSchedules((current) => [
          ...current.filter(
            (schedule) =>
              schedule.id !== item.id
              && !(schedule.custom_item_id === item.custom_item_id && schedule.date === item.date && schedule.time_block === item.time_block),
          ),
          item,
        ]);
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '新增自定义事项排期失败');
        }
      });
  };

  const handleDeleteCalendarCustomSchedule = (scheduleId: number) => {
    apiFetch<{ ok: boolean; removed: boolean }>(`/api/course-calendar/custom-schedules/${scheduleId}`, {
      method: 'DELETE',
    })
      .then(() => {
        setCalendarCustomSchedules((current) => current.filter((schedule) => schedule.id !== scheduleId));
      })
      .catch((error) => {
        console.error(error);
        if (typeof window !== 'undefined') {
          window.alert(error instanceof Error ? error.message : '删除自定义事项排期失败');
        }
      });
  };

  if (calendarLoading) {
    return (
      <div className={workspacePageClass}>
        <div className={`${workspaceCardClass} p-8`}>
          <div className="flex items-center justify-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">正在整理课程日历...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {calendarError && (
        <div className={`${workspacePageClass} pb-0`}>
          <div className={`${workspaceCardClass} flex items-center gap-2 border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600 dark:border-rose-400/20 dark:bg-rose-500/10 dark:text-rose-300`}>
            <AlertCircle size={16} />
            <span>课程日历加载失败：{calendarError}</span>
          </div>
        </div>
      )}
      <CourseCalendarPage
        anchorDate={calendarAnchorDate}
        today={getTodayIsoDate()}
        currentUserId={currentUser.id}
        currentUserRole={currentUser.role}
        classes={calendarClasses}
        schedules={calendarSchedules}
        customItems={calendarCustomItems}
        customSchedules={calendarCustomSchedules}
        pageStepDays={calendarPageStepDays}
        onPageStepDaysChange={handleCalendarPageStepDaysChange}
        onPreviousPage={handlePreviousCalendarPage}
        onNextPage={handleNextCalendarPage}
        onScheduleClass={handleScheduleCalendarClass}
        onScheduleCustomItem={handleScheduleCalendarCustomItem}
        onCreateCustomItem={handleCreateCalendarCustomItem}
        onDeleteCustomItem={handleDeleteCalendarCustomItem}
        onDeleteSchedule={handleDeleteCalendarSchedule}
        onDeleteCustomSchedule={handleDeleteCalendarCustomSchedule}
      />
    </>
  );
}
