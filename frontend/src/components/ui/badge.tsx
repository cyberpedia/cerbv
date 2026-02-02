import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Badge component following Technical Brutalism design system
 * Simple badge component with variants
 * WCAG 2.1 AAA compliant with high contrast
 */

const badgeVariants = cva(
  "inline-flex items-center border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        industrial:
          "border-2 border-industrial-400 bg-transparent text-foreground hover:bg-industrial-100 dark:border-industrial-600 dark:hover:bg-industrial-900",
        success:
          "border-transparent bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-900 dark:text-green-100 dark:hover:bg-green-800",
        warning:
          "border-transparent bg-yellow-100 text-yellow-800 hover:bg-yellow-200 dark:bg-yellow-900 dark:text-yellow-100 dark:hover:bg-yellow-800",
        info:
          "border-transparent bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-900 dark:text-blue-100 dark:hover:bg-blue-800",
        safety:
          "border-transparent bg-safety-100 text-safety-800 hover:bg-safety-200",
      },
      size: {
        default: "rounded-full",
        sm: "rounded-full px-2 py-0 text-[10px]",
        lg: "rounded-full px-3 py-1 text-sm",
        industrial: "rounded-none",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, size, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant, size }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
