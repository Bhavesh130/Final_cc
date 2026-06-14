"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePrices } from "@/lib/usePrices";
import type { Portfolio, Snapshot, WatchlistItem } from "@/lib/types";
import Header from "@/components/Header";
import Watchlist from "@/components/Watchlist";
import MainChart from "@/components/MainChart";
import Heatmap from "@/components/Heatmap";
import PnlChart from "@/components/PnlChart";
import Positions from "@/components/Positions";
import TradeBar from "@/components/TradeBar";
import ChatPanel from "@/components/ChatPanel";

export default function Page() {
  const { prices, history, historyVersion, status } = usePrices();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const refreshPortfolio = useCallback(() => {
    api.getPortfolio().then(setPortfolio).catch(() => {});
  }, []);
  const refreshWatchlist = useCallback(() => {
    api.getWatchlist().then(setWatchlist).catch(() => {});
  }, []);
  const refreshHistory = useCallback(() => {
    api.getHistory().then(setSnapshots).catch(() => {});
  }, []);

  // Initial load.
  useEffect(() => {
    refreshPortfolio();
    refreshWatchlist();
    refreshHistory();
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  // Default the selected ticker to the first watchlist symbol.
  useEffect(() => {
    if (!selectedRef.current && watchlist.length > 0) {
      setSelected(watchlist[0].ticker);
    }
  }, [watchlist]);

  // Light polling so positions/heatmap/value stay fresh from server-side prices.
  useEffect(() => {
    const a = setInterval(refreshPortfolio, 4000);
    const b = setInterval(refreshHistory, 15000);
    return () => {
      clearInterval(a);
      clearInterval(b);
    };
  }, [refreshPortfolio, refreshHistory]);

  const handleTrade = useCallback(
    async (ticker: string, qty: number, side: "buy" | "sell") => {
      await api.trade(ticker, qty, side);
      refreshPortfolio();
      refreshHistory();
    },
    [refreshPortfolio, refreshHistory]
  );

  const handleAdd = useCallback(
    async (ticker: string) => {
      const res = await api.addTicker(ticker);
      setWatchlist(res.watchlist);
      setSelected(ticker.toUpperCase());
    },
    []
  );

  const handleRemove = useCallback(
    async (ticker: string) => {
      try {
        const res = await api.removeTicker(ticker);
        setWatchlist(res.watchlist);
      } catch {
        /* ignore */
      }
    },
    []
  );

  const handleChatResponse = useCallback(() => {
    refreshPortfolio();
    refreshWatchlist();
    refreshHistory();
  }, [refreshPortfolio, refreshWatchlist, refreshHistory]);

  return (
    <div className="flex h-screen flex-col">
      <Header portfolio={portfolio} status={status} />
      <TradeBar prices={prices} defaultTicker={selected} onTrade={handleTrade} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 overflow-hidden p-2 lg:grid-cols-[260px_1fr_360px]">
        {/* Watchlist */}
        <div className="min-h-0 lg:row-span-1">
          <Watchlist
            items={watchlist}
            prices={prices}
            history={history}
            historyVersion={historyVersion}
            selected={selected}
            onSelect={setSelected}
            onRemove={handleRemove}
            onAdd={handleAdd}
          />
        </div>

        {/* Center column */}
        <div className="flex min-h-0 flex-col gap-2">
          <div className="min-h-0 flex-[5]">
            <MainChart ticker={selected} prices={prices} history={history} />
          </div>
          <div className="grid min-h-0 flex-[4] grid-cols-1 gap-2 md:grid-cols-2">
            <Heatmap positions={portfolio?.positions ?? []} />
            <PnlChart snapshots={snapshots} />
          </div>
          <div className="min-h-0 flex-[4]">
            <Positions positions={portfolio?.positions ?? []} onSelect={setSelected} />
          </div>
        </div>

        {/* Chat */}
        <div className="min-h-0">
          <ChatPanel onAfterResponse={handleChatResponse} />
        </div>
      </div>
    </div>
  );
}
