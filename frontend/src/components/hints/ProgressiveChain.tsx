import * as React from "react"
import { cn } from "@/lib/utils"
import { CheckCircle2, Lock, Circle } from "lucide-react"

/**
 * ProgressiveChain Component
 * 
 * Visual chain display for progressive hint unlocking mode.
 * Shows the sequence of hints with connection lines and status indicators.
 * 
 * @example
 * <ProgressiveChain
 *   totalHints={3}
 *   unlockedCount={1}
 *   currentAvailable={2}
 * />
 */

interface ProgressiveChainProps {
  /** Total number of hints in the chain */
  totalHints: number
  /** Number of hints already unlocked */
  unlockedCount: number
  /** Current hint available for unlocking (1-based index) */
  currentAvailable: number
  /** Optional className for styling */
  className?: string
}

export function ProgressiveChain({
  totalHints,
  unlockedCount,
  currentAvailable,
  className,
}: ProgressiveChainProps) {
  return (
    <div className={cn("w-full", className)}>
      {/* Desktop view - horizontal chain */}
      <div className="hidden sm:flex items-center justify-between">
        {Array.from({ length: totalHints }, (_, index) => {
          const hintNumber = index + 1
          const isUnlocked = hintNumber <= unlockedCount
          const isAvailable = hintNumber === currentAvailable
          const isLocked = hintNumber > currentAvailable

          return (
            <React.Fragment key={index}>
              {/* Chain node */}
              <div className="flex flex-col items-center">
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300",
                    isUnlocked && [
                      "bg-green-500 border-green-500 text-white",
                      "shadow-lg shadow-green-500/30"
                    ],
                    isAvailable && [
                      "bg-primary border-primary text-primary-foreground",
                      "animate-pulse shadow-lg shadow-primary/30"
                    ],
                    isLocked && [
                      "bg-muted border-muted-foreground/30 text-muted-foreground"
                    ]
                  )}
                  aria-label={`Hint ${hintNumber} ${isUnlocked ? "unlocked" : isAvailable ? "available" : "locked"}`}
                >
                  {isUnlocked ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : isLocked ? (
                    <Lock className="h-4 w-4" />
                  ) : (
                    <Circle className="h-5 w-5" />
                  )}
                </div>
                <span className={cn(
                  "text-xs mt-2 font-medium",
                  isUnlocked && "text-green-600 dark:text-green-400",
                  isAvailable && "text-primary",
                  isLocked && "text-muted-foreground"
                )}>
                  Hint {hintNumber}
                </span>
              </div>

              {/* Connector line */}
              {index < totalHints - 1 && (
                <div className="flex-1 mx-2 relative">
                  <div
                    className={cn(
                      "h-0.5 transition-all duration-500",
                      hintNumber < unlockedCount
                        ? "bg-green-500"
                        : hintNumber === unlockedCount
                        ? "bg-gradient-to-r from-green-500 to-muted"
                        : "bg-muted"
                    )}
                  />
                  {/* Progress indicator on the line */}
                  {hintNumber === unlockedCount && (
                    <div 
                      className="absolute right-0 top-1/2 -translate-y-1/2 w-2 h-2 bg-primary rounded-full animate-ping"
                      aria-hidden="true"
                    />
                  )}
                </div>
              )}
            </React.Fragment>
          )
        })}
      </div>

      {/* Mobile view - vertical chain */}
      <div className="sm:hidden flex flex-col items-start pl-4">
        {Array.from({ length: totalHints }, (_, index) => {
          const hintNumber = index + 1
          const isUnlocked = hintNumber <= unlockedCount
          const isAvailable = hintNumber === currentAvailable
          const isLocked = hintNumber > currentAvailable
          const isLast = index === totalHints - 1

          return (
            <div key={index} className="flex items-stretch">
              {/* Vertical line and node */}
              <div className="flex flex-col items-center mr-4">
                {/* Top connector */}
                {index > 0 && (
                  <div
                    className={cn(
                      "w-0.5 flex-1 min-h-[20px]",
                      hintNumber <= unlockedCount + 1 ? "bg-green-500" : "bg-muted"
                    )}
                  />
                )}
                
                {/* Node */}
                <div
                  className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center border-2 flex-shrink-0 transition-all duration-300",
                    isUnlocked && [
                      "bg-green-500 border-green-500 text-white",
                      "shadow-lg shadow-green-500/30"
                    ],
                    isAvailable && [
                      "bg-primary border-primary text-primary-foreground",
                      "animate-pulse shadow-lg shadow-primary/30"
                    ],
                    isLocked && [
                      "bg-muted border-muted-foreground/30 text-muted-foreground"
                    ]
                  )}
                >
                  {isUnlocked ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : isLocked ? (
                    <Lock className="h-3 w-3" />
                  ) : (
                    <Circle className="h-4 w-4" />
                  )}
                </div>

                {/* Bottom connector */}
                {!isLast && (
                  <div
                    className={cn(
                      "w-0.5 flex-1 min-h-[20px]",
                      hintNumber <= unlockedCount ? "bg-green-500" : "bg-muted"
                    )}
                  />
                )}
              </div>

              {/* Label */}
              <div className="py-1">
                <span className={cn(
                  "text-sm font-medium",
                  isUnlocked && "text-green-600 dark:text-green-400",
                  isAvailable && "text-primary",
                  isLocked && "text-muted-foreground"
                )}>
                  Hint {hintNumber}
                  {isUnlocked && " (Unlocked)"}
                  {isAvailable && " (Available)"}
                  {isLocked && " (Locked)"}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-green-500" />
          Unlocked
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-primary animate-pulse" />
          Available
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-muted border border-muted-foreground/30" />
          Locked
        </span>
      </div>
    </div>
  )
}

export default ProgressiveChain
