import * as React from "react"
import { cn } from "@/lib/utils"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, Unlock, Coins, Info } from "lucide-react"

import type { Hint } from "@/types"

/**
 * HintUnlockConfirm Component
 * 
 * Confirmation modal displayed before unlocking a hint.
 * Shows cost, remaining points preview, and requires explicit confirmation.
 * 
 * @example
 * <HintUnlockConfirm
 *   hint={hint}
 *   currentPoints={500}
 *   isOpen={showConfirm}
 *   onConfirm={() => unlockHint(hint.id)}
 *   onCancel={() => setShowConfirm(false)}
 * />
 */

interface HintUnlockConfirmProps {
  /** The hint to be unlocked */
  hint: Hint | null
  /** User's current points */
  currentPoints: number
  /** Whether the dialog is open */
  isOpen: boolean
  /** Callback when unlock is confirmed */
  onConfirm: () => void
  /** Callback when cancelled */
  onCancel: () => void
  /** Whether an unlock is in progress */
  isUnlocking?: boolean
  /** Optional className for styling */
  className?: string
}

export function HintUnlockConfirm({
  hint,
  currentPoints,
  isOpen,
  onConfirm,
  onCancel,
  isUnlocking = false,
  className,
}: HintUnlockConfirmProps) {
  if (!hint) return null

  const remainingPoints = currentPoints - hint.cost
  const canAfford = remainingPoints >= 0

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className={cn("sm:max-w-md", className)}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Unlock className="h-5 w-5 text-primary" />
            Unlock Hint?
          </DialogTitle>
          <DialogDescription>
            You are about to unlock a hint for this challenge.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Hint preview */}
          <div className="p-4 rounded-lg border bg-muted/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Hint {hint.order}</span>
              <Badge variant="outline">-{hint.cost} pts</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              This hint will reveal information to help you solve the challenge.
              Once unlocked, the point cost cannot be refunded.
            </p>
          </div>

          {/* Points breakdown */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Current Points:</span>
              <span className="font-medium">{currentPoints}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Hint Cost:</span>
              <span className="font-medium text-destructive">-{hint.cost}</span>
            </div>
            <div className="border-t pt-2 mt-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">Remaining Points:</span>
                <span className={cn(
                  "font-bold",
                  canAfford ? "text-foreground" : "text-destructive"
                )}>
                  {remainingPoints}
                </span>
              </div>
            </div>
          </div>

          {/* Warning messages */}
          {!canAfford && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>
                You don't have enough points to unlock this hint. 
                Solve more challenges to earn points.
              </span>
            </div>
          )}

          {canAfford && remainingPoints < 50 && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 text-sm">
              <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>
                This will leave you with few points. Consider if you really need this hint.
              </span>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isUnlocking}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            disabled={!canAfford || isUnlocking}
            className="gap-2"
          >
            {isUnlocking ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                Unlocking...
              </>
            ) : (
              <>
                <Coins className="h-4 w-4" />
                Unlock for {hint.cost} pts
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default HintUnlockConfirm
