/**
 * Authentication State Management
 * Zustand store for auth state with persistence
 */

import { create } from "zustand"
import { persist, createJSONStorage } from "zustand/middleware"
import type { User, AuthTokens, AuthState } from "@/types"

interface AuthStore extends AuthState {
  // Actions
  setUser: (user: User | null) => void
  setTokens: (tokens: AuthTokens | null) => void
  login: (user: User, tokens: AuthTokens) => void
  logout: () => void
  updateUser: (updates: Partial<User>) => void
}

const initialState: AuthState = {
  user: null,
  tokens: null,
  isAuthenticated: false,
  isLoading: false,
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
        }),

      setTokens: (tokens) =>
        set({
          tokens,
        }),

      login: (user, tokens) =>
        set({
          user,
          tokens,
          isAuthenticated: true,
          isLoading: false,
        }),

      logout: () =>
        set({
          ...initialState,
        }),

      updateUser: (updates) =>
        set({
          user: get().user ? { ...get().user!, ...updates } : null,
        }),
    }),
    {
      name: "cerberus-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

/**
 * Hook to get current authenticated user
 */
export function useCurrentUser(): User | null {
  return useAuthStore((state) => state.user)
}

/**
 * Hook to check if user is authenticated
 */
export function useIsAuthenticated(): boolean {
  return useAuthStore((state) => state.isAuthenticated)
}

/**
 * Hook to check if user has specific role
 */
export function useHasRole(role: "superadmin" | "admin" | "user"): boolean {
  const user = useAuthStore((state) => state.user)
  if (!user) return false

  const roleHierarchy = {
    superadmin: ["superadmin"],
    admin: ["superadmin", "admin"],
    user: ["superadmin", "admin", "user"],
  }

  return roleHierarchy[role].includes(user.role)
}

/**
 * Hook to check if user is admin
 */
export function useIsAdmin(): boolean {
  return useHasRole("admin")
}

/**
 * Hook to get auth tokens
 */
export function useAuthTokens(): AuthTokens | null {
  return useAuthStore((state) => state.tokens)
}

/**
 * Hook to get logout function
 */
export function useLogout(): () => void {
  return useAuthStore((state) => state.logout)
}
