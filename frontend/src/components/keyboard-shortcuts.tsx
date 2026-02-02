"use client"

/**
 * Keyboard Shortcuts Component
 * Global keyboard shortcuts for accessibility
 * - g: Focus search
 * - c: Navigate to challenges
 * - l: Navigate to leaderboard
 * - h: Navigate to home
 * - ?: Show keyboard shortcuts help
 */

import * as React from "react"
import { useRouter } from "next/navigation"

export function KeyboardShortcuts() {
  const router = useRouter()

  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if user is typing in an input
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement ||
        event.target instanceof HTMLSelectElement
      ) {
        return
      }

      // Ignore if meta key is pressed (for browser shortcuts)
      if (event.metaKey || event.ctrlKey) {
        return
      }

      switch (event.key.toLowerCase()) {
        case "g":
          event.preventDefault()
          // Focus search input if it exists
          const searchInput = document.querySelector('[data-search-input]') as HTMLInputElement
          if (searchInput) {
            searchInput.focus()
          }
          break
        case "c":
          event.preventDefault()
          router.push("/challenges")
          break
        case "l":
          event.preventDefault()
          router.push("/leaderboard")
          break
        case "h":
          event.preventDefault()
          router.push("/")
          break
        case "?":
          event.preventDefault()
          // Show keyboard shortcuts help modal
          // This would be implemented with a modal/dialog
          console.log("Show keyboard shortcuts help")
          break
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [router])

  return null
}
