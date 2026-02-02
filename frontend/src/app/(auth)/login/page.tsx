"use client"

/**
 * Login Page - Cerberus CTF Platform
 * React Hook Form + Zod validation
 * Technical Brutalism design with Safety Orange accent
 */

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { Eye, EyeOff, Lock, Shield, User as UserIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { useToast } from "@/hooks/use-toast"
import { useAuthStore } from "@/hooks/use-auth"
import { api, handleApiError } from "@/lib/api"
import { loginSchema, type LoginFormData } from "@/lib/validations/auth"
import type { User, AuthTokens, ApiResponse } from "@/types"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { toast } = useToast()
  const login = useAuthStore((state) => state.login)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const redirectTo = searchParams.get("redirect") || "/challenges"

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: "",
      password: "",
      rememberMe: false,
    },
  })

  const rememberMe = watch("rememberMe")

  async function onSubmit(data: LoginFormData) {
    setIsLoading(true)

    try {
      const response = await api.post<ApiResponse<{
        user: User
        tokens: AuthTokens
      }>>("/auth/login", {
        username: data.username,
        password: data.password,
      })

      const { user, tokens } = response.data.data
      login(user, tokens)

      toast({
        title: "Welcome back!",
        description: `Successfully logged in as ${user.username}`,
        variant: "success",
      })

      router.push(redirectTo)
      router.refresh()
    } catch (error) {
      const apiError = handleApiError(error)
      
      toast({
        title: "Login failed",
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
          Sign in to Cerberus
        </CardTitle>
        <CardDescription className="text-center">
          Enter your credentials to access the CTF platform
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
                placeholder="Enter your username"
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
            <Label htmlFor="password" variant="industrial">
              Password
            </Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                className="pl-10 pr-10"
                variant="industrial"
                state={errors.password ? "error" : "default"}
                errorMessage={errors.password?.message}
                {...register("password")}
                disabled={isLoading}
                autoComplete="current-password"
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
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="rememberMe"
                checked={rememberMe}
                onCheckedChange={(checked) => setValue("rememberMe", checked as boolean)}
                disabled={isLoading}
              />
              <Label
                htmlFor="rememberMe"
                className="text-sm font-normal cursor-pointer"
              >
                Remember me
              </Label>
            </div>
            <Link
              href="/forgot-password"
              className="text-sm text-safety hover:text-safety-600 hover:underline underline-offset-4"
            >
              Forgot password?
            </Link>
          </div>

          <Button
            type="submit"
            className="w-full"
            size="lg"
            loading={isLoading}
            disabled={isLoading}
          >
            Sign in
          </Button>
        </form>
      </CardContent>
      <CardFooter className="flex flex-col space-y-4">
        <div className="relative w-full">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-industrial-200 dark:border-industrial-700" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground">
              Or continue with
            </span>
          </div>
        </div>
        <div className="text-center text-sm">
          Don't have an account?{" "}
          <Link
            href="/register"
            className="font-medium text-safety hover:text-safety-600 hover:underline underline-offset-4"
          >
            Create an account
          </Link>
        </div>
      </CardFooter>
    </Card>
  )
}
