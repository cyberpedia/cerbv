"use client"

import * as React from "react"
import { useRouter } from "next/navigation"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ProgressBar } from "./ProgressBar"
import { QuestionCard } from "./QuestionCard"
import { MCQResults } from "./MCQResults"
import { get, post } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { 
  Clock, 
  X, 
  ChevronLeft, 
  ChevronRight, 
  AlertTriangle,
  Send,
  Loader2
} from "lucide-react"

import type { MCQQuestion, MCQResult } from "@/types"

/**
 * MCQChallenge Component
 * 
 * Main challenge container that manages the MCQ quiz flow including:
 * - Timer countdown with auto-submit
 * - Question navigation
 * - Answer state management
 * - Submission handling
 * - Results display
 * 
 * @example
 * <MCQChallenge 
 *   challengeId="challenge-123"
 *   config={{ timeLimit: 600, allowMultiple: false }}
 *   onClose={() => router.push('/challenges')}
 * />
 */

interface MCQChallengeConfig {
  /** Time limit in seconds (0 for no limit) */
  timeLimit: number
  /** Whether multiple answers per question are allowed */
  allowMultiple: boolean
  /** Passing threshold percentage */
  passingThreshold?: number
}

interface MCQChallengeProps {
  /** Challenge ID */
  challengeId: string
  /** Challenge configuration */
  config: MCQChallengeConfig
  /** Callback when challenge is closed */
  onClose: () => void
  /** Callback when challenge is completed successfully */
  onComplete?: () => void
  /** Optional className for styling */
  className?: string
}

interface QuestionWithAnswers {
  question: MCQQuestion
  selectedOptionIds: string[]
  result?: MCQResult
}

export function MCQChallenge({
  challengeId,
  config,
  onClose,
  onComplete,
  className,
}: MCQChallengeProps) {
  const router = useRouter()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  
  // State
  const [currentQuestionIndex, setCurrentQuestionIndex] = React.useState(0)
  const [answers, setAnswers] = React.useState<Map<string, string[]>>(new Map())
  const [timeRemaining, setTimeRemaining] = React.useState(config.timeLimit)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [showResults, setShowResults] = React.useState(false)
  const [showConfirmDialog, setShowConfirmDialog] = React.useState(false)
  const [showExitDialog, setShowExitDialog] = React.useState(false)
  const [results, setResults] = React.useState<{
    questions: QuestionWithAnswers[]
    totalPoints: number
    earnedPoints: number
    timeTaken: number
    passed: boolean
  } | null>(null)
  
  const startTimeRef = React.useRef<number>(Date.now())
  const timerRef = React.useRef<NodeJS.Timeout | null>(null)

  // Fetch questions
  const { data: questions, isLoading, error } = useQuery({
    queryKey: ["mcq-questions", challengeId],
    queryFn: async () => {
      const response = await get<MCQQuestion[]>(`/challenges/${challengeId}/mcq/questions`)
      return response
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Timer effect
  React.useEffect(() => {
    if (config.timeLimit <= 0 || showResults || !questions) return

    timerRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          // Auto-submit when time runs out
          handleSubmit()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
      }
    }
  }, [config.timeLimit, showResults, questions])

  // Beforeunload warning
  React.useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!showResults && questions && answers.size > 0) {
        e.preventDefault()
        e.returnValue = "You have unsaved changes. Are you sure you want to leave?"
        return e.returnValue
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [showResults, questions, answers])

  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  // Get time color based on remaining time
  const getTimeColor = (): string => {
    if (config.timeLimit === 0) return "text-foreground"
    const percentage = timeRemaining / config.timeLimit
    if (percentage > 0.5) return "text-foreground"
    if (percentage > 0.25) return "text-yellow-500"
    return "text-red-500 animate-pulse"
  }

  // Handle answer selection
  const handleAnswerChange = (questionId: string, optionIds: string[]) => {
    setAnswers((prev) => {
      const newAnswers = new Map(prev)
      newAnswers.set(questionId, optionIds)
      return newAnswers
    })
  }

  // Navigation handlers
  const handlePrevious = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex((prev) => prev - 1)
    }
  }

  const handleNext = () => {
    if (questions && currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex((prev) => prev + 1)
    }
  }

  const handleQuestionClick = (index: number) => {
    setCurrentQuestionIndex(index)
  }

  // Submit handlers
  const handleSubmitClick = () => {
    const unansweredCount = questions?.filter(
      (q) => !answers.has(q.id) || answers.get(q.id)?.length === 0
    ).length ?? 0

    if (unansweredCount > 0) {
      setShowConfirmDialog(true)
    } else {
      handleSubmit()
    }
  }

  const handleSubmit = async () => {
    if (!questions || isSubmitting) return

    setIsSubmitting(true)
    
    try {
      const timeTaken = Math.floor((Date.now() - startTimeRef.current) / 1000)
      
      // Format answers for submission
      const submissionAnswers = Array.from(answers.entries()).flatMap(
        ([questionId, optionIds]) =>
          optionIds.map((optionId) => ({
            question_id: questionId,
            selected_option_id: optionId,
          }))
      )

      const response = await post<{
        results: MCQResult[]
        total_points: number
        earned_points: number
        passed: boolean
      }>(`/challenges/${challengeId}/mcq/submit`, {
        answers: submissionAnswers,
        time_taken: timeTaken,
      })

      // Build results
      const questionsWithResults: QuestionWithAnswers[] = questions.map((q) => ({
        question: q,
        selectedOptionIds: answers.get(q.id) || [],
        result: response.results.find((r) => r.question_id === q.id),
      }))

      setResults({
        questions: questionsWithResults,
        totalPoints: response.total_points,
        earnedPoints: response.earned_points,
        timeTaken,
        passed: response.passed,
      })

      setShowResults(true)
      setShowConfirmDialog(false)

      if (response.passed && onComplete) {
        onComplete()
      }

      // Invalidate queries to refresh challenge status
      queryClient.invalidateQueries({ queryKey: ["challenge", challengeId] })
      queryClient.invalidateQueries({ queryKey: ["challenges"] })

      toast({
        title: response.passed ? "Challenge Completed!" : "Challenge Failed",
        description: `You scored ${response.earned_points}/${response.total_points} points`,
        variant: response.passed ? "default" : "destructive",
      })
    } catch (error) {
      toast({
        title: "Submission Failed",
        description: "Failed to submit your answers. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle retry
  const handleRetry = () => {
    setAnswers(new Map())
    setCurrentQuestionIndex(0)
    setTimeRemaining(config.timeLimit)
    setShowResults(false)
    setResults(null)
    startTimeRef.current = Date.now()
  }

  // Get answered question indices
  const getAnsweredIndices = (): number[] => {
    if (!questions) return []
    return questions
      .map((q, index) => ({ index, hasAnswer: answers.has(q.id) && (answers.get(q.id)?.length ?? 0) > 0 }))
      .filter((item) => item.hasAnswer)
      .map((item) => item.index)
  }

  // Loading state
  if (isLoading) {
    return (
      <Card className={cn("w-full max-w-4xl mx-auto", className)}>
        <CardContent className="p-8 flex flex-col items-center justify-center min-h-[400px]">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Loading questions...</p>
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (error) {
    return (
      <Card className={cn("w-full max-w-4xl mx-auto", className)}>
        <CardContent className="p-8 flex flex-col items-center justify-center min-h-[400px]">
          <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to Load Questions</h3>
          <p className="text-muted-foreground mb-4">Unable to load the challenge questions.</p>
          <Button onClick={onClose}>Go Back</Button>
        </CardContent>
      </Card>
    )
  }

  // Results view
  if (showResults && results) {
    return (
      <div className={cn("w-full max-w-4xl mx-auto", className)}>
        <MCQResults
          questions={results.questions}
          totalPoints={results.totalPoints}
          earnedPoints={results.earnedPoints}
          timeTaken={results.timeTaken}
          passed={results.passed}
          passingThreshold={config.passingThreshold || 70}
          onRetry={handleRetry}
          onClose={onClose}
        />
      </div>
    )
  }

  const currentQuestion = questions?.[currentQuestionIndex]
  const answeredIndices = getAnsweredIndices()

  return (
    <div className={cn("w-full max-w-4xl mx-auto space-y-6", className)}>
      {/* Header */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowExitDialog(true)}
                aria-label="Close challenge"
              >
                <X className="h-5 w-5" />
              </Button>
              <div>
                <h2 className="font-semibold">Challenge Quiz</h2>
                <p className="text-sm text-muted-foreground">
                  {questions?.length ?? 0} questions
                </p>
              </div>
            </div>
            
            {config.timeLimit > 0 && (
              <div 
                className={cn("flex items-center gap-2 font-mono text-lg", getTimeColor())}
                aria-live="polite"
                aria-label={`Time remaining: ${formatTime(timeRemaining)}`}
              >
                <Clock className="h-5 w-5" />
                {formatTime(timeRemaining)}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Progress Bar */}
      {questions && (
        <ProgressBar
          totalQuestions={questions.length}
          currentIndex={currentQuestionIndex}
          answeredQuestions={answeredIndices}
          onQuestionClick={handleQuestionClick}
        />
      )}

      {/* Question Card */}
      {currentQuestion && questions && (
        <QuestionCard
          question={currentQuestion}
          selectedOptionIds={answers.get(currentQuestion.id) || []}
          onSelectionChange={(ids) => handleAnswerChange(currentQuestion.id, ids)}
          allowMultiple={config.allowMultiple}
          questionNumber={currentQuestionIndex + 1}
          totalQuestions={questions.length}
        />
      )}

      {/* Footer Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handlePrevious}
          disabled={currentQuestionIndex === 0}
          className="gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>

        {currentQuestionIndex === (questions?.length ?? 0) - 1 ? (
          <Button
            onClick={handleSubmitClick}
            disabled={isSubmitting}
            className="gap-2"
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            Submit
          </Button>
        ) : (
          <Button
            onClick={handleNext}
            className="gap-2"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Confirm Submit Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              Unanswered Questions
            </DialogTitle>
            <DialogDescription>
              You have {questions?.filter(q => !answers.has(q.id) || answers.get(q.id)?.length === 0).length} unanswered 
              question(s). Are you sure you want to submit?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Continue Quiz
            </Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              Submit Anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Exit Confirm Dialog */}
      <Dialog open={showExitDialog} onOpenChange={setShowExitDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Leave Challenge?</DialogTitle>
            <DialogDescription>
              Your progress will be lost. Are you sure you want to leave?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExitDialog(false)}>
              Stay
            </Button>
            <Button variant="destructive" onClick={onClose}>
              Leave
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default MCQChallenge
