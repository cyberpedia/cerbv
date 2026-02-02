"use client"

/**
 * Challenge Detail Page - Cerberus CTF Platform
 * Challenge details with flag submission and hints
 * Technical Brutalism design with Safety Orange accent
 */

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Trophy,
  Users,
  Clock,
  Lock,
  CheckCircle2,
  Download,
  Lightbulb,
  ArrowLeft,
  Flag,
  Send,
  FileText,
  AlertTriangle,
  Unlock,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/hooks/use-toast"
import { api, handleApiError } from "@/lib/api"
import { cn, formatDate, formatRelativeTime } from "@/lib/utils"
import type { ChallengeDetail, SubmissionResponse, Hint, Attachment } from "@/types"

const difficultyColors = {
  easy: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100",
  hard: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100",
  extreme: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100",
}

export default function ChallengeDetailPage() {
  const params = useParams()
  const router = useRouter()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const challengeId = params.id as string
  const [flag, setFlag] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { data: challenge, isLoading, error } = useQuery({
    queryKey: ["challenge", challengeId],
    queryFn: async () => {
      return await api.get<ChallengeDetail>(`/challenges/${challengeId}`)
    },
  })

  const submitMutation = useMutation({
    mutationFn: async (flagValue: string) => {
      const response = await api.post<SubmissionResponse>(`/challenges/${challengeId}/submit`, {
        flag: flagValue,
      })
      return response.data
    },
    onSuccess: (data) => {
      if (data.correct) {
        toast({
          title: "Correct!",
          description: data.message,
          variant: "success",
        })
        queryClient.invalidateQueries({ queryKey: ["challenge", challengeId] })
        queryClient.invalidateQueries({ queryKey: ["challenges"] })
      } else {
        toast({
          title: "Incorrect",
          description: data.message,
          variant: "destructive",
        })
      }
    },
    onError: (error) => {
      const apiError = handleApiError(error)
      toast({
        title: "Submission failed",
        description: apiError.detail,
        variant: "destructive",
      })
    },
  })

  const unlockHintMutation = useMutation({
    mutationFn: async (hintId: string) => {
      return await api.post<Hint>(`/hints/${hintId}/unlock`, {})
    },
    onSuccess: () => {
      toast({
        title: "Hint unlocked",
        description: "The hint has been unlocked for you",
        variant: "success",
      })
      queryClient.invalidateQueries({ queryKey: ["challenge", challengeId] })
    },
    onError: (error) => {
      const apiError = handleApiError(error)
      toast({
        title: "Failed to unlock hint",
        description: apiError.detail,
        variant: "destructive",
      })
    },
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!flag.trim()) return
    
    setIsSubmitting(true)
    await submitMutation.mutateAsync(flag.trim())
    setIsSubmitting(false)
    if (submitMutation.data?.correct) {
      setFlag("")
    }
  }

  if (isLoading) {
    return <ChallengeSkeleton />
  }

  if (error || !challenge) {
    return (
      <div className="container mx-auto py-8 px-4">
        <div className="text-center py-16">
          <AlertTriangle className="h-12 w-12 mx-auto text-destructive mb-4" />
          <h2 className="text-xl font-semibold">Failed to load challenge</h2>
          <p className="text-muted-foreground mt-2">
            {error ? handleApiError(error).detail : "Challenge not found"}
          </p>
          <Button className="mt-4" onClick={() => router.push("/challenges")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Challenges
          </Button>
        </div>
      </div>
    )
  }

  const challengeData = challenge as unknown as ChallengeDetail

  return (
    <div className="container mx-auto py-8 px-4 md:px-6">
      {/* Back Button */}
      <Button
        variant="ghost"
        className="mb-4"
        onClick={() => router.push("/challenges")}
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        Back to Challenges
      </Button>

      {/* Header */}
      <div className="mb-8">
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold tracking-tight">{challengeData.title}</h1>
              {challengeData.is_solved && (
                <Badge className="bg-green-500 text-white">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Solved
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={cn(difficultyColors[challengeData.difficulty], "capitalize")}>
                {challengeData.difficulty}
              </Badge>
              <Badge variant="outline" className="capitalize">
                {challengeData.category}
              </Badge>
              {challengeData.tags.map((tag: string) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-muted px-4 py-2 rounded-lg">
              <Trophy className="h-5 w-5 text-safety" />
              <div>
                <p className="text-xs text-muted-foreground">Points</p>
                <p className="font-bold">{challengeData.points}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 bg-muted px-4 py-2 rounded-lg">
              <Users className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Solves</p>
                <p className="font-bold">{challengeData.solve_count}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="prose dark:prose-invert max-w-none">
                <p className="whitespace-pre-wrap">{challengeData.description}</p>
              </div>
            </CardContent>
          </Card>

          {/* Attachments */}
          {challengeData.attachments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Attachments</CardTitle>
                <CardDescription>Download files to help solve this challenge</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {challengeData.attachments.map((attachment: Attachment) => (
                    <a
                      key={attachment.id}
                      href={attachment.download_url}
                      download
                      className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted transition-colors"
                    >
                      <FileText className="h-5 w-5 text-safety" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{attachment.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {(attachment.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <Download className="h-4 w-4 text-muted-foreground" />
                    </a>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Hints */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lightbulb className="h-5 w-5" />
                Hints
              </CardTitle>
              <CardDescription>Unlock hints to get help solving this challenge</CardDescription>
            </CardHeader>
            <CardContent>
              {challengeData.hints.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">No hints available for this challenge</p>
              ) : (
                <Accordion type="single" collapsible className="w-full">
                  {challengeData.hints.map((hint: Hint, index: number) => (
                    <AccordionItem key={hint.id} value={hint.id}>
                      <AccordionTrigger className="hover:no-underline">
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-medium">Hint {index + 1}</span>
                          {hint.is_unlocked ? (
                            <Badge variant="outline" className="text-xs">
                              <Unlock className="h-3 w-3 mr-1" />
                              Unlocked
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-xs">
                              <Lock className="h-3 w-3 mr-1" />
                              {hint.cost} points
                            </Badge>
                          )}
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        {hint.is_unlocked ? (
                          <p className="text-muted-foreground">{hint.content}</p>
                        ) : (
                          <div className="flex items-center justify-between">
                            <p className="text-sm text-muted-foreground">
                              Unlock this hint for {hint.cost} points
                            </p>
                            <Button
                              size="sm"
                              onClick={() => unlockHintMutation.mutate(hint.id)}
                              disabled={unlockHintMutation.isPending}
                            >
                              <Unlock className="h-4 w-4 mr-2" />
                              Unlock
                            </Button>
                          </div>
                        )}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Flag Submission */}
          <Card className={cn(
            "border-2",
            challengeData.is_solved ? "border-green-500" : "border-safety"
          )}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Flag className="h-5 w-5" />
                Submit Flag
              </CardTitle>
            </CardHeader>
            <CardContent>
              {challengeData.is_solved ? (
                <div className="text-center py-4">
                  <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-2" />
                  <p className="font-semibold text-green-600 dark:text-green-400">Challenge Solved!</p>
                  <p className="text-sm text-muted-foreground">You have already solved this challenge</p>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="flag">Flag</Label>
                    <Input
                      id="flag"
                      placeholder="CTF{...}"
                      value={flag}
                      onChange={(e) => setFlag(e.target.value)}
                      disabled={isSubmitting}
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full"
                    disabled={isSubmitting || !flag.trim()}
                  >
                    <Send className="h-4 w-4 mr-2" />
                    Submit
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          {/* Author Info */}
          {challengeData.author && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Author</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-safety/10 flex items-center justify-center">
                    <span className="font-bold text-safety">
                      {challengeData.author.username.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium">{challengeData.author.username}</p>
                    <p className="text-xs text-muted-foreground capitalize">{challengeData.author.role}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Challenge Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Created</span>
                <span>{formatRelativeTime(challengeData.created_at)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Updated</span>
                <span>{formatRelativeTime(challengeData.updated_at)}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function ChallengeSkeleton() {
  return (
    <div className="container mx-auto py-8 px-4 md:px-6">
      <Skeleton className="h-10 w-32 mb-4" />
      <div className="mb-8">
        <Skeleton className="h-10 w-64 mb-2" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-16" />
          <Skeleton className="h-6 w-20" />
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Skeleton className="h-40" />
          <Skeleton className="h-32" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-48" />
          <Skeleton className="h-32" />
        </div>
      </div>
    </div>
  )
}
