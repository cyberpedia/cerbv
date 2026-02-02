/**
 * Cerberus API Client
 * Axios-based HTTP client with interceptors for auth and request signing
 */

import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from "axios"
import { useAuthStore } from "@/hooks/use-auth"
import { generateRequestSignature } from "./utils"
import type { ApiResponse, ApiError, AuthTokens } from "@/types"

// Environment configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"
const REQUEST_SIGNING_ENABLED = process.env.NEXT_PUBLIC_REQUEST_SIGNING === "true"
const REQUEST_SIGNING_SECRET = process.env.NEXT_PUBLIC_REQUEST_SIGNING_KEY || ""

/**
 * Create configured Axios instance
 */
function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
  })

  // Request interceptor - add auth token and request signing
  client.interceptors.request.use(
    async (config: InternalAxiosRequestConfig) => {
      // Add auth token if available
      const tokens = useAuthStore.getState().tokens
      if (tokens?.access_token) {
        config.headers.Authorization = `Bearer ${tokens.access_token}`
      }

      // Add request signing if enabled
      if (REQUEST_SIGNING_ENABLED && REQUEST_SIGNING_SECRET) {
        const timestamp = new Date().toISOString()
        const method = config.method || "GET"
        const path = config.url || "/"
        const body = config.data ? JSON.stringify(config.data) : null

        const signature = await generateRequestSignature(
          method,
          path,
          body,
          timestamp,
          REQUEST_SIGNING_SECRET
        )

        config.headers["X-Cerberus-Sig"] = signature
        config.headers["X-Cerberus-Timestamp"] = timestamp
      }

      return config
    },
    (error) => Promise.reject(error)
  )

  // Response interceptor - handle token refresh and errors
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError<ApiError>) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

      // Handle 401 Unauthorized - attempt token refresh
      if (error.response?.status === 401 && !originalRequest._retry) {
        originalRequest._retry = true

        try {
          const tokens = useAuthStore.getState().tokens
          if (!tokens?.refresh_token) {
            throw new Error("No refresh token available")
          }

          // Attempt to refresh token
          const refreshResponse = await axios.post<ApiResponse<AuthTokens>>(
            `${API_BASE_URL}/auth/refresh`,
            { refresh_token: tokens.refresh_token }
          )

          const newTokens = refreshResponse.data.data
          useAuthStore.getState().setTokens(newTokens)

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${newTokens.access_token}`
          return client(originalRequest)
        } catch (refreshError) {
          // Token refresh failed - logout user
          useAuthStore.getState().logout()
          if (typeof window !== "undefined") {
            window.location.href = "/login"
          }
          return Promise.reject(refreshError)
        }
      }

      // Handle rate limiting
      if (error.response?.status === 429) {
        const retryAfter = error.response.headers["retry-after"]
        console.warn(`Rate limited. Retry after: ${retryAfter} seconds`)
      }

      return Promise.reject(error)
    }
  )

  return client
}

// Global API client instance
export const api = createApiClient()

/**
 * Generic GET request
 */
export async function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<ApiResponse<T>>(url, config)
  return response.data.data
}

/**
 * Generic POST request
 */
export async function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.post<ApiResponse<T>>(url, data, config)
  return response.data.data
}

/**
 * Generic PUT request
 */
export async function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.put<ApiResponse<T>>(url, data, config)
  return response.data.data
}

/**
 * Generic PATCH request
 */
export async function patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.patch<ApiResponse<T>>(url, data, config)
  return response.data.data
}

/**
 * Generic DELETE request
 */
export async function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.delete<ApiResponse<T>>(url, config)
  return response.data.data
}

/**
 * API error handler
 */
export function handleApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiError>
    return (
      axiosError.response?.data || {
        detail: axiosError.message || "An unexpected error occurred",
        code: "UNKNOWN_ERROR",
        field: null,
      }
    )
  }

  return {
    detail: error instanceof Error ? error.message : "An unexpected error occurred",
    code: "UNKNOWN_ERROR",
    field: null,
  }
}

/**
 * Check if error is a network error
 */
export function isNetworkError(error: unknown): boolean {
  return axios.isAxiosError(error) && !error.response
}

/**
 * Check if error is a validation error
 */
export function isValidationError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 422
}
