package com.hsa.hsaai.security

import android.os.Handler
import android.os.Looper
import java.util.concurrent.Executors

/**
 * Tiny background-thread executor used by HSASecurityModule for file I/O
 * and crypto operations that must NOT block the JS thread.
 *
 * MASVS-RESILIENCE-1: detection checks MUST run off the UI/JS thread so
 * a Frida hook on `File.exists()` cannot easily synchronize with the
 * main thread (which would let an attacker time their evasions).
 */
internal object BackgroundTaskExecutor {
  private val executor = Executors.newSingleThreadExecutor { r ->
    Thread(r, "hsa-security-bg").apply {
      isDaemon = true
      // Lower priority so we don't jank the UI thread on cold start.
      priority = Thread.MIN_PRIORITY
    }
  }
  private val mainHandler = Handler(Looper.getMainLooper())

  fun execute(runnable: java.lang.Runnable) {
    executor.execute(runnable)
  }
}
