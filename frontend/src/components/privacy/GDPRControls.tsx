"use client";

import { useState } from "react";
import { Download, Trash2, AlertTriangle, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface GDPRControlsProps {
  userId: string;
}

export function GDPRControls({ userId }: GDPRControlsProps) {
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [deletionDaysRemaining, setDeletionDaysRemaining] = useState<number | null>(null);

  const handleDataExport = async () => {
    setIsExporting(true);
    try {
      const response = await fetch("/api/v1/privacy/user/request-export", {
        method: "POST",
      });
      const data = await response.json();
      setExportStatus(data.status);
    } catch (error) {
      console.error("Export failed:", error);
    } finally {
      setIsExporting(false);
      setExportDialogOpen(false);
    }
  };

  const handleAccountDeletion = async () => {
    setIsDeleting(true);
    try {
      const response = await fetch("/api/v1/privacy/user/request-deletion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "User requested" }),
      });
      const data = await response.json();
      setDeletionDaysRemaining(data.days_remaining);
    } catch (error) {
      console.error("Deletion request failed:", error);
    } finally {
      setIsDeleting(false);
      setDeleteDialogOpen(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Your Data & Privacy</h3>

      {/* Data Export */}
      <div className="flex items-center justify-between p-4 border rounded-lg">
        <div className="flex items-center gap-3">
          <Download className="w-5 h-5 text-slate-500" />
          <div>
            <p className="font-medium">Download My Data</p>
            <p className="text-sm text-slate-500">
              Export all your data in JSON and CSV format (GDPR Right to Access)
            </p>
          </div>
        </div>
        <Dialog open={exportDialogOpen} onOpenChange={setExportDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="outline">Request Export</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Download Your Data</DialogTitle>
              <DialogDescription>
                We'll prepare an export of all your data including:
                <ul className="list-disc pl-5 mt-2 space-y-1">
                  <li>Profile information</li>
                  <li>Solve history</li>
                  <li>Submission history</li>
                  <li>Hint usage</li>
                  <li>Session history</li>
                </ul>
                The export will be available for 7 days.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setExportDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleDataExport} disabled={isExporting}>
                {isExporting ? "Preparing..." : "Request Export"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {exportStatus && (
        <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700">
          <CheckCircle className="w-4 h-4" />
          <span className="text-sm">Export {exportStatus}</span>
        </div>
      )}

      {/* Account Deletion */}
      <div className="flex items-center justify-between p-4 border border-red-200 rounded-lg bg-red-50">
        <div className="flex items-center gap-3">
          <Trash2 className="w-5 h-5 text-red-500" />
          <div>
            <p className="font-medium text-red-700">Delete Account</p>
            <p className="text-sm text-red-600">
              Permanently delete your account and associated data (GDPR Right to be Forgotten)
            </p>
          </div>
        </div>
        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogTrigger asChild>
            <Button variant="destructive">Delete Account</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <AlertTriangle className="w-5 h-5" />
                Delete Account
              </DialogTitle>
              <DialogDescription>
                This action cannot be undone. Your account will be:
                <ul className="list-disc pl-5 mt-2 space-y-1">
                  <li>Marked for deletion with a 30-day grace period</li>
                  <li>Your solves will be anonymized (statistics preserved)</li>
                  <li>All personal information will be removed</li>
                  <li>You can cancel during the grace period</li>
                </ul>
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleAccountDeletion}
                disabled={isDeleting}
              >
                {isDeleting ? "Processing..." : "I Understand, Delete My Account"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {deletionDaysRemaining !== null && deletionDaysRemaining > 0 && (
        <div className="flex items-center gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">
            Deletion scheduled in {deletionDaysRemaining} days.{" "}
            <button className="underline">Cancel deletion</button>
          </span>
        </div>
      )}
    </div>
  );
}
