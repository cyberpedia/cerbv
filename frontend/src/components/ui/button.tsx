import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Button component following Technical Brutalism design system
 * Uses Safety Orange (#ff5f00) as primary accent
 * WCAG 2.1 AAA compliant with high contrast ratios
 */

const buttonVariants = cva(
  // Base styles - Industrial aesthetic with sharp edges
  "inline-flex items-center justify-center whitespace-nowrap font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        // Primary: Safety Orange - High contrast on light/dark
        default:
          "bg-primary text-primary-foreground hover:bg-primary/90 border-2 border-transparent",
        // Secondary: Industrial gray
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80 border-2 border-transparent",
        // Destructive: Red for errors/warnings
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 border-2 border-transparent",
        // Outline: Bordered style
        outline:
          "border-2 border-input bg-background hover:bg-accent hover:text-accent-foreground",
        // Ghost: No background until hover
        ghost:
          "hover:bg-accent hover:text-accent-foreground border-2 border-transparent",
        // Link: Text only with underline
        link:
          "text-primary underline-offset-4 hover:underline border-2 border-transparent",
        // Industrial: Thick border variant
        industrial:
          "border-2 border-industrial-400 bg-background text-foreground hover:bg-industrial-50 hover:border-industrial-500 dark:border-industrial-600 dark:hover:bg-industrial-900 dark:hover:border-industrial-500",
      },
      size: {
        default: "h-10 px-4 py-2 text-sm",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-6 text-base",
        icon: "h-10 w-10",
        "icon-sm": "h-8 w-8",
        "icon-lg": "h-12 w-12",
      },
      // Swiss grid alignment
      align: {
        default: "",
        left: "justify-start",
        center: "justify-center",
        right: "justify-end",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
      align: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  /**
   * Loading state - shows spinner and disables button
   */
  loading?: boolean
  /**
   * Icon to display before text
   */
  leftIcon?: React.ReactNode
  /**
   * Icon to display after text
   */
  rightIcon?: React.ReactNode
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      align,
      asChild = false,
      loading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button"
    const isDisabled = disabled || loading

    return (
      <Comp
        className={cn(buttonVariants({ variant, size, align, className }))}
        ref={ref}
        disabled={isDisabled}
        aria-disabled={isDisabled}
        aria-busy={loading}
        {...props}
      >
        {loading && (
          <span
            className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            aria-hidden="true"
          />
        )}
        {!loading && leftIcon && (
          <span className="mr-2 inline-flex" aria-hidden="true">
            {leftIcon}
          </span>
        )}
        {children}
        {!loading && rightIcon && (
          <span className="ml-2 inline-flex" aria-hidden="true">
            {rightIcon}
          </span>
        )}
      </Comp>
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
