"use client";

import { useState } from "react";
import type { PriceMap } from "@/lib/types";
import { usd } from "@/lib/format";

interface Props {
  prices: PriceMap;
  defaultTicker: string | null;
  onTrade: (ticker: string, qty: number, side: "buy" | "sell") => Promise<void>;
}

export default function TradeBar({ prices, defaultTicker, onTrade }: Props) {
  const [ticker, setTicker] = useState("");
  const [qty, setQty] = useState("1");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  const effectiveTicker = (ticker || defaultTicker || "").toUpperCase();
  const live = prices[effectiveTicker];
  const quantity = parseFloat(qty);
  const estimate = live && !isNaN(quantity) ? live.price * quantity : null;

  async function execute(side: "buy" | "sell") {
    if (!effectiveTicker || isNaN(quantity) || quantity <= 0) {
      setMsg({ kind: "err", text: "Enter a ticker and positive quantity." });
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      await onTrade(effectiveTicker, quantity, side);
      setMsg({
        kind: "ok",
        text: `${side === "buy" ? "Bought" : "Sold"} ${quantity} ${effectiveTicker}`,
      });
    } catch (err) {
      setMsg({ kind: "err", text: err instanceof Error ? err.message : "Trade failed" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel flex items-center gap-3 p-2">
      <span className="panel-title border-0 px-1">Trade</span>
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        placeholder={defaultTicker ?? "Ticker"}
        className="input w-28 uppercase"
        aria-label="Trade ticker"
      />
      <input
        value={qty}
        onChange={(e) => setQty(e.target.value)}
        type="number"
        min="0"
        step="any"
        className="input w-24"
        aria-label="Trade quantity"
      />
      <button className="btn-buy" onClick={() => execute("buy")} disabled={busy}>
        Buy
      </button>
      <button className="btn-sell" onClick={() => execute("sell")} disabled={busy}>
        Sell
      </button>
      {estimate !== null && (
        <span className="text-xs text-muted">≈ {usd(estimate)}</span>
      )}
      {msg && (
        <span className={`text-xs ${msg.kind === "ok" ? "text-up" : "text-down"}`}>
          {msg.text}
        </span>
      )}
    </div>
  );
}
