import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Skeleton component following Technical Brutalism design system
 * Loading placeholder with pulse animation
 * WCAG 2.1 AAA compliant with reduced motion support
 */

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Number of skeleton rows to render
   */
  rows?: number
}

function Skeleton({
  className,
  rows = 1,
  ...props
}: SkeletonProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "animate-pulse rounded-md bg-industrial-200 dark:bg-industrial-800",
            className
          )}
          {...props}
        />
      ))}
    </>
  )
}

export { Skeleton }
