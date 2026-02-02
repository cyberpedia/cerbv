"use client"

/**
 * Skip Link Component
 * Accessibility feature for keyboard navigation
 * Allows users to skip to main content
 */

import * as React from "react"

export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-safety focus:px-4 focus:py-2 focus:text-white focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
    >
      Skip to main content
    </a>
  )
}
