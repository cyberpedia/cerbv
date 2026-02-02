/**
 * Home Page - Cerberus CTF Platform
 * Landing page with CTF overview and navigation
 */

import { Metadata } from "next"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Shield, Trophy, Users, Zap, Lock, Terminal } from "lucide-react"

export const metadata: Metadata = {
  title: "Home",
  description: "Welcome to Cerberus CTF Platform - Test your cybersecurity skills",
}

export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Hero Section */}
      <section className="relative flex flex-col items-center justify-center px-4 py-24 text-center md:py-32">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-safety/10 via-background to-background" />
        
        <Badge variant="safety" className="mb-4">
          <Shield className="mr-1 h-3 w-3" />
          Enterprise CTF Platform
        </Badge>
        
        <h1 className="mb-4 text-4xl font-bold tracking-tight md:text-6xl lg:text-7xl">
          <span className="text-safety">Cerberus</span>
          <span className="block text-foreground">CTF Platform</span>
        </h1>
        
        <p className="mb-8 max-w-2xl text-lg text-muted-foreground md:text-xl">
          Test your cybersecurity skills in a controlled environment. 
          From web exploitation to reverse engineering, prove your worth.
        </p>
        
        <div className="flex flex-col gap-4 sm:flex-row">
          <Button asChild size="lg" className="min-w-[160px]">
            <Link href="/challenges">
              <Terminal className="mr-2 h-4 w-4" />
              Start Hacking
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="min-w-[160px]">
            <Link href="/leaderboard">
              <Trophy className="mr-2 h-4 w-4" />
              View Leaderboard
            </Link>
          </Button>
        </div>
      </section>

      <Separator />

      {/* Features Section */}
      <section className="px-4 py-16 md:py-24">
        <div className="mx-auto max-w-7xl">
          <div className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-bold tracking-tight md:text-4xl">
              Challenge Categories
            </h2>
            <p className="text-muted-foreground">
              Master multiple disciplines in cybersecurity
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            <CategoryCard
              title="Web Exploitation"
              description="SQL injection, XSS, CSRF, and modern web vulnerabilities"
              icon={<Zap className="h-6 w-6" />}
              count={12}
            />
            <CategoryCard
              title="Cryptography"
              description="Classical ciphers, modern encryption, and hash challenges"
              icon={<Lock className="h-6 w-6" />}
              count={8}
            />
            <CategoryCard
              title="Binary Exploitation"
              description="Buffer overflows, ROP chains, and memory corruption"
              icon={<Terminal className="h-6 w-6" />}
              count={10}
            />
            <CategoryCard
              title="Reverse Engineering"
              description="Disassembly, decompilation, and malware analysis"
              icon={<Shield className="h-6 w-6" />}
              count={6}
            />
            <CategoryCard
              title="Forensics"
              description="Memory dumps, network captures, and file analysis"
              icon={<Users className="h-6 w-6" />}
              count={9}
            />
            <CategoryCard
              title="Miscellaneous"
              description="Steganography, OSINT, and creative challenges"
              icon={<Trophy className="h-6 w-6" />}
              count={15}
            />
          </div>
        </div>
      </section>

      <Separator />

      {/* Stats Section */}
      <section className="bg-muted/50 px-4 py-16">
        <div className="mx-auto max-w-7xl">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard value="60+" label="Challenges" />
            <StatCard value="1,200+" label="Active Players" />
            <StatCard value="5,400+" label="Total Solves" />
            <StatCard value="$5,000" label="Prize Pool" />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="px-4 py-16 md:py-24">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight">
            Ready to Begin?
          </h2>
          <p className="mb-8 text-muted-foreground">
            Join thousands of security professionals and enthusiasts. 
            Create an account and start solving challenges today.
          </p>
          <div className="flex flex-col gap-4 sm:flex-row sm:justify-center">
            <Button asChild size="lg">
              <Link href="/register">Create Account</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <Link href="/login">Sign In</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}

interface CategoryCardProps {
  title: string
  description: string
  icon: React.ReactNode
  count: number
}

function CategoryCard({ title, description, icon, count }: CategoryCardProps) {
  return (
    <Card className="group transition-all hover:border-safety/50 hover:shadow-lg">
      <CardHeader>
        <div className="mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-safety/10 text-safety transition-colors group-hover:bg-safety group-hover:text-white">
          {icon}
        </div>
        <CardTitle className="flex items-center justify-between">
          {title}
          <Badge variant="secondary">{count}</Badge>
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  )
}

interface StatCardProps {
  value: string
  label: string
}

function StatCard({ value, label }: StatCardProps) {
  return (
    <div className="text-center">
      <div className="text-4xl font-bold text-safety">{value}</div>
      <div className="text-sm text-muted-foreground">{label}</div>
    </div>
  )
}
