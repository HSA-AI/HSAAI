package com.hsa.hsaai.security

import com.facebook.react.ReactPackage
import com.facebook.react.bridge.NativeModule
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.uimanager.ViewManager

/**
 * React Native package registration for the HSAAI security native modules.
 *
 * Add this package to MainApplication.kt's `getPackages()` list:
 *
 *   override fun getPackages(): List<ReactPackage> =
 *     PackageList(this).packages.apply {
 *       add(HSASecurityPackage())
 *     }
 *
 * OWASP MASVS-RESILIENCE-1: registration must happen in release builds.
 * The ProGuard rules in proguard-rules.pro keep `com.hsa.hsaai.security.**`
 * so the JS-side `NativeModules.HSASecurity` binding resolves post-R8.
 */
class HSASecurityPackage : ReactPackage {
  override fun createNativeModules(reactContext: ReactApplicationContext): List<NativeModule> =
    listOf(
      HSASecurityModule(reactContext),
      HSARootDetectionModule(reactContext),
    )

  override fun createViewManagers(reactContext: ReactApplicationContext): List<ViewManager<*, *>> =
    emptyList()
}
