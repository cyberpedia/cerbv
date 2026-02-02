/**
 * Theme State Management
 * Zustand store for theme preferences with system preference detection
 */

import { create } from "zustand"
import { persist, createJSONStorage } from "zustand/middleware"
import type { ThemeMode, ThemeConfig } from "@/types"

interface ThemeStore extends ThemeConfig {
  // Actions
  setMode: (mode: ThemeMode) => void
  setFontSize: (size: "small" | "medium" | "large") => void
  toggleReducedMotion: () => void
  toggleHighContrast: () => void
  toggleMode: () => void
}

const initialState: ThemeConfig = {
  mode: "system",
  safetyOrange: "#ff5f00",
  fontSize: "medium",
  reducedMotion: false,
  highContrast: false,
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setMode: (mode) =>
        set({
          mode,
        }),

      setFontSize: (fontSize) =>
        set({
          fontSize,
        }),

      toggleReducedMotion: () =>
        set({
          reducedMotion: !get().reducedMotion,
        }),

      toggleHighContrast: () =>
        set({
          highContrast: !get().highContrast,
        }),

      toggleMode: () =>
        set({
          mode: get().mode === "dark" ? "light" : "dark",
        }),
    }),
    {
      name: "cerberus-theme",
      storage: createJSONStorage(() => localStorage),
    }
  )
)

/**
 * Hook to get current theme mode
 */
export function useThemeMode(): ThemeMode {
  return useThemeStore((state) => state.mode)
}

/**
 * Hook to check if dark mode is active
 * Considers system preference when mode is "system"
 */
export function useIsDarkMode(): boolean {
  const mode = useThemeStore((state) => state.mode)

  if (mode === "system") {
    if (typeof window !== "undefined") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches
    }
    return false
  }

  return mode === "dark"
}

/**
 * Hook to check if reduced motion is preferred
 */
export function useReducedMotion(): boolean {
  const storeReducedMotion = useThemeStore((state) => state.reducedMotion)

  if (typeof window !== "undefined") {
    const systemPrefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches
    return storeReducedMotion || systemPrefersReducedMotion
  }

  return storeReducedMotion
}

/**
 * Hook to check if high contrast is enabled
 */
export function useHighContrast(): boolean {
  return useThemeStore((state) => state.highContrast)
}

/**
 * Hook to get font size
 */
export function useFontSize(): "small" | "medium" | "large" {
  return useThemeStore((state) => state.fontSize)
}
