"use client"

/**
 * Challenges Listing Page - Cerberus CTF Platform
 * Challenge grid with filtering and search
 * Technical Brutalism design with Safety Orange accent
 */

import { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import {
  Trophy,
  Users,
  Filter,
  Search,
  Lock,
  CheckCircle2,
  Clock,
  Flame,
  Brain,
  Eye,
  FileText,
  Terminal,
  Search as SearchIcon,
  Fingerprint,
  Bitcoin,
  Image as ImageIcon,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/hooks/use-toast"
import { api, handleApiError } from "@/lib/api"
import { cn } from "@/lib/utils"
import type { Challenge, ChallengeCategory, ChallengeDifficulty, PaginatedResponse } from "@/types"

const categoryIcons: Record<ChallengeCategory, React.ReactNode> = {
  web: <Globe className="h-4 w-4" />,
  crypto: <Lock className="h-4 w-4" />,
  pwn: <Terminal className="h-4 w-4" />,
  reverse: <Brain className="h-4 w-4" />,
  forensics: <SearchIcon className="h-4 w-4" />,
  misc: <Clock className="h-4 w-4" />,
  osint: <Eye className="h-4 w-4" />,
  blockchain: <Bitcoin className="h-4 w-4" />,
  steganography: <ImageIcon className="h-4 w-4" />,
}

const difficultyColors: Record<ChallengeDifficulty, string> = {
  easy: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100 border-green-200 dark:border-green-800",
  medium: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100 border-yellow-200 dark:border-yellow-800",
  hard: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100 border-orange-200 dark:border-orange-800",
  extreme: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100 border-red-200 dark:border-red-800",
}

const categories: ChallengeCategory[] = [
  "web",
  "crypto",
  "pwn",
  "reverse",
  "forensics",
  "misc",
  "osint",
  "blockchain",
  "steganography",
]

const difficulties: ChallengeDifficulty[] = ["easy", "medium", "hard", "extreme"]

export default function ChallengesPage() {
  const router = useRouter()
  const { toast } = useToast()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedCategory, setSelectedCategory] = useState<ChallengeCategory | "all">("all")
  const [selectedDifficulty, setSelectedDifficulty] = useState<ChallengeDifficulty | "all">("all")
  const [selectedStatus, setSelectedStatus] = useState<"all" | "solved" | "unsolved">("all")
  const [sortBy, setSortBy] = useState<"points" | "difficulty" | "name" | "solves">("points")

  const { data: challenges, isLoading, error } = useQuery({
    queryKey: ["challenges", selectedCategory, selectedDifficulty, selectedStatus, sortBy],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (selectedCategory !== "all") params.append("category", selectedCategory)
      if (selectedDifficulty !== "all") params.append("difficulty", selectedDifficulty)
      if (selectedStatus !== "all") params.append("status", selectedStatus)
      params.append("sort", sortBy)
      
      return await api.get<PaginatedResponse<Challenge>>(`/challenges?${params.toString()}`)
    },
  })

  const challengeItems = (challenges as unknown as PaginatedResponse<Challenge>)?.items || []
  
  const filteredChallenges = challengeItems.filter((challenge: Challenge) =>
    searchQuery === "" ||
    challenge.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    challenge.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    challenge.tags.some((tag: string) => tag.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const stats = {
    total: challengeItems.length,
    solved: challengeItems.filter((c: Challenge) => c.is_solved).length,
    totalPoints: challengeItems.reduce((acc: number, c: Challenge) => acc + c.points, 0),
    userPoints: challengeItems.filter((c: Challenge) => c.is_solved).reduce((acc: number, c: Challenge) => acc + c.points, 0),
  }

  if (error) {
    toast({
      title: "Error loading challenges",
      description: handleApiError(error).detail,
      variant: "destructive",
    })
  }

  return (
    <div className="container mx-auto py-8 px-4 md:px-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Challenges</h1>
            <p className="text-muted-foreground mt-1">
              Test your skills and earn points by solving CTF challenges
            </p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-muted px-4 py-2 rounded-lg">
              <Trophy className="h-5 w-5 text-safety" />
              <div>
                <p className="text-xs text-muted-foreground">Your Score</p>
                <p className="font-bold">{stats.userPoints} / {stats.totalPoints}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 bg-muted px-4 py-2 rounded-lg">
              <CheckCircle2 className="h-5 w-5 text-green-500" />
              <div>
                <p className="text-xs text-muted-foreground">Solved</p>
                <p className="font-bold">{stats.solved} / {stats.total}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 space-y-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search challenges..."
              className="pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            <Select value={selectedDifficulty} onValueChange={(v) => setSelectedDifficulty(v as ChallengeDifficulty | "all")}>
              <SelectTrigger className="w-[140px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Difficulty" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Difficulties</SelectItem>
                {difficulties.map((d) => (
                  <SelectItem key={d} value={d} className="capitalize">{d}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={(v) => setSortBy(v as typeof sortBy)}>
              <SelectTrigger className="w-[140px]">
                <Clock className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Sort by" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="points">Points</SelectItem>
                <SelectItem value="difficulty">Difficulty</SelectItem>
                <SelectItem value="name">Name</SelectItem>
                <SelectItem value="solves">Solves</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <Tabs value={selectedCategory} onValueChange={(v) => setSelectedCategory(v as ChallengeCategory | "all")}>
          <TabsList className="flex flex-wrap h-auto gap-1">
            <TabsTrigger value="all">All</TabsTrigger>
            {categories.map((cat) => (
              <TabsTrigger key={cat} value={cat} className="capitalize">
                {cat}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        <div className="flex gap-2">
          <Button
            variant={selectedStatus === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedStatus("all")}
          >
            All
          </Button>
          <Button
            variant={selectedStatus === "unsolved" ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedStatus("unsolved")}
          >
            Unsolved
          </Button>
          <Button
            variant={selectedStatus === "solved" ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedStatus("solved")}
          >
            Solved
          </Button>
        </div>
      </div>

      {/* Challenge Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-48" />
          ))}
        </div>
      ) : filteredChallenges?.length === 0 ? (
        <div className="text-center py-16">
          <Flame className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold">No challenges found</h3>
          <p className="text-muted-foreground">Try adjusting your filters or search query</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredChallenges?.map((challenge: Challenge) => (
            <ChallengeCard key={challenge.id} challenge={challenge} />
          ))}
        </div>
      )}
    </div>
  )
}

interface ChallengeCardProps {
  challenge: Challenge
}

function ChallengeCard({ challenge }: ChallengeCardProps) {
  return (
    <Link href={`/challenges/${challenge.id}`}>
      <Card
        className={cn(
          "h-full cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-safety",
          challenge.is_solved && "border-l-4 border-l-green-500",
          !challenge.is_solved && "border-l-4 border-l-transparent hover:border-l-safety"
        )}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <CardTitle className="text-lg font-semibold truncate">
                {challenge.title}
              </CardTitle>
              <div className="flex items-center gap-2 mt-2">
                <Badge variant="outline" className={cn("text-xs", difficultyColors[challenge.difficulty])}>
                  {challenge.difficulty}
                </Badge>
                <Badge variant="outline" className="text-xs capitalize">
                  {categoryIcons[challenge.category]}
                  <span className="ml-1">{challenge.category}</span>
                </Badge>
              </div>
            </div>
            {challenge.is_solved ? (
              <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
            ) : challenge.solve_count > 0 ? (
              <Lock className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            ) : null}
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground line-clamp-2 mb-4">
            {challenge.description}
          </p>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-1 text-muted-foreground">
              <Trophy className="h-4 w-4" />
              <span>{challenge.points} pts</span>
            </div>
            <div className="flex items-center gap-1 text-muted-foreground">
              <Users className="h-4 w-4" />
              <span>{challenge.solve_count} solves</span>
            </div>
          </div>
          {challenge.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-3">
              {challenge.tags.slice(0, 3).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {challenge.tags.length > 3 && (
                <Badge variant="secondary" className="text-xs">
                  +{challenge.tags.length - 3}
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  )
}

// Import Globe icon separately to avoid naming conflict
import { Globe } from "lucide-react"
