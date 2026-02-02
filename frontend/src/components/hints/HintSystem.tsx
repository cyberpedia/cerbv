"use client"

import * as React from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { HintCard } from "./HintCard"
import { HintUnlockConfirm } from "./HintUnlockConfirm"
import { ProgressiveChain } from "./ProgressiveChain"
import { get, post } from "@/lib/api"
import { useToast } from "@/hooks/use-toast"
import { 
  Lightbulb, 
  Lock, 
  Unlock, 
  AlertCircle,
  ChevronDown,
  Settings
} from "lucide-react"

import type { Hint } from "@/types"

/**
 * HintSystem Component
 * 
 * Container component for managing hints on a challenge.
 * Features:
 * - Fetches hints from API
 * - Displays hints in accordion or progressive chain mode
 * - Manages unlock state and confirmations
 * - Shows global hint settings
 * 
 * @example
 * <HintSystem
 *   challengeId="challenge-123"
 *   challengeStatus="unlocked"
 *   userPoints={500}
 *   progressiveMode={true}
 * />
 */

type ChallengeStatus = "locked" | "unlocked" | "solved"
type HintDisplayMode = "accordion" | "progressive" | "list"

interface HintSystemProps {
  /** Challenge ID */
  challengeId: string
  /** Current challenge status */
  challengeStatus: ChallengeStatus
  /** User's current points */
  userPoints: number
  /** Display mode for hints */
  displayMode?: HintDisplayMode
  /** Whether to use progressive unlocking */
  progressiveMode?: boolean
  /** Global hint cost (if all hints cost the same) */
  globalHintCost?: number
  /** Whether hints are enabled for this challenge */
  hintsEnabled?: boolean
  /** Optional className for styling */
  className?: string
}

interface HintWithState extends Hint {
  state: "locked" | "available" | "unlocking" | "unlocked"
  unlockCondition?: {
    type: "time" | "attempts" | "previous" | "none"
    remainingSeconds?: number
    required?: number
    current?: number
    hintTitle?: string
  }
}

export function HintSystem({
  challengeId,
  challengeStatus,
  userPoints,
  displayMode = "accordion",
  progressiveMode = false,
  globalHintCost,
  hintsEnabled = true,
  className,
}: HintSystemProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  
  const [selectedHint, setSelectedHint] = React.useState<Hint | null>(null)
  const [showConfirmDialog, setShowConfirmDialog] = React.useState(false)
  const [unlockingHintId, setUnlockingHintId] = React.useState<string | null>(null)

  // Fetch hints
  const { data: hints, isLoading, error } = useQuery({
    queryKey: ["hints", challengeId],
    queryFn: async () => {
      const response = await get<Hint[]>(`/challenges/${challengeId}/hints`)
      return response
    },
    enabled: challengeStatus !== "locked" && hintsEnabled,
    staleTime: 5 * 60 * 1000,
  })

  // Unlock mutation
  const unlockMutation = useMutation({
    mutationFn: async (hintId: string) => {
      const response = await post<{ hint: Hint; remaining_points: number }>(
        `/challenges/${challengeId}/hints/${hintId}/unlock`,
        {}
      )
      return response
    },
    onSuccess: (data) => {
      toast({
        title: "Hint Unlocked",
        description: `You spent ${selectedHint?.cost} points. Remaining: ${data.remaining_points}`,
      })
      
      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ["hints", challengeId] })
      queryClient.invalidateQueries({ queryKey: ["user"] })
      
      setUnlockingHintId(null)
      setShowConfirmDialog(false)
      setSelectedHint(null)
    },
    onError: (error: Error) => {
      toast({
        title: "Unlock Failed",
        description: error.message || "Failed to unlock hint. Please try again.",
        variant: "destructive",
      })
      setUnlockingHintId(null)
    },
  })

  // Process hints with state
  const processedHints: HintWithState[] = React.useMemo(() => {
    if (!hints) return []
    
    return hints.map((hint, index) => {
      let state: HintWithState["state"] = "locked"
      let unlockCondition: HintWithState["unlockCondition"] = { type: "none" }

      if (hint.is_unlocked) {
        state = "unlocked"
      } else if (unlockingHintId === hint.id) {
        state = "unlocking"
      } else {
        // Determine availability based on progressive mode
        if (progressiveMode) {
          const previousHint = hints[index - 1]
          if (index === 0 || previousHint?.is_unlocked) {
            state = "available"
          } else {
            state = "locked"
            unlockCondition = {
              type: "previous",
              hintTitle: previousHint ? `Hint ${previousHint.order}` : "",
            }
          }
        } else {
          state = "available"
        }
      }

      return { ...hint, state, unlockCondition }
    })
  }, [hints, unlockingHintId, progressiveMode])

  // Calculate stats
  const stats = React.useMemo(() => {
    const unlocked = processedHints.filter(h => h.is_unlocked).length
    const available = processedHints.filter(h => h.state === "available").length
    const totalCost = processedHints
      .filter(h => h.is_unlocked)
      .reduce((sum, h) => sum + h.cost, 0)
    
    return { unlocked, available, totalCost, total: processedHints.length }
  }, [processedHints])

  // Handle unlock request
  const handleUnlockRequest = (hint: Hint) => {
    setSelectedHint(hint)
    setShowConfirmDialog(true)
  }

  // Handle confirm unlock
  const handleConfirmUnlock = () => {
    if (!selectedHint) return
    
    setUnlockingHintId(selectedHint.id)
    unlockMutation.mutate(selectedHint.id)
  }

  // Challenge locked state
  if (challengeStatus === "locked") {
    return (
      <Card className={cn("opacity-75", className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-muted-foreground">
            <Lock className="h-5 w-5" />
            Hints Locked
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Unlock this challenge to access hints.
          </p>
        </CardContent>
      </Card>
    )
  }

  // Hints disabled state
  if (!hintsEnabled) {
    return (
      <Card className={cn("opacity-75", className)}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-muted-foreground">
            <Lightbulb className="h-5 w-5" />
            No Hints Available
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            This challenge does not have any hints.
          </p>
        </CardContent>
      </Card>
    )
  }

  // Loading state
  if (isLoading) {
    return (
      <Card className={className}>
        <CardContent className="p-6">
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        </CardContent>
      </Card>
    )
  }

  // Error state
  if (error) {
    return (
      <Card className={cn("border-destructive", className)}>
        <CardContent className="p-6">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <p className="text-sm">Failed to load hints. Please try again.</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Empty state
  if (!hints || hints.length === 0) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5" />
            Hints
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No hints available for this challenge.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header with stats */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Lightbulb className="h-5 w-5 text-yellow-500" />
              Hints
            </CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="gap-1">
                <Unlock className="h-3 w-3" />
                {stats.unlocked}/{stats.total}
              </Badge>
              {stats.totalCost > 0 && (
                <Badge variant="secondary">
                  -{stats.totalCost} pts used
                </Badge>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {globalHintCost && (
            <p className="text-sm text-muted-foreground">
              Each hint costs {globalHintCost} points
            </p>
          )}
        </CardContent>
      </Card>

      {/* Progressive chain visualization */}
      {progressiveMode && displayMode === "progressive" && (
        <Card>
          <CardContent className="p-6">
            <ProgressiveChain
              totalHints={stats.total}
              unlockedCount={stats.unlocked}
              currentAvailable={stats.unlocked + 1}
            />
          </CardContent>
        </Card>
      )}

      {/* Hints list */}
      {displayMode === "accordion" ? (
        <Accordion type="multiple" className="space-y-2">
          {processedHints.map((hint, index) => (
            <AccordionItem 
              key={hint.id} 
              value={hint.id}
              className={cn(
                "border rounded-lg px-4",
                hint.is_unlocked && "border-green-500/50 bg-green-50/30 dark:bg-green-900/10",
                hint.state === "available" && "border-primary/50"
              )}
            >
              <AccordionTrigger className="hover:no-underline py-4">
                <div className="flex items-center gap-3 text-left">
                  {hint.is_unlocked ? (
                    <Unlock className="h-4 w-4 text-green-500" />
                  ) : (
                    <Lock className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span className="font-medium">Hint {hint.order}</span>
                  {!hint.is_unlocked && (
                    <Badge variant="outline" className="ml-2">
                      {hint.cost} pts
                    </Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-4">
                <HintCard
                  hint={hint}
                  state={hint.state}
                  onUnlock={() => handleUnlockRequest(hint)}
                  unlockCondition={hint.unlockCondition}
                  isProgressive={progressiveMode}
                  isFirst={index === 0}
                  isLast={index === processedHints.length - 1}
                />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      ) : (
        <div className="space-y-4">
          {processedHints.map((hint, index) => (
            <HintCard
              key={hint.id}
              hint={hint}
              state={hint.state}
              onUnlock={() => handleUnlockRequest(hint)}
              unlockCondition={hint.unlockCondition}
              isProgressive={progressiveMode}
              isFirst={index === 0}
              isLast={index === processedHints.length - 1}
            />
          ))}
        </div>
      )}

      {/* Unlock confirmation dialog */}
      <HintUnlockConfirm
        hint={selectedHint}
        currentPoints={userPoints}
        isOpen={showConfirmDialog}
        onConfirm={handleConfirmUnlock}
        onCancel={() => {
          setShowConfirmDialog(false)
          setSelectedHint(null)
        }}
        isUnlocking={unlockMutation.isPending}
      />
    </div>
  )
}

export default HintSystem
