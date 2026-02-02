/**
 * Admin Dashboard Page
 * Role-based dashboard for administrators
 */

import { Metadata } from "next"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { 
  Users, 
  Shield, 
  Trophy, 
  Activity,
  AlertTriangle,
  CheckCircle,
  Database
} from "lucide-react"

export const metadata: Metadata = {
  title: "Admin Dashboard",
  description: "Manage challenges, users, and platform settings",
}

// Mock data - replace with actual API calls
const stats = {
  totalUsers: 1247,
  totalChallenges: 60,
  totalSolves: 5420,
  activeUsers: 89,
  systemHealth: {
    database: "healthy" as const,
    redis: "healthy" as const,
    storage: "healthy" as const,
  },
  recentActivity: [
    { id: 1, action: "Challenge Created", user: "admin", timestamp: "2 minutes ago" },
    { id: 2, action: "User Registered", user: "new_hacker", timestamp: "5 minutes ago" },
    { id: 3, action: "Flag Submitted", user: "player123", timestamp: "10 minutes ago" },
  ],
}

export default function AdminPage() {
  return (
    <div className="container mx-auto py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
        <p className="text-muted-foreground">
          Manage challenges, users, and monitor platform health
        </p>
      </div>

      {/* Stats Grid */}
      <div className="mb-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Users"
          value={stats.totalUsers.toString()}
          icon={<Users className="h-4 w-4" />}
          trend="+12 this week"
        />
        <StatCard
          title="Challenges"
          value={stats.totalChallenges.toString()}
          icon={<Shield className="h-4 w-4" />}
          trend="5 pending review"
        />
        <StatCard
          title="Total Solves"
          value={stats.totalSolves.toString()}
          icon={<Trophy className="h-4 w-4" />}
          trend="+234 today"
        />
        <StatCard
          title="Active Now"
          value={stats.activeUsers.toString()}
          icon={<Activity className="h-4 w-4" />}
          trend="Live"
        />
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="challenges">Challenges</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <Card className="col-span-2">
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest actions on the platform</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {stats.recentActivity.map((activity) => (
                    <div key={activity.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Activity className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm">{activity.action}</span>
                        <span className="text-sm text-muted-foreground">by {activity.user}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{activity.timestamp}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>System Health</CardTitle>
                <CardDescription>Service status</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <HealthStatus 
                  name="Database" 
                  status={stats.systemHealth.database} 
                  icon={<Database className="h-4 w-4" />}
                />
                <HealthStatus 
                  name="Redis Cache" 
                  status={stats.systemHealth.redis} 
                  icon={<Activity className="h-4 w-4" />}
                />
                <HealthStatus 
                  name="Storage" 
                  status={stats.systemHealth.storage} 
                  icon={<Shield className="h-4 w-4" />}
                />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="challenges" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Challenge Management</CardTitle>
              <CardDescription>Create, edit, and manage challenges</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Challenge management interface will be implemented here.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>User Management</CardTitle>
              <CardDescription>Manage user accounts and permissions</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                User management interface will be implemented here.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="system" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Settings</CardTitle>
              <CardDescription>Configure platform settings</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                System configuration interface will be implemented here.
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: string
  icon: React.ReactNode
  trend: string
}

function StatCard({ title, value, icon, trend }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{trend}</p>
      </CardContent>
    </Card>
  )
}

interface HealthStatusProps {
  name: string
  status: "healthy" | "degraded" | "down"
  icon: React.ReactNode
}

function HealthStatus({ name, status, icon }: HealthStatusProps) {
  const statusConfig = {
    healthy: { color: "text-green-500", bg: "bg-green-500", label: "Healthy" },
    degraded: { color: "text-yellow-500", bg: "bg-yellow-500", label: "Degraded" },
    down: { color: "text-red-500", bg: "bg-red-500", label: "Down" },
  }

  const config = statusConfig[status]

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm">{name}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${config.bg}`} />
        <span className={`text-sm ${config.color}`}>{config.label}</span>
      </div>
    </div>
  )
}
