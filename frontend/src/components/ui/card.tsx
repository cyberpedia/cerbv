import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Card component following Technical Brutalism design system
 * Industrial aesthetic with sharp edges and optional Safety Orange accent
 * WCAG 2.1 AAA compliant
 */

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    /**
     * Show Safety Orange accent border on the left
     */
    accent?: boolean
    /**
     * Use thick industrial borders
     */
    industrial?: boolean
    /**
     * Remove padding for custom layouts
     */
    noPadding?: boolean
  }
>(({ className, accent = false, industrial = false, noPadding = false, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "bg-card text-card-foreground",
      // Border styles
      industrial
        ? "border-2 border-industrial-400 dark:border-industrial-600"
        : "border border-border",
      // Accent border on left
      accent && "border-l-4 border-l-safety",
      // Rounded corners (sharp for industrial)
      industrial ? "rounded-none" : "rounded-lg",
      // Shadow
      "shadow-sm",
      // Padding
      !noPadding && "p-6",
      className
    )}
    {...props}
  />
))
Card.displayName = "Card"

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    /**
     * Use Swiss grid layout
     */
    grid?: boolean
  }
>(({ className, grid = false, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex flex-col space-y-1.5",
      grid && "swiss-grid items-center",
      className
    )}
    {...props}
  />
))
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement> & {
    as?: "h1" | "h2" | "h3" | "h4" | "h5" | "h6"
  }
>(({ className, as: Component = "h3", ...props }, ref) => (
  <Component
    ref={ref as React.Ref<HTMLHeadingElement>}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("pt-0", className)} {...props} />
))
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    /**
     * Align items to the end
     */
    align?: "start" | "center" | "end" | "between"
  }
>(({ className, align = "start", ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "flex items-center pt-4",
      align === "start" && "justify-start",
      align === "center" && "justify-center",
      align === "end" && "justify-end",
      align === "between" && "justify-between",
      className
    )}
    {...props}
  />
))
CardFooter.displayName = "CardFooter"

const CardDivider = React.forwardRef<
  HTMLHRElement,
  React.HTMLAttributes<HTMLHRElement>
>(({ className, ...props }, ref) => (
  <hr
    ref={ref}
    className={cn(
      "my-4 border-0 border-t border-border",
      className
    )}
    {...props}
  />
))
CardDivider.displayName = "CardDivider"

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
  CardDivider,
}
