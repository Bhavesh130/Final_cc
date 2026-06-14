"use client";

import type { ConnectionStatus } from "@/lib/types";

const MAP: Record<ConnectionStatus, { color: string; label: string }> = {
  connected: { color: "bg-up", label: "Live" },
  reconnecting: { color: "bg-accent", label: "Reconnecting" },
  disconnected: { color: "bg-down", label: "Disconnected" },
};

export default function StatusDot({ status }: { status: ConnectionStatus }) {
  const { color, label } = MAP[status];
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <span className={`relative flex h-2.5 w-2.5`}>
        {status === "connected" && (
          <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${color} opacity-60`} />
        )}
        <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
      </span>
      {label}
    </div>
  );
}
