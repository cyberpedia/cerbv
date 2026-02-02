"use client";

import { Shield } from "lucide-react";

interface AnonymousBadgeProps {
  mode: "anonymous" | "stealth" | "delayed";
  className?: string;
}

export function AnonymousBadge({ mode, className = "" }: AnonymousBadgeProps) {
  const labels = {
    anonymous: "Anonymous Mode Active",
    stealth: "Stealth Mode Active",
    delayed: "Scoreboard Frozen",
  };

  const descriptions = {
    anonymous: "Team names are masked",
    stealth: "Solves are hidden",
    delayed: "Updates are delayed",
  };

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-full text-amber-700 text-sm ${className}`}
    >
      <Shield className="w-4 h-4" />
      <div className="flex flex-col">
        <span className="font-medium">{labels[mode]}</span>
        <span className="text-xs opacity-75">{descriptions[mode]}</span>
      </div>
    </div>
  );
}
