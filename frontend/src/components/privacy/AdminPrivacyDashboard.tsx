"use client";

import { useState, useEffect } from "react";
import { Shield, Clock, Users, Trash2, Download, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AdminPrivacyDashboardProps {
  isAdmin?: boolean;
}

export function AdminPrivacyDashboard({ isAdmin = true }: AdminPrivacyDashboardProps) {
  const [privacyMode, setPrivacyMode] = useState("full");
  const [delayedMinutes, setDelayedMinutes] = useState(15);
  const [metrics, setMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchMetrics();
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await fetch("/api/v1/privacy/admin/privacy/metrics");
      const data = await response.json();
      setMetrics(data);
      setPrivacyMode(data.current_mode);
    } catch (error) {
      console.error("Failed to fetch metrics:", error);
    }
  };

  const updatePrivacyMode = async () => {
    setLoading(true);
    try {
      await fetch("/api/v1/privacy/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: privacyMode,
          delayed_minutes: delayedMinutes,
        }),
      });
      fetchMetrics();
    } catch (error) {
      console.error("Failed to update privacy mode:", error);
    } finally {
      setLoading(false);
    }
  };

  const runRetentionCheck = async () => {
    setLoading(true);
    try {
      await fetch("/api/v1/privacy/admin/retention/run-check", {
        method: "POST",
      });
      fetchMetrics();
    } catch (error) {
      console.error("Failed to run retention check:", error);
    } finally {
      setLoading(false);
    }
  };

  const modeDescriptions: Record<string, string> = {
    full: "All data visible - standard operation",
    anonymous: "Team names masked as 'Team #1234'",
    stealth: "Solves hidden completely, only counts shown",
    delayed: "Scoreboard updates batched and delayed",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Shield className="w-6 h-6" />
        <h2 className="text-2xl font-bold">Privacy Controls</h2>
      </div>

      {/* Privacy Mode Selector */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5" />
            Privacy Mode
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <Select value={privacyMode} onValueChange={setPrivacyMode}>
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="full">Full Visibility</SelectItem>
                <SelectItem value="anonymous">Anonymous</SelectItem>
                <SelectItem value="stealth">Stealth</SelectItem>
                <SelectItem value="delayed">Delayed</SelectItem>
              </SelectContent>
            </Select>

            {privacyMode === "delayed" && (
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-500" />
                <input
                  type="number"
                  value={delayedMinutes}
                  onChange={(e) => setDelayedMinutes(Number(e.target.value))}
                  className="w-20 px-3 py-2 border rounded"
                  min="1"
                  max="120"
                />
                <span className="text-sm text-slate-600">minutes delay</span>
              </div>
            )}

            <Button onClick={updatePrivacyMode} disabled={loading}>
              {loading ? "Saving..." : "Apply"}
            </Button>
          </div>

          <p className="text-sm text-slate-600">{modeDescriptions[privacyMode]}</p>
        </CardContent>
      </Card>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-amber-100 rounded-full">
                <Download className="w-6 h-6 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{metrics?.total_exports_pending || 0}</p>
                <p className="text-sm text-slate-600">Pending Exports</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-red-100 rounded-full">
                <Trash2 className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{metrics?.total_deletions_pending || 0}</p>
                <p className="text-sm text-slate-600">Pending Deletions</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 rounded-full">
                <Clock className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {metrics?.queue_stats?.ready_to_reveal || 0}
                </p>
                <p className="text-sm text-slate-600">Ready to Reveal</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Retention Policies */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Retention Compliance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {Object.entries(metrics?.retention_compliance || {}).map(([key, value]: [string, any]) => (
              <div key={key} className="flex items-center justify-between p-3 border rounded">
                <div>
                  <p className="font-medium capitalize">{key.replace("_", " ")}</p>
                  <p className="text-sm text-slate-500">
                    {value.days_until_action
                      ? `${value.days_until_action} days until action`
                      : "No action needed"}
                  </p>
                </div>
                <Badge variant={value.compliant ? "default" : "destructive"}>
                  {value.compliant ? "Compliant" : "Action Required"}
                </Badge>
              </div>
            ))}
          </div>

          <Button variant="outline" className="mt-4" onClick={runRetentionCheck} disabled={loading}>
            <Clock className="w-4 h-4 mr-2" />
            Run Retention Check
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
