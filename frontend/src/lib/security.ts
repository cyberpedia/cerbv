/**
 * Security Utilities
 * CSP nonce generation, debugger detection, and encryption helpers
 */

/**
 * Generate a cryptographically secure nonce for CSP
 * Returns a base64-encoded random string
 */
export function generateCSPNonce(): string {
  const array = new Uint8Array(16)
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(array)
  } else {
    // Fallback for environments without crypto
    for (let i = 0; i < array.length; i++) {
      array[i] = Math.floor(Math.random() * 256)
    }
  }
  return btoa(String.fromCharCode(...Array.from(array)))
}

/**
 * Generate a nonce for inline scripts
 * This should be used server-side and passed to the client
 */
export function generateScriptNonce(): string {
  return generateCSPNonce()
}

/**
 * Debugger detection - detects if DevTools is open
 * Uses timing-based detection (may have false positives)
 */
export function detectDebugger(): boolean {
  if (typeof window === 'undefined') return false
  
  const threshold = 100
  const start = performance.now()
  debugger // eslint-disable-line no-debugger
  const end = performance.now()
  
  return end - start > threshold
}

/**
 * Add debugger detection listener
 * Calls callback when debugger is detected
 */
export function onDebuggerDetected(callback: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  
  let isRunning = true
  
  const check = () => {
    if (!isRunning) return
    
    if (detectDebugger()) {
      callback()
    }
    
    // Check periodically
    setTimeout(check, 1000)
  }
  
  check()
  
  // Return cleanup function
  return () => {
    isRunning = false
  }
}

/**
 * Encrypt data using AES-GCM
 * Used for client-side flag encryption before submission
 */
export async function encryptData(
  data: string,
  key: CryptoKey
): Promise<{ ciphertext: string; iv: string; tag: string }> {
  const encoder = new TextEncoder()
  const encoded = encoder.encode(data)
  
  // Generate random IV
  const iv = crypto.getRandomValues(new Uint8Array(12))
  
  // Encrypt
  const encrypted = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    encoded
  )
  
  // Extract ciphertext and authentication tag
  const encryptedArray = new Uint8Array(encrypted)
  const tag = encryptedArray.slice(-16)
  const ciphertext = encryptedArray.slice(0, -16)
  
  return {
    ciphertext: btoa(String.fromCharCode(...ciphertext)),
    iv: btoa(String.fromCharCode(...iv)),
    tag: btoa(String.fromCharCode(...tag)),
  }
}

/**
 * Decrypt data using AES-GCM
 */
export async function decryptData(
  ciphertext: string,
  iv: string,
  tag: string,
  key: CryptoKey
): Promise<string> {
  const decoder = new TextDecoder()
  
  // Decode base64
  const ciphertextBytes = Uint8Array.from(atob(ciphertext), c => c.charCodeAt(0))
  const ivBytes = Uint8Array.from(atob(iv), c => c.charCodeAt(0))
  const tagBytes = Uint8Array.from(atob(tag), c => c.charCodeAt(0))
  
  // Combine ciphertext and tag
  const encrypted = new Uint8Array(ciphertextBytes.length + tagBytes.length)
  encrypted.set(ciphertextBytes)
  encrypted.set(tagBytes, ciphertextBytes.length)
  
  // Decrypt
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: ivBytes },
    key,
    encrypted
  )
  
  return decoder.decode(decrypted)
}

/**
 * Generate AES-GCM key for encryption
 */
export async function generateEncryptionKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    true,
    ['encrypt', 'decrypt']
  )
}

/**
 * Import key from raw bytes
 */
export async function importKey(rawKey: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    'raw',
    rawKey,
    { name: 'AES-GCM' },
    false,
    ['encrypt', 'decrypt']
  )
}

/**
 * Sanitize user input to prevent XSS
 * Basic HTML entity encoding
 */
export function sanitizeInput(input: string): string {
  const div = document.createElement('div')
  div.textContent = input
  return div.innerHTML
}

/**
 * Build Content Security Policy header value
 */
export function buildCSP(nonce: string): string {
  const policies = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'self'",
    "object-src 'none'",
    "frame-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ]
  
  return policies.join('; ')
}

/**
 * Check if running in a secure context (HTTPS or localhost)
 */
export function isSecureContext(): boolean {
  if (typeof window === 'undefined') return true
  return window.isSecureContext
}

/**
 * Rate limiter for client-side actions
 * Simple in-memory rate limiting
 */
export class RateLimiter {
  private attempts: Map<string, number[]> = new Map()
  private maxAttempts: number
  private windowMs: number

  constructor(maxAttempts = 5, windowMs = 60000) {
    this.maxAttempts = maxAttempts
    this.windowMs = windowMs
  }

  canProceed(key: string): boolean {
    const now = Date.now()
    const attempts = this.attempts.get(key) || []
    
    // Remove old attempts outside the window
    const validAttempts = attempts.filter(time => now - time < this.windowMs)
    
    return validAttempts.length < this.maxAttempts
  }

  recordAttempt(key: string): void {
    const now = Date.now()
    const attempts = this.attempts.get(key) || []
    attempts.push(now)
    this.attempts.set(key, attempts)
  }

  getRemainingTime(key: string): number {
    const now = Date.now()
    const attempts = this.attempts.get(key) || []
    
    if (attempts.length === 0) return 0
    
    const oldestAttempt = Math.min(...attempts)
    const remaining = this.windowMs - (now - oldestAttempt)
    
    return Math.max(0, remaining)
  }
}

// Global rate limiter instance
export const globalRateLimiter = new RateLimiter()
