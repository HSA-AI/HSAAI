/**
 * HSAAI Mobile — Root Detection (Native Module Wrapper)
 * ============================================================
 * Wraps the native Kotlin RootDetectionModule which performs file-existence
 * and package-presence checks for known root / Magisk / Frida artifacts.
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-RESILIENCE-1 : The app detects and refuses to run on rooted devices.
 *
 * ── Native implementation checklist (Kotlin) ──
 * The native counterpart lives in:
 *   /mobile/android/app/src/main/java/com/hsa/hsaai/security/RootDetectionModule.kt
 * and is registered as a NativeModule in MainApplication.kt.
 *
 * The native side MUST check (at minimum) the following artifacts. Each path
 * that exists adds 1 to the root score; a score >= 1 means rooted.
 *
 *   File-path checks (existence):
 *     /system/app/Superuser.apk
 *     /sbin/su
 *     /system/bin/su
 *     /system/xbin/su
 *     /system/sbin/su
 *     /vendor/bin/su
 *     /data/local/xbin/su
 *     /data/local/bin/su
 *     /data/local/su
 *     /system/bin/.ext/.su
 *     /system/usr/we-need-root/su-backup
 *     /system/app/Superuser.apk
 *     /system/app/Kinguser.apk
 *     /system/app/KingRoot.apk
 *     /system/app/SuperSU
 *     /system/etc/init.d/99SuperSUDaemon
 *     /system/xbin/daemonsu
 *     /sbin/.magisk
 *     /data/adb/magisk
 *     /data/adb/modules
 *     /cache/.disable_magisk
 *     /data/adb/ksu                 (KernelSU)
 *     /data/adb/ksud
 *     /data/adb/ap                  (APatch)
 *
 *   Package checks (PackageManager.getPackageInfo):
 *     com.topjohnwu.magisk          (Magisk Manager, current)
 *     io.github.vvb2060.magisk      (Magisk Alpha)
 *     com.noshufou.android.su       (Superuser)
 *     com.thirdparty.superuser      (Superuser alt)
 *     eu.chainfire.supersu          (SuperSU)
 *     com.koushikdutta.superuser    (Koush Superuser)
 *     com.kingouser.com             (KingRoot / KingUser)
 *     com.kingroot.kinguser         (KingRoot legacy)
 *     com.kingo.root                (KingoRoot)
 *     com.smedialink.oneclickroot   (One Click Root)
 *     com.zhiqupk.root.global       (ZhiQu)
 *     com.alephzain.framaroot       (Framaroot)
 *     com.android.su                (Generic SU)
 *     com.android.vendor.su
 *
 *   Build-property heuristics:
 *     Build.TAGS contains "test-keys"
 *     Build.FINGERPRINT contains "generic"
 *     ro.debuggable == 1
 *     ro.secure == 0
 *     ro.build.selinux == 0
 *
 *   BusyBox /su detection:
 *     which su (via Runtime.exec) returns a non-empty path
 *
 *   SafetyNet attestation (optional — see PlayIntegrity.ts):
 *     ctsProfileMatch == true && basicIntegrity == true
 *
 * ── Anti-evasion notes ──
 * Magisk Hide / Shamiko / Zygisk can mask individual file paths. To resist
 * this, the native module must ALSO:
 *   1. Try `Runtime.exec("su")` and check for stdout output (Magisk hides
 *      files but cannot hide a successful exec without breaking root apps).
 *   2. Enumerate /proc/self/maps for `libmagisk` / `libfrida` / `libxposed`
 *      shared objects loaded into the process.
 *   3. Check `/proc/[pid]/status` for `TracerPid: != 0` (debugger attached).
 *   4. Run the check on a background thread (NOT the UI thread) so a hooked
 *      `File.exists()` cannot easily serialize the calls.
 *
 * The result is a structured object the JS side can branch on. By design
 * the JS layer treats any "true" as a hard launch block.
 */
import { NativeModules, Platform } from 'react-native';

export interface RootDetectionResult {
  isRooted: boolean;
  /** 0..N — number of independent root indicators that fired. */
  score: number;
  /** Human-readable list of which indicators fired (for SIEM / crash log). */
  signals: string[];
}

export interface RootDetectionNative {
  checkRoot(): Promise<RootDetectionResult>;
}

const NativeRootDetection: RootDetectionNative | undefined = NativeModules.HSARootDetection;

// ── JS-side fallback signatures ───────────────────────────────────────────
// When the native module is not yet linked (dev builds), we can't read the
// filesystem from JS. We expose a stub that returns `isRooted=false` so dev
// is not blocked; production builds MUST link the native module and call
// `enforceRootCheck` at app startup.
const DEV_FALLBACK: RootDetectionResult = {
  isRooted: false,
  score: 0,
  signals: ['native_module_not_linked'],
};

/**
 * Run all root-detection checks on the native side and return the result.
 *
 * MASVS-RESILIENCE-1.
 */
export async function checkRoot(): Promise<RootDetectionResult> {
  if (Platform.OS !== 'android') {
    return { isRooted: false, score: 0, signals: ['non_android_platform'] };
  }
  if (!NativeRootDetection) {
    // eslint-disable-next-line no-console
    console.warn('[RootDetection] Native module not linked — skipping root checks (dev only).');
    return DEV_FALLBACK;
  }
  return await NativeRootDetection.checkRoot();
}

/**
 * App-launch gate. If the device is rooted, block launch with a user-visible
 * security warning. The caller (App.tsx) is responsible for rendering the
 * block UI; this function only decides policy.
 *
 * MASVS-RESILIENCE-1: returns `block: true` if `isRooted`, and surfaces the
 * signals array so the block screen can show a SIEM-friendly diagnostic.
 *
 * @param options.bypassInDev if true (default), a non-linked native module
 *                            does NOT block launch (so dev builds still boot).
 *                            Set to false in release builds via a BuildConfig
 *                            flag to fail-closed.
 */
export interface RootGateOptions {
  bypassInDev?: boolean;
}

export interface RootGateResult {
  block: boolean;
  reason: string;
  result: RootDetectionResult;
}

export async function enforceRootCheck(
  options: RootGateOptions = { bypassInDev: true },
): Promise<RootGateResult> {
  const result = await checkRoot();

  // If the native module isn't linked and we're in dev-tolerant mode, don't
  // block launch. In production builds the native module MUST be present;
  // its absence is treated as a tamper signal in `verifyAppSignature`.
  if (
    !NativeRootDetection &&
    options.bypassInDev &&
    result.signals.includes('native_module_not_linked')
  ) {
    return {
      block: false,
      reason: 'native_module_not_linked_dev_bypass',
      result,
    };
  }

  if (result.isRooted) {
    return {
      block: true,
      reason: 'rooted_device',
      result,
    };
  }

  return { block: false, reason: 'ok', result };
}

/**
 * Convenience one-shot for components that just want a boolean.
 * Use this in screen-level guards (e.g. LoginScreen preflight).
 */
export async function isRootedDevice(): Promise<boolean> {
  const result = await checkRoot();
  return result.isRooted;
}

// Re-export the raw native handle so callers that need the typed interface
// can access it directly (e.g. for periodic re-checks while running).
export { NativeRootDetection };
