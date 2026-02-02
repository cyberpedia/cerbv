/**
 * Dashboard Layout
 * Layout for authenticated dashboard pages
 */

import { MainNav } from "@/components/main-nav"
import { UserNav } from "@/components/user-nav"
import { MobileNav } from "@/components/mobile-nav"

interface DashboardLayoutProps {
  children: React.ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center">
          <MobileNav />
          <div className="mr-4 hidden md:flex">
            <MainNav />
          </div>
          <div className="flex flex-1 items-center justify-between space-x-2 md:justify-end">
            <div className="w-full flex-1 md:w-auto md:flex-none">
              {/* Search will go here */}
            </div>
            <UserNav />
          </div>
        </div>
      </header>
      <main id="main-content" className="flex-1">
        {children}
      </main>
    </div>
  )
}
