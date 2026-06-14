"use client";

import { useEffect, useRef, useState } from "react";
import type { PriceMap, WatchlistItem } from "@/lib/types";
import type { PricePoint } from "@/lib/usePrices";
import { num, pct } from "@/lib/format";
import Sparkline from "./Sparkline";

interface Props {
  items: WatchlistItem[];
  prices: PriceMap;
  history: Record<string, PricePoint[]>;
  historyVersion: number;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<void> | void;
}

export default function Watchlist({
  items,
  prices,
  history,
  selected,
  onSelect,
  onRemove,
  onAdd,
}: Props) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = draft.trim().toUpperCase();
    if (!t) return;
    setError(null);
    try {
      await onAdd(t);
      setDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add");
    }
  }

  return (
    <div className="panel flex h-full flex-col">
      <div className="panel-title flex items-center justify-between">
        <span>Watchlist</span>
        <span>{items.length} symbols</span>
      </div>

      <form onSubmit={submit} className="flex gap-2 border-b border-border p-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Add ticker…"
          className="input w-full uppercase"
          aria-label="Add ticker"
        />
        <button type="submit" className="btn-submit shrink-0">
          Add
        </button>
      </form>
      {error && <div className="px-3 py-1 text-xs text-down">{error}</div>}

      <div className="flex-1 overflow-y-auto">
        <table className="w-full text-sm">
          <tbody>
            {items.map((item) => {
              const live = prices[item.ticker];
              const price = live?.price ?? item.price;
              const changePct = live?.change_percent ?? item.change_percent;
              const spark = (history[item.ticker] ?? []).map((p: PricePoint) => p.price);
              return (
                <tr
                  key={item.ticker}
                  onClick={() => onSelect(item.ticker)}
                  className={`group cursor-pointer border-b border-border/50 hover:bg-white/5 ${
                    selected === item.ticker ? "bg-blue/10" : ""
                  }`}
                >
                  <td className="py-1.5 pl-3 font-semibold">{item.ticker}</td>
                  <td className="py-1.5 text-right tabular-nums">
                    <FlashPrice price={price} />
                  </td>
                  <td
                    className={`py-1.5 pr-2 text-right tabular-nums text-xs ${
                      changePct > 0 ? "text-up" : changePct < 0 ? "text-down" : "text-muted"
                    }`}
                  >
                    {pct(changePct)}
                  </td>
                  <td className="py-1.5 pr-2">
                    <Sparkline data={spark} />
                  </td>
                  <td className="py-1.5 pr-2 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(item.ticker);
                      }}
                      className="text-muted opacity-0 transition-opacity hover:text-down group-hover:opacity-100"
                      aria-label={`Remove ${item.ticker}`}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FlashPrice({ price }: { price: number | null }) {
  const prev = useRef<number | null>(price);
  const [flash, setFlash] = useState<{ dir: "up" | "down"; key: number } | null>(null);
  const counter = useRef(0);

  useEffect(() => {
    if (price === null) return;
    if (prev.current !== null && price !== prev.current) {
      counter.current += 1;
      setFlash({ dir: price > prev.current ? "up" : "down", key: counter.current });
    }
    prev.current = price;
  }, [price]);

  return (
    <span
      key={flash?.key}
      className={`inline-block rounded px-1 ${
        flash ? (flash.dir === "up" ? "animate-flash-up" : "animate-flash-down") : ""
      }`}
    >
      {num(price)}
    </span>
  );
}
