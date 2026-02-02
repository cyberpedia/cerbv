import * as React from "react"
import * as AccordionPrimitive from "@radix-ui/react-accordion"
import { ChevronDown } from "lucide-react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Accordion component following Technical Brutalism design system
 * Uses Radix UI Accordion primitive
 * WCAG 2.1 AAA compliant with keyboard navigation
 */

const Accordion = AccordionPrimitive.Root

const accordionItemVariants = cva(
  "border-b",
  {
    variants: {
      variant: {
        default: "border-border",
        industrial: "border-industrial-400 dark:border-industrial-600",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface AccordionItemProps
  extends React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Item>,
    VariantProps<typeof accordionItemVariants> {}

const AccordionItem = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Item>,
  AccordionItemProps
>(({ className, variant, ...props }, ref) => (
  <AccordionPrimitive.Item
    ref={ref}
    className={cn(accordionItemVariants({ variant }), className)}
    {...props}
  />
))
AccordionItem.displayName = "AccordionItem"

const accordionTriggerVariants = cva(
  "flex flex-1 items-center justify-between py-4 font-medium transition-all hover:underline [&[data-state=open]>svg]:rotate-180",
  {
    variants: {
      variant: {
        default: "",
        industrial: "px-4 hover:bg-industrial-50 dark:hover:bg-industrial-900",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface AccordionTriggerProps
  extends React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Trigger>,
    VariantProps<typeof accordionTriggerVariants> {}

const AccordionTrigger = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Trigger>,
  AccordionTriggerProps
>(({ className, variant, children, ...props }, ref) => (
  <AccordionPrimitive.Header className="flex">
    <AccordionPrimitive.Trigger
      ref={ref}
      className={cn(accordionTriggerVariants({ variant }), className)}
      {...props}
    >
      {children}
      <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200" />
    </AccordionPrimitive.Trigger>
  </AccordionPrimitive.Header>
))
AccordionTrigger.displayName = AccordionPrimitive.Trigger.displayName

const accordionContentVariants = cva(
  "overflow-hidden text-sm transition-all data-[state=closed]:animate-accordion-up data-[state=open]:animate-accordion-down",
  {
    variants: {
      variant: {
        default: "",
        industrial: "px-4",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface AccordionContentProps
  extends React.ComponentPropsWithoutRef<typeof AccordionPrimitive.Content>,
    VariantProps<typeof accordionContentVariants> {}

const AccordionContent = React.forwardRef<
  React.ElementRef<typeof AccordionPrimitive.Content>,
  AccordionContentProps
>(({ className, variant, children, ...props }, ref) => (
  <AccordionPrimitive.Content
    ref={ref}
    className={cn(accordionContentVariants({ variant }), className)}
    {...props}
  >
    <div className="pb-4 pt-0">{children}</div>
  </AccordionPrimitive.Content>
))

AccordionContent.displayName = AccordionPrimitive.Content.displayName

export { Accordion, AccordionItem, AccordionTrigger, AccordionContent }
