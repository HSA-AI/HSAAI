import { create } from 'zustand';
import type { HSAAIUser } from '@api/auth';
import { getCurrentUser, isAuthenticated, clearAuth, loginWithPassword } from '@api/auth';

interface AuthState {
  user: HSAAIUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  initialize: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  error: null,

  initialize: async () => {
    set({ isLoading: true });
    try {
      const authed = await isAuthenticated();
      if (authed) {
        const user = await getCurrentUser();
        set({ user, isAuthenticated: true, isLoading: false });
      } else {
        set({ user: null, isAuthenticated: false, isLoading: false });
      }
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const user = await loginWithPassword(username, password);
      set({ user, isAuthenticated: true, isLoading: false, error: null });
    } catch (err) {
      const error = err instanceof Error ? err.message : 'فشل تسجيل الدخول';
      set({ isLoading: false, error, isAuthenticated: false });
      throw err;
    }
  },

  logout: async () => {
    set({ isLoading: true });
    await clearAuth();
    set({ user: null, isAuthenticated: false, isLoading: false });
  },

  clearError: () => set({ error: null }),
}));
