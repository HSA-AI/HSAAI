/**
 * HSAAI Mobile — useSecureScreen React Hook
 * ============================================================
 * Activates FLAG_SECURE on the active Android Activity window for the
 * lifetime of a screen component. While active:
 *   - Screenshots are blocked (returns a black bitmap).
 *   - Screen recording via MediaProjection returns a black stream.
 *   - The screen content is omitted from the recent-apps preview.
 *
 * Usage (any sensitive screen):
 *
 *   import { useSecureScreen } from '@security/useSecureScreen';
 *
 *   export function LoginScreen() {
 *     useSecureScreen(); // <-- top of component body
 *     // ... rest of screen
 *   }
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-RESILIENCE-9 : Blocks screenshots on screens containing PII /
 *                          credentials / chat content / document previews.
 *   - MASVS-STORAGE-7    : Prevents sensitive screen content from being
 *                          persisted by the OS into the recents carousel.
 *
 * Screens that MUST mount this hook:
 *   - src/screens/auth/LoginScreen.tsx          (credentials)
 *   - src/screens/auth/SplashScreen.tsx         (may show user PII)
 *   - src/screens/chat/ChatScreen.tsx           (chat content)
 *   - src/screens/documents/DocumentUploadScreen.tsx (document previews)
 *   - src/screens/profile/ProfileScreen.tsx     (user PII)
 *   - src/screens/governance/ApprovalsScreen.tsx(approval secrets)
 *
 * Screens that SHOULD NOT use this hook (UX cost):
 *   - Dashboard, Knowledge Hub — these are non-sensitive and users frequently
 *     share screenshots of dashboards in support tickets. Blocking
 *     screenshots there is friction without security value.
 */
import { useEffect } from 'react';
import { Platform } from 'react-native';
import { setFlagSecure } from './SecurityModule';

/**
 * Activate FLAG_SECURE for the lifetime of the calling screen.
 *
 * @param enabled defaults to true; pass false to conditionally disable
 *                (e.g. when a developer-settings toggle is active).
 */
export function useSecureScreen(enabled: boolean = true): void {
  useEffect(() => {
    if (!enabled || Platform.OS !== 'android') return;

    // Set FLAG_SECURE on mount.
    let cancelled = false;
    setFlagSecure(true).catch((err) => {
      // eslint-disable-next-line no-console
      console.warn('[useSecureScreen] failed to enable FLAG_SECURE:', err);
    });

    return () => {
      cancelled = true;
      // Clear FLAG_SECURE on unmount so subsequent (non-sensitive) screens
      // are screenshotable again. The native module must hop to the UI
      // thread to call getWindow().clearFlags(FLAG_SECURE).
      setFlagSecure(false).catch((err) => {
        if (!cancelled) {
          // eslint-disable-next-line no-console
          console.warn('[useSecureScreen] failed to disable FLAG_SECURE:', err);
        }
      });
    };
  }, [enabled]);
}

export default useSecureScreen;
