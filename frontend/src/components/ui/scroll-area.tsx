import * as React from "react"
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Scroll Area component following Technical Brutalism design system
 * Uses Radix UI Scroll Area primitive
 * WCAG 2.1 AAA compliant with keyboard navigation
 */

const scrollAreaVariants = cva(
  "relative overflow-hidden",
  {
    variants: {
      variant: {
        default: "",
        industrial: "border-2 border-industrial-400 dark:border-industrial-600",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface ScrollAreaProps
  extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>,
    VariantProps<typeof scrollAreaVariants> {}

const ScrollArea = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
  ScrollAreaProps
>(({ className, variant, children, ...props }, ref) => (
  <ScrollAreaPrimitive.Root
    ref={ref}
    className={cn(scrollAreaVariants({ variant }), className)}
    {...props}
  >
    <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
      {children}
    </ScrollAreaPrimitive.Viewport>
    <ScrollBar />
    <ScrollAreaPrimitive.Corner />
  </ScrollAreaPrimitive.Root>
))
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName

const scrollBarVariants = cva(
  "flex touch-none select-none transition-colors",
  {
    variants: {
      variant: {
        default: "",
        industrial: "",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface ScrollBarProps
  extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>,
    VariantProps<typeof scrollBarVariants> {}

const ScrollBar = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>,
  ScrollBarProps
>(({ className, orientation = "vertical", variant, ...props }, ref) => (
  <ScrollAreaPrimitive.ScrollAreaScrollbar
    ref={ref}
    orientation={orientation}
    className={cn(
      scrollBarVariants({ variant }),
      orientation === "vertical" ? "h-full w-2.5 border-l border-l-transparent p-[1px]" : "h-2.5 flex-col border-t border-t-transparent p-[1px]",
      className
    )}
    {...props}
  >
    <ScrollAreaPrimitive.ScrollAreaThumb className={cn(
      "relative flex-1 rounded-full bg-border",
      variant === "industrial" && "rounded-none bg-industrial-400 dark:bg-industrial-600"
    )} />
  </ScrollAreaPrimitive.ScrollAreaScrollbar>
))
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName

export { ScrollArea, ScrollBar }
