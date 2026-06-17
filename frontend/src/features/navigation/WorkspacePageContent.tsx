import { useCallback, useEffect, useState, type ComponentType } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import { SmartWrongQuestionsPage } from '../../SmartWrongQuestionsPage';
import { WorkspaceDashboard } from '../../WorkspaceDashboard';
import type { ClassBindingTarget, CurrentUser } from '../../appTypes';
import { CalendarWorkspacePage } from '../calendar/CalendarWorkspacePage';
import { StudentCenterPage } from '../student-center/StudentCenterPage';
import { ClassFeedbackGenerationPage } from '../class-feedback/ClassFeedbackGenerationPage';
import {
  ReviewGenerationPage,
  ReviewGenerationTaskDock,
  type ReviewGenerationFloatingNotice,
} from '../review-generation/ReviewGenerationPage';
import { LessonInput } from '../review-generation/LessonInput';
import { CreditCenterPage } from '../credits/CreditCenterPage';
import { SettingsPage } from '../settings/SettingsPage';
import { ApprovalPage } from '../approval/ApprovalPage';
import {
  getReviewLessonTaskState,
  isReviewLessonPending,
  normalizeReviewLessonsResponse,
  type ReviewLessonRecord,
} from '../../reviewGenerationAsync';
import {
  apiFetch,
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
  classBindingTarget,
  handleClearClassBindingTarget,
  handleOpenClassBinding,
  handleLogout,
  onCurrentUserUpdated,
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
  classBindingTarget: ClassBindingTarget | null;
  handleClearClassBindingTarget: () => void;
  handleOpenClassBinding: (target: ClassBindingTarget) => void;
  handleLogout: () => void;
  onCurrentUserUpdated: (user: CurrentUser) => void;
}) {
  const [reviewFloatingNotice, setReviewFloatingNotice] = useState<ReviewGenerationFloatingNotice | null>(null);
  const [reviewLatestLessons, setReviewLatestLessons] = useState<ReviewLessonRecord[]>([]);
  const [reviewTaskStartedAtById, setReviewTaskStartedAtById] = useState<Record<number, number>>({});
  const [activeReviewTaskIds, setActiveReviewTaskIds] = useState<Set<number>>(() => new Set());
  const [reviewProgressNow, setReviewProgressNow] = useState(() => Date.now());

  const refreshReviewLessons = useCallback((quiet = true) => (
    apiFetch<unknown>('/api/review-plans')
      .then((payload) => {
        setReviewLatestLessons(normalizeReviewLessonsResponse(payload));
      })
      .catch((error) => {
        if (!quiet) {
          console.error(error);
        }
      })
  ), []);

  const handleReviewLessonsChange = useCallback((lessons: ReviewLessonRecord[]) => {
    setReviewLatestLessons(lessons);
  }, []);

  const handleReviewTaskStarted = useCallback((lessonId: number, startedAtMs: number) => {
    setReviewTaskStartedAtById((current) => ({ ...current, [lessonId]: startedAtMs }));
    setActiveReviewTaskIds((current) => new Set(current).add(lessonId));
    void refreshReviewLessons();
  }, [refreshReviewLessons]);

  const hasReviewFloatingTask = reviewLatestLessons.some((lesson) => {
    const state = getReviewLessonTaskState(lesson);
    return state === 'pending' || state === 'failed' || state === 'missing-output';
  });
  const hasReviewPendingTask = reviewLatestLessons.some(isReviewLessonPending);
  const shouldPollReviewTasks = activeReviewTaskIds.size > 0 || hasReviewPendingTask;

  useEffect(() => {
    if (!hasReviewFloatingTask && activeReviewTaskIds.size === 0) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setReviewProgressNow(Date.now());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeReviewTaskIds, hasReviewFloatingTask]);

  useEffect(() => {
    if (!shouldPollReviewTasks) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void refreshReviewLessons();
    }, activeWorkspacePage === 'review-generation' ? 6000 : 3000);
    return () => window.clearInterval(timer);
  }, [activeWorkspacePage, refreshReviewLessons, shouldPollReviewTasks]);

  useEffect(() => {
    if (activeReviewTaskIds.size === 0) {
      return;
    }

    setActiveReviewTaskIds((current) => {
      const next = new Set(current);
      for (const taskId of current) {
        const matchingLesson = reviewLatestLessons.find((lesson) => lesson.id === taskId);
        if (matchingLesson && !isReviewLessonPending(matchingLesson)) {
          next.delete(taskId);
        }
      }
      return next.size === current.size ? current : next;
    });
  }, [activeReviewTaskIds, reviewLatestLessons]);

  const reviewTaskControls = {
    progressNow: reviewProgressNow,
    taskStartedAtById: reviewTaskStartedAtById,
    onLessonsChange: handleReviewLessonsChange,
    onTaskStarted: handleReviewTaskStarted,
    onFloatingNotice: setReviewFloatingNotice,
  };

  return (
    <>
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
              taskControls={reviewTaskControls}
              renderLessonInput={(handleFormSuccess) => (
                <LessonInput onSuccess={handleFormSuccess} currentUser={currentUser} />
              )}
            />
          )}
          {activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage(currentUser, 'class-feedback-generation') && <ClassFeedbackGenerationPage currentUser={currentUser} />}
          {activeWorkspacePage === 'consultation' && canOpenWorkspacePage(currentUser, 'consultation') && <ConsultationPageComponent currentUser={currentUser} />}
          {activeWorkspacePage === 'calendar' && canOpenWorkspacePage(currentUser, 'calendar') && <CalendarWorkspacePage currentUser={currentUser} />}
          {activeWorkspacePage === 'smartWrongQuestions' &&
            canOpenWorkspacePage(currentUser, 'smartWrongQuestions') &&
            <SmartWrongQuestionsPage currentUser={currentUser} />}
          {activeWorkspacePage === 'classes' && canOpenWorkspacePage(currentUser, 'classes') && (
            <StudentCenterPage currentUser={currentUser} classBindingTarget={classBindingTarget} onClearClassBindingTarget={handleClearClassBindingTarget} />
          )}
          {activeWorkspacePage === 'credit' && hasOwnerAccess(currentUser.role) && <CreditCenterPage currentUser={currentUser} />}
          {activeWorkspacePage === 'accounts' && hasStaffAccess(currentUser.role) && <ApprovalPage currentUser={currentUser} onOpenClassBinding={handleOpenClassBinding} />}
          {activeWorkspacePage === 'settings' && (
            <SettingsPage currentUser={currentUser} onCurrentUserUpdated={onCurrentUserUpdated} />
          )}
        </motion.div>
      </AnimatePresence>

      <ReviewGenerationTaskDock
        lessons={reviewLatestLessons}
        notice={reviewFloatingNotice}
        onDismissNotice={() => setReviewFloatingNotice(null)}
        progressNow={reviewProgressNow}
        taskStartedAtById={reviewTaskStartedAtById}
      />
    </>
  );
}
