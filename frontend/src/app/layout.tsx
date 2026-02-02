/**
 * Root Layout - Cerberus CTF Platform
 * Provides theme provider, query client, and global context
 */

import type { Metadata, Viewport } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import { ThemeProvider } from "@/components/theme-provider"
import { QueryProvider } from "@/components/query-provider"
import { Toaster } from "@/components/ui/toaster"
import { SkipLink } from "@/components/skip-link"
import { KeyboardShortcuts } from "@/components/keyboard-shortcuts"
import "./globals.css"

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
})

export const metadata: Metadata = {
  title: {
    default: "Cerberus CTF Platform",
    template: "%s | Cerberus CTF",
  },
  description: "Enterprise-grade Capture The Flag platform for cybersecurity training and competitions",
  keywords: ["CTF", "cybersecurity", "hacking", "capture the flag", "security training"],
  authors: [{ name: "Cerberus Team" }],
  creator: "Cerberus CTF Platform",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"),
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "Cerberus CTF Platform",
  },
  twitter: {
    card: "summary_large_image",
    creator: "@cerberusctf",
  },
  robots: {
    index: true,
    follow: true,
  },
  manifest: "/manifest.json",
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
}

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange={false}
        >
          <QueryProvider>
            <SkipLink />
            <KeyboardShortcuts />
            <div className="relative flex min-h-screen flex-col">
              {children}
            </div>
            <Toaster />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
