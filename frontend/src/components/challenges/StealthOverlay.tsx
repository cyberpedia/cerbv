import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  EyeOff, 
  Shield, 
  Lock, 
  Users, 
  Clock,
  Info,
  Unlock
} from "lucide-react"

/**
 * StealthOverlay Component
 * 
 * Overlay component for challenges in stealth mode.
 * Hides solve details until event ends, showing only minimal information.
 * Can display countdown or reveal button when appropriate.
 * 
 * @example
 * <StealthOverlay
 *   solveCount={15}
 *   eventEndTime={new Date('2024-12-31T23:59:59')}
 *   onRevealRequest={() => requestReveal()}
 * />
 */

type StealthState = "active" | "ending-soon" | "ended"

interface StealthOverlayProps {
  /** Number of solves (shown as approximate) */
  solveCount: number
  /** Event end time for countdown */
  eventEndTime?: Date
  /** Whether the event has ended */
  eventEnded?: boolean
  /** Callback when user requests reveal */
  onRevealRequest?: () => void
  /** Whether reveal is loading */
  isRevealing?: boolean
  /** Custom message to display */
  customMessage?: string
  /** Optional className for styling */
  className?: string
}

// Format countdown
function formatCountdown(targetDate: Date): string {
  const now = new Date()
  const diff = targetDate.getTime() - now.getTime()
  
  if (diff <= 0) return "Ended"
  
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))
  const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
  
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${mins}m`
  return `${mins}m`
}

// Get approximate solve count
function getApproximateCount(count: number): string {
  if (count === 0) return "No solves yet"
  if (count < 5) return "A few teams"
  if (count < 15) return "Several teams"
  if (count < 30) return "Many teams"
  return "Dozens of teams"
}

export function StealthOverlay({
  solveCount,
  eventEndTime,
  eventEnded = false,
  onRevealRequest,
  isRevealing = false,
  customMessage,
  className,
}: StealthOverlayProps) {
  const [countdown, setCountdown] = React.useState<string>("")
  const [stealthState, setStealthState] = React.useState<StealthState>("active")

  // Update countdown
  React.useEffect(() => {
    if (!eventEndTime || eventEnded) return

    const updateCountdown = () => {
      const now = new Date()
      const diff = eventEndTime.getTime() - now.getTime()
      
      if (diff <= 0) {
        setStealthState("ended")
        setCountdown("Event Ended")
        return
      }
      
      // Less than 1 hour = ending soon
      if (diff < 60 * 60 * 1000) {
        setStealthState("ending-soon")
      }
      
      setCountdown(formatCountdown(eventEndTime))
    }

    updateCountdown()
    const timer = setInterval(updateCountdown, 60000) // Update every minute

    return () => clearInterval(timer)
  }, [eventEndTime, eventEnded])

  // Event has ended - show reveal option
  if (eventEnded) {
    return (
      <Card className={cn("border-dashed border-primary/50", className)}>
        <CardContent className="p-6">
          <div className="flex flex-col items-center text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
              <Unlock className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Event Has Ended</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Solve details are now available
              </p>
            </div>
            <Button 
              onClick={onRevealRequest}
              disabled={isRevealing}
              className="gap-2"
            >
              {isRevealing ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Loading...
                </>
              ) : (
                <>
                  <EyeOff className="h-4 w-4" />
                  Reveal Solves
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={cn(
      "relative overflow-hidden",
      stealthState === "ending-soon" && "border-yellow-500/50",
      className
    )}>
      {/* Background pattern */}
      <div 
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
        }}
        aria-hidden="true"
      />
      
      <CardContent className="relative p-6">
        <div className="flex flex-col items-center text-center space-y-4">
          {/* Icon */}
          <div className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-colors",
            stealthState === "ending-soon" 
              ? "bg-yellow-500/10" 
              : "bg-muted"
          )}>
            <Shield className={cn(
              "h-8 w-8",
              stealthState === "ending-soon" 
                ? "text-yellow-500" 
                : "text-muted-foreground"
            )} />
          </div>

          {/* Status */}
          <div>
            <h3 className="font-semibold text-lg flex items-center justify-center gap-2">
              <EyeOff className="h-5 w-5" />
              Stealth Mode Active
            </h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              {customMessage || 
                "Solve details are hidden until the event ends. Focus on solving, not the leaderboard!"
              }
            </p>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Badge variant="outline" className="gap-1">
              <Users className="h-3 w-3" />
              {getApproximateCount(solveCount)}
            </Badge>
            
            {countdown && (
              <Badge 
                variant={stealthState === "ending-soon" ? "default" : "secondary"}
                className={cn(
                  "gap-1",
                  stealthState === "ending-soon" && "bg-yellow-500 text-yellow-950 animate-pulse"
                )}
              >
                <Clock className="h-3 w-3" />
                {countdown}
              </Badge>
            )}
          </div>

          {/* Info note */}
          <div className="flex items-start gap-2 text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg max-w-sm">
            <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <p>
              First blood and solve times will be revealed when the event ends. 
              Keep trying to get the best score!
            </p>
          </div>
        </div>
      </CardContent>

      {/* Corner decoration */}
      <div 
        className="absolute top-0 right-0 w-16 h-16 opacity-10"
        aria-hidden="true"
      >
        <Lock className="w-full h-full p-4" />
      </div>
    </Card>
  )
}

// Compact version for inline use
interface StealthBadgeProps {
  solveCount: number
  className?: string
}

export function StealthBadge({ solveCount, className }: StealthBadgeProps) {
  return (
    <Badge 
      variant="outline" 
      className={cn("gap-1 text-muted-foreground", className)}
    >
      <EyeOff className="h-3 w-3" />
      {getApproximateCount(solveCount)}
    </Badge>
  )
}

export default StealthOverlay
