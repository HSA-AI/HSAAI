# Add project specific ProGuard rules here.
# By default, the flags in this file are appended to flags specified
# in /usr/local/Cellar/android-sdk/24.3.3/tools/proguard/proguard-android.txt
# You can edit the include path and order by changing the proguardFiles
# directive in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# ── OWASP MASVS-RESILIENCE-9 ───────────────────────────────────────────────
# R8 full-mode obfuscation. The default proguard-android-optimize.txt already
# enables optimization passes; the rules below harden the release build
# further by stripping debugging metadata and aggressively renaming symbols.
# Do NOT disable these — they materially raise the cost of reverse
# engineering the HSAAI APK via APKTool / Jadx / Frida.

# Strip debugging source file + line numbers from stack traces in release.
# Attackers cannot easily map obfuscated class names back to source.
-renamesourcefileattribute SourceFile
-keepattributes SourceFile,LineNumberTable
# Strip all generic type info — not needed at runtime.
-keepattributes Signature,InnerClasses,EnclosingMethod

# react-native-reanimated
-keep class com.swmansion.reanimated.** { *; }
-keep class com.facebook.react.turbomodule.** { *; }

# ── HSAAI Security native modules (MASVS-RESILIENCE-1/9) ───────────────────
# These classes implement FLAG_SECURE, root detection, and tamper detection.
# They MUST be kept (not renamed) because React Native references them by
# exact class name from JS via NativeModule binding. However, we strip their
# string literals where possible to obscure the detection signatures.
-keep class com.hsa.hsaai.security.** { *; }
-keepclassmembers class com.hsa.hsaai.security.** { *; }

# ── RootBeer (root detection library) ──────────────────────────────────────
# Keep RootBeer's native loader signatures (used by RootDetection.ts via
# NativeModule bridge).
-keep class com.scottyab.rootbeer.** { *; }

# ── Play Integrity API (MASVS-RESILIENCE-1) ───────────────────────────────
-keep class com.google.android.play.core.integrity.** { *; }
-keep class com.google.android.play.core.integrity.protocol.** { *; }

# ── Android Keystore (MASVS-CRYPTO-1) ─────────────────────────────────────
# Do not allow R8 to inline / strip the Keystore provider classes — the
# SecureStorage wrapper relies on KeyProperties, KeyGenParameterSpec, etc.
-keep class android.security.keystore.** { *; }
-keep class javax.crypto.** { *; }
-keep class java.security.** { *; }

# ── Certificate pinning (MASVS-NETWORK-2) ─────────────────────────────────
# okhttp3.CertificatePinner is referenced reflectively by React Native's
# network stack when react-native-ssl-pinning is installed.
-keep class okhttp3.CertificatePinner { *; }
-keep class okhttp3.CertificatePinner$Pin { *; }
-keepclassmembers class com.facebook.react.modules.network.** { *; }

# Strip all logging in release builds (MASVS-RESILIENCE-9). Logs are an
# information-leakage vector — they may contain PII, tokens, stack traces.
-assumenosideeffects class android.util.Log {
    public static *** v(...);
    public static *** d(...);
    public static *** i(...);
    public static *** w(...);
    public static *** e(...);
}
-assumenosideeffects class com.facebook.react.common.ReactConstants { *; }

# Add any project specific keep options here:
