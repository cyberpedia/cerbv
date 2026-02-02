import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { OptionList } from "./OptionList"
import { Code2, Image as ImageIcon, HelpCircle } from "lucide-react"

import type { MCQQuestion } from "@/types"

/**
 * QuestionCard Component
 * 
 * Displays a single MCQ question with Markdown rendering, code syntax highlighting,
 * optional image display, and integrated OptionList for answers.
 * 
 * @example
 * <QuestionCard
 *   question={question}
 *   selectedOptionIds={["opt_1"]}
 *   onSelectionChange={(ids) => setSelected(ids)}
 *   allowMultiple={false}
 *   questionNumber={1}
 * />
 */

interface QuestionCardProps {
  /** The question to display */
  question: MCQQuestion
  /** Currently selected option IDs */
  selectedOptionIds: string[]
  /** Callback when selection changes */
  onSelectionChange: (optionIds: string[]) => void
  /** Whether multiple options can be selected */
  allowMultiple?: boolean
  /** Whether to show result feedback */
  showResults?: boolean
  /** IDs of correct options (for result display) */
  correctOptionIds?: string[]
  /** Question number for display */
  questionNumber: number
  /** Total number of questions */
  totalQuestions: number
  /** Optional code snippet */
  codeSnippet?: string
  /** Optional code language for syntax highlighting */
  codeLanguage?: string
  /** Optional image URL */
  imageUrl?: string
  /** Whether the component is disabled */
  disabled?: boolean
  /** Optional className for styling */
  className?: string
}

// Simple Markdown-like parser for question text
function parseMarkdown(text: string): React.ReactNode {
  // Handle code blocks
  const parts = text.split(/(```[\s\S]*?```|`[^`]+`)/g)
  
  return parts.map((part, index) => {
    // Code block
    if (part.startsWith("```") && part.endsWith("```")) {
      const code = part.slice(3, -3).trim()
      const lines = code.split("\n")
      const language = lines[0] && !lines[0].includes("{") ? lines[0] : ""
      const codeContent = language ? lines.slice(1).join("\n") : code
      
      return (
        <pre
          key={index}
          className="my-4 p-4 rounded-lg bg-industrial-100 dark:bg-industrial-900 font-mono text-sm overflow-x-auto"
        >
          {language && (
            <div className="text-xs text-muted-foreground mb-2 uppercase tracking-wider">
              {language}
            </div>
          )}
          <code>{codeContent}</code>
        </pre>
      )
    }
    
    // Inline code
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={index}
          className="px-1.5 py-0.5 rounded bg-industrial-100 dark:bg-industrial-900 font-mono text-sm"
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    
    // Regular text with bold/italic
    return (
      <span key={index}>
        {part.split(/(\*\*.*?\*\*|\*.*?\*)/g).map((subPart, subIndex) => {
          if (subPart.startsWith("**") && subPart.endsWith("**")) {
            return <strong key={subIndex}>{subPart.slice(2, -2)}</strong>
          }
          if (subPart.startsWith("*") && subPart.endsWith("*")) {
            return <em key={subIndex}>{subPart.slice(1, -1)}</em>
          }
          return subPart
        })}
      </span>
    )
  })
}

export function QuestionCard({
  question,
  selectedOptionIds,
  onSelectionChange,
  allowMultiple = false,
  showResults = false,
  correctOptionIds = [],
  questionNumber,
  totalQuestions,
  codeSnippet,
  codeLanguage = "text",
  imageUrl,
  disabled = false,
  className,
}: QuestionCardProps) {
  const [imageExpanded, setImageExpanded] = React.useState(false)
  const questionRef = React.useRef<HTMLDivElement>(null)

  // Focus management for accessibility
  React.useEffect(() => {
    if (questionRef.current) {
      questionRef.current.focus()
    }
  }, [question.id])

  return (
    <Card
      ref={questionRef}
      className={cn(
        "w-full",
        showResults && "border-l-4",
        showResults && selectedOptionIds.some(id => correctOptionIds.includes(id))
          ? "border-l-green-500"
          : showResults && "border-l-red-500",
        className
      )}
      tabIndex={-1}
      aria-labelledby={`question-${question.id}-label`}
    >
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-3">
              <Badge variant="secondary" className="text-xs">
                Question {questionNumber} of {totalQuestions}
              </Badge>
              {allowMultiple && (
                <Badge variant="outline" className="text-xs">
                  Multiple Select
                </Badge>
              )}
              <Badge variant="outline" className="text-xs">
                {question.points} pts
              </Badge>
            </div>
            <CardTitle
              id={`question-${question.id}-label`}
              className="text-lg font-medium leading-relaxed"
            >
              {parseMarkdown(question.question)}
            </CardTitle>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Code Snippet */}
        {codeSnippet && (
          <div className="relative">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Code2 className="h-4 w-4" />
              <span className="uppercase tracking-wider text-xs">{codeLanguage}</span>
            </div>
            <pre className="p-4 rounded-lg bg-industrial-100 dark:bg-industrial-900 font-mono text-sm overflow-x-auto">
              <code>{codeSnippet}</code>
            </pre>
          </div>
        )}

        {/* Question Image */}
        {imageUrl && (
          <div className="relative">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <ImageIcon className="h-4 w-4" />
              <span>Reference Image</span>
            </div>
            <div
              className={cn(
                "relative overflow-hidden rounded-lg border border-border cursor-pointer transition-all duration-200",
                imageExpanded ? "fixed inset-4 z-50 bg-background/95 flex items-center justify-center" : ""
              )}
              onClick={() => setImageExpanded(!imageExpanded)}
              role="button"
              aria-label={imageExpanded ? "Close image" : "Expand image"}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault()
                  setImageExpanded(!imageExpanded)
                }
              }}
            >
              <img
                src={imageUrl}
                alt="Question reference"
                className={cn(
                  "object-contain",
                  imageExpanded ? "max-w-full max-h-full" : "w-full h-auto max-h-64"
                )}
              />
              {!imageExpanded && (
                <div className="absolute inset-0 bg-black/0 hover:bg-black/10 transition-colors flex items-center justify-center">
                  <span className="sr-only">Click to expand</span>
                </div>
              )}
            </div>
            {imageExpanded && (
              <button
                className="fixed top-6 right-6 z-50 p-2 bg-background border rounded-full shadow-lg hover:bg-muted transition-colors"
                onClick={(e) => {
                  e.stopPropagation()
                  setImageExpanded(false)
                }}
                aria-label="Close expanded image"
              >
                <span className="sr-only">Close</span>
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        )}

        {/* Options */}
        <div className="pt-2">
          <div className="flex items-center gap-2 mb-4">
            <HelpCircle className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">
              {allowMultiple ? "Select all correct answers" : "Select one answer"}
            </span>
          </div>
          <OptionList
            questionId={question.id}
            options={question.options}
            selectedOptionIds={selectedOptionIds}
            onSelectionChange={onSelectionChange}
            allowMultiple={allowMultiple}
            showResults={showResults}
            correctOptionIds={correctOptionIds}
            disabled={disabled}
          />
        </div>
      </CardContent>
    </Card>
  )
}

export default QuestionCard
