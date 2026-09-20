package com.hsa.hsaai.security

import com.facebook.react.bridge.*
import java.io.File

/**
 * HSARootDetectionModule — Kotlin native side of `RootDetection.ts`.
 *
 * Returns a structured `RootDetectionResult` (isRooted / score / signals)
 * so the JS layer can decide policy (block launch vs. SIEM log).
 *
 * OWASP MASVS-RESILIENCE-1.
 */
class HSARootDetectionModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext) {

  override fun getName(): String = "HSARootDetection"

  @ReactMethod
  fun checkRoot(promise: Promise) {
    BackgroundTaskExecutor.execute {
      try {
        val signals = mutableListOf<String>()

        // 1. Known root file paths
        val rootPaths = listOf(
          "/system/app/Superuser.apk", "/sbin/su", "/system/bin/su",
          "/system/xbin/su", "/system/sbin/su", "/vendor/bin/su",
          "/data/local/xbin/su", "/data/local/bin/su", "/data/local/su",
          "/system/bin/.ext/.su", "/system/usr/we-need-root/su-backup",
          "/system/app/Kinguser.apk", "/system/app/KingRoot.apk",
          "/system/app/SuperSU", "/system/etc/init.d/99SuperSUDaemon",
          "/system/xbin/daemonsu",
          "/sbin/.magisk", "/data/adb/magisk", "/data/adb/modules",
          "/cache/.disable_magisk",
          "/data/adb/ksu", "/data/adb/ksud", "/data/adb/ap"
        )
        rootPaths.forEach { p ->
          if (File(p).exists()) signals.add("path:$p")
        }

        // 2. `which su` succeeds
        try {
          val proc = Runtime.getRuntime().exec(arrayOf("which", "su"))
          val reader = proc.inputStream.bufferedReader()
          val line = reader.readLine()
          proc.waitFor()
          if (!line.isNullOrEmpty()) signals.add("which_su:$line")
        } catch (_: Exception) { /* ignore */ }

        // 3. Build tags
        if (android.os.Build.TAGS?.contains("test-keys") == true) {
          signals.add("build_tags_test_keys")
        }

        // 4. Root apps installed
        val rootApps = listOf(
          "com.topjohnwu.magisk", "io.github.vvb2060.magisk",
          "com.noshufou.android.su", "com.thirdparty.superuser",
          "eu.chainfire.supersu", "com.koushikdutta.superuser",
          "com.kingouser.com", "com.kingroot.kinguser", "com.kingo.root"
        )
        val pm = reactApplicationContext.packageManager
        rootApps.forEach { pkg ->
          try {
            pm.getPackageInfo(pkg, 0)
            signals.add("pkg:$pkg")
          } catch (_: android.content.pm.PackageManager.NameNotFoundException) {
            /* not installed — skip */
          }
        }

        val result = Arguments.createMap()
        result.putBoolean("isRooted", signals.isNotEmpty())
        result.putInt("score", signals.size)
        val sigArray = Arguments.createArray()
        signals.forEach { sigArray.pushString(it) }
        result.putArray("signals", sigArray)
        promise.resolve(result)
      } catch (t: Throwable) {
        // Fail-closed: on exception, assume rooted.
        val result = Arguments.createMap()
        result.putBoolean("isRooted", true)
        result.putInt("score", 1)
        val sigArray = Arguments.createArray()
        sigArray.pushString("exception:${t.message}")
        result.putArray("signals", sigArray)
        promise.resolve(result)
      }
    }
  }
}
