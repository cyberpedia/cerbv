import * as React from "react"
import { cn } from "@/lib/utils"
import { Check, Circle } from "lucide-react"

/**
 * ProgressBar Component
 * 
 * Displays question navigation with progress indicators.
 * Shows answered/unanswered status and allows jumping between questions.
 * 
 * @example
 * <ProgressBar
 *   totalQuestions={5}
 *   currentIndex={2}
 *   answeredQuestions={[0, 1]}
 *   onQuestionClick={(index) => setCurrentQuestion(index)}
 * />
 */

interface ProgressBarProps {
  /** Total number of questions */
  totalQuestions: number
  /** Current question index (0-based) */
  currentIndex: number
  /** Array of answered question indices */
  answeredQuestions: number[]
  /** Callback when a question indicator is clicked */
  onQuestionClick: (index: number) => void
  /** Optional className for styling */
  className?: string
  /** Whether to show question numbers */
  showNumbers?: boolean
}

export function ProgressBar({
  totalQuestions,
  currentIndex,
  answeredQuestions,
  onQuestionClick,
  className,
  showNumbers = true,
}: ProgressBarProps) {
  const progressPercentage = ((currentIndex + 1) / totalQuestions) * 100

  return (
    <div className={cn("w-full", className)} role="navigation" aria-label="Question navigation">
      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm text-muted-foreground mb-2">
          <span aria-live="polite">
            Question {currentIndex + 1} of {totalQuestions}
          </span>
          <span>{Math.round(progressPercentage)}% Complete</span>
        </div>
        <div 
          className="h-2 bg-muted rounded-full overflow-hidden"
          role="progressbar"
          aria-valuenow={currentIndex + 1}
          aria-valuemin={1}
          aria-valuemax={totalQuestions}
          aria-label="Quiz progress"
        >
          <div
            className="h-full bg-primary transition-all duration-300 ease-in-out"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>
      </div>

      {/* Question indicators */}
      <div 
        className="flex items-center justify-center gap-2 flex-wrap"
        role="tablist"
        aria-label="Question tabs"
      >
        {Array.from({ length: totalQuestions }, (_, index) => {
          const isAnswered = answeredQuestions.includes(index)
          const isCurrent = index === currentIndex
          const isPast = index < currentIndex
          const isFuture = index > currentIndex

          return (
            <button
              key={index}
              onClick={() => onQuestionClick(index)}
              role="tab"
              aria-selected={isCurrent}
              aria-label={`Question ${index + 1}${isAnswered ? " (answered)" : " (unanswered)"}`}
              className={cn(
                "relative flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                // Current question
                isCurrent && [
                  "border-primary bg-primary text-primary-foreground",
                  "ring-2 ring-primary ring-offset-2",
                ],
                // Answered and past questions
                !isCurrent && isAnswered && [
                  "border-green-500 bg-green-50 text-green-700",
                  "dark:bg-green-900/30 dark:text-green-400",
                ],
                // Unanswered past questions
                !isCurrent && isPast && !isAnswered && [
                  "border-yellow-500 bg-yellow-50 text-yellow-700",
                  "dark:bg-yellow-900/30 dark:text-yellow-400",
                ],
                // Future questions
                isFuture && [
                  "border-muted bg-background text-muted-foreground",
                  "hover:border-muted-foreground/50",
                ],
                // Hover states
                !isCurrent && "hover:scale-105"
              )}
            >
              {isAnswered ? (
                <Check className="h-5 w-5" aria-hidden="true" />
              ) : (
                showNumbers && <span className="text-sm font-medium">{index + 1}</span>
              )}
              
              {/* Status indicator dot */}
              {!isCurrent && (
                <span
                  className={cn(
                    "absolute -bottom-1 -right-1 w-3 h-3 rounded-full border-2 border-background",
                    isAnswered ? "bg-green-500" : "bg-muted-foreground/30"
                  )}
                  aria-hidden="true"
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Summary text */}
      <div className="mt-4 text-center text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-4">
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" aria-hidden="true" />
            {answeredQuestions.length} answered
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-muted-foreground/30" aria-hidden="true" />
            {totalQuestions - answeredQuestions.length} remaining
          </span>
        </span>
      </div>
    </div>
  )
}

export default ProgressBar
