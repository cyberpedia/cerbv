"use client"

/**
 * Register Page - Cerberus CTF Platform
 * React Hook Form + Zod validation
 * Technical Brutalism design with Safety Orange accent
 */

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Eye, EyeOff, Lock, Mail, Shield, User as UserIcon, Check, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { useAuthStore } from "@/hooks/use-auth"
import { api, handleApiError } from "@/lib/api"
import { registerSchema, type RegisterFormData } from "@/lib/validations/auth"
import type { User, AuthTokens, ApiResponse } from "@/types"
import { cn } from "@/lib/utils"

export default function RegisterPage() {
  const router = useRouter()
  const { toast } = useToast()
  const login = useAuthStore((state) => state.login)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      passwordConfirm: "",
      acceptTerms: false,
    },
  })

  const password = watch("password")
  const acceptTerms = watch("acceptTerms")

  // Password strength indicators
  const passwordChecks = {
    length: password.length >= 12,
    uppercase: /[A-Z]/.test(password),
    lowercase: /[a-z]/.test(password),
    number: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  }

  const passwordStrength = Object.values(passwordChecks).filter(Boolean).length

  async function onSubmit(data: RegisterFormData) {
    setIsLoading(true)

    try {
      const response = await api.post<ApiResponse<{
        user: User
        tokens: AuthTokens
      }>>("/auth/register", {
        username: data.username,
        email: data.email,
        password: data.password,
        password_confirm: data.passwordConfirm,
      })

      const { user, tokens } = response.data.data
      login(user, tokens)

      toast({
        title: "Account created!",
        description: `Welcome to Cerberus, ${user.username}!`,
        variant: "success",
      })

      router.push("/challenges")
      router.refresh()
    } catch (error) {
      const apiError = handleApiError(error)
      
      toast({
        title: "Registration failed",
        description: apiError.detail,
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className="border-2 border-industrial-200 dark:border-industrial-700">
      <CardHeader className="space-y-1">
        <div className="flex items-center justify-center mb-4">
          <div className="p-3 rounded-full bg-safety/10">
            <Shield className="h-8 w-8 text-safety" />
          </div>
        </div>
        <CardTitle className="text-2xl text-center font-bold tracking-tight">
          Create an account
        </CardTitle>
        <CardDescription className="text-center">
          Join Cerberus CTF and start your security journey
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username" variant="industrial">
              Username
            </Label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="username"
                placeholder="Choose a username"
                className="pl-10"
                variant="industrial"
                state={errors.username ? "error" : "default"}
                errorMessage={errors.username?.message}
                {...register("username")}
                disabled={isLoading}
                autoComplete="username"
                autoFocus
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="email" variant="industrial">
              Email
            </Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                placeholder="Enter your email"
                className="pl-10"
                variant="industrial"
                state={errors.email ? "error" : "default"}
                errorMessage={errors.email?.message}
                {...register("email")}
                disabled={isLoading}
                autoComplete="email"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="password" variant="industrial">
              Password
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Create a password"
                className="pl-10 pr-10"
                variant="industrial"
                state={errors.password ? "error" : "default"}
                errorMessage={errors.password?.message}
                {...register("password")}
                disabled={isLoading}
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            
            {/* Password strength indicator */}
            {password.length > 0 && (
              <div className="mt-2 space-y-2">
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((level) => (
                    <div
                      key={level}
                      className={cn(
                        "h-1 flex-1 rounded-full transition-colors",
                        passwordStrength >= level
                          ? level <= 2
                            ? "bg-red-500"
                            : level <= 3
                            ? "bg-yellow-500"
                            : level <= 4
                            ? "bg-green-500"
                            : "bg-safety"
                          : "bg-industrial-200 dark:bg-industrial-700"
                      )}
                    />
                  ))}
                </div>
                <ul className="space-y-1 text-xs">
                  <PasswordRequirement met={passwordChecks.length}>
                    At least 12 characters
                  </PasswordRequirement>
                  <PasswordRequirement met={passwordChecks.uppercase}>
                    One uppercase letter
                  </PasswordRequirement>
                  <PasswordRequirement met={passwordChecks.lowercase}>
                    One lowercase letter
                  </PasswordRequirement>
                  <PasswordRequirement met={passwordChecks.number}>
                    One number
                  </PasswordRequirement>
                  <PasswordRequirement met={passwordChecks.special}>
                    One special character
                  </PasswordRequirement>
                </ul>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="passwordConfirm" variant="industrial">
              Confirm Password
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="passwordConfirm"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="Confirm your password"
                className="pl-10 pr-10"
                variant="industrial"
                state={errors.passwordConfirm ? "error" : "default"}
                errorMessage={errors.passwordConfirm?.message}
                {...register("passwordConfirm")}
                disabled={isLoading}
                autoComplete="new-password"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                aria-label={showConfirmPassword ? "Hide password" : "Show password"}
              >
                {showConfirmPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
          </div>

          <div className="flex items-start space-x-2">
            <Checkbox
              id="acceptTerms"
              checked={acceptTerms}
              onCheckedChange={(checked) => setValue("acceptTerms", checked as boolean)}
              disabled={isLoading}
              className="mt-1"
            />
            <div className="grid gap-1.5 leading-none">
              <Label
                htmlFor="acceptTerms"
                className="text-sm font-normal cursor-pointer"
              >
                I accept the{" "}
                <Link
                  href="/terms"
                  className="text-safety hover:text-safety-600 hover:underline underline-offset-4"
                >
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link
                  href="/privacy"
                  className="text-safety hover:text-safety-600 hover:underline underline-offset-4"
                >
                  Privacy Policy
                </Link>
              </Label>
              {errors.acceptTerms && (
                <p className="text-xs text-destructive" role="alert">
                  {errors.acceptTerms.message}
                </p>
              )}
            </div>
          </div>

          <Button
            type="submit"
            className="w-full"
            size="lg"
            loading={isLoading}
            disabled={isLoading}
          >
            Create account
          </Button>
        </form>
      </CardContent>
      <CardFooter>
        <div className="text-center text-sm w-full">
          Already have an account?{" "}
          <Link
            href="/login"
            className="font-medium text-safety hover:text-safety-600 hover:underline underline-offset-4"
          >
            Sign in
          </Link>
        </div>
      </CardFooter>
    </Card>
  )
}

interface PasswordRequirementProps {
  met: boolean
  children: React.ReactNode
}

function PasswordRequirement({ met, children }: PasswordRequirementProps) {
  return (
    <li className={cn("flex items-center gap-1.5", met ? "text-green-600 dark:text-green-400" : "text-muted-foreground")}>
      {met ? (
        <Check className="h-3 w-3" />
      ) : (
        <X className="h-3 w-3" />
      )}
      {children}
    </li>
  )
}
