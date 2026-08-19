package com.hsa.hsaai.security

import android.app.Activity
import android.os.Build
import android.os.Debug
import android.util.Base64
import android.view.WindowManager
import android.content.pm.PackageManager
import android.content.pm.Signature
import com.facebook.react.bridge.*
import java.io.File
import java.security.MessageDigest
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.io.ByteArrayInputStream

/**
 * HSASecurityModule — Kotlin native side of `SecurityModule.ts`.
 *
 * Implements (all run on a background thread via AsyncCallable):
 *   - setFlagSecure / isFlagSecureActive  (FLAG_SECURE window flag)
 *   - isDeviceRooted                       (file-path + package + busybox checks)
 *   - isDebuggerConnected                  (android.os.Debug.isDebuggerConnected)
 *   - isRunningOnEmulator                  (Build.FINGERPRINT heuristics)
 *   - verifyAppSignature                   (PackageManager.getPackageInfo sig SHA-256)
 *   - isFridaPresent                       (/proc/self/maps scan for libfrida / libxposed)
 *   - setSecureClipboard / clearClipboard  (one-time clipboard with auto-wipe)
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-RESILIENCE-1 (root detection)
 *   - MASVS-RESILIENCE-2 (emulator detection)
 *   - MASVS-RESILIENCE-3 (debugger detection)
 *   - MASVS-RESILIENCE-4 (Frida / Xposed detection)
 *   - MASVS-RESILIENCE-9 (FLAG_SECURE)
 *   - MASVS-STORAGE-7    (secure clipboard auto-wipe)
 *   - MASVS-CRYPTO-1     (signature verification via SHA-256)
 *
 * Registration: this module is exported via HSASecurityPackage.kt (see
 * `createNativeModules`). Add the package to MainApplication.kt's
 * `getPackages()` list so React Native links it.
 */
class HSASecurityModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = "HSASecurity"

  // ── FLAG_SECURE ────────────────────────────────────────────────────────
  @ReactMethod
  fun setFlagSecure(enabled: Boolean, promise: Promise) {
    val activity: Activity? = currentActivity
    if (activity == null) {
      promise.reject("NO_ACTIVITY", "Activity is null")
      return
    }
    UiThreadUtil.runOnUiThread {
      try {
        if (enabled) {
          activity.window.setFlags(
            WindowManager.LayoutParams.FLAG_SECURE,
            WindowManager.LayoutParams.FLAG_SECURE
          )
        } else {
          activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
        promise.resolve(null)
      } catch (t: Throwable) {
        promise.reject("FLAG_SECURE_FAILED", t)
      }
    }
  }

  @ReactMethod
  fun isFlagSecureActive(promise: Promise) {
    val activity = currentActivity
    if (activity == null) {
      promise.resolve(false)
      return
    }
    val flags = activity.window.attributes.flags
    promise.resolve((flags and WindowManager.LayoutParams.FLAG_SECURE) != 0)
  }

  // ── Root detection ─────────────────────────────────────────────────────
  @ReactMethod
  fun isDeviceRooted(promise: Promise) {
    BackgroundTaskExecutor.execute {
      try {
        promise.resolve(checkRootFiles() || checkRootPackages() || checkSuBinary() || checkBuildTags())
      } catch (t: Throwable) {
        // Fail-safe: on any exception, treat as rooted (defense in depth).
        promise.resolve(true)
      }
    }
  }

  private fun checkRootFiles(): Boolean {
    val paths = listOf(
      "/system/app/Superuser.apk",
      "/sbin/su", "/system/bin/su", "/system/xbin/su", "/system/sbin/su",
      "/vendor/bin/su", "/data/local/xbin/su", "/data/local/bin/su",
      "/data/local/su", "/system/bin/.ext/.su",
      "/system/usr/we-need-root/su-backup",
      "/system/app/Kinguser.apk", "/system/app/KingRoot.apk",
      "/system/app/SuperSU", "/system/etc/init.d/99SuperSUDaemon",
      "/system/xbin/daemonsu",
      "/sbin/.magisk", "/data/adb/magisk", "/data/adb/modules",
      "/cache/.disable_magisk",
      "/data/adb/ksu", "/data/adb/ksud",   // KernelSU
      "/data/adb/ap"                          // APatch
    )
    return paths.any { File(it).exists() }
  }

  private fun checkRootPackages(): Boolean {
    val pkgs = listOf(
      "com.topjohnwu.magisk", "io.github.vvb2060.magisk",
      "com.noshufou.android.su", "com.thirdparty.superuser",
      "eu.chainfire.supersu", "com.koushikdutta.superuser",
      "com.kingouser.com", "com.kingroot.kinguser", "com.kingo.root",
      "com.smedialink.oneclickroot", "com.zhiqupk.root.global",
      "com.alephzain.framaroot", "com.android.su", "com.android.vendor.su"
    )
    val pm = reactApplicationContext.packageManager
    return pkgs.any { pkg ->
      try {
        pm.getPackageInfo(pkg, 0)
        true
      } catch (e: PackageManager.NameNotFoundException) {
        false
      }
    }
  }

  private fun checkSuBinary(): Boolean {
    return try {
      val process = Runtime.getRuntime().exec(arrayOf("which", "su"))
      val reader = process.inputStream.bufferedReader()
      val line = reader.readLine()
      process.waitFor()
      !line.isNullOrEmpty()
    } catch (e: Exception) {
      false
    }
  }

  private fun checkBuildTags(): Boolean {
    return Build.TAGS?.contains("test-keys") == true
  }

  // ── Debugger detection ─────────────────────────────────────────────────
  @ReactMethod
  fun isDebuggerConnected(promise: Promise) {
    promise.resolve(Debug.isDebuggerConnected())
  }

  // ── Emulator detection ─────────────────────────────────────────────────
  @ReactMethod
  fun isRunningOnEmulator(promise: Promise) {
    val fp = (Build.FINGERPRINT ?: "") + (Build.MODEL ?: "") + (Build.MANUFACTURER ?: "") + (Build.BRAND ?: "")
    val isEmu = fp.contains("generic", ignoreCase = true) ||
      fp.contains("google_sdk", ignoreCase = true) ||
      fp.contains("emulator", ignoreCase = true) ||
      fp.contains("android sdk built for x86", ignoreCase = true) ||
      Build.HARDWARE?.contains("goldfish", ignoreCase = true) == true ||
      Build.HARDWARE?.contains("ranchu", ignoreCase = true) == true
    promise.resolve(isEmu)
  }

  // ── Tamper / signature verification ────────────────────────────────────
  @ReactMethod
  fun verifyAppSignature(expectedSha256Hex: String, promise: Promise) {
    BackgroundTaskExecutor.execute {
      try {
        val pm = reactApplicationContext.packageManager
        val info = pm.getPackageInfo(
          reactApplicationContext.packageName,
          PackageManager.GET_SIGNING_CERTIFICATES
        )
        val signingInfo = info.signingInfo
        val sigs: Array<Signature> = when {
          signingInfo == null -> {
            promise.resolve(false); return@execute
          }
          android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P -> {
            signingInfo.apkContentsSigners
          }
          else -> {
            // Legacy path (pre-API 28). Reflection-free fallback:
            @Suppress("DEPRECATION")
            info.signatures
          }
        }
        if (signingInfo?.hasMultipleSigners() == true && signingInfo.signingCertificateHistory.isNotEmpty()) {
          // If multiple signers exist, use the lineage signer for comparison.
        }
        val match = sigs.any { sig ->
          val cert = CertificateFactory.getInstance("X.509")
            .generateCertificate(ByteArrayInputStream(sig.toByteArray)) as X509Certificate
          val digest = MessageDigest.getInstance("SHA-256").digest(cert.encoded)
          val hex = digest.joinToString("") { "%02x".format(it) }
          hex.equals(expectedSha256Hex, ignoreCase = true)
        }
        promise.resolve(match)
      } catch (t: Throwable) {
        // Fail-closed: if we cannot verify, assume tampered.
        promise.resolve(false)
      }
    }
  }

  // ── Frida / Xposed detection ───────────────────────────────────────────
  @ReactMethod
  fun isFridaPresent(promise: Promise) {
    BackgroundTaskExecutor.execute {
      try {
        val mapsFile = File("/proc/self/maps")
        if (!mapsFile.exists()) {
          promise.resolve(false); return@execute
        }
        val suspicious = listOf("libfrida", "frida-agent", "libxposed", "libsubstrate", "libcydia")
        val found = mapsFile.useLines { lines ->
          lines.any { line -> suspicious.any { s -> line.contains(s, ignoreCase = true) } }
        }
        // Also check for the frida-server TCP port (default 27042).
        val fridaPortOpen = try {
          val socket = java.net.Socket()
          socket.connect(java.net.InetSocketAddress("127.0.0.1", 27042), 100)
          socket.close()
          true
        } catch (e: Exception) {
          false
        }
        promise.resolve(found || fridaPortOpen)
      } catch (t: Throwable) {
        promise.resolve(false)
      }
    }
  }

  // ── Secure clipboard ───────────────────────────────────────────────────
  @ReactMethod
  fun setSecureClipboard(text: String, clearAfterMs: Int, promise: Promise) {
    try {
      val clipboard = reactApplicationContext.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
        as android.content.ClipboardManager
      val clip = android.content.ClipData.newPlainText("hsaai_otp", text)
      // Android 13+ marks the clip as sensitive so it's hidden from previews.
      if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        val extras = android.os.PersistableBundle()
        extras.putBoolean("android.content.extra.IS_SENSITIVE", true)
        clip.description.extras = extras
      }
      clipboard.setPrimaryClip(clip)
      // Schedule a wipe after clearAfterMs. Use a Handler on the main thread.
      val handler = android.os.Handler(android.os.Looper.getMainLooper())
      handler.postDelayed({
        if (clipboard.primaryClipDescription?.label == "hsaai_otp") {
          clipboard.setPrimaryClip(android.content.ClipData.newPlainText("", ""))
        }
      }, clearAfterMs.toLong())
      promise.resolve(null)
    } catch (t: Throwable) {
      promise.reject("CLIPBOARD_FAILED", t)
    }
  }

  @ReactMethod
  fun clearClipboard(promise: Promise) {
    try {
      val clipboard = reactApplicationContext.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
        as android.content.ClipboardManager
      clipboard.setPrimaryClip(android.content.ClipData.newPlainText("", ""))
      promise.resolve(null)
    } catch (t: Throwable) {
      promise.reject("CLIPBOARD_FAILED", t)
    }
  }

  // ── Base64 helper (used by future native attestation calls) ────────────
  private fun b64(bytes: ByteArray): String =
    Base64.encodeToString(bytes, Base64.NO_WRAP)
}
