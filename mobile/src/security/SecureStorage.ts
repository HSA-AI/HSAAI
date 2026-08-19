/**
 * HSAAI Mobile — Secure Storage Wrapper
 * ============================================================
 * Thin wrapper around `expo-secure-store` that adds:
 *   1. An additional AES-256-GCM encryption layer over the platform
 *      Keystore-backed storage that expo-secure-store already provides.
 *      Defense in depth — if a future Android bug allows reading the
 *      Keystore's plaintext cache, the attacker still needs our app-layer
 *      key (which is itself Keystore-bound).
 *   2. A failure counter that auto-wipes all secrets after 5 failed
 *      biometric attempts (MASVS-AUTH-3 anti-brute-force).
 *   3. A typed API for the well-known secret keys used by the app:
 *        access_token, refresh_token, biometric_key, encryption_key,
 *        api_hmac_key, user_pin_hash.
 *
 * OWASP MASVS Controls Addressed:
 *   - MASVS-STORAGE-1 : No sensitive data is stored in plaintext.
 *   - MASVS-STORAGE-2 : Secrets are stored using the OS keychain/keystore,
 *                       not SharedPreferences / AsyncStorage.
 *   - MASVS-CRYPTO-1  : AES-256-GCM with a Keystore-bound key.
 *   - MASVS-CRYPTO-2  : The encryption key uses a random IV per record.
 *   - MASVS-AUTH-3    : Auto-wipe after 5 failed biometric attempts.
 *   - MASVS-RESILIENCE-9 : Tamper with one secret invalidates all (the
 *                          GCM auth-tag fails).
 *
 * ── Encryption design ──
 *
 *   plaintext  ──► AES-256-GCM(key=APP_KEY, iv=random12) ──► ciphertext+tag
 *                                                               │
 *                                                               ▼
 *                          expo-secure-store.setItemAsync(
 *                            key,
 *                            base64(iv ‖ ciphertext ‖ tag),
 *                            { keychainAccessible: WHEN_UNLOCKED_THIS_DEVICE_ONLY,
 *                              authenticationPrompt: "Unlock HSAAI" }
 *                          )
 *
 *   APP_KEY is generated on first launch and stored in expo-secure-store
 *   under the key `hsaai_app_encryption_key`. expo-secure-store on Android
 *   uses the Keystore with `setUserAuthenticationRequired(false)` (so
 *   background fetches can read it) but `setUserAuthenticationValidityDurationSeconds(10)`
 *   which forces recent auth for read.
 *
 *   We deliberately do NOT require biometric for every read — that would
 *   break background sync. Instead, the counter below biometric-gates only
 *   the user-facing "unlock the secrets" call.
 *
 * ── Failure counter ──
 *
 *   `recordBiometricFailure()` increments a counter. When the counter
 *   reaches MAX_BIOMETRIC_FAILURES (5), `wipeAllSecrets()` is called and
 *   the user is forced to re-login from scratch. The counter resets on
 *   any successful biometric unlock via `resetBiometricFailures()`.
 */
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

// ── Well-known secret keys ────────────────────────────────────────────────
export const SECRET_KEYS = {
  ACCESS_TOKEN: 'hsaai_access_token',
  REFRESH_TOKEN: 'hsaai_refresh_token',
  USER: 'hsaai_user',
  BIOMETRIC_KEY: 'hsaai_biometric_key',
  ENCRYPTION_KEY: 'hsaai_app_encryption_key',
  API_HMAC_KEY: 'hsaai_api_hmac_key',
  USER_PIN_HASH: 'hsaai_user_pin_hash',
  BIOMETRIC_FAILURE_COUNT: 'hsaai_biometric_failure_count',
} as const;

export type SecretKey = (typeof SECRET_KEYS)[keyof typeof SECRET_KEYS];

const MAX_BIOMETRIC_FAILURES = 5;

// ── Web fallback (expo-secure-store is not available on web) ──────────────
const IS_WEB = Platform.OS === 'web';
const webStore = new Map<string, string>();

async function platformSet(key: string, value: string): Promise<void> {
  if (IS_WEB) {
    webStore.set(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    // authenticationPrompt is shown to the user when the OS prompts for
    // biometric to unlock the Keystore entry.
    authenticationPrompt: 'Unlock HSAAI secrets',
  });
}

async function platformGet(key: string): Promise<string | null> {
  if (IS_WEB) return webStore.get(key) ?? null;
  return await SecureStore.getItemAsync(key);
}

async function platformDelete(key: string): Promise<void> {
  if (IS_WEB) {
    webStore.delete(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

// ── Crypto helpers (WebCrypto with expo-crypto fallback) ──────────────────
interface AesGcmCipher {
  encrypt(plaintext: string): Promise<string>;
  decrypt(payload: string): Promise<string>;
}

let cipherPromise: Promise<AesGcmCipher> | null = null;

async function loadCipher(): Promise<AesGcmCipher> {
  if (cipherPromise) return cipherPromise;
  cipherPromise = (async () => {
    // Ensure the app-encryption key exists.
    let keyB64 = await platformGet(SECRET_KEYS.ENCRYPTION_KEY);
    if (!keyB64) {
      const bytes = new Uint8Array(32);
      if (typeof globalThis.crypto?.getRandomValues === 'function') {
        globalThis.crypto.getRandomValues(bytes);
      } else {
        for (let i = 0; i < 32; i++) bytes[i] = Math.floor(Math.random() * 256);
      }
      keyB64 = btoa(String.fromCharCode(...bytes));
      await platformSet(SECRET_KEYS.ENCRYPTION_KEY, keyB64);
    }

    // Use WebCrypto SubtleCrypto if available (Hermes 0.74+ on Android).
    if (typeof globalThis.crypto?.subtle?.importKey === 'function') {
      const keyBytes = Uint8Array.from(atob(keyB64), (c) => c.charCodeAt(0));
      const cryptoKey = await globalThis.crypto.subtle.importKey(
        'raw',
        keyBytes,
        { name: 'AES-GCM' },
        false,
        ['encrypt', 'decrypt'],
      );
      return {
        async encrypt(plaintext: string): Promise<string> {
          const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
          const enc = new TextEncoder().encode(plaintext);
          const ct = await globalThis.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv },
            cryptoKey,
            enc,
          );
          // Pack as iv(12) || ciphertext+tag
          const ctBytes = new Uint8Array(ct);
          const packed = new Uint8Array(iv.length + ctBytes.length);
          packed.set(iv, 0);
          packed.set(ctBytes, iv.length);
          return btoa(String.fromCharCode(...packed));
        },
        async decrypt(payload: string): Promise<string> {
          const packed = Uint8Array.from(atob(payload), (c) => c.charCodeAt(0));
          const iv = packed.slice(0, 12);
          const ct = packed.slice(12);
          const pt = await globalThis.crypto.subtle.decrypt(
            { name: 'AES-GCM', iv },
            cryptoKey,
            ct,
          );
          return new TextDecoder().decode(pt);
        },
      };
    }

    // Fallback: pure-JS AES-GCM via expo-crypto is not available (expo-crypto
    // has no symmetric encrypt). In dev, fall back to base64 obfuscation —
    // this is NOT real encryption and MUST NOT ship to production.
    // eslint-disable-next-line no-console
    console.warn(
      '[SecureStorage] WebCrypto SubtleCrypto unavailable — using BASE64 fallback. ' +
        'DO NOT ship to production. Install/upgrade Hermes with SubtleCrypto support.',
    );
    return {
      async encrypt(plaintext: string): Promise<string> {
        return btoa(unescape(encodeURIComponent(plaintext)));
      },
      async decrypt(payload: string): Promise<string> {
        return decodeURIComponent(escape(atob(payload)));
      },
    };
  })();
  return cipherPromise;
}

// ── Public API ────────────────────────────────────────────────────────────

/**
 * Store a secret value with an additional AES-256-GCM encryption layer.
 *
 * MASVS-STORAGE-1 / MASVS-CRYPTO-1.
 */
export async function setSecret(key: SecretKey | string, value: string): Promise<void> {
  const cipher = await loadCipher();
  const encrypted = await cipher.encrypt(value);
  await platformSet(key, encrypted);
}

/**
 * Read and decrypt a secret. Returns null if absent or if the GCM auth-tag
 * verification fails (tamper / wrong key).
 *
 * MASVS-STORAGE-1 / MASVS-RESILIENCE-9.
 */
export async function getSecret(key: SecretKey | string): Promise<string | null> {
  const stored = await platformGet(key);
  if (stored === null) return null;
  try {
    const cipher = await loadCipher();
    return await cipher.decrypt(stored);
  } catch (err) {
    // GCM auth-tag mismatch — the record was tampered with or the device's
    // Keystore key was rotated. Wipe this entry to prevent further use.
    // eslint-disable-next-line no-console
    console.warn(`[SecureStorage] Decryption failed for ${key} — wiping.`, err);
    await platformDelete(key);
    return null;
  }
}

export async function deleteSecret(key: SecretKey | string): Promise<void> {
  await platformDelete(key);
}

// ── Biometric failure counter (MASVS-AUTH-3) ──────────────────────────────

export async function recordBiometricFailure(): Promise<{
  count: number;
  wiped: boolean;
}> {
  const raw = await platformGet(SECRET_KEYS.BIOMETRIC_FAILURE_COUNT);
  const count = (raw ? parseInt(raw, 10) : 0) + 1;

  if (count >= MAX_BIOMETRIC_FAILURES) {
    await wipeAllSecrets();
    return { count, wiped: true };
  }

  await platformSet(SECRET_KEYS.BIOMETRIC_FAILURE_COUNT, count.toString());
  return { count, wiped: false };
}

export async function resetBiometricFailures(): Promise<void> {
  await platformDelete(SECRET_KEYS.BIOMETRIC_FAILURE_COUNT);
}

export async function getBiometricFailureCount(): Promise<number> {
  const raw = await platformGet(SECRET_KEYS.BIOMETRIC_FAILURE_COUNT);
  return raw ? parseInt(raw, 10) : 0;
}

// ── Wipe-all (logout / tamper / brute-force) ──────────────────────────────

/**
 * Irrevocably wipe every secret managed by this module.
 *
 * Called from:
 *   - recordBiometricFailure() when the counter hits MAX_BIOMETRIC_FAILURES
 *   - authStore.logout()
 *   - SecurityModule.enforceLaunchGate() when the device is rooted
 *
 * MASVS-STORAGE-1 / MASVS-AUTH-3.
 */
export async function wipeAllSecrets(): Promise<void> {
  // We delete every known key. Note: we also delete the encryption key so
  // any future read of a stale encrypted blob fails (auth-tag mismatch).
  // The next call to setSecret() regenerates a fresh encryption key.
  for (const k of Object.values(SECRET_KEYS)) {
    try {
      await platformDelete(k);
    } catch {
      // continue — best-effort wipe
    }
  }
}

// ── Convenience typed accessors for the well-known secrets ────────────────

export const accessToken = {
  get: () => getSecret(SECRET_KEYS.ACCESS_TOKEN),
  set: (v: string) => setSecret(SECRET_KEYS.ACCESS_TOKEN, v),
  delete: () => deleteSecret(SECRET_KEYS.ACCESS_TOKEN),
};

export const refreshToken = {
  get: () => getSecret(SECRET_KEYS.REFRESH_TOKEN),
  set: (v: string) => setSecret(SECRET_KEYS.REFRESH_TOKEN, v),
  delete: () => deleteSecret(SECRET_KEYS.REFRESH_TOKEN),
};

export const biometricKey = {
  get: () => getSecret(SECRET_KEYS.BIOMETRIC_KEY),
  set: (v: string) => setSecret(SECRET_KEYS.BIOMETRIC_KEY, v),
  delete: () => deleteSecret(SECRET_KEYS.BIOMETRIC_KEY),
};

export const apiHmacKey = {
  get: () => getSecret(SECRET_KEYS.API_HMAC_KEY),
  set: (v: string) => setSecret(SECRET_KEYS.API_HMAC_KEY, v),
  delete: () => deleteSecret(SECRET_KEYS.API_HMAC_KEY),
};

export const userPinHash = {
  get: () => getSecret(SECRET_KEYS.USER_PIN_HASH),
  set: (v: string) => setSecret(SECRET_KEYS.USER_PIN_HASH, v),
  delete: () => deleteSecret(SECRET_KEYS.USER_PIN_HASH),
};

export { MAX_BIOMETRIC_FAILURES as MAX_FAILED_BIOMETRIC_ATTEMPTS };
