/**
 * Leaderboard Page
 * Real-time rankings with WebSocket updates
 */

import { Metadata } from "next"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Trophy, Medal, Award } from "lucide-react"

export const metadata: Metadata = {
  title: "Leaderboard",
  description: "Top performers and rankings",
}

// Mock data - replace with actual API calls
const leaderboardData = [
  { rank: 1, username: "CyberNinja", points: 4500, solves: 45, avatar: "CN" },
  { rank: 2, username: "HackMaster", points: 4200, solves: 42, avatar: "HM" },
  { rank: 3, username: "ByteHunter", points: 3800, solves: 38, avatar: "BH" },
  { rank: 4, username: "RootAdmin", points: 3500, solves: 35, avatar: "RA" },
  { rank: 5, username: "ShellShock", points: 3200, solves: 32, avatar: "SS" },
  { rank: 6, username: "NullPointer", points: 2900, solves: 29, avatar: "NP" },
  { rank: 7, username: "StackOverflow", points: 2600, solves: 26, avatar: "SO" },
  { rank: 8, username: "BufferFlow", points: 2300, solves: 23, avatar: "BF" },
  { rank: 9, username: "CryptoKing", points: 2000, solves: 20, avatar: "CK" },
  { rank: 10, username: "WebWizard", points: 1800, solves: 18, avatar: "WW" },
]

const teamLeaderboard = [
  { rank: 1, name: "RedTeam Alpha", points: 12500, members: 5 },
  { rank: 2, name: "BlueTeam Elite", points: 11200, members: 4 },
  { rank: 3, name: "Purple Hats", points: 9800, members: 6 },
]

export default function LeaderboardPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold tracking-tight">Leaderboard</h1>
        <p className="text-muted-foreground">
          Top performers and rankings updated in real-time
        </p>
      </div>

      {/* Top 3 Podium */}
      <div className="mb-12 flex items-end justify-center gap-4">
        {leaderboardData.slice(0, 3).map((user, index) => (
          <PodiumCard
            key={user.username}
            rank={user.rank}
            username={user.username}
            points={user.points}
            avatar={user.avatar}
            position={index === 0 ? "center" : index === 1 ? "left" : "right"}
          />
        ))}
      </div>

      <Tabs defaultValue="individual" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="individual">Individual</TabsTrigger>
          <TabsTrigger value="teams">Teams</TabsTrigger>
        </TabsList>

        <TabsContent value="individual">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-safety" />
                Individual Rankings
              </CardTitle>
              <CardDescription>Ranked by total points earned</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {leaderboardData.map((user) => (
                  <LeaderboardRow
                    key={user.username}
                    rank={user.rank}
                    username={user.username}
                    points={user.points}
                    solves={user.solves}
                    avatar={user.avatar}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="teams">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Award className="h-5 w-5 text-safety" />
                Team Rankings
              </CardTitle>
              <CardDescription>Ranked by combined team points</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {teamLeaderboard.map((team) => (
                  <TeamLeaderboardRow
                    key={team.name}
                    rank={team.rank}
                    name={team.name}
                    points={team.points}
                    members={team.members}
                  />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface PodiumCardProps {
  rank: number
  username: string
  points: number
  avatar: string
  position: "left" | "center" | "right"
}

function PodiumCard({ rank, username, points, avatar, position }: PodiumCardProps) {
  const heightClass = position === "center" ? "h-48" : position === "left" ? "h-40" : "h-36"
  const medalColor = rank === 1 ? "text-yellow-500" : rank === 2 ? "text-gray-400" : "text-amber-600"

  return (
    <div className={`flex flex-col items-center ${heightClass}`}>
      <div className="mb-2">
        <Avatar className="h-16 w-16 border-4 border-background">
          <AvatarFallback className="bg-safety text-white text-lg">
            {avatar}
          </AvatarFallback>
        </Avatar>
      </div>
      <div className="mb-1 text-center">
        <p className="font-semibold">{username}</p>
        <p className="text-sm text-muted-foreground">{points.toLocaleString()} pts</p>
      </div>
      <div className={`mt-auto flex w-24 items-center justify-center rounded-t-lg bg-muted ${heightClass === "h-48" ? "bg-yellow-100 dark:bg-yellow-900/20" : heightClass === "h-40" ? "bg-gray-100 dark:bg-gray-800" : "bg-amber-100 dark:bg-amber-900/20"}`}>
        <Medal className={`h-8 w-8 ${medalColor}`} />
      </div>
    </div>
  )
}

interface LeaderboardRowProps {
  rank: number
  username: string
  points: number
  solves: number
  avatar: string
}

function LeaderboardRow({ rank, username, points, solves, avatar }: LeaderboardRowProps) {
  const isTopThree = rank <= 3

  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-4">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full font-bold ${
          isTopThree ? "bg-safety text-white" : "bg-muted text-muted-foreground"
        }`}>
          {rank}
        </div>
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs">{avatar}</AvatarFallback>
        </Avatar>
        <span className="font-medium">{username}</span>
        {isTopThree && <Badge variant="safety">Top {rank}</Badge>}
      </div>
      <div className="flex items-center gap-6 text-sm">
        <span className="text-muted-foreground">{solves} solves</span>
        <span className="font-semibold w-20 text-right">{points.toLocaleString()} pts</span>
      </div>
    </div>
  )
}

interface TeamLeaderboardRowProps {
  rank: number
  name: string
  points: number
  members: number
}

function TeamLeaderboardRow({ rank, name, points, members }: TeamLeaderboardRowProps) {
  const isTopThree = rank <= 3

  return (
    <div className="flex items-center justify-between rounded-lg border p-3 hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-4">
        <div className={`flex h-8 w-8 items-center justify-center rounded-full font-bold ${
          isTopThree ? "bg-safety text-white" : "bg-muted text-muted-foreground"
        }`}>
          {rank}
        </div>
        <span className="font-medium">{name}</span>
        {isTopThree && <Badge variant="safety">Top {rank}</Badge>}
      </div>
      <div className="flex items-center gap-6 text-sm">
        <span className="text-muted-foreground">{members} members</span>
        <span className="font-semibold w-24 text-right">{points.toLocaleString()} pts</span>
      </div>
    </div>
  )
}
