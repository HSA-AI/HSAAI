/**
 * HSA Brand Colors
 * Gold #F0CF3A + Black #050505 + supporting palette
 */
export const colors = {
  // ── Primary brand ──
  hsaYellow: '#F0CF3A',
  hsaGold: '#C7A833',
  hsaBlack: '#050505',
  hsaSoft: '#FFF7CC',

  // ── Surfaces ──
  background: '#0B0F19',
  surface: '#0F172A',
  surfaceLight: '#1E293B',
  card: '#FFFFFF',
  cardDark: '#1A1A2E',

  // ── Text ──
  textPrimary: '#0F172A',
  textSecondary: '#475569',
  textLight: '#94A3B8',
  textWhite: '#FFFFFF',
  textMuted: '#64748B',

  // ── Semantic ──
  success: '#059669',
  successBg: '#D1FAE5',
  warning: '#D97706',
  warningBg: '#FEF3C7',
  error: '#DC2626',
  errorBg: '#FEE2E2',
  info: '#2563EB',
  infoBg: '#DBEAFE',

  // ── Borders & dividers ──
  border: '#E2E8F0',
  borderDark: '#334155',
  divider: '#F1F5F9',

  // ── Chat bubbles ──
  bubbleUser: '#F0CF3A',
  bubbleUserText: '#050505',
  bubbleAssistant: '#1E293B',
  bubbleAssistantText: '#F1F5F9',

  // ── Status indicators ──
  online: '#22C55E',
  offline: '#EF4444',
  pending: '#F59E0B',
} as const;

export type ColorKey = keyof typeof colors;
