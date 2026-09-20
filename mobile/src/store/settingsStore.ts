import { create } from 'zustand';

interface SettingsState {
  apiBaseUrl: string;
  isRTL: boolean;
  theme: 'dark' | 'light';
  language: 'ar' | 'en';
  setApiBaseUrl: (url: string) => void;
  setLanguage: (lang: 'ar' | 'en') => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  apiBaseUrl: 'http://hsaai.local:8080',
  isRTL: true,
  theme: 'dark',
  language: 'ar',

  setApiBaseUrl: (url) => set({ apiBaseUrl: url }),
  setLanguage: (lang) => set({ language: lang, isRTL: lang === 'ar' }),
}));
