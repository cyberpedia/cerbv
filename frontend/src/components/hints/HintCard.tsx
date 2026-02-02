import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { 
  Lock, 
  Unlock, 
  Clock, 
  AlertCircle, 
  CheckCircle2,
  Loader2,
  ChevronRight,
  Lightbulb
} from "lucide-react"

import type { Hint } from "@/types"

/**
 * HintCard Component
 * 
 * Displays an individual hint with a state machine for:
 * - locked: Grayed out, shows unlock conditions
 * - available: Shows cost and unlock button
 * - unlocking: Loading state
 * - unlocked: Full content visible
 * 
 * Supports progressive mode with chain connectors and timed unlocks.
 * 
 * @example
 * <HintCard
 *   hint={hint}
 *   state="available"
 *   onUnlock={() => unlockHint(hint.id)}
 *   isProgressive={true}
 *   isFirst={false}
 *   isLast={false}
 * />
 */

type HintState = "locked" | "available" | "unlocking" | "unlocked"

type UnlockCondition = 
  | { type: "time"; remainingSeconds: number }
  | { type: "attempts"; required: number; current: number }
  | { type: "previous"; hintTitle: string }
  | { type: "none" }

interface HintCardProps {
  /** The hint data */
  hint: Hint
  /** Current state of the hint */
  state: HintState
  /** Callback to unlock the hint */
  onUnlock?: () => void
  /** Unlock condition details */
  unlockCondition?: UnlockCondition
  /** Whether this is part of a progressive chain */
  isProgressive?: boolean
  /** Whether this is the first hint in chain */
  isFirst?: boolean
  /** Whether this is the last hint in chain */
  isLast?: boolean
  /** Whether the hint is highlighted/focused */
  isHighlighted?: boolean
  /** Optional className for styling */
  className?: string
}

export function HintCard({
  hint,
  state,
  onUnlock,
  unlockCondition = { type: "none" },
  isProgressive = false,
  isFirst = false,
  isLast = false,
  isHighlighted = false,
  className,
}: HintCardProps) {
  const [timeRemaining, setTimeRemaining] = React.useState(
    unlockCondition.type === "time" ? unlockCondition.remainingSeconds : 0
  )

  // Timer for timed unlocks
  React.useEffect(() => {
    if (state !== "locked" || unlockCondition.type !== "time") return

    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [state, unlockCondition])

  // Format time display
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  // Get state-based styles
  const getCardStyles = () => {
    const baseStyles = "relative transition-all duration-300"
    
    switch (state) {
      case "locked":
        return cn(
          baseStyles,
          "opacity-50 grayscale",
          "border-muted bg-muted/50"
        )
      case "available":
        return cn(
          baseStyles,
          "border-dashed border-primary",
          "animate-pulse-subtle",
          isHighlighted && "ring-2 ring-primary ring-offset-2"
        )
      case "unlocking":
        return cn(
          baseStyles,
          "border-primary/50",
          "opacity-80"
        )
      case "unlocked":
        return cn(
          baseStyles,
          "border-green-500",
          "bg-green-50/50 dark:bg-green-900/10"
        )
      default:
        return baseStyles
    }
  }

  // Get status badge
  const getStatusBadge = () => {
    switch (state) {
      case "locked":
        return (
          <Badge variant="secondary" className="gap-1">
            <Lock className="h-3 w-3" />
            Locked
          </Badge>
        )
      case "available":
        return (
          <Badge variant="outline" className="gap-1 border-primary text-primary">
            <Unlock className="h-3 w-3" />
            Available
          </Badge>
        )
      case "unlocking":
        return (
          <Badge variant="outline" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            Unlocking...
          </Badge>
        )
      case "unlocked":
        return (
          <Badge variant="success" className="gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Unlocked
          </Badge>
        )
    }
  }

  // Get unlock condition message
  const getUnlockMessage = (): React.ReactNode => {
    switch (unlockCondition.type) {
      case "time":
        return (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>Unlocks in {formatTime(timeRemaining)}</span>
          </div>
        )
      case "attempts":
        return (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <AlertCircle className="h-4 w-4" />
            <span>
              Available after {unlockCondition.required} wrong attempts
              ({unlockCondition.current}/{unlockCondition.required})
            </span>
          </div>
        )
      case "previous":
        return (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Lock className="h-4 w-4" />
            <span>Complete "{unlockCondition.hintTitle}" first</span>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className={cn("relative", className)}>
      {/* Progressive chain connector */}
      {isProgressive && !isFirst && (
        <div 
          className={cn(
            "absolute left-6 -top-6 w-0.5 h-6",
            state === "unlocked" ? "bg-green-500" : "bg-muted"
          )}
          aria-hidden="true"
        />
      )}
      
      <Card className={getCardStyles()}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              {/* Chain indicator for progressive mode */}
              {isProgressive && (
                <div 
                  className={cn(
                    "w-3 h-3 rounded-full border-2 flex-shrink-0",
                    state === "unlocked" 
                      ? "bg-green-500 border-green-500" 
                      : state === "available"
                      ? "bg-primary border-primary animate-pulse"
                      : "bg-background border-muted"
                  )}
                  aria-hidden="true"
                />
              )}
              
              <div className="flex items-center gap-2">
                <Lightbulb className={cn(
                  "h-5 w-5",
                  state === "unlocked" ? "text-green-500" : "text-muted-foreground"
                )} />
                <div>
                  <h4 className="font-semibold">Hint {hint.order}</h4>
                  {getStatusBadge()}
                </div>
              </div>
            </div>
            
            {/* Cost badge */}
            {state !== "unlocked" && (
              <Badge variant="outline" className="flex-shrink-0">
                -{hint.cost} pts
              </Badge>
            )}
            
            {/* Points used badge */}
            {state === "unlocked" && (
              <Badge variant="success" className="flex-shrink-0">
                Used (-{hint.cost} pts)
              </Badge>
            )}
          </div>
        </CardHeader>

        <CardContent>
          {/* Content based on state */}
          {state === "unlocked" ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <p className="text-foreground leading-relaxed">{hint.content}</p>
              {hint.unlocked_at && (
                <p className="text-xs text-muted-foreground mt-4">
                  Unlocked {new Date(hint.unlocked_at).toLocaleString()}
                </p>
              )}
            </div>
          ) : state === "available" ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                This hint will help you solve the challenge. Unlocking will cost {hint.cost} points.
              </p>
              <Button 
                onClick={onUnlock}
                className="w-full gap-2"
              >
                <Unlock className="h-4 w-4" />
                Unlock Hint
              </Button>
            </div>
          ) : state === "unlocking" ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : (
            <div className="space-y-2">
              {getUnlockMessage()}
              <p className="text-sm text-muted-foreground">
                Cost: {hint.cost} points
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Progressive chain connector to next */}
      {isProgressive && !isLast && state === "unlocked" && (
        <div 
          className="absolute left-6 -bottom-6 w-0.5 h-6 bg-green-500"
          aria-hidden="true"
        />
      )}
    </div>
  )
}

export default HintCard
