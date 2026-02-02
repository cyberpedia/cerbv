import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Tabs component following Technical Brutalism design system
 * Uses Radix UI Tabs primitive
 * WCAG 2.1 AAA compliant with keyboard navigation
 */

const Tabs = TabsPrimitive.Root

const tabsListVariants = cva(
  "inline-flex items-center justify-center text-muted-foreground",
  {
    variants: {
      variant: {
        default: "h-10 rounded-md bg-muted p-1",
        industrial: "h-12 border-b-2 border-industrial-400 dark:border-industrial-600 bg-transparent p-0",
        pills: "h-auto gap-2 bg-transparent p-0",
        underline: "h-12 border-b border-border bg-transparent p-0 w-full",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface TabsListProps
  extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>,
    VariantProps<typeof tabsListVariants> {}

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  TabsListProps
>(({ className, variant, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(tabsListVariants({ variant }), className)}
    {...props}
  />
))
TabsList.displayName = TabsPrimitive.List.displayName

const tabsTriggerVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "rounded-sm px-3 py-1.5 data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=active]:shadow-sm",
        industrial: "rounded-none px-4 py-2 border-b-2 border-transparent data-[state=active]:border-safety data-[state=active]:text-foreground data-[state=active]:bg-transparent",
        pills: "rounded-full px-4 py-2 border-2 border-transparent data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary hover:bg-muted",
        underline: "flex-1 rounded-none px-4 py-2 border-b-2 border-transparent data-[state=active]:border-safety data-[state=active]:text-foreground hover:text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface TabsTriggerProps
  extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>,
    VariantProps<typeof tabsTriggerVariants> {}

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  TabsTriggerProps
>(({ className, variant, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(tabsTriggerVariants({ variant }), className)}
    {...props}
  />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const tabsContentVariants = cva(
  "mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
  {
    variants: {
      variant: {
        default: "",
        industrial: "mt-4 border-2 border-industrial-400 dark:border-industrial-600 p-4",
        contained: "mt-0 p-4 border border-t-0 border-border rounded-b-lg",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface TabsContentProps
  extends React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>,
    VariantProps<typeof tabsContentVariants> {}

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  TabsContentProps
>(({ className, variant, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(tabsContentVariants({ variant }), className)}
    {...props}
  />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
