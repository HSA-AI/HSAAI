/**
 * HSAAI Mobile — i18n Configuration (Phase 17)
 * ===============================================
 * Full internationalization: Arabic + English, RTL support, plural rules.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { getLocales } from 'expo-localization';
import AsyncStorage from '@react-native-async-storage/async-storage';

import ar from './locales/ar.json';
import en from './locales/en.json';

const LANGUAGE_KEY = '@hsaai/language';

// Detect device language
const deviceLocale = getLocales()[0]?.languageCode || 'ar';
const isRTL = deviceLocale === 'ar';

// Load saved language preference
const loadLanguage = async () => {
  try {
    const saved = await AsyncStorage.getItem(LANGUAGE_KEY);
    return saved || deviceLocale;
  } catch {
    return deviceLocale;
  }
};

const saveLanguage = async (lang: string) => {
  try {
    await AsyncStorage.setItem(LANGUAGE_KEY, lang);
  } catch (e) {
    console.warn('Failed to save language preference', e);
  }
};

i18n.use(initReactI18next).init({
  resources: {
    ar: { translation: ar },
    en: { translation: en },
  },
  lng: deviceLocale,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

// Save language on change
i18n.on('languageChanged', (lng) => {
  saveLanguage(lng);
});

export const changeLanguage = async (lang: string) => {
  await i18n.changeLanguage(lang);
};

export const isRTLLanguage = (lang: string) => lang === 'ar';

export default i18n;
