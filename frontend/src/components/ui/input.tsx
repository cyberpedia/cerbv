import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Input component following Technical Brutalism design system
 * WCAG 2.1 AAA compliant with high contrast focus states
 * Supports Safety Orange accent for focus rings
 */

const inputVariants = cva(
  // Base styles - Industrial aesthetic
  "flex w-full border bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        // Default: Standard input with industrial border
        default: "border-input rounded-md",
        // Industrial: Thick border with sharp corners
        industrial:
          "border-2 border-industrial-400 rounded-none focus-visible:border-safety dark:border-industrial-600",
        // Ghost: Minimal border
        ghost:
          "border-transparent bg-transparent focus-visible:bg-muted/50 rounded-md",
        // Underline: Bottom border only
        underline:
          "border-0 border-b-2 border-input rounded-none px-0 focus-visible:border-ring",
      },
      inputSize: {
        default: "h-10",
        sm: "h-8 px-2 text-xs",
        lg: "h-12 px-4 text-base",
      },
      // Error state
      state: {
        default: "",
        error:
          "border-destructive focus-visible:ring-destructive text-destructive placeholder:text-destructive/60",
        success:
          "border-green-500 focus-visible:ring-green-500 text-green-600 dark:text-green-400",
      },
    },
    defaultVariants: {
      variant: "default",
      inputSize: "default",
      state: "default",
    },
  }
)

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement>,
    VariantProps<typeof inputVariants> {
  /**
   * Left icon or element
   */
  leftElement?: React.ReactNode
  /**
   * Right icon or element
   */
  rightElement?: React.ReactNode
  /**
   * Error message for accessibility
   */
  errorMessage?: string
  /**
   * Helper text for accessibility
   */
  helperText?: string
  /**
   * Size of the input
   */
  inputSize?: "default" | "sm" | "lg"
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      variant,
      inputSize,
      state,
      type = "text",
      leftElement,
      rightElement,
      errorMessage,
      helperText,
      id,
      "aria-describedby": ariaDescribedBy,
      "aria-invalid": ariaInvalid,
      ...props
    },
    ref
  ) => {
    // Generate unique IDs for accessibility
    const inputId = id || React.useId()
    const errorId = `${inputId}-error`
    const helperId = `${inputId}-helper`

    // Build aria-describedby
    const describedByIds = []
    if (helperText) describedByIds.push(helperId)
    if (errorMessage && state === "error") describedByIds.push(errorId)
    const finalAriaDescribedBy = describedByIds.join(" ") || ariaDescribedBy

    // Determine aria-invalid
    const isInvalid = ariaInvalid !== undefined ? ariaInvalid : state === "error"

    const hasAddons = leftElement || rightElement

    if (hasAddons) {
      return (
        <div className="relative flex items-center">
          {leftElement && (
            <div className="absolute left-3 flex items-center text-muted-foreground">
              {leftElement}
            </div>
          )}
          <input
            id={inputId}
            type={type}
            className={cn(
              inputVariants({ variant, inputSize, state }),
              leftElement && "pl-10",
              rightElement && "pr-10",
              className
            )}
            ref={ref}
            aria-describedby={finalAriaDescribedBy}
            aria-invalid={isInvalid}
            {...props}
          />
          {rightElement && (
            <div className="absolute right-3 flex items-center text-muted-foreground">
              {rightElement}
            </div>
          )}
        </div>
      )
    }

    return (
      <>
        <input
          id={inputId}
          type={type}
          className={cn(inputVariants({ variant, inputSize, state, className }))}
          ref={ref}
          aria-describedby={finalAriaDescribedBy}
          aria-invalid={isInvalid}
          {...props}
        />
        {helperText && state !== "error" && (
          <p id={helperId} className="mt-1 text-xs text-muted-foreground">
            {helperText}
          </p>
        )}
        {errorMessage && state === "error" && (
          <p id={errorId} className="mt-1 text-xs text-destructive" role="alert">
            {errorMessage}
          </p>
        )}
      </>
    )
  }
)
Input.displayName = "Input"

export { Input, inputVariants }
