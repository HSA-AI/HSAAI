package com.hsa.hsaai

import android.os.Build
import android.os.Bundle
import android.view.WindowManager

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // Set the theme to AppTheme BEFORE onCreate to support
    // coloring the background, status bar, and navigation bar.
    // This is required for expo-splash-screen.
    setTheme(R.style.AppTheme);

    // ── OWASP MASVS-RESILIENCE-9 ───────────────────────────────────────────
    // FLAG_SECURE on the Activity window prevents:
    //   - Screenshots (returns a black bitmap)
    //   - Screen recording via MediaProjection (returns a black stream)
    //   - The activity's content appearing in the recent-apps preview carousel
    //
    // We set FLAG_SECURE here at Activity creation so the splash screen
    // itself is also protected. The JS-side `useSecureScreen()` hook can
    // CLEAR this flag on non-sensitive screens (e.g. dashboard) to allow
    // support screenshots there — but the default is SECURE.
    //
    // To enable on a per-screen basis from JS, use:
    //   import { useSecureScreen } from '@security/useSecureScreen';
    //   useSecureScreen();  // at the top of a sensitive screen component
    //
    // The Kotlin side of `setFlagSecure()` is implemented in
    // /mobile/android/app/src/main/java/com/hsa/hsaai/security/SecurityModule.kt
    // (see HSASecurityModule.kt for the NativeModule binding).
    window.setFlags(
      WindowManager.LayoutParams.FLAG_SECURE,
      WindowManager.LayoutParams.FLAG_SECURE
    )

    super.onCreate(null)
  }

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "main"

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate {
    return ReactActivityDelegateWrapper(
          this,
          BuildConfig.IS_NEW_ARCHITECTURE_ENABLED,
          object : DefaultReactActivityDelegate(
              this,
              mainComponentName,
              fabricEnabled
          ){})
  }

  /**
    * Align the back button behavior with Android S
    * where moving root activities to background instead of finishing activities.
    * @see <a href="https://developer.android.com/reference/android/app/Activity#onBackPressed()">onBackPressed</a>
    */
  override fun invokeDefaultOnBackPressed() {
      if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.R) {
          if (!moveTaskToBack(false)) {
              // For non-root activities, use the default implementation to finish them.
              super.invokeDefaultOnBackPressed()
          }
          return
      }

      // Use the default back button implementation on Android S
      // because it's doing more than [Activity.moveTaskToBack] in fact.
      super.invokeDefaultOnBackPressed()
  }
}
