"use client";

import { ResponsiveContainer, Tooltip, Treemap } from "recharts";
import type { Position } from "@/lib/types";
import { pct, usd } from "@/lib/format";

interface Props {
  positions: Position[];
}

// Map a P&L percentage to a green/red shade.
function colorFor(pnlPct: number): string {
  const clamped = Math.max(-8, Math.min(8, pnlPct));
  const intensity = Math.abs(clamped) / 8; // 0..1
  if (clamped >= 0) {
    const g = Math.round(40 + intensity * 150);
    return `rgb(22, ${g + 50}, 90)`;
  }
  const r = Math.round(120 + intensity * 130);
  return `rgb(${r}, 40, 60)`;
}

export default function Heatmap({ positions }: Props) {
  const data = positions
    .filter((p) => p.market_value > 0)
    .map((p) => ({
      name: p.ticker,
      size: p.market_value,
      pnlPct: p.unrealized_pnl_percent,
      pnl: p.unrealized_pnl,
    }));

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title">Positions Heatmap</div>
      <div className="flex-1 p-2">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            No positions yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              stroke="#0d1117"
              isAnimationActive={false}
              content={<HeatCell />}
            >
              <Tooltip
                contentStyle={{
                  background: "#161b22",
                  border: "1px solid #30363d",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(_v, _n, item: { payload?: { pnl?: number; pnlPct?: number } }) => {
                  const p = item?.payload;
                  return [`${usd(p?.pnl)} (${pct(p?.pnlPct)})`, "Unrealized P&L"];
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPct?: number;
}

function HeatCell({ x = 0, y = 0, width = 0, height = 0, name, pnlPct = 0 }: CellProps) {
  const show = width > 44 && height > 24;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={colorFor(pnlPct)} stroke="#0d1117" />
      {show && (
        <>
          <text x={x + 5} y={y + 16} fill="#fff" fontSize={12} fontWeight={700}>
            {name}
          </text>
          <text x={x + 5} y={y + 30} fill="rgba(255,255,255,0.85)" fontSize={10}>
            {pct(pnlPct)}
          </text>
        </>
      )}
    </g>
  );
}
