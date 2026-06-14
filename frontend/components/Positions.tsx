"use client";

import type { Position } from "@/lib/types";
import { num, pct, pnlColor, usd } from "@/lib/format";

interface Props {
  positions: Position[];
  onSelect: (ticker: string) => void;
}

export default function Positions({ positions, onSelect }: Props) {
  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title">Positions</div>
      <div className="flex-1 overflow-y-auto">
        {positions.length === 0 ? (
          <div className="flex h-full items-center justify-center p-4 text-sm text-muted">
            No open positions. Use the trade bar or ask the AI to buy something.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-panel text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-3 py-1.5 text-left">Ticker</th>
                <th className="px-2 py-1.5 text-right">Qty</th>
                <th className="px-2 py-1.5 text-right">Avg Cost</th>
                <th className="px-2 py-1.5 text-right">Price</th>
                <th className="px-2 py-1.5 text-right">Mkt Value</th>
                <th className="px-3 py-1.5 text-right">Unrealized P&L</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => (
                <tr
                  key={p.ticker}
                  onClick={() => onSelect(p.ticker)}
                  className="cursor-pointer border-b border-border/50 hover:bg-white/5"
                >
                  <td className="px-3 py-1.5 font-semibold">{p.ticker}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{num(p.quantity, 4)}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{usd(p.avg_cost)}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{usd(p.current_price)}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{usd(p.market_value)}</td>
                  <td className={`px-3 py-1.5 text-right tabular-nums ${pnlColor(p.unrealized_pnl)}`}>
                    {usd(p.unrealized_pnl)}{" "}
                    <span className="text-xs">({pct(p.unrealized_pnl_percent)})</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
