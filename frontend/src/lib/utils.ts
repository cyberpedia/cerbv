import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Utility function to merge Tailwind CSS classes with proper precedence
 * Handles conditional classes and resolves conflicts
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a number with thousands separators
 */
export function formatNumber(num: number): string {
  return num.toLocaleString()
}

/**
 * Format bytes to human-readable string
 */
export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes === 0) return "0 Bytes"

  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ["Bytes", "KB", "MB", "GB", "TB"]

  const i = Math.floor(Math.log(bytes) / Math.log(k))

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

/**
 * Format a date to relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: string | Date): string {
  const now = new Date()
  const then = new Date(date)
  const diffInSeconds = Math.floor((now.getTime() - then.getTime()) / 1000)

  const intervals = [
    { label: "year", seconds: 31536000 },
    { label: "month", seconds: 2592000 },
    { label: "week", seconds: 604800 },
    { label: "day", seconds: 86400 },
    { label: "hour", seconds: 3600 },
    { label: "minute", seconds: 60 },
    { label: "second", seconds: 1 },
  ]

  for (const interval of intervals) {
    const count = Math.floor(diffInSeconds / interval.seconds)
    if (count >= 1) {
      return `${count} ${interval.label}${count > 1 ? "s" : ""} ago`
    }
  }

  return "just now"
}

/**
 * Format a date to local string
 */
export function formatDate(date: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const d = new Date(date)
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }
  return d.toLocaleDateString("en-US", options || defaultOptions)
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}...`
}

/**
 * Generate a random ID
 */
export function generateId(length = 8): string {
  return Math.random()
    .toString(36)
    .substring(2, 2 + length)
}

/**
 * Debounce function
 */
export function debounce<T extends (...args: unknown[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return function (...args: Parameters<T>) {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

/**
 * Deep clone an object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

/**
 * Check if code is running on client side
 */
export function isClient(): boolean {
  return typeof window !== "undefined"
}

/**
 * Get initial from name
 */
export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/**
 * Sleep/delay utility
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Check if element is in viewport
 */
export function isInViewport(element: HTMLElement): boolean {
  const rect = element.getBoundingClientRect()
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  )
}

/**
 * Generate HMAC signature for request signing
 * Matches backend request signing implementation
 */
export async function generateRequestSignature(
  method: string,
  path: string,
  body: string | null,
  timestamp: string,
  secret: string
): Promise<string> {
  const encoder = new TextEncoder()
  const data = `${method.toUpperCase()}|${path}|${body || ""}|${timestamp}`
  
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  )
  
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(data))
  const signatureArray = Array.from(new Uint8Array(signature))
  return btoa(String.fromCharCode.apply(null, signatureArray))
}

/**
 * Sanitize HTML to prevent XSS
 */
export function sanitizeHtml(html: string): string {
  const div = document.createElement("div")
  div.textContent = html
  return div.innerHTML
}

/**
 * Parse query string to object
 */
export function parseQueryString(queryString: string): Record<string, string> {
  const params = new URLSearchParams(queryString)
  const result: Record<string, string> = {}
  params.forEach((value, key) => {
    result[key] = value
  })
  return result
}

/**
 * Build query string from object
 */
export function buildQueryString(params: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.append(key, String(value))
    }
  })
  const queryString = query.toString()
  return queryString ? `?${queryString}` : ""
}
