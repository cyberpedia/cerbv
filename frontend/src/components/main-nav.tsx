"use client"

/**
 * Main Navigation Component
 * Primary navigation links for authenticated users
 */

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Shield, Trophy, LayoutDashboard } from "lucide-react"

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
  {
    title: "Admin",
    href: "/admin",
    icon: Shield,
    adminOnly: true,
  },
]

export function MainNav() {
  const pathname = usePathname()

  return (
    <div className="mr-4 flex">
      <Link href="/" className="mr-6 flex items-center space-x-2">
        <Shield className="h-6 w-6 text-safety" />
        <span className="hidden font-bold sm:inline-block">Cerberus</span>
      </Link>
      <nav className="flex items-center space-x-6 text-sm font-medium">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center space-x-2 transition-colors hover:text-foreground/80",
              pathname === item.href
                ? "text-foreground"
                : "text-foreground/60"
            )}
          >
            <item.icon className="h-4 w-4" />
            <span>{item.title}</span>
          </Link>
        ))}
      </nav>
    </div>
  )
}
