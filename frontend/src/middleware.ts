/**
 * Next.js Middleware
 * Handles security headers, authentication checks, and request signing
 */

import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { generateCSPNonce, buildCSP } from './lib/security'

// Paths that don't require authentication
const publicPaths = [
  '/',
  '/login',
  '/register',
  '/api/auth/login',
  '/api/auth/register',
  '/api/auth/refresh',
  '/_next',
  '/favicon.ico',
  '/manifest.json',
  '/robots.txt',
]

// Check if path is public
function isPublicPath(pathname: string): boolean {
  return publicPaths.some(path => 
    pathname === path || pathname.startsWith(path + '/')
  )
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl
  
  // Generate CSP nonce
  const nonce = generateCSPNonce()
  
  // Create response
  const response = NextResponse.next()
  
  // Add security headers
  response.headers.set('X-DNS-Prefetch-Control', 'on')
  response.headers.set('Strict-Transport-Security', 'max-age=63072000; includeSubDomains; preload')
  response.headers.set('X-XSS-Protection', '1; mode=block')
  response.headers.set('X-Frame-Options', 'SAMEORIGIN')
  response.headers.set('X-Content-Type-Options', 'nosniff')
  response.headers.set('Referrer-Policy', 'origin-when-cross-origin')
  response.headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
  
  // Add CSP header with nonce
  const csp = buildCSP(nonce)
  response.headers.set('Content-Security-Policy', csp)
  
  // Add nonce to response for use in components
  response.headers.set('X-CSP-Nonce', nonce)
  
  // Check authentication for protected routes
  if (!isPublicPath(pathname)) {
    const token = request.cookies.get('auth-token')?.value
    
    if (!token) {
      // Redirect to login if no token
      const loginUrl = new URL('/login', request.url)
      loginUrl.searchParams.set('redirect', pathname)
      return NextResponse.redirect(loginUrl)
    }
  }
  
  return response
}

// Configure middleware to run on specific paths
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    '/((?!_next/static|_next/image|favicon.ico|public).*)',
  ],
}
