import type { ComponentType } from 'react';
import { AnimatePresence, motion } from 'motion/react';

import { SmartWrongQuestionsPage } from '../../SmartWrongQuestionsPage';
import { WorkspaceDashboard } from '../../WorkspaceDashboard';
import type { ClassBindingTarget, CurrentUser } from '../../appTypes';
import { CalendarWorkspacePage } from '../calendar/CalendarWorkspacePage';
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
          <SettingsPage currentUser={currentUser} onLogout={handleLogout} onCurrentUserUpdated={onCurrentUserUpdated} />
        )}
      </motion.div>
    </AnimatePresence>
  );
}
