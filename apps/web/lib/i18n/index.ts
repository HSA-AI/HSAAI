/**
 * HSAAI Web i18n Configuration (Phase 17)
 * ==========================================
 * Full internationalization: Arabic + English, RTL support, plural rules.
 */
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enCommon from '@/locales/en/common.json';
import arCommon from '@/locales/ar/common.json';

export const SUPPORTED_LANGUAGES = ['ar', 'en'] as const;
export type SupportedLanguage = typeof SUPPORTED_LANGUAGES[number];

export const DEFAULT_LANGUAGE: SupportedLanguage = 'ar';
export const FALLBACK_LANGUAGE: SupportedLanguage = 'en';

export const isRTL = (lang: string): boolean => lang === 'ar';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: enCommon },
      ar: { common: arCommon },
    },
    lng: DEFAULT_LANGUAGE,
    fallbackLng: FALLBACK_LANGUAGE,
    defaultNS: 'common',
    ns: ['common'],
    interpolation: {
      escapeValue: false,
      format: (value, format, lang) => {
        if (value instanceof Date) {
          return new Intl.DateTimeFormat(lang, {
            dateStyle: 'medium',
            timeStyle: 'short',
          }).format(value);
        }
        if (format === 'currency') {
          return new Intl.NumberFormat(lang, {
            style: 'currency',
            currency: lang === 'ar' ? 'SAR' : 'USD',
          }).format(value);
        }
        if (format === 'number') {
          return new Intl.NumberFormat(lang).format(value);
        }
        return value;
      },
    },
    react: {
      useSuspense: false,
    },
    detection: {
      order: ['localStorage', 'navigator', 'htmlTag'],
      lookupLocalStorage: 'hsaai-language',
      caches: ['localStorage'],
    },
  });

// Apply RTL direction
export const applyDirection = (lang: string) => {
  if (typeof document !== 'undefined') {
    document.documentElement.dir = isRTL(lang) ? 'rtl' : 'ltr';
    document.documentElement.lang = lang;
  }
};

// Apply on language change
i18n.on('languageChanged', applyDirection);

// Initialize direction
applyDirection(i18n.language);

export const changeLanguage = async (lang: SupportedLanguage) => {
  await i18n.changeLanguage(lang);
  applyDirection(lang);
};

export const getCurrentLanguage = (): SupportedLanguage =>
  (i18n.language as SupportedLanguage) || DEFAULT_LANGUAGE;

export default i18n;
