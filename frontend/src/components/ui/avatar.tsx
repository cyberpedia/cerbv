import * as React from "react"
import * as AvatarPrimitive from "@radix-ui/react-avatar"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Avatar component following Technical Brutalism design system
 * Uses Radix UI Avatar primitive
 * WCAG 2.1 AAA compliant with fallback support
 */

const avatarVariants = cva(
  "relative flex shrink-0 overflow-hidden",
  {
    variants: {
      size: {
        default: "h-10 w-10",
        sm: "h-8 w-8",
        lg: "h-12 w-12",
        xl: "h-16 w-16",
        "2xl": "h-20 w-20",
      },
      variant: {
        default: "rounded-full",
        industrial: "rounded-none border-2 border-industrial-400 dark:border-industrial-600",
        square: "rounded-md",
      },
    },
    defaultVariants: {
      size: "default",
      variant: "default",
    },
  }
)

interface AvatarProps
  extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root>,
    VariantProps<typeof avatarVariants> {}

const Avatar = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Root>,
  AvatarProps
>(({ className, size, variant, ...props }, ref) => (
  <AvatarPrimitive.Root
    ref={ref}
    className={cn(avatarVariants({ size, variant }), className)}
    {...props}
  />
))
Avatar.displayName = AvatarPrimitive.Root.displayName

const AvatarImage = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Image>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image>
>(({ className, ...props }, ref) => (
  <AvatarPrimitive.Image
    ref={ref}
    className={cn("aspect-square h-full w-full", className)}
    {...props}
  />
))
AvatarImage.displayName = AvatarPrimitive.Image.displayName

const avatarFallbackVariants = cva(
  "flex h-full w-full items-center justify-center bg-muted font-medium",
  {
    variants: {
      variant: {
        default: "rounded-full",
        industrial: "rounded-none",
        square: "rounded-md",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

interface AvatarFallbackProps
  extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>,
    VariantProps<typeof avatarFallbackVariants> {}

const AvatarFallback = React.forwardRef<
  React.ElementRef<typeof AvatarPrimitive.Fallback>,
  AvatarFallbackProps
>(({ className, variant, ...props }, ref) => (
  <AvatarPrimitive.Fallback
    ref={ref}
    className={cn(avatarFallbackVariants({ variant }), className)}
    {...props}
  />
))
AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName

export { Avatar, AvatarImage, AvatarFallback }
