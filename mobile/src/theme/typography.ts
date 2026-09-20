import { Platform } from 'react-native';

export const typography = {
  // ── Headings ──
  h1: { fontSize: 28, fontWeight: '800' as const, lineHeight: 36 },
  h2: { fontSize: 22, fontWeight: '700' as const, lineHeight: 30 },
  h3: { fontSize: 18, fontWeight: '700' as const, lineHeight: 26 },
  h4: { fontSize: 16, fontWeight: '600' as const, lineHeight: 24 },

  // ── Body ──
  body: { fontSize: 14, fontWeight: '400' as const, lineHeight: 22 },
  bodyLarge: { fontSize: 16, fontWeight: '400' as const, lineHeight: 24 },
  bodySmall: { fontSize: 12, fontWeight: '400' as const, lineHeight: 18 },

  // ── Labels & captions ──
  caption: { fontSize: 11, fontWeight: '500' as const, lineHeight: 16 },
  label: { fontSize: 12, fontWeight: '600' as const, lineHeight: 16 },
  overline: { fontSize: 10, fontWeight: '700' as const, lineHeight: 14, letterSpacing: 1.5 },

  // ── Special ──
  kpiValue: { fontSize: 24, fontWeight: '800' as const, lineHeight: 30 },
  kpiLabel: { fontSize: 10, fontWeight: '500' as const, lineHeight: 14 },

  // ── Chat ──
  chatMessage: { fontSize: 15, fontWeight: '400' as const, lineHeight: 22 },
  chatInput: { fontSize: 16, fontWeight: '400' as const, lineHeight: 22 },

  // ── Button ──
  button: { fontSize: 15, fontWeight: '700' as const, lineHeight: 22 },
  buttonSmall: { fontSize: 13, fontWeight: '600' as const, lineHeight: 18 },
} as const;

export const fontFamily = {
  regular: Platform.select({
    ios: 'System',
    android: 'sans-serif',
  }),
  medium: Platform.select({
    ios: 'System',
    android: 'sans-serif-medium',
  }),
  bold: Platform.select({
    ios: 'System',
    android: 'sans-serif',
  }),
};
