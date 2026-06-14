"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PriceMap } from "@/lib/types";
import type { PricePoint } from "@/lib/usePrices";
import { num, pct, usd } from "@/lib/format";

interface Props {
  ticker: string | null;
  prices: PriceMap;
  history: Record<string, PricePoint[]>;
}

export default function MainChart({ ticker, prices, history }: Props) {
  const live = ticker ? prices[ticker] : null;
  const points = (ticker ? history[ticker] : []) ?? [];
  const data = points.map((p) => ({
    time: new Date(p.t * 1000).toLocaleTimeString("en-US", {
      hour12: false,
    }),
    price: p.price,
  }));

  const changePct = live?.change_percent ?? 0;
  const lineColor = changePct >= 0 ? "#16c784" : "#ea3943";

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Chart</span>
        {ticker && live && (
          <span className="flex items-center gap-3 text-sm normal-case tracking-normal">
            <span className="font-bold text-gray-100">{ticker}</span>
            <span className="tabular-nums text-gray-100">{usd(live.price)}</span>
            <span
              className={
                changePct > 0 ? "text-up" : changePct < 0 ? "text-down" : "text-muted"
              }
            >
              {pct(changePct)}
            </span>
          </span>
        )}
      </div>
      <div className="flex-1 p-2">
        {!ticker ? (
          <Empty label="Select a ticker to view its chart" />
        ) : data.length < 2 ? (
          <Empty label="Accumulating live data…" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
                width={48}
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
                formatter={(v: number) => [usd(v), "Price"]}
              />
              <Line
                type="monotone"
                dataKey="price"
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center text-sm text-muted">{label}</div>
  );
}
