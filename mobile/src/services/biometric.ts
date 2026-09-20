/**
 * HSAAI Mobile — Biometric Authentication Service (Phase 11)
 * ============================================================
 * Fingerprint / Face ID authentication for secure enterprise login.
 */
import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';
import { Alert, Platform } from 'react-native';

const BIOMETRIC_ENABLED_KEY = '@hsaai/biometric_enabled';
const BIOMETRIC_TOKEN_KEY = '@hsaai/biometric_token';

class BiometricService {
  async isAvailable(): Promise<boolean> {
    const compatible = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    return compatible && enrolled;
  }

  async isEnabled(): Promise<boolean> {
    const enabled = await SecureStore.getItemAsync(BIOMETRIC_ENABLED_KEY);
    return enabled === 'true';
  }

  async enable(token: string): Promise<boolean> {
    const available = await this.isAvailable();
    if (!available) {
      Alert.alert(
        'Biometric Unavailable',
        'Biometric authentication is not available on this device.'
      );
      return false;
    }

    // Authenticate to confirm identity before enabling
    const result = await this.authenticate('Enable biometric login');
    if (result.success) {
      await SecureStore.setItemAsync(BIOMETRIC_ENABLED_KEY, 'true');
      await SecureStore.setItemAsync(BIOMETRIC_TOKEN_KEY, token);
      return true;
    }
    return false;
  }

  async disable(): Promise<void> {
    await SecureStore.deleteItemAsync(BIOMETRIC_ENABLED_KEY);
    await SecureStore.deleteItemAsync(BIOMETRIC_TOKEN_KEY);
  }

  async authenticate(reason: string = 'Authenticate to continue'): Promise<{ success: boolean; token?: string; error?: string }> {
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: reason,
        fallbackLabel: 'Use password',
        cancelLabel: 'Cancel',
        disableDeviceFallback: false,
      });

      if (result.success) {
        const token = await SecureStore.getItemAsync(BIOMETRIC_TOKEN_KEY);
        return { success: true, token };
      } else {
        return {
          success: false,
          error: result.error === 'user_cancel' ? 'Cancelled' :
                 result.error === 'too_many_attempts' ? 'Too many attempts' :
                 'Authentication failed',
        };
      }
    } catch (err) {
      return { success: false, error: String(err) };
    }
  }

  async tryBiometricLogin(): Promise<{ success: boolean; token?: string }> {
    const enabled = await this.isEnabled();
    if (!enabled) return { success: false };

    const result = await this.authenticate('Log in to HSAAI');
    return result;
  }
}

export const biometric = new BiometricService();
