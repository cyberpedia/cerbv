import * as React from "react"
import * as SeparatorPrimitive from "@radix-ui/react-separator"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Separator component following Technical Brutalism design system
 * Uses Radix UI Separator primitive
 * WCAG 2.1 AAA compliant with proper ARIA attributes
 */

const separatorVariants = cva(
  "shrink-0 bg-border",
  {
    variants: {
      variant: {
        default: "bg-border",
        industrial: "bg-industrial-400 dark:bg-industrial-600",
        safety: "bg-safety",
        muted: "bg-muted",
      },
      thickness: {
        default: "",
        thick: "",
      },
    },
    defaultVariants: {
      variant: "default",
      thickness: "default",
    },
  }
)

interface SeparatorProps
  extends React.ComponentPropsWithoutRef<typeof SeparatorPrimitive.Root>,
    VariantProps<typeof separatorVariants> {}

const Separator = React.forwardRef<
  React.ElementRef<typeof SeparatorPrimitive.Root>,
  SeparatorProps
>(
  (
    { className, orientation = "horizontal", variant, thickness, decorative = true, ...props },
    ref
  ) => (
    <SeparatorPrimitive.Root
      ref={ref}
      decorative={decorative}
      orientation={orientation}
      className={cn(
        separatorVariants({ variant, thickness }),
        orientation === "horizontal" ? "h-[1px] w-full" : "h-full w-[1px]",
        thickness === "thick" && (orientation === "horizontal" ? "h-[2px]" : "w-[2px]"),
        className
      )}
      {...props}
    />
  )
)
Separator.displayName = SeparatorPrimitive.Root.displayName

export { Separator }
