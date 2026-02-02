import * as React from "react"
import { cn } from "@/lib/utils"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { Check, X, HelpCircle } from "lucide-react"

import type { MCQOption } from "@/types"

/**
 * OptionList Component
 * 
 * Renders MCQ options with support for both single (radio) and multiple (checkbox) selection.
 * Includes keyboard navigation, accessibility features, and result feedback styling.
 * 
 * @example
 * <OptionList
 *   options={question.options}
 *   selectedOptionIds={["opt_1"]}
 *   onSelectionChange={(ids) => setSelected(ids)}
 *   allowMultiple={false}
 * />
 */

type OptionStatus = "neutral" | "correct" | "incorrect"

interface OptionListProps {
  /** Array of options to display */
  options: MCQOption[]
  /** Currently selected option IDs */
  selectedOptionIds: string[]
  /** Callback when selection changes */
  onSelectionChange: (optionIds: string[]) => void
  /** Whether multiple options can be selected */
  allowMultiple?: boolean
  /** Whether to show result feedback (correct/incorrect) */
  showResults?: boolean
  /** IDs of correct options (for result display) */
  correctOptionIds?: string[]
  /** Whether the component is disabled */
  disabled?: boolean
  /** Optional className for styling */
  className?: string
  /** Question ID for accessibility */
  questionId: string
}

export function OptionList({
  options,
  selectedOptionIds,
  onSelectionChange,
  allowMultiple = false,
  showResults = false,
  correctOptionIds = [],
  disabled = false,
  className,
  questionId,
}: OptionListProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)

  // Handle keyboard navigation
  React.useEffect(() => {
    const container = containerRef.current
    if (!container || disabled) return

    const handleKeyDown = (e: KeyboardEvent) => {
      const optionElements = container.querySelectorAll('[role="radio"], [role="checkbox"]')
      const currentIndex = Array.from(optionElements).findIndex(
        (el) => el === document.activeElement
      )

      switch (e.key) {
        case "ArrowDown":
        case "ArrowRight":
          e.preventDefault()
          const nextIndex = (currentIndex + 1) % optionElements.length
          ;(optionElements[nextIndex] as HTMLElement).focus()
          break
        case "ArrowUp":
        case "ArrowLeft":
          e.preventDefault()
          const prevIndex = currentIndex <= 0 ? optionElements.length - 1 : currentIndex - 1
          ;(optionElements[prevIndex] as HTMLElement).focus()
          break
        case " ":
        case "Enter":
          if (currentIndex >= 0) {
            e.preventDefault()
            const optionId = options[currentIndex]?.id
            if (optionId) {
              handleOptionToggle(optionId)
            }
          }
          break
      }
    }

    container.addEventListener("keydown", handleKeyDown)
    return () => container.removeEventListener("keydown", handleKeyDown)
  }, [options, disabled])

  const handleOptionToggle = (optionId: string) => {
    if (disabled || showResults) return

    if (allowMultiple) {
      // Toggle selection for multiple choice
      const newSelection = selectedOptionIds.includes(optionId)
        ? selectedOptionIds.filter((id) => id !== optionId)
        : [...selectedOptionIds, optionId]
      onSelectionChange(newSelection)
    } else {
      // Single selection for radio
      onSelectionChange([optionId])
    }
  }

  const getOptionStatus = (optionId: string): OptionStatus => {
    if (!showResults) return "neutral"
    if (correctOptionIds.includes(optionId)) return "correct"
    if (selectedOptionIds.includes(optionId) && !correctOptionIds.includes(optionId)) {
      return "incorrect"
    }
    return "neutral"
  }

  const getOptionStyles = (status: OptionStatus, isSelected: boolean) => {
    const baseStyles = "relative flex items-start gap-3 p-4 rounded-lg border-2 transition-all duration-200 cursor-pointer"
    
    if (showResults) {
      switch (status) {
        case "correct":
          return cn(
            baseStyles,
            "border-green-500 bg-green-50 dark:bg-green-900/20",
            "hover:border-green-600"
          )
        case "incorrect":
          return cn(
            baseStyles,
            "border-red-500 bg-red-50 dark:bg-red-900/20",
            "hover:border-red-600"
          )
        default:
          return cn(
            baseStyles,
            "border-muted bg-background",
            "opacity-60"
          )
      }
    }

    // Neutral state (during quiz)
    if (isSelected) {
      return cn(
        baseStyles,
        "border-primary bg-primary/5",
        "hover:border-primary/80"
      )
    }

    return cn(
      baseStyles,
      "border-muted bg-background",
      "hover:border-muted-foreground/50"
    )
  }

  return (
    <div
      ref={containerRef}
      className={cn("space-y-3", className)}
      role="group"
      aria-labelledby={`question-${questionId}-label`}
    >
      {allowMultiple ? (
        // Multiple choice (checkboxes)
        <div className="space-y-3">
          {options.map((option, index) => {
            const isSelected = selectedOptionIds.includes(option.id)
            const status = getOptionStatus(option.id)
            const optionId = `option-${questionId}-${option.id}`

            return (
              <div
                key={option.id}
                className={getOptionStyles(status, isSelected)}
                onClick={() => handleOptionToggle(option.id)}
                role="checkbox"
                aria-checked={isSelected}
                aria-disabled={disabled || showResults}
                tabIndex={disabled || showResults ? -1 : 0}
              >
                <Checkbox
                  id={optionId}
                  checked={isSelected}
                  disabled={disabled || showResults}
                  className="mt-0.5 pointer-events-none"
                  aria-hidden="true"
                />
                <Label
                  htmlFor={optionId}
                  className="flex-1 cursor-pointer font-normal text-base leading-relaxed pointer-events-none"
                >
                  {option.text}
                </Label>
                {showResults && status === "correct" && (
                  <Check className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" aria-hidden="true" />
                )}
                {showResults && status === "incorrect" && (
                  <X className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" aria-hidden="true" />
                )}
              </div>
            )
          })}
        </div>
      ) : (
        // Single choice (radio group)
        <RadioGroup
          value={selectedOptionIds[0] || ""}
          onValueChange={(value) => handleOptionToggle(value)}
          disabled={disabled || showResults}
          className="space-y-3"
        >
          {options.map((option) => {
            const isSelected = selectedOptionIds.includes(option.id)
            const status = getOptionStatus(option.id)
            const optionId = `option-${questionId}-${option.id}`

            return (
              <div
                key={option.id}
                className={getOptionStyles(status, isSelected)}
                onClick={() => !disabled && !showResults && handleOptionToggle(option.id)}
                role="radio"
                aria-checked={isSelected}
                aria-disabled={disabled || showResults}
                tabIndex={disabled || showResults ? -1 : 0}
              >
                <RadioGroupItem
                  value={option.id}
                  id={optionId}
                  disabled={disabled || showResults}
                  className="mt-0.5 pointer-events-none"
                  aria-hidden="true"
                />
                <Label
                  htmlFor={optionId}
                  className="flex-1 cursor-pointer font-normal text-base leading-relaxed pointer-events-none"
                >
                  {option.text}
                </Label>
                {showResults && status === "correct" && (
                  <Check className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0" aria-hidden="true" />
                )}
                {showResults && status === "incorrect" && (
                  <X className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" aria-hidden="true" />
                )}
              </div>
            )
          })}
        </RadioGroup>
      )}

      {/* Selection hint */}
      {!showResults && (
        <p className="text-sm text-muted-foreground mt-4">
          {allowMultiple ? (
            <span className="inline-flex items-center gap-1">
              <HelpCircle className="h-4 w-4" />
              Select all that apply. Use arrow keys to navigate, Space to select.
            </span>
          ) : (
            <span className="inline-flex items-center gap-1">
              <HelpCircle className="h-4 w-4" />
              Select one option. Use arrow keys to navigate, Enter to select.
            </span>
          )}
        </p>
      )}
    </div>
  )
}

export default OptionList
