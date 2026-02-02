import * as React from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Hash, Users, Shield } from "lucide-react"

/**
 * AnonymousBadge Component
 * 
 * Displays team information in anonymous mode with consistent hashing.
 * Shows "Team #123" format with optional avatar fallback.
 * 
 * @example
 * <AnonymousBadge teamId="team-abc-123" showAvatar />
 * <AnonymousBadge teamId="team-xyz-789" variant="compact" />
 */

type BadgeVariant = "default" | "compact" | "large" | "minimal"

interface AnonymousBadgeProps {
  /** Team ID for generating consistent anonymous name */
  teamId: string
  /** Display variant */
  variant?: BadgeVariant
  /** Whether to show avatar */
  showAvatar?: boolean
  /** Custom prefix (default: "Team") */
  prefix?: string
  /** Whether this is the current user's team */
  isCurrentUser?: boolean
  /** Optional className for styling */
  className?: string
}

// Generate consistent team number from ID
function getTeamNumber(teamId: string): number {
  let hash = 0
  for (let i = 0; i < teamId.length; i++) {
    const char = teamId.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash = hash & hash
  }
  // Use absolute value and map to 1-9999 for larger events
  return (Math.abs(hash) % 9999) + 1
}

// Generate avatar color based on team ID
function getAvatarColor(teamId: string): string {
  const colors = [
    "bg-red-500",
    "bg-orange-500",
    "bg-amber-500",
    "bg-yellow-500",
    "bg-lime-500",
    "bg-green-500",
    "bg-emerald-500",
    "bg-teal-500",
    "bg-cyan-500",
    "bg-sky-500",
    "bg-blue-500",
    "bg-indigo-500",
    "bg-violet-500",
    "bg-purple-500",
    "bg-fuchsia-500",
    "bg-pink-500",
    "bg-rose-500",
  ]
  
  let hash = 0
  for (let i = 0; i < teamId.length; i++) {
    hash = ((hash << 5) - hash) + teamId.charCodeAt(i)
    hash = hash & hash
  }
  
  return colors[Math.abs(hash) % colors.length]
}

export function AnonymousBadge({
  teamId,
  variant = "default",
  showAvatar = true,
  prefix = "Team",
  isCurrentUser = false,
  className,
}: AnonymousBadgeProps) {
  const teamNumber = getTeamNumber(teamId)
  const displayName = `${prefix} #${teamNumber}`
  const avatarColor = getAvatarColor(teamId)
  const initials = prefix.slice(0, 1).toUpperCase()

  // Minimal variant - just text
  if (variant === "minimal") {
    return (
      <span className={cn(
        "font-mono text-sm",
        isCurrentUser && "text-primary font-medium",
        className
      )}>
        {displayName}
      </span>
    )
  }

  // Compact variant - badge style
  if (variant === "compact") {
    return (
      <Badge 
        variant={isCurrentUser ? "default" : "outline"}
        className={cn("gap-1 font-mono", className)}
      >
        <Hash className="h-3 w-3" />
        {teamNumber}
      </Badge>
    )
  }

  // Large variant - prominent display
  if (variant === "large") {
    return (
      <div className={cn("flex items-center gap-3", className)}>
        {showAvatar && (
          <Avatar className={cn("h-12 w-12", avatarColor)}>
            <AvatarFallback className="text-white text-lg font-bold">
              {initials}
            </AvatarFallback>
          </Avatar>
        )}
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold font-mono">{displayName}</span>
            {isCurrentUser && (
              <Badge variant="outline" className="text-xs">
                You
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-1 text-sm text-muted-foreground">
            <Shield className="h-3 w-3" />
            <span>Anonymous Mode</span>
          </div>
        </div>
      </div>
    )
  }

  // Default variant
  return (
    <div className={cn("flex items-center gap-2", className)}>
      {showAvatar && (
        <Avatar className={cn("h-8 w-8", avatarColor)}>
          <AvatarFallback className="text-white text-xs font-bold">
            {initials}
          </AvatarFallback>
        </Avatar>
      )}
      <div className="flex items-center gap-2">
        <span className={cn(
          "font-mono font-medium",
          isCurrentUser && "text-primary"
        )}>
          {displayName}
        </span>
        {isCurrentUser && (
          <Badge variant="outline" className="text-xs">
            You
          </Badge>
        )}
      </div>
    </div>
  )
}

// Team list component for displaying multiple anonymous teams
interface AnonymousTeamListProps {
  /** Array of team IDs */
  teamIds: string[]
  /** Current user's team ID */
  currentUserTeamId?: string
  /** Maximum number to display */
  maxDisplay?: number
  /** Optional className for styling */
  className?: string
}

export function AnonymousTeamList({
  teamIds,
  currentUserTeamId,
  maxDisplay = 5,
  className,
}: AnonymousTeamListProps) {
  const displayTeams = teamIds.slice(0, maxDisplay)
  const remainingCount = teamIds.length - maxDisplay

  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {displayTeams.map((teamId) => (
        <AnonymousBadge
          key={teamId}
          teamId={teamId}
          variant="compact"
          isCurrentUser={teamId === currentUserTeamId}
        />
      ))}
      {remainingCount > 0 && (
        <Badge variant="secondary" className="text-xs">
          +{remainingCount} more
        </Badge>
      )}
    </div>
  )
}

export default AnonymousBadge
