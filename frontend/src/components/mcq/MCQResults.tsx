import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { 
  CheckCircle2, 
  XCircle, 
  Trophy, 
  Clock, 
  Target, 
  RotateCcw,
  ChevronRight,
  AlertCircle
} from "lucide-react"

import type { MCQQuestion, MCQResult } from "@/types"

/**
 * MCQResults Component
 * 
 * Displays post-submission review with score breakdown, correct/incorrect answers,
 * and explanations. Includes options to retry or view detailed analysis.
 * 
 * @example
 * <MCQResults
 *   questions={questions}
 *   userAnswers={answers}
 *   results={results}
 *   timeTaken={300}
 *   onRetry={() => resetQuiz()}
 *   onClose={() => router.push('/challenges')}
 * />
 */

interface QuestionResult {
  question: MCQQuestion
  selectedOptionIds: string[]
  result?: MCQResult
}

interface MCQResultsProps {
  /** Array of questions with user answers */
  questions: QuestionResult[]
  /** Total points possible */
  totalPoints: number
  /** Points earned */
  earnedPoints: number
  /** Time taken in seconds */
  timeTaken: number
  /** Whether the challenge was passed */
  passed: boolean
  /** Passing threshold percentage */
  passingThreshold?: number
  /** Callback to retry the quiz */
  onRetry?: () => void
  /** Callback to close results */
  onClose?: () => void
  /** Callback to view detailed explanation */
  onViewExplanation?: (questionIndex: number) => void
  /** Optional className for styling */
  className?: string
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

export function MCQResults({
  questions,
  totalPoints,
  earnedPoints,
  timeTaken,
  passed,
  passingThreshold = 70,
  onRetry,
  onClose,
  onViewExplanation,
  className,
}: MCQResultsProps) {
  const [expandedQuestion, setExpandedQuestion] = React.useState<number | null>(null)
  
  const correctCount = questions.filter(q => q.result?.correct).length
  const incorrectCount = questions.length - correctCount
  const percentage = Math.round((earnedPoints / totalPoints) * 100)
  
  // Calculate statistics
  const accuracy = Math.round((correctCount / questions.length) * 100)
  const avgTimePerQuestion = Math.round(timeTaken / questions.length)

  return (
    <div className={cn("space-y-6", className)}>
      {/* Score Summary Card */}
      <Card className={cn(
        "border-l-4",
        passed ? "border-l-green-500" : "border-l-red-500"
      )}>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-2xl flex items-center gap-2">
                {passed ? (
                  <>
                    <Trophy className="h-6 w-6 text-yellow-500" />
                    Challenge Complete!
                  </>
                ) : (
                  <>
                    <AlertCircle className="h-6 w-6 text-red-500" />
                    Challenge Failed
                  </>
                )}
              </CardTitle>
              <CardDescription className="mt-2">
                {passed 
                  ? "Congratulations! You passed the challenge." 
                  : `You need ${passingThreshold}% to pass. Try again!`
                }
              </CardDescription>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold">
                {percentage}%
              </div>
              <div className="text-sm text-muted-foreground">
                {earnedPoints} / {totalPoints} points
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-sm mb-2">
              <span>Score</span>
              <span className={passed ? "text-green-600" : "text-red-600"}>
                {passed ? "Passed" : "Failed"}
              </span>
            </div>
            <Progress 
              value={percentage} 
              className="h-3"
            />
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>0%</span>
              <span>Pass: {passingThreshold}%</span>
              <span>100%</span>
            </div>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              icon={<Target className="h-4 w-4" />}
              label="Accuracy"
              value={`${accuracy}%`}
              description={`${correctCount}/${questions.length} correct`}
            />
            <StatCard
              icon={<Clock className="h-4 w-4" />}
              label="Time Taken"
              value={formatDuration(timeTaken)}
              description={`${avgTimePerQuestion}s per question`}
            />
            <StatCard
              icon={<CheckCircle2 className="h-4 w-4 text-green-500" />}
              label="Correct"
              value={correctCount.toString()}
              description="Questions"
            />
            <StatCard
              icon={<XCircle className="h-4 w-4 text-red-500" />}
              label="Incorrect"
              value={incorrectCount.toString()}
              description="Questions"
            />
          </div>
        </CardContent>
      </Card>

      {/* Question Breakdown */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Question Breakdown</h3>
        {questions.map((item, index) => {
          const isCorrect = item.result?.correct ?? false
          const isExpanded = expandedQuestion === index
          
          return (
            <Card 
              key={item.question.id}
              className={cn(
                "border-l-4 transition-all duration-200",
                isCorrect ? "border-l-green-500" : "border-l-red-500",
                isExpanded && "ring-2 ring-ring"
              )}
            >
              <div 
                className="p-4 cursor-pointer"
                onClick={() => setExpandedQuestion(isExpanded ? null : index)}
                role="button"
                aria-expanded={isExpanded}
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault()
                    setExpandedQuestion(isExpanded ? null : index)
                  }
                }}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge variant="outline">Q{index + 1}</Badge>
                      {isCorrect ? (
                        <Badge variant="success" className="gap-1">
                          <CheckCircle2 className="h-3 w-3" />
                          Correct
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="gap-1">
                          <XCircle className="h-3 w-3" />
                          Incorrect
                        </Badge>
                      )}
                      <span className="text-sm text-muted-foreground">
                        {item.result?.points_awarded ?? 0} / {item.question.points} pts
                      </span>
                    </div>
                    <p className="font-medium">{item.question.question}</p>
                  </div>
                  <ChevronRight 
                    className={cn(
                      "h-5 w-5 text-muted-foreground transition-transform",
                      isExpanded && "rotate-90"
                    )} 
                  />
                </div>
              </div>
              
              {isExpanded && (
                <CardContent className="pt-0 pb-4 border-t">
                  <div className="pt-4 space-y-4">
                    {/* Show user's answer vs correct answer */}
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-muted-foreground">Your Answer:</p>
                      <div className="space-y-1">
                        {item.selectedOptionIds.length > 0 ? (
                          item.selectedOptionIds.map(id => {
                            const option = item.question.options.find(o => o.id === id)
                            return option ? (
                              <div 
                                key={id}
                                className={cn(
                                  "p-2 rounded text-sm",
                                  item.result?.correct_option_id === id
                                    ? "bg-green-100 text-green-800 dark:bg-green-900/30"
                                    : "bg-red-100 text-red-800 dark:bg-red-900/30"
                                )}
                              >
                                {option.text}
                              </div>
                            ) : null
                          })
                        ) : (
                          <p className="text-sm text-muted-foreground italic">No answer selected</p>
                        )}
                      </div>
                    </div>
                    
                    {!isCorrect && item.result?.correct_option_id && (
                      <div className="space-y-2">
                        <p className="text-sm font-medium text-muted-foreground">Correct Answer:</p>
                        {item.question.options
                          .filter(o => o.id === item.result?.correct_option_id)
                          .map(option => (
                            <div 
                              key={option.id}
                              className="p-2 rounded text-sm bg-green-100 text-green-800 dark:bg-green-900/30"
                            >
                              {option.text}
                            </div>
                          ))
                        }
                      </div>
                    )}

                    {onViewExplanation && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onViewExplanation(index)}
                      >
                        View Explanation
                      </Button>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 justify-center pt-4">
        {!passed && onRetry && (
          <Button 
            onClick={onRetry}
            variant="outline"
            className="gap-2"
          >
            <RotateCcw className="h-4 w-4" />
            Try Again
          </Button>
        )}
        {onClose && (
          <Button onClick={onClose}>
            Back to Challenges
          </Button>
        )}
      </div>
    </div>
  )
}

// Helper component for stat cards
interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
  description: string
}

function StatCard({ icon, label, value, description }: StatCardProps) {
  return (
    <div className="p-4 rounded-lg border bg-card">
      <div className="flex items-center gap-2 text-muted-foreground mb-1">
        {icon}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-muted-foreground">{description}</div>
    </div>
  )
}

export default MCQResults
