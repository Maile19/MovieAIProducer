"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";

export function useAuth(options?: { requireAuth?: boolean; redirectTo?: string }) {
  const { user, isLoading, isAuthenticated, error, initialized, checkAuth, logout, setUser } = useAuthStore();

  useEffect(() => {
    if (!initialized) {
      checkAuth();
    }
  }, [initialized, checkAuth]);

  useEffect(() => {
    if (options?.requireAuth && initialized && !isLoading && !isAuthenticated) {
      const redirectUrl = options.redirectTo || "/login";
      if (typeof window !== "undefined") {
        window.location.href = redirectUrl;
      }
    }
  }, [options?.requireAuth, options?.redirectTo, initialized, isLoading, isAuthenticated]);

  return {
    user,
    isLoading,
    isAuthenticated,
    error,
    initialized,
    checkAuth,
    logout,
    setUser,
  };
}
