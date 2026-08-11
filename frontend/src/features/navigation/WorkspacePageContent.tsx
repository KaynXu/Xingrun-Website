import { useCallback, useEffect, useRef, useState, type ComponentType } from 'react';
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
import { ConsultationMeetingWorkbench } from '../consultation/ConsultationMeetingWorkbench';
import { CurriculumKnowledgePage } from '../curriculum/CurriculumKnowledgePage';
import {
  getReviewTaskDockLessons,
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
  | 'curriculum-knowledge'
  | 'classes'
  | 'accounts'
  | 'credit'
  | 'settings';

const REVIEW_NOTICE_AUTO_DISMISS_MS = 6000;
const REVIEW_FAILED_TASK_AUTO_DISMISS_MS = 12000;

type ReviewFailureDockNotice = {
  lesson: ReviewLessonRecord;
  expiresAt: number;
};

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
  reviewTaskDockDismissed,
  setReviewTaskDockDismissed,
  onReviewTaskDockAvailableChange,
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
  reviewTaskDockDismissed: boolean;
  setReviewTaskDockDismissed: (dismissed: boolean) => void;
  onReviewTaskDockAvailableChange: (available: boolean) => void;
}) {
  const consultationMeetingMode = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('consultationMeeting') === '1';
  const [reviewFloatingNotice, setReviewFloatingNotice] = useState<ReviewGenerationFloatingNotice | null>(null);
  const [reviewLatestLessons, setReviewLatestLessons] = useState<ReviewLessonRecord[]>([]);
  const [reviewTaskStartedAtById, setReviewTaskStartedAtById] = useState<Record<number, number>>({});
  const [activeReviewTaskIds, setActiveReviewTaskIds] = useState<Set<number>>(() => new Set());
  const [reviewFailureNoticesByVersionId, setReviewFailureNoticesByVersionId] = useState<Record<number, ReviewFailureDockNotice>>({});
  const [reviewProgressNow, setReviewProgressNow] = useState(() => Date.now());
  const reviewFailureReceiptRequestedIds = useRef<Set<number>>(new Set());

  const refreshReviewLessons = useCallback((quiet = true) => (
    Promise.all([
      apiFetch<unknown>('/api/review-plans'),
      apiFetch<unknown>('/api/review-plans/failure-notifications'),
    ])
      .then(([lessonsPayload, notificationsPayload]) => {
        setReviewLatestLessons(normalizeReviewLessonsResponse(lessonsPayload));
        const failureLessons = normalizeReviewLessonsResponse(notificationsPayload)
          .filter((lesson) => lesson.latest_failed_version_id !== null);
        if (failureLessons.length === 0) {
          return;
        }
        const expiresAt = Date.now() + REVIEW_FAILED_TASK_AUTO_DISMISS_MS;
        setReviewFailureNoticesByVersionId((current) => {
          const next = { ...current };
          let changed = false;
          failureLessons.forEach((lesson) => {
            const versionId = lesson.latest_failed_version_id;
            if (versionId === null || next[versionId]) {
              return;
            }
            next[versionId] = { lesson, expiresAt };
            changed = true;
          });
          return changed ? next : current;
        });
        const failedLessonIds = new Set(failureLessons.map((lesson) => lesson.id));
        setActiveReviewTaskIds((current) => {
          const next = new Set(current);
          failedLessonIds.forEach((lessonId) => next.delete(lessonId));
          return next.size === current.size ? current : next;
        });
        setReviewTaskDockDismissed(false);
      })
      .catch((error) => {
        if (!quiet) {
          console.error(error);
        }
      })
  ), [setReviewTaskDockDismissed]);

  const acknowledgeReviewFailureNotifications = useCallback((versionIds: number[]) => {
    if (versionIds.length === 0) {
      return Promise.resolve();
    }
    const requests = [];
    for (let offset = 0; offset < versionIds.length; offset += 100) {
      requests.push(apiFetch('/api/review-plans/failure-notifications/seen', {
        method: 'POST',
        body: JSON.stringify({ version_ids: versionIds.slice(offset, offset + 100) }),
      }));
    }
    return Promise.all(requests).then(() => undefined);
  }, []);

  const handleReviewLessonsChange = useCallback((lessons: ReviewLessonRecord[]) => {
    setReviewLatestLessons(lessons);
  }, []);

  const handleReviewTaskStarted = useCallback((lessonId: number, startedAtMs: number) => {
    setReviewTaskStartedAtById((current) => ({ ...current, [lessonId]: startedAtMs }));
    setActiveReviewTaskIds((current) => new Set(current).add(lessonId));
    setReviewFailureNoticesByVersionId((current) => Object.fromEntries(
      Object.entries(current).filter(([, notice]) => notice.lesson.id !== lessonId),
    ));
    setReviewLatestLessons((current) => current.map((lesson) => (
      lesson.id === lessonId
        ? {
          ...lesson,
          has_version_generating: true,
          active_version_status: 'generating',
          active_version_created_at: new Date(startedAtMs).toISOString(),
          latest_generation_error: '',
          record_status: 'generating',
          generation_error: '',
        }
        : lesson
    )));
    setReviewTaskDockDismissed(false);
    void refreshReviewLessons();
  }, [refreshReviewLessons]);

  const handleReviewFloatingNotice = useCallback((notice: ReviewGenerationFloatingNotice) => {
    setReviewFloatingNotice(notice);
    setReviewTaskDockDismissed(false);
  }, []);

  const visibleFailedReviewVersionIds = new Set(Object.keys(reviewFailureNoticesByVersionId).map(Number));
  const reviewTaskDockSourceLessons = [
    ...reviewLatestLessons,
    ...Object.values(reviewFailureNoticesByVersionId).map((notice) => notice.lesson),
  ];
  const reviewDockLessons = getReviewTaskDockLessons(reviewTaskDockSourceLessons, visibleFailedReviewVersionIds);
  const hasReviewFloatingTask = reviewDockLessons.length > 0;
  const hasReviewDockContent = Boolean(reviewFloatingNotice) || hasReviewFloatingTask;
  const hasReviewPendingTask = reviewLatestLessons.some(isReviewLessonPending);
  const shouldPollReviewTasks = activeReviewTaskIds.size > 0 || hasReviewPendingTask;

  useEffect(() => {
    reviewFailureReceiptRequestedIds.current.clear();
    setReviewFailureNoticesByVersionId({});
    void refreshReviewLessons();
  }, [currentUser.id, refreshReviewLessons]);

  useEffect(() => {
    const versionIds = Object.keys(reviewFailureNoticesByVersionId)
      .map(Number)
      .filter((versionId) => !reviewFailureReceiptRequestedIds.current.has(versionId));
    if (versionIds.length === 0) {
      return;
    }
    versionIds.forEach((versionId) => reviewFailureReceiptRequestedIds.current.add(versionId));
    void acknowledgeReviewFailureNotifications(versionIds).catch(() => {
      versionIds.forEach((versionId) => reviewFailureReceiptRequestedIds.current.delete(versionId));
    });
  }, [acknowledgeReviewFailureNotifications, reviewFailureNoticesByVersionId]);

  useEffect(() => {
    if (!reviewFloatingNotice) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setReviewFloatingNotice(null);
    }, REVIEW_NOTICE_AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [reviewFloatingNotice]);

  useEffect(() => {
    onReviewTaskDockAvailableChange(hasReviewDockContent);
  }, [hasReviewDockContent, onReviewTaskDockAvailableChange]);

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
    const pendingTaskIds = reviewLatestLessons.filter(isReviewLessonPending).map((lesson) => lesson.id);
    if (pendingTaskIds.length === 0) {
      return;
    }

    setActiveReviewTaskIds((current) => {
      const next = new Set(current);
      pendingTaskIds.forEach((taskId) => next.add(taskId));
      return next.size === current.size ? current : next;
    });
  }, [reviewLatestLessons]);

  useEffect(() => {
    if (activeReviewTaskIds.size === 0) {
      return;
    }

    const settledLessons = reviewLatestLessons.filter((lesson) => (
      activeReviewTaskIds.has(lesson.id) && !isReviewLessonPending(lesson)
    ));
    if (settledLessons.length === 0) {
      return;
    }

    const settledTaskIds = new Set(settledLessons.map((lesson) => lesson.id));
    setActiveReviewTaskIds((current) => {
      const next = new Set(current);
      settledTaskIds.forEach((taskId) => next.delete(taskId));
      return next.size === current.size ? current : next;
    });
  }, [activeReviewTaskIds, reviewLatestLessons]);

  useEffect(() => {
    const nextExpiresAt = Math.min(...Object.values(reviewFailureNoticesByVersionId).map((notice) => notice.expiresAt));
    if (!Number.isFinite(nextExpiresAt)) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      const now = Date.now();
      setReviewFailureNoticesByVersionId((current) => Object.fromEntries(
        Object.entries(current).filter(([, notice]) => notice.expiresAt > now),
      ));
    }, Math.max(0, nextExpiresAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [reviewFailureNoticesByVersionId]);

  const reviewTaskControls = {
    progressNow: reviewProgressNow,
    taskStartedAtById: reviewTaskStartedAtById,
    onLessonsChange: handleReviewLessonsChange,
    onTaskStarted: handleReviewTaskStarted,
    onFloatingNotice: handleReviewFloatingNotice,
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
              renderLessonInput={(handleFormSuccess, handleFormCancel) => (
                <LessonInput onSuccess={handleFormSuccess} currentUser={currentUser} onCancel={handleFormCancel} />
              )}
            />
          )}
          {activeWorkspacePage === 'class-feedback-generation' && canOpenWorkspacePage(currentUser, 'class-feedback-generation') && <ClassFeedbackGenerationPage currentUser={currentUser} />}
          {activeWorkspacePage === 'consultation' && canOpenWorkspacePage(currentUser, 'consultation') && (
            consultationMeetingMode
              ? <ConsultationMeetingWorkbench currentUser={currentUser} />
              : <ConsultationPageComponent currentUser={currentUser} />
          )}
          {activeWorkspacePage === 'calendar' && canOpenWorkspacePage(currentUser, 'calendar') && <CalendarWorkspacePage currentUser={currentUser} />}
          {activeWorkspacePage === 'smartWrongQuestions' &&
            canOpenWorkspacePage(currentUser, 'smartWrongQuestions') &&
            <SmartWrongQuestionsPage currentUser={currentUser} />}
          {activeWorkspacePage === 'curriculum-knowledge' && canOpenWorkspacePage(currentUser, 'curriculum-knowledge') && (
            <CurriculumKnowledgePage currentUser={currentUser} />
          )}
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

      {!reviewTaskDockDismissed && hasReviewDockContent && (
        <ReviewGenerationTaskDock
          lessons={reviewTaskDockSourceLessons}
          notice={reviewFloatingNotice}
          onDismiss={() => {
            const versionIds = Array.from(visibleFailedReviewVersionIds);
            void acknowledgeReviewFailureNotifications(versionIds).catch(() => undefined);
            setReviewFloatingNotice(null);
            setReviewFailureNoticesByVersionId({});
            setReviewTaskDockDismissed(true);
          }}
          progressNow={reviewProgressNow}
          taskStartedAtById={reviewTaskStartedAtById}
          visibleFailedVersionIds={visibleFailedReviewVersionIds}
        />
      )}
    </>
  );
}
