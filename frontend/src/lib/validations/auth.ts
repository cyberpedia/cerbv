import { z } from "zod"

/**
 * Authentication form validation schemas
 * Used with React Hook Form + Zod
 */

export const loginSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(32, "Username must be at most 32 characters")
    .regex(/^[a-zA-Z0-9_-]+$/, "Username can only contain letters, numbers, underscores, and hyphens"),
  password: z
    .string()
    .min(1, "Password is required"),
  rememberMe: z.boolean().optional(),
})

export type LoginFormData = z.infer<typeof loginSchema>

export const registerSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(32, "Username must be at most 32 characters")
    .regex(/^[a-zA-Z0-9_-]+$/, "Username can only contain letters, numbers, underscores, and hyphens"),
  email: z
    .string()
    .min(1, "Email is required")
    .email("Please enter a valid email address"),
  password: z
    .string()
    .min(12, "Password must be at least 12 characters")
    .max(128, "Password must be at most 128 characters")
    .regex(/[A-Z]/, "Password must contain at least one uppercase letter")
    .regex(/[a-z]/, "Password must contain at least one lowercase letter")
    .regex(/[0-9]/, "Password must contain at least one number")
    .regex(/[^A-Za-z0-9]/, "Password must contain at least one special character"),
  passwordConfirm: z.string().min(1, "Please confirm your password"),
  acceptTerms: z.boolean().refine((val) => val === true, {
    message: "You must accept the terms of service",
  }),
}).refine((data) => data.password === data.passwordConfirm, {
  message: "Passwords do not match",
  path: ["passwordConfirm"],
})

export type RegisterFormData = z.infer<typeof registerSchema>
