import { create } from "zustand";
import { User, api, ApiError } from "@/lib/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  initialized: boolean;
  checkAuth: () => Promise<User | null>;
  logout: () => Promise<void>;
  setUser: (user: User | null) => void;
  setError: (error: string | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  error: null,
  initialized: false,

  checkAuth: async () => {
    try {
      set({ isLoading: true, error: null });
      const res = await api.auth.me();
      if (res?.data) {
        set({
          user: res.data,
          isAuthenticated: true,
          isLoading: false,
          initialized: true,
          error: null,
        });
        return res.data;
      }
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        initialized: true,
      });
      return null;
    } catch (err: unknown) {
      const is401 = err instanceof ApiError && err.status === 401;
      const message = err instanceof Error ? err.message : "Failed to authenticate session";
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        initialized: true,
        error: is401 ? null : message,
      });
      return null;
    }
  },

  logout: async () => {
    try {
      set({ isLoading: true });
      await api.auth.logout();
    } catch (err) {
      console.warn("Logout error:", err);
    } finally {
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,
      });
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  },

  setUser: (user) => {
    set({
      user,
      isAuthenticated: !!user,
      isLoading: false,
    });
  },

  setError: (error) => {
    set({ error });
  },
}));
