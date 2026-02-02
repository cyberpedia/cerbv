"use client"

/**
 * Mobile Navigation Component
 * Sheet-based mobile navigation menu
 */

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"
import { Menu, Shield, Trophy, LayoutDashboard } from "lucide-react"

const navItems = [
  {
    title: "Challenges",
    href: "/challenges",
    icon: LayoutDashboard,
  },
  {
    title: "Leaderboard",
    href: "/leaderboard",
    icon: Trophy,
  },
]

export function MobileNav() {
  const [open, setOpen] = React.useState(false)
  const pathname = usePathname()

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="ghost"
          className="mr-2 px-0 text-base hover:bg-transparent focus-visible:bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0 md:hidden"
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Toggle Menu</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="pr-0">
        <MobileLink href="/" className="flex items-center" onOpenChange={setOpen}>
          <Shield className="mr-2 h-4 w-4 text-safety" />
          <span className="font-bold">Cerberus</span>
        </MobileLink>
        <ScrollArea className="my-4 h-[calc(100vh-8rem)] pb-10 pl-6">
          <div className="flex flex-col space-y-3">
            {navItems.map((item) => (
              <MobileLink
                key={item.href}
                href={item.href}
                onOpenChange={setOpen}
                className={cn(
                  "flex items-center space-x-2 text-sm font-medium",
                  pathname === item.href
                    ? "text-foreground"
                    : "text-muted-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                <span>{item.title}</span>
              </MobileLink>
            ))}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}

interface MobileLinkProps {
  href: string
  onOpenChange?: (open: boolean) => void
  className?: string
  children: React.ReactNode
}

function MobileLink({ href, onOpenChange, className, children }: MobileLinkProps) {
  return (
    <Link
      href={href}
      onClick={() => onOpenChange?.(false)}
      className={cn(className)}
    >
      {children}
    </Link>
  )
}
