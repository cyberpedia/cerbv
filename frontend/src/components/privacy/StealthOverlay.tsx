"use client";

import { EyeOff, Lock } from "lucide-react";

interface StealthOverlayProps {
  visible?: boolean;
  message?: string;
}

export function StealthOverlay({
  visible = true,
  message = "Solve information hidden in stealth mode",
}: StealthOverlayProps) {
  if (!visible) return null;

  return (
    <div className="flex flex-col items-center justify-center p-8 bg-slate-50 border border-slate-200 rounded-lg">
      <div className="flex items-center gap-3 mb-2">
        <EyeOff className="w-6 h-6 text-slate-500" />
        <Lock className="w-6 h-6 text-slate-500" />
      </div>
      <p className="text-slate-600 text-center max-w-md">{message}</p>
    </div>
  );
}
