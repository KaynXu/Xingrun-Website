export const CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT = 'xr:class-commentary-navigation-request';

export type ClassCommentaryNavigationRequestDetail = {
  proceed: () => void;
};

export function requestClassCommentaryNavigation(proceed: () => void): boolean {
  if (typeof window === 'undefined') {
    return true;
  }
  return window.dispatchEvent(new CustomEvent<ClassCommentaryNavigationRequestDetail>(
    CLASS_COMMENTARY_NAVIGATION_REQUEST_EVENT,
    {
      cancelable: true,
      detail: { proceed },
    },
  ));
}
