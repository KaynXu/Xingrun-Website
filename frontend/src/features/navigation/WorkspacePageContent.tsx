import type { ComponentType } from 'react';
import { AlertCircle } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';

import { CourseCalendarPage } from '../../CourseCalendarPage';
import type { CourseCalendarCustomItemRecord, CourseCalendarCustomScheduleRecord, CourseCalendarScheduleRecord, CourseCalendarTimeBlock } from '../../courseCalendarData';
import { SmartWrongQuestionsPage } from '../../SmartWrongQuestionsPage';
import { WorkspaceDashboard } from '../../WorkspaceDashboard';
import type { ClassBindingTarget, CurrentUser } from '../../App';
import type { ClassItem } from '../../App';
import { StudentCenterPage } from '../student-center/StudentCenterPage';
import { ClassFeedbackGenerationPage } from '../class-feedback/ClassFeedbackGenerationPage';
import { ReviewGenerationPage } from '../review-generation/ReviewGenerationPage';
import { LessonInput } from '../review-generation/LessonInput';
import { CreditCenterPage } from '../credits/CreditCenterPage';
import { SettingsPage } from '../settings/SettingsPage';
import { ApprovalPage } from '../approval/ApprovalPage';
import {
  workspaceCardClass,
  workspacePageClass,
  workspacePrimaryButtonClass,
  workspaceSecondaryButtonClass,
} from '../../workspaceShared';

type WorkspaceShellPage =
  | 'dashboard'
  | 'review-generation'
  | 'class-feedback-generation'
  | 'consultation'
  | 'calendar'
  | 'smartWrongQuestions'
  | 'classes'
  | 'accounts'
  | 'credit'
  | 'settings';

export function WorkspacePageContent({
  activeWorkspacePage,
  currentUser,
  isMobileViewport,
  canOpenWorkspacePage,
  hasOwnerAccess,
  hasStaffAccess,
  navigateWorkspacePage,
  handleReviewGenerationSuccess,
  ConsultationPageComponent,
  calendarLoading,
  calendarError,
  calendarAnchorDate,
  getTodayIsoDate,
  calendarClasses,
  calendarSchedules,
  calendarCustomItems,
  calendarCustomSchedules,
  calendarPageStepDays,
  handleCalendarPageStepDaysChange,
  handlePreviousCalendarPage,
  handleNextCalendarPage,
  handleScheduleCalendarClass,
  handleScheduleCalendarCustomItem,
  handleCreateCalendarCustomItem,
  handleDeleteCalendarCustomItem,
  handleDeleteCalendarSchedule,
  handleDeleteCalendarCustomSchedule,
  WorkspaceLoadingComponent,
  classBindingTarget,
  handleClearClassBindingTarget,
  handleOpenClassBinding,
  handleLogout,
}: {
  activeWorkspacePage: WorkspaceShellPage;
  currentUser: CurrentUser;
  isMobileViewport: boolean;
  canOpenWorkspacePage: (user: CurrentUser, page: WorkspaceShellPage) => boolean;
  hasOwnerAccess: (role: CurrentUser['role']) => boolean;
  hasStaffAccess: (role: CurrentUser['role']) => boolean;
  navigateWorkspacePage: (page: WorkspaceShellPage) => void;
  handleReviewGenerationSuccess: () => void;
  ConsultationPageComponent: ComponentType<{ currentUser: CurrentUser }>;
  calendarLoading: boolean;
  calendarError: string;
  calendarAnchorDate: string;
  getTodayIsoDate: () => string;
  calendarClasses: ClassItem[];
  calendarSchedules: CourseCalendarScheduleRecord[];
  calendarCustomItems: CourseCalendarCustomItemRecord[];
  calendarCustomSchedules: CourseCalendarCustomScheduleRecord[];
  calendarPageStepDays: number;
  handleCalendarPageStepDaysChange: (days: number) => void;
  handlePreviousCalendarPage: () => void;
  handleNextCalendarPage: () => void;
  handleScheduleCalendarClass: (classId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes?: number) => void;
  handleScheduleCalendarCustomItem: (customItemId: number, date: string, timeBlock: CourseCalendarTimeBlock, startOffsetMinutes?: number) => void;
  handleCreateCalendarCustomItem: (item: { title: string; time_range: string; note: string; visibility: 'private' | 'organization' }) => Promise<CourseCalendarCustomItemRecord>;
  handleDeleteCalendarCustomItem: (itemId: number) => void;
  handleDeleteCalendarSchedule: (scheduleId: number) => void;
  handleDeleteCalendarCustomSchedule: (scheduleId: number) => void;
  WorkspaceLoadingComponent: ComponentType<{ label?: string }>;
  classBindingTarget: ClassBindingTarget | null;
  handleClearClassBindingTarget: () => void;
  handleOpenClassBinding: (target: ClassBindingTarget) => void;
  handleLogout: () => void;
}) {
  return (
    <AnimatePresence mode={isMobileViewport ? undefined : 'wait'}>
      <motion.div
        key={activeWorkspacePage}
        initial={isMobileViewport ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={isMobileViewport ? { opacity: 1, y: 0 } : { opacity: 0, y: -6 }}
        transition={isMobileViewport ? { duration: 0 } : { duration: 0.18 }}
      >
        {activeWorkspacePage === 'dashboard' && (
          <WorkspaceDashboard
            currentUser={currentUser}
            setActivePage={navigateWorkspacePage}
            styles={{
              pageClass: workspacePageClass,
              cardClass: workspaceCardClass,
              primaryButtonClass: workspacePrimaryButtonClass,
              secondaryButtonClass: workspaceSecondaryButtonClass,
            }}
            canOpenAccounts={hasStaffAccess(currentUser.role)}
          />
        )}
        {activeWorkspacePage === 'review-generation' && canOpenWorkspacePage(currentUser, 'review-generation') && (
          <ReviewGenerationPage
            onSuccess={handleReviewGenerationSuccess}
            renderLessonInput={(handleFormSuccess) => (
              <LessonInput onSuccess={handleFormSuccess} currentUser={currentUser} />
            )}
          />
        )}
        {activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage(currentUser, 'class-feedback-generation') && <ClassFeedbackGenerationPage currentUser={currentUser} />}
        {activeWorkspacePage === 'consultation' && canOpenWorkspacePage(currentUser, 'consultation') && <ConsultationPageComponent currentUser={currentUser} />}
        {activeWorkspacePage === 'calendar' && canOpenWorkspacePage(currentUser, 'calendar') &&
          (calendarLoading ? (
            <div className={`${workspacePageClass}`}>
              <div className={`${workspaceCardClass} p-8`}>
                <WorkspaceLoadingComponent label="正在整理课程日历..." />
              </div>
            </div>
          ) : (
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
          ))}
        {activeWorkspacePage === 'smartWrongQuestions' &&
          canOpenWorkspacePage(currentUser, 'smartWrongQuestions') &&
          <SmartWrongQuestionsPage currentUser={currentUser} />}
        {activeWorkspacePage === 'classes' && canOpenWorkspacePage(currentUser, 'classes') && (
          <StudentCenterPage currentUser={currentUser} classBindingTarget={classBindingTarget} onClearClassBindingTarget={handleClearClassBindingTarget} />
        )}
        {activeWorkspacePage === 'credit' && hasOwnerAccess(currentUser.role) && <CreditCenterPage currentUser={currentUser} />}
        {activeWorkspacePage === 'accounts' && hasStaffAccess(currentUser.role) && <ApprovalPage currentUser={currentUser} onOpenClassBinding={handleOpenClassBinding} />}
        {activeWorkspacePage === 'settings' && <SettingsPage currentUser={currentUser} onLogout={handleLogout} />}
      </motion.div>
    </AnimatePresence>
  );
}
