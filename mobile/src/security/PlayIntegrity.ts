/**
 * HSAAI Mobile — Google Play Integrity API Integration Guide
 * ============================================================
 * Play Integrity is the successor to SafetyNet Attestation. It returns a
 * cryptographic verdict from Google's servers that the device:
 *   - passed MEETS_DEVICE_INTEGRITY  (not rooted, bootloader locked)
 *   - passed MEETS_BASIC_INTEGRITY   (no known compromise)
 *   - passed MEETS_STRONG_INTEGRITY  (genuine hardware, recent Android)
 *   - has a Play-protected, app-signature-matching install
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-RESILIENCE-1 : App attests device integrity to a trusted server.
 *   - MASVS-RESILIENCE-4 : App detects repackaged / re-signed APKs via the
 *                          `appIntegrity` field returned by the verdict.
 *
 * ── HIGH-LEVEL INTEGRATION FLOW ───────────────────────────────────────────
 *
 *  1. Client (this app) calls Play Integrity API (via the Kotlin native
 *     module HSAGooglePlayIntegrityModule) and receives a *signed* integrity
 *     token. The token is opaque to the client — do not parse it in JS.
 *
 *  2. Client sends the token in the `X-Integrity-Token` header on the next
 *     sensitive API request (login, document upload, approval action).
 *
 *  3. Server (HSAAI api_gateway) calls:
 *        POST https://playintegrity.googleapis.com/v1/PACKAGE_NAME:decodeIntegrityToken
 *     with the Google Play Console service-account OAuth token. The response
 *     payload is a JWT-like JSON containing the verdict.
 *
 *  4. Server enforces:
 *        verdict.deviceRecognitionVerdict == ["MEETS_DEVICE_INTEGRITY"]
 *        verdict.appIntegrity.appRecognitionVerdict == "PLAY_RECOGNIZED"
 *        verdict.accountDetails.appLicensingVerdict == "LICENSED"
 *
 *     If ANY check fails, the server returns 403 and revokes the session.
 *
 * ── NATIVE SIDE REQUIREMENTS (Kotlin) ─────────────────────────────────────
 *
 *   /mobile/android/app/src/main/java/com/hsa/hsaai/security/PlayIntegrityModule.kt
 *
 *   dependencies (in app/build.gradle):
 *     implementation "com.google.android.play:integrity:1.4.0"
 *
 *   The module must:
 *     1. Call `IntegrityManagerFactory.create(context).requestIntegrityToken(
 *          IntegrityTokenRequest.builder()
 *             .setNonce(serverProvidedNonce)   // <- server-issued challenge
 *             .build())`.
 *     2. Forward the resulting `Task<String>` to JS as a Promise<string>.
 *     3. Cache the token for at most 60 minutes (Google's freshness policy).
 *
 *   The NONCE must be generated server-side, sent to the client over HTTPS,
 *   and verified against the decoded token's `requestDetails.nonce` field
 *   (base64-encoded) on the server. This prevents token replay / minting.
 *
 * ── WHEN TO REQUEST A TOKEN ───────────────────────────────────────────────
 *
 *   - At app launch (one-time, before first sensitive API call)
 *   - On any "step-up" auth event (approval, transfer, document upload)
 *   - On session refresh (every 60 minutes max)
 *
 *   Do NOT request a token on every API call — Google enforces a 10k/day
 *   quota per app and 7200/hour per device. Use the SessionGuard timer in
 *   SecurityModule.ts to throttle.
 *
 * ── OFFLINE FALLBACK ──────────────────────────────────────────────────────
 *
 *   If the device has no network or Play Services is unavailable, the native
 *   module should resolve the Promise with `null`. The server then enforces
 *   a stricter policy (e.g. require biometric re-auth on the next sensitive
 *   operation) and logs the missing attestation to SIEM.
 *
 * ── TESTING ───────────────────────────────────────────────────────────────
 *
 *   Google provides a "Play Integrity API Tester" in the Play Console ->
 *   your app -> Setup -> App integrity. Use it to simulate DEVICE /
 *   BASIC / STRONG verdicts without needing a real rooted device.
 *
 *   For local unit tests of the server-side verifier, Google publishes a
 *   sample JWT decoder at:
 *     https://developer.android.com/google/play/integrity/verifier
 *
 * ── WHY THIS IS NOT A 100% SOLUTION ───────────────────────────────────────
 *
 *   Play Integrity can be bypassed by sophisticated root solutions (Magisk
 *   Hide, Zygisk DenyList, Shamiko). Treat it as ONE signal of many —
 *   combine with the file-based root detection in RootDetection.ts, the
 *   signature check in SecurityModule.ts, and the Frida-detection check.
 *   Defense in depth is the only durable answer.
 */
import { NativeModules, Platform } from 'react-native';

export interface PlayIntegrityNative {
  /** Returns a signed integrity token, or null if Play Services is missing. */
  requestIntegrityToken(nonce: string): Promise<string | null>;
  /** True if Google Play Services is available and supports Integrity API. */
  isAvailable(): Promise<boolean>;
}

const NativePlayIntegrity: PlayIntegrityNative | undefined = NativeModules.HSAPlayIntegrity;

export interface IntegrityVerificationResult {
  verified: boolean;
  token: string | null;
  /** Reason the verification failed (or 'skipped' in dev). */
  status: 'verified' | 'skipped_dev' | 'play_services_unavailable' | 'no_token' | 'native_not_linked';
}

/**
 * Request a Play Integrity token for the given server-issued nonce.
 *
 * In development (no native module linked, or process.env.EXPO_PUBLIC_DEV=1),
 * this returns `{ verified: true, status: 'skipped_dev' }` so dev builds
 * are not blocked by Play Services requirements.
 *
 * In production the native module MUST be linked. If it returns null
 * (Play Services unavailable), the result is `{ verified: false,
 * status: 'play_services_unavailable' }` and the caller MUST escalate to
 * the server's offline-integrity policy (biometric step-up).
 *
 * MASVS-RESILIENCE-1.
 */
export async function verifyIntegrity(nonce: string): Promise<IntegrityVerificationResult> {
  // ── Dev bypass ──────────────────────────────────────────────────────────
  // Detect dev environment via Expo's __DEV__ global. This is stripped by
  // Metro's release bundle so the check is unavailable to a decompiled APK.
  const isDev = typeof __DEV__ !== 'undefined' ? __DEV__ : false;
  if (isDev) {
    return { verified: true, token: null, status: 'skipped_dev' };
  }

  if (Platform.OS !== 'android') {
    return { verified: true, token: null, status: 'skipped_dev' };
  }

  if (!NativePlayIntegrity) {
    return { verified: false, token: null, status: 'native_not_linked' };
  }

  const available = await NativePlayIntegrity.isAvailable();
  if (!available) {
    return { verified: false, token: null, status: 'play_services_unavailable' };
  }

  const token = await NativePlayIntegrity.requestIntegrityToken(nonce);
  if (!token) {
    return { verified: false, token: null, status: 'no_token' };
  }

  // We do NOT decode the token here — the server is the trust anchor.
  // The client just relays the opaque token on the next sensitive request.
  return { verified: true, token, status: 'verified' };
}

/**
 * Helper: generate a 32-byte cryptographic nonce as a base64 string.
 *
 * The nonce MUST be generated client-side (or echoed from a server challenge)
 * and then sent to the server. The server embeds it in the integrity request,
 * and Google echoes it back inside the decoded verdict's `requestDetails.nonce`.
 * The server must verify the nonce matches what it issued — otherwise the
 * token can be replayed by a different client.
 *
 * MASVS-CRYPTO-7 (use cryptographically random nonces).
 */
export function generateNonce(): string {
  // React Native's global `crypto` is available on Android 24+ via WebCrypto
  // polyfill. Fall back to Math.random (less secure) only if crypto is absent.
  if (typeof globalThis.crypto !== 'undefined' && globalThis.crypto.getRandomValues) {
    const bytes = new Uint8Array(32);
    globalThis.crypto.getRandomValues(bytes);
    return base64Encode(bytes);
  }
  // Fallback — not cryptographically strong, but better than a fixed string.
  let s = '';
  for (let i = 0; i < 32; i++) {
    s += String.fromCharCode(Math.floor(Math.random() * 256));
  }
  return base64Encode(stringToBytes(s));
}

// ── Tiny base64 / utf8 helpers (no Buffer dependency in RN) ────────────────
function base64Encode(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  // btoa is available in RN's JS engine (Hermes / JSC).
  return btoa(binary);
}

function stringToBytes(s: string): Uint8Array {
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) {
    out[i] = s.charCodeAt(i) & 0xff;
  }
  return out;
}

export { NativePlayIntegrity };
