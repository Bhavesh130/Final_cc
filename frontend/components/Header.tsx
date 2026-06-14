"use client";

import type { ConnectionStatus, Portfolio } from "@/lib/types";
import { pct, pnlColor, usd } from "@/lib/format";
import StatusDot from "./StatusDot";

interface Props {
  portfolio: Portfolio | null;
  status: ConnectionStatus;
}

export default function Header({ portfolio, status }: Props) {
  const totalValue = portfolio?.total_value ?? 0;
  const cash = portfolio?.cash_balance ?? 0;
  const pnl = portfolio?.total_unrealized_pnl ?? 0;
  const pnlPct = portfolio && portfolio.positions_value
    ? (pnl / (portfolio.positions_value - pnl || 1)) * 100
    : 0;

  return (
    <header className="flex items-center justify-between border-b border-border bg-panel px-4 py-2.5">
      <div className="flex items-baseline gap-2">
        <span className="text-lg font-bold tracking-tight text-accent">FinAlly</span>
        <span className="hidden text-[11px] text-muted sm:inline">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <Metric label="Portfolio Value" value={usd(totalValue)} />
        <Metric
          label="Unrealized P&L"
          value={`${usd(pnl)} (${pct(pnlPct)})`}
          className={pnlColor(pnl)}
        />
        <Metric label="Cash" value={usd(cash)} />
        <StatusDot status={status} />
      </div>
    </header>
  );
}

function Metric({
  label,
  value,
  className = "",
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="text-right">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`text-sm font-semibold tabular-nums ${className}`}>{value}</div>
    </div>
  );
}
