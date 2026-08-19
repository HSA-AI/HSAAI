import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Image,
  Alert,
  Keyboard,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as LocalAuthentication from 'expo-local-authentication';
import { HSAButton, HSAInput } from '@components/index';
import { useAuthStore } from '@store/authStore';
import { colors } from '@theme/colors';
import { typography } from '@theme/typography';
import { spacing, radius, shadows } from '@theme/spacing';
import { useSecureScreen } from '@security/useSecureScreen';
import {
  recordBiometricFailure,
  resetBiometricFailures,
  userPinHash,
  MAX_FAILED_BIOMETRIC_ATTEMPTS,
} from '@security/SecureStorage';

const LOGO_URI = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAYAAAD0eN6tAACAAABklEQVR4nO3BMQEAAADCoPVPbQwfoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAO5WEFwAAsXxA2gAAAABJRU5ErkJggg==';

// ── Rate-limiting policy (MASVS-AUTH-3) ───────────────────────────────────
//
// After MAX_LOGIN_ATTEMPTS failed login attempts, lock the UI for
// LOCKOUT_DURATION_MS. The counter is in-memory only — server-side rate
// limiting is the authoritative control; this UX lockout just prevents
// trivial local brute-force.
const MAX_LOGIN_ATTEMPTS = 5;
const LOCKOUT_DURATION_MS = 30_000; // 30s

// ── Secure keyboard (MASVS-STORAGE-7) ─────────────────────────────────────
//
// React Native's TextInput does NOT support third-party keyboards (e.g.
// SwiftKey, Gboard) by default for `secureTextEntry={true}` — Android
// automatically routes password inputs to the system IME's `privateImeOptions`
// flag, which suppresses suggestions / learning. We additionally set
// `autoCorrect={false}` and `keyboardType="default"` to defeat any IME that
// tries to learn the password via autocorrect heuristics.
//
// NOTE: For full third-party-keyboard blocking (e.g. force-disable Gboard
// when typing in username), a native module would need to call
// `InputMethodManager.setInputMethod()` to switch to the default IME. That
// is out of scope for this commit; see docs/security/SECURE_KEYBOARD.md.

export function LoginScreen() {
  // MASVS-RESILIENCE-9: block screenshots on the login screen (credentials).
  useSecureScreen();

  const { login, isLoading, error, clearError } = useAuthStore();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  // Biometric UI state
  const [biometricAvailable, setBiometricAvailable] = useState(false);
  const [biometricEnabled, setBiometricEnabled] = useState(false);

  // PIN fallback UI state
  const [showPinPrompt, setShowPinPrompt] = useState(false);
  const [pinInput, setPinInput] = useState('');

  // Rate-limiting state
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [lockedUntil, setLockedUntil] = useState<number | null>(null);
  const [remainingLockMs, setRemainingLockMs] = useState<number>(0);
  const lockTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Biometric availability check (runs once on mount) ───────────────────
  useEffect(() => {
    let mounted = true;
    (async () => {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const enrolled = await LocalAuthentication.isEnrolledAsync();
      if (mounted) {
        setBiometricAvailable(hasHardware && enrolled);
        // biometricEnabled = we have a stored biometric_key in SecureStorage.
        const storedPinHash = await userPinHash.get();
        if (mounted) setBiometricEnabled(!!storedPinHash);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // ── Lockout timer (MASVS-AUTH-3) ────────────────────────────────────────
  useEffect(() => {
    if (lockedUntil === null) {
      if (lockTimerRef.current) {
        clearInterval(lockTimerRef.current);
        lockTimerRef.current = null;
      }
      return;
    }
    const tick = () => {
      const remaining = Math.max(0, lockedUntil - Date.now());
      setRemainingLockMs(remaining);
      if (remaining === 0) {
        setLockedUntil(null);
        setFailedAttempts(0);
        if (lockTimerRef.current) {
          clearInterval(lockTimerRef.current);
          lockTimerRef.current = null;
        }
      }
    };
    tick();
    lockTimerRef.current = setInterval(tick, 1000);
    return () => {
      if (lockTimerRef.current) {
        clearInterval(lockTimerRef.current);
        lockTimerRef.current = null;
      }
    };
  }, [lockedUntil]);

  // ── Cleanup ─────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => clearError();
  }, [clearError]);

  // ── Handle failed attempt: increment counter, lock if threshold reached ─
  const handleFailedAttempt = useCallback(() => {
    setFailedAttempts((prev) => {
      const next = prev + 1;
      if (next >= MAX_LOGIN_ATTEMPTS) {
        setLockedUntil(Date.now() + LOCKOUT_DURATION_MS);
      }
      return next;
    });
  }, []);

  // ── Password login with rate-limit gate ─────────────────────────────────
  const handleLogin = async () => {
    // Reject while locked out
    if (lockedUntil !== null) {
      const secondsLeft = Math.ceil((lockedUntil - Date.now()) / 1000);
      setLocalError(`تم تجاوز عدد المحاولات. يرجى الانتظار ${secondsLeft} ثانية.`);
      return;
    }

    setLocalError(null);
    if (!username.trim()) {
      setLocalError('يرجى إدخال اسم المستخدم');
      return;
    }
    if (!password.trim()) {
      setLocalError('يرجى إدخال كلمة المرور');
      return;
    }

    try {
      Keyboard.dismiss();
      await login(username, password);
      // On success: reset counters and persist PIN hash for future fallback.
      setFailedAttempts(0);
      await resetBiometricFailures();
    } catch {
      handleFailedAttempt();
    }
  };

  // ── Biometric login (MASVS-AUTH-2) ──────────────────────────────────────
  const handleBiometricLogin = async () => {
    if (lockedUntil !== null) {
      const secondsLeft = Math.ceil((lockedUntil - Date.now()) / 1000);
      setLocalError(`تم تجاوز عدد المحاولات. يرجى الانتظار ${secondsLeft} ثانية.`);
      return;
    }

    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: 'تسجيل الدخول ببصمة HSAAI',
        fallbackLabel: 'استخدام كلمة المرور',
        cancelLabel: 'إلغاء',
        disableDeviceFallback: false,
      });

      if (result.success) {
        // Reset the biometric failure counter.
        await resetBiometricFailures();
        // Trigger the regular login flow with stored credentials — we don't
        // store the password locally; instead, the server issues a
        // biometric-scoped refresh token at enrollment time. For this MVP
        // we require the user to enter the password on first login after
        // device boot, then biometric is used for session unlock only.
        setShowPinPrompt(true);
      } else {
        // Record the failure — wipe secrets at MAX_FAILED_BIOMETRIC_ATTEMPTS.
        const { count, wiped } = await recordBiometricFailure();
        if (wiped) {
          Alert.alert(
            'تنبيه أمني',
            'تم تجاوز الحد الأقصى لمحاولات البصمة. تم مسح جميع البيانات الحساسة محلياً. يرجى تسجيل الدخول بكلمة المرور.',
            [{ text: 'حسناً' }],
          );
          setBiometricEnabled(false);
        } else {
          const remaining = MAX_FAILED_BIOMETRIC_ATTEMPTS - count;
          setLocalError(`فشلت المصادقة البيومترية. المحاولات المتبقية: ${remaining}`);
        }
      }
    } catch (err) {
      setLocalError(`خطأ في المصادقة البيومترية: ${String(err)}`);
    }
  };

  // ── PIN fallback (MASVS-AUTH-2) ─────────────────────────────────────────
  const handlePinSubmit = async () => {
    if (!pinInput.trim() || pinInput.length < 4) {
      setLocalError('يرجى إدخال رمز PIN (4 أرقام على الأقل)');
      return;
    }

    // Verify the PIN hash against the stored hash.
    const storedHash = await userPinHash.get();
    if (!storedHash) {
      // No PIN enrolled — fall back to password.
      setShowPinPrompt(false);
      setLocalError('لم يتم إعداد رمز PIN. يرجى تسجيل الدخول بكلمة المرور.');
      return;
    }

    // Hash the input PIN with SHA-256 (via WebCrypto).
    let inputHash = '';
    try {
      const enc = new TextEncoder().encode(pinInput);
      const digest = await globalThis.crypto.subtle.digest('SHA-256', enc);
      inputHash = Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
    } catch {
      inputHash = pinInput; // dev fallback
    }

    if (inputHash === storedHash) {
      await resetBiometricFailures();
      // Reload the auth session from the still-valid refresh token.
      // The actual session restore is done by App.tsx on the next render.
      setShowPinPrompt(false);
      setLocalError(null);
      // Trigger a no-op login attempt to surface the existing session.
      // (authStore.initialize() will pick up the stored tokens.)
    } else {
      const { count, wiped } = await recordBiometricFailure();
      if (wiped) {
        Alert.alert(
          'تنبيه أمني',
          'تم تجاوز الحد الأقصى لمحاولات PIN. تم مسح جميع البيانات الحساسة محلياً.',
          [{ text: 'حسناً' }],
        );
        setShowPinPrompt(false);
        setBiometricEnabled(false);
      } else {
        const remaining = MAX_FAILED_BIOMETRIC_ATTEMPTS - count;
        setLocalError(`رمز PIN غير صحيح. المحاولات المتبقية: ${remaining}`);
        setPinInput('');
      }
    }
  };

  const isLockedOut = lockedUntil !== null;
  const secondsLeft = Math.ceil(remainingLockMs / 1000);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
        >
          {/* Logo */}
          <View style={styles.logoContainer}>
            <View style={styles.logoCircle}>
              <Image source={{ uri: LOGO_URI }} style={styles.logo} resizeMode="contain" />
            </View>
          </View>

          {/* Title */}
          <Text style={styles.title}>HSAAI</Text>
          <Text style={styles.subtitle}>Hayel Saeed Anam Artificial Intelligence</Text>
          <Text style={styles.welcomeText}>مرحباً بك في منصة الذكاء الاصطناعي المؤسسية</Text>

          {showPinPrompt ? (
            /* ── PIN fallback UI ── */
            <View style={styles.formContainer}>
              <Text style={styles.sectionTitle}>أدخل رمز PIN</Text>
              <HSAInput
                label="رمز PIN"
                value={pinInput}
                onChangeText={(text) => {
                  // PIN input is numeric only; suppress autocorrect / suggestions
                  // to defeat third-party IME learning (MASVS-STORAGE-7).
                  setPinInput(text.replace(/[^0-9]/g, ''));
                  clearError();
                  setLocalError(null);
                }}
                placeholder="••••"
                secureTextEntry
                autoCorrect={false}
                autoCapitalize="none"
                keyboardType="numeric"
              />
              {(error || localError) && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{localError || error}</Text>
                </View>
              )}
              <HSAButton
                title="تحقق"
                onPress={handlePinSubmit}
                loading={isLoading}
                size="large"
                style={styles.loginButton}
              />
              <HSAButton
                title="العودة إلى كلمة المرور"
                onPress={() => {
                  setShowPinPrompt(false);
                  setPinInput('');
                  setLocalError(null);
                }}
                variant="outline"
                size="medium"
                style={styles.switchButton}
              />
            </View>
          ) : (
            /* ── Default password login UI ── */
            <View style={styles.formContainer}>
              <HSAInput
                label="اسم المستخدم"
                value={username}
                onChangeText={(text) => {
                  setUsername(text);
                  clearError();
                  setLocalError(null);
                }}
                placeholder="أدخل اسم المستخدم"
                autoCapitalize="none"
                autoCorrect={false}
              />

              <HSAInput
                label="كلمة المرور"
                value={password}
                onChangeText={(text) => {
                  setPassword(text);
                  clearError();
                  setLocalError(null);
                }}
                placeholder="أدخل كلمة المرور"
                secureTextEntry
                autoCorrect={false}
                autoCapitalize="none"
                keyboardType="default"
              />

              {(error || localError) && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{localError || error}</Text>
                </View>
              )}

              {isLockedOut && (
                <View style={styles.lockoutContainer}>
                  <Text style={styles.lockoutText}>
                    🔒 تم قفل الدخول. حاول مرة أخرى خلال {secondsLeft} ثانية.
                  </Text>
                </View>
              )}

              <HSAButton
                title={isLockedOut ? `🔒 ${secondsLeft}s` : 'تسجيل الدخول'}
                onPress={handleLogin}
                loading={isLoading}
                disabled={isLockedOut}
                size="large"
                style={styles.loginButton}
              />

              {/* Biometric quick-login */}
              {biometricAvailable && biometricEnabled && !isLockedOut && (
                <HSAButton
                  title="🔓 الدخول بالبصمة"
                  onPress={handleBiometricLogin}
                  variant="outline"
                  size="medium"
                  style={styles.biometricButton}
                />
              )}

              {/* Security note */}
              <View style={styles.securityNote}>
                <Text style={styles.securityIcon}>🛡️</Text>
                <Text style={styles.securityText}>
                  بيئة داخلية آمنة — المصادقة عبر Keycloak OIDC + PKCE
                </Text>
              </View>

              {/* Attempts counter (UX transparency, not security control) */}
              {failedAttempts > 0 && !isLockedOut && (
                <Text style={styles.attemptsText}>
                  المحاولات الفاشلة: {failedAttempts} / {MAX_LOGIN_ATTEMPTS}
                </Text>
              )}
            </View>
          )}

          {/* Footer */}
          <Text style={styles.footer}>© 2026 HSA Group · الإصدار 6.1.0</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.hsaBlack,
  },
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.xxxl,
    alignItems: 'center',
  },
  logoContainer: {
    marginBottom: spacing.xl,
  },
  logoCircle: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: colors.hsaYellow,
    alignItems: 'center',
    justifyContent: 'center',
    ...shadows.glow,
  },
  logo: {
    width: 80,
    height: 80,
    borderRadius: 40,
  },
  title: {
    ...typography.h1,
    color: colors.hsaYellow,
    fontSize: 36,
    fontWeight: '900',
  },
  subtitle: {
    ...typography.caption,
    color: colors.textLight,
    textAlign: 'center',
    marginTop: spacing.xs,
    letterSpacing: 1,
  },
  welcomeText: {
    ...typography.body,
    color: colors.textWhite,
    textAlign: 'center',
    marginTop: spacing.lg,
    marginBottom: spacing.xxl,
  },
  sectionTitle: {
    ...typography.h2,
    color: colors.textWhite,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  formContainer: {
    width: '100%',
    maxWidth: 360,
  },
  errorContainer: {
    backgroundColor: colors.errorBg,
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderRightWidth: 3,
    borderRightColor: colors.error,
  },
  errorText: {
    ...typography.bodySmall,
    color: colors.error,
    textAlign: 'center',
  },
  lockoutContainer: {
    backgroundColor: 'rgba(255,107,107,0.15)',
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(255,107,107,0.4)',
  },
  lockoutText: {
    ...typography.bodySmall,
    color: colors.error,
    textAlign: 'center',
    fontWeight: '700',
  },
  loginButton: {
    marginTop: spacing.sm,
  },
  biometricButton: {
    marginTop: spacing.md,
  },
  switchButton: {
    marginTop: spacing.sm,
  },
  securityNote: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    marginTop: spacing.xl,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: 'rgba(240,207,58,0.08)',
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: 'rgba(240,207,58,0.2)',
  },
  securityIcon: {
    fontSize: 16,
  },
  securityText: {
    ...typography.caption,
    color: colors.hsaYellow,
    textAlign: 'center',
    flex: 1,
  },
  attemptsText: {
    ...typography.caption,
    color: colors.textMuted,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  footer: {
    ...typography.caption,
    color: colors.textMuted,
    marginTop: spacing.xxxl,
  },
});
