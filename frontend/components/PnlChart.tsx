"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Snapshot } from "@/lib/types";
import { num, usd } from "@/lib/format";

export default function PnlChart({ snapshots }: { snapshots: Snapshot[] }) {
  const data = snapshots.map((s) => ({
    time: new Date(s.recorded_at).toLocaleTimeString("en-US", { hour12: false }),
    value: s.total_value,
  }));

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title">Portfolio Value</div>
      <div className="flex-1 p-2">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            Building history…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#209dd7" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="#209dd7" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#30363d" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fill: "#8b949e", fontSize: 10 }}
                minTickGap={40}
                stroke="#30363d"
              />
              <YAxis
                domain={["auto", "auto"]}
                tick={{ fill: "#8b949e", fontSize: 10 }}
                tickFormatter={(v) => num(v, 0)}
                width={56}
                stroke="#30363d"
              />
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                labelStyle={{ color: "#8b949e" }}
                formatter={(v: number) => [usd(v), "Value"]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#209dd7"
                strokeWidth={2}
                fill="url(#pnlFill)"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
