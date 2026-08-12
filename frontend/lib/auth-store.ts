/**
 * lib/auth-store.ts
 * ───────────────────
 * Global auth state — persisted to localStorage under "career-os-auth" so
 * lib/api.ts (a plain module, not a hook) can read the token synchronously
 * for every authenticated request without going through React.
 */
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { auth as authApi, ApiError } from "@/lib/api";

interface AuthState {
  token: string | null;
  userId: string | null;
  email: string | null;
  hydrated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      userId: null,
      email: null,
      hydrated: false,
      login: async (email: string, password: string) => {
        const res = await authApi.login(email, password);
        set({ token: res.token, userId: res.user_id, email: res.email });
      },
      register: async (email: string, password: string) => {
        const res = await authApi.register(email, password);
        set({ token: res.token, userId: res.user_id, email: res.email });
      },
      logout: () => set({ token: null, userId: null, email: null }),
      setHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "career-os-auth",
      onRehydrateStorage: () => (state) => state?.setHydrated(),
    }
  )
);

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}
