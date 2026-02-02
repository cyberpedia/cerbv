import * as React from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { ScrollArea } from "@/components/ui/scroll-area"
import { 
  Trophy, 
  Users, 
  Eye, 
  EyeOff, 
  Clock,
  Shield,
  Hash
} from "lucide-react"

/**
 * SolveVisibilityPanel Component
 * 
 * Displays challenge solves with privacy-aware modes:
 * - full: Table with team names, times, avatars
 * - anonymous: "Team #1", "Team #2" with consistent hashing
 * - stealth: "Multiple teams solved" banner only
 * 
 * Respects anonymity settings while highlighting first blood.
 * 
 * @example
 * <SolveVisibilityPanel
 *   solves={solves}
 *   mode="anonymous"
 *   currentUserTeamId="team-123"
 *   eventEnded={false}
 * />
 */

type PrivacyMode = "full" | "anonymous" | "stealth"

interface Solve {
  id: string
  team_id: string
  team_name: string
  team_avatar?: string
  solved_at: string
  solve_time?: number // Time taken in seconds
  is_first_blood?: boolean
}

interface SolveVisibilityPanelProps {
  /** Array of solve records */
  solves: Solve[]
  /** Privacy mode for display */
  mode: PrivacyMode
  /** Current user's team ID (to highlight their solves) */
  currentUserTeamId?: string
  /** Whether the CTF event has ended (reveals stealth mode) */
  eventEnded?: boolean
  /** Whether to show solve times */
  showSolveTimes?: boolean
  /** Maximum number of solves to display */
  maxDisplayCount?: number
  /** Optional className for styling */
  className?: string
}

// Generate consistent anonymous team name from team ID
function getAnonymousTeamName(teamId: string, index: number): string {
  // Simple hash for consistent numbering
  let hash = 0
  for (let i = 0; i < teamId.length; i++) {
    const char = teamId.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  // Use absolute value and map to 1-999
  const teamNumber = (Math.abs(hash) % 999) + 1
  return `Team #${teamNumber}`
}

// Format duration
function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  
  if (hours > 0) {
    return `${hours}h ${mins}m`
  }
  if (mins > 0) {
    return `${mins}m ${secs}s`
  }
  return `${secs}s`
}

export function SolveVisibilityPanel({
  solves,
  mode,
  currentUserTeamId,
  eventEnded = false,
  showSolveTimes = true,
  maxDisplayCount = 50,
  className,
}: SolveVisibilityPanelProps) {
  // Sort solves by time (first blood first)
  const sortedSolves = React.useMemo(() => {
    return [...solves].sort((a, b) => 
      new Date(a.solved_at).getTime() - new Date(b.solved_at).getTime()
    )
  }, [solves])

  // Determine effective mode (stealth reveals after event ends)
  const effectiveMode = mode === "stealth" && eventEnded ? "anonymous" : mode

  // Stealth mode - minimal info
  if (effectiveMode === "stealth") {
    return (
      <Card className={cn("bg-muted/50", className)}>
        <CardContent className="p-6">
          <div className="flex flex-col items-center justify-center text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
              <Shield className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <p className="font-medium">Multiple teams have solved this challenge</p>
              <p className="text-sm text-muted-foreground">
                Solve details will be revealed when the event ends
              </p>
            </div>
            <Badge variant="outline">
              {solves.length} {solves.length === 1 ? "solve" : "solves"}
            </Badge>
          </div>
        </CardContent>
      </Card>
    )
  }

  // Get display data based on mode
  const getDisplayData = (solve: Solve, index: number) => {
    const isCurrentUser = solve.team_id === currentUserTeamId
    const isFirstBlood = index === 0 || solve.is_first_blood

    if (effectiveMode === "anonymous") {
      return {
        name: getAnonymousTeamName(solve.team_id, index),
        avatar: undefined,
        initials: "T",
        isCurrentUser,
        isFirstBlood,
      }
    }

    return {
      name: solve.team_name,
      avatar: solve.team_avatar,
      initials: solve.team_name.slice(0, 2).toUpperCase(),
      isCurrentUser,
      isFirstBlood,
    }
  }

  const displaySolves = sortedSolves.slice(0, maxDisplayCount)
  const hasMore = sortedSolves.length > maxDisplayCount

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Users className="h-5 w-5" />
            Solves
          </CardTitle>
          <div className="flex items-center gap-2">
            {effectiveMode === "anonymous" && (
              <Badge variant="outline" className="gap-1">
                <EyeOff className="h-3 w-3" />
                Anonymous
              </Badge>
            )}
            <Badge variant="secondary">
              {solves.length}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <ScrollArea className="h-[300px] pr-4">
          <div className="space-y-2">
            {displaySolves.map((solve, index) => {
              const data = getDisplayData(solve, index)
              const solveDate = new Date(solve.solved_at)

              return (
                <div
                  key={solve.id}
                  className={cn(
                    "flex items-center gap-3 p-3 rounded-lg transition-colors",
                    data.isCurrentUser 
                      ? "bg-primary/10 border border-primary/20" 
                      : "hover:bg-muted/50",
                    data.isFirstBlood && "bg-yellow-500/5"
                  )}
                >
                  {/* Rank / First Blood */}
                  <div className="flex-shrink-0 w-8 text-center">
                    {data.isFirstBlood ? (
                      <Trophy className="h-5 w-5 text-yellow-500 mx-auto" aria-label="First Blood" />
                    ) : (
                      <span className="text-sm text-muted-foreground font-mono">
                        #{index + 1}
                      </span>
                    )}
                  </div>

                  {/* Avatar */}
                  <Avatar className="h-8 w-8 flex-shrink-0">
                    {data.avatar && effectiveMode === "full" ? (
                      <AvatarImage src={data.avatar} alt={data.name} />
                    ) : null}
                    <AvatarFallback className={cn(
                      "text-xs",
                      data.isFirstBlood && "bg-yellow-500 text-yellow-950"
                    )}>
                      {data.initials}
                    </AvatarFallback>
                  </Avatar>

                  {/* Team Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "font-medium truncate",
                        data.isCurrentUser && "text-primary"
                      )}>
                        {data.name}
                      </span>
                      {data.isCurrentUser && (
                        <Badge variant="outline" className="text-xs flex-shrink-0">
                          You
                        </Badge>
                      )}
                      {data.isFirstBlood && (
                        <Badge 
                          variant="outline" 
                          className="text-xs flex-shrink-0 gap-1 border-yellow-500 text-yellow-600"
                        >
                          <Trophy className="h-3 w-3" />
                          First Blood
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock className="h-3 w-3" />
                      <span>
                        {solveDate.toLocaleDateString()} {solveDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>

                  {/* Solve Time */}
                  {showSolveTimes && solve.solve_time && (
                    <div className="text-right flex-shrink-0">
                      <span className="text-sm font-mono text-muted-foreground">
                        {formatDuration(solve.solve_time)}
                      </span>
                    </div>
                  )}
                </div>
              )
            })}

            {hasMore && (
              <div className="text-center py-4 text-sm text-muted-foreground">
                +{sortedSolves.length - maxDisplayCount} more solves
              </div>
            )}

            {solves.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No solves yet</p>
                <p className="text-sm">Be the first to solve this challenge!</p>
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}

export default SolveVisibilityPanel
