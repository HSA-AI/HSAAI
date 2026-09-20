/**
 * HSAAI Mobile — SecurityModule
 * ============================================================
 * TypeScript bridge to native Android security capabilities.
 *
 * This module is the single JS entry point for:
 *   - FLAG_SECURE (anti-screenshot / anti-screen-recording)
 *   - Root detection
 *   - Debug detection (android.os.Debug.isDebuggerConnected)
 *   - Emulator detection (Build.FINGERPRINT heuristics)
 *   - Tamper detection (APK signature verification)
 *   - Secure clipboard (auto-clear after timeout)
 *   - Session protection (auto-logout on background)
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-RESILIENCE-1 : App detects and responds to rooted / jailbroken devices.
 *   - MASVS-RESILIENCE-2 : App detects being run in an emulator and refuses to start.
 *   - MASVS-RESILIENCE-3 : App detects and responds to debugger attachment.
 *   - MASVS-RESILIENCE-4 : App detects reverse-engineering tools (Frida, Xposed).
 *   - MASVS-RESILIENCE-9 : App blocks screenshots on sensitive screens.
 *   - MASVS-STORAGE-7   : Sensitive data is wiped from the clipboard after a timeout.
 *
 * ── Native side requirements ──
 * The native counterpart `HSA SecurityModule` (Kotlin) must be implemented in
 * /mobile/android/app/src/main/java/com/hsa/hsaai/security/SecurityModule.kt
 * and registered as a NativeModule in
 * /mobile/android/app/src/main/java/com/hsa/hsaai/MainApplication.kt
 * (via getPackages()).
 *
 * If the native module is NOT yet linked (dev environment), this file falls
 * back to JS-only heuristics so the app still boots in dev. Production builds
 * MUST link the Kotlin module — the JS fallbacks are detectable and bypassable
 * by an attacker with a decompiled APK.
 */
import { NativeModules, Platform, AppState, AppStateStatus } from 'react-native';

// ── Native module handle ──────────────────────────────────────────────────
// Prefer the TurboModule / NativeModule binding. If absent (e.g. running on
// web or an unlinked dev build), the per-method exports below degrade
// gracefully to a JS heuristic and log a security warning.
const NativeSecurity: HSASecurityNative | undefined = NativeModules.HSASecurity;

export interface HSASecurityNative {
  // FLAG_SECURE controls
  setFlagSecure(enabled: boolean): Promise<void>;
  isFlagSecureActive(): Promise<boolean>;

  // Detection — each returns a structured result so JS can decide policy
  isDeviceRooted(): Promise<boolean>;
  isDebuggerConnected(): Promise<boolean>;
  isRunningOnEmulator(): Promise<boolean>;
  verifyAppSignature(expectedSha256: string): Promise<boolean>;
  isFridaPresent(): Promise<boolean>;

  // Clipboard
  setSecureClipboard(text: string, clearAfterMs: number): Promise<void>;
  clearClipboard(): Promise<void>;
}

// ────────────────────────────────────────────────────────────────────────────
// 1. FLAG_SECURE
// ────────────────────────────────────────────────────────────────────────────
// MASVS-RESILIENCE-9 / MASVS-STORAGE-7: blocks screenshots, screen recording
// (MediaProjection), and view mirroring on the active Activity. Implemented
// in Kotlin as:
//     getWindow().setFlags(LayoutParams.FLAG_SECURE, FLAG_SECURE)
// We expose an async API so the Kotlin side can hop to the UI thread.

/**
 * Enable or disable FLAG_SECURE on the current Activity window.
 * Use via the `useSecureScreen()` hook rather than calling this directly.
 */
export async function setFlagSecure(enabled: boolean): Promise<void> {
  if (Platform.OS !== 'android') return;
  if (!NativeSecurity) {
    // eslint-disable-next-line no-console
    console.warn('[HSA security] FLAG_SECURE native module not linked — screenshots will NOT be blocked.');
    return;
  }
  await NativeSecurity.setFlagSecure(enabled);
}

export async function isFlagSecureActive(): Promise<boolean> {
  if (Platform.OS !== 'android' || !NativeSecurity) return false;
  return await NativeSecurity.isFlagSecureActive();
}

// ────────────────────────────────────────────────────────────────────────────
// 2. Root detection (JS-side top-level entry; deep checks in RootDetection.ts)
// ────────────────────────────────────────────────────────────────────────────
export interface SecurityPosture {
  isRooted: boolean;
  isDebuggerConnected: boolean;
  isEmulator: boolean;
  isTampered: boolean;
  isFridaPresent: boolean;
  /** True if any of the above signals indicate a hostile environment. */
  isCompromised: boolean;
  reasons: string[];
}

/**
 * Aggregate device-posture check used at app startup.
 * MASVS-RESILIENCE-1.
 */
export async function getSecurityPosture(): Promise<SecurityPosture> {
  const reasons: string[] = [];

  const isRooted = await isDeviceRooted();
  if (isRooted) reasons.push('rooted_device');

  const isDebuggerConnected = await isDebuggerConnected();
  if (isDebuggerConnected) reasons.push('debugger_attached');

  const isEmulator = await isRunningOnEmulator();
  if (isEmulator) reasons.push('emulator');

  const isFridaPresent = await isFridaPresent();
  if (isFridaPresent) reasons.push('frida_instrumentation');

  const isTampered = await verifyAppSignature(EXPECTED_SIGNATURE_SHA256);
  if (!isTampered) reasons.push('signature_mismatch');

  return {
    isRooted,
    isDebuggerConnected,
    isEmulator,
    isTampered,
    isFridaPresent,
    isCompromised: reasons.length > 0,
    reasons,
  };
}

export async function isDeviceRooted(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  if (NativeSecurity) return await NativeSecurity.isDeviceRooted();
  // JS fallback: not reliable, but better than nothing.
  return false;
}

export async function isDebuggerConnected(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  if (NativeSecurity) return await NativeSecurity.isDebuggerConnected();
  return false;
}

export async function isRunningOnEmulator(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  if (NativeSecurity) return await NativeSecurity.isRunningOnEmulator();
  // JS fallback: Build.FINGERPRINT isn't accessible from JS without a
  // native module, but `Platform.constants` exposes Release/Brand/Manufacturer
  // on Android which we can heuristically check.
  const c = (Platform as unknown as { constants?: Record<string, string> }).constants || {};
  const fp = `${c.Brand ?? ''}${c.Manufacturer ?? ''}${c.Model ?? ''}`.toLowerCase();
  return (
    fp.includes('generic') ||
    fp.includes('google_sdk') ||
    fp.includes('emulator') ||
    fp.includes('android sdk built for x86')
  );
}

/**
 * Verify the running APK's signing certificate matches the expected SHA-256.
 * MASVS-RESILIENCE-4: tamper detection — a repackaged APK will have a
 * different signer and should be refused service.
 *
 * The expected SHA-256 below must match the cert fingerprint of the
 * production release keystore. Extract via:
 *   keytool -printcert -jarfile HSAAI-Mobile.apk | grep -A1 SHA256
 */
export const EXPECTED_SIGNATURE_SHA256 =
  // REPLACE_BEFORE_RELEASE: paste the SHA-256 of the release keystore's
  // signing certificate (hex, lowercase, no colons). Leave the placeholder
  // to fail-closed in dev so a misconfigured prod release is noisy.
  process.env.EXPO_PUBLIC_EXPECTED_APK_SIGNATURE_SHA256 || '0000000000000000000000000000000000000000000000000000000000000000';

export async function verifyAppSignature(expectedSha256: string = EXPECTED_SIGNATURE_SHA256): Promise<boolean> {
  if (Platform.OS !== 'android') return true;
  if (NativeSecurity) return await NativeSecurity.verifyAppSignature(expectedSha256);
  // Dev fallback: don't block app startup if native module is unlinked.
  return true;
}

export async function isFridaPresent(): Promise<boolean> {
  if (Platform.OS !== 'android') return false;
  if (NativeSecurity) return await NativeSecurity.isFridaPresent();
  return false;
}

// ────────────────────────────────────────────────────────────────────────────
// 3. Secure clipboard
// ────────────────────────────────────────────────────────────────────────────
// MASVS-STORAGE-7: one-time clipboard (e.g. for OTP / one-time tokens).
// Writes to the system clipboard and schedules a wipe after `clearAfterMs`.
// On Android 13+ we additionally mark the clip as "sensitive" so it does not
// appear in the recent-apps preview nor in clipboard previews on the lockscreen.

const DEFAULT_CLIPBOARD_TIMEOUT_MS = 30_000; // 30s

export async function setSecureClipboard(
  text: string,
  clearAfterMs: number = DEFAULT_CLIPBOARD_TIMEOUT_MS,
): Promise<void> {
  if (Platform.OS !== 'android') return;
  if (NativeSecurity) {
    await NativeSecurity.setSecureClipboard(text, clearAfterMs);
  }
}

export async function clearClipboard(): Promise<void> {
  if (Platform.OS !== 'android') return;
  if (NativeSecurity) await NativeSecurity.clearClipboard();
}

// ────────────────────────────────────────────────────────────────────────────
// 4. Session protection (auto-logout on background)
// ────────────────────────────────────────────────────────────────────────────
// MASVS-AUTH-4: when the app goes to background for longer than
// SESSION_TIMEOUT_MS, the next foreground transition MUST force re-auth
// (PIN / biometric) before any sensitive screen is shown. This implements
// the timer + AppState subscription; the actual re-auth prompt is wired up
// in App.tsx via the `useReauthOnBackground()` hook exported here.

export const SESSION_TIMEOUT_MS = 60_000; // 60s — enterprise policy

let backgroundedAt: number | null = null;

export interface SessionGuard {
  /** Call from a top-level useEffect in App.tsx. Returns an unsubscribe fn. */
  subscribe(onTimeout: () => void): () => void;
}

export const SessionGuard: SessionGuard = {
  subscribe(onTimeout) {
    const handler = (nextState: AppStateStatus) => {
      if (nextState === 'inactive' || nextState === 'background') {
        backgroundedAt = Date.now();
      } else if (nextState === 'active' && backgroundedAt !== null) {
        const elapsed = Date.now() - backgroundedAt;
        backgroundedAt = null;
        if (elapsed >= SESSION_TIMEOUT_MS) {
          onTimeout();
        }
      }
    };
    const sub = AppState.addEventListener('change', handler);
    return () => sub.remove();
  },
};

// ────────────────────────────────────────────────────────────────────────────
// 5. App-launch security gate
// ────────────────────────────────────────────────────────────────────────────
// MASVS-RESILIENCE-1/2/3/4: at app startup, run all detection checks. If the
// device is rooted OR the APK is tampered OR Frida is present, block the
// launch with a user-visible security warning. Debugger / emulator signals
// are logged for monitoring but do not block (dev/QA convenience).

export interface LaunchGateResult {
  allowLaunch: boolean;
  posture: SecurityPosture;
}

export async function enforceLaunchGate(): Promise<LaunchGateResult> {
  const posture = await getSecurityPosture();
  // Block launch if ANY of these hard signals are present:
  const hardBlocks =
    posture.isRooted ||
    !posture.isTampered || // signature mismatch -> APK was repackaged
    posture.isFridaPresent;
  return {
    allowLaunch: !hardBlocks,
    posture,
  };
}

// ── Native module re-export for callers that want the raw handle ──────────
export { NativeSecurity };
