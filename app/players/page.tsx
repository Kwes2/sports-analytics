// app/players/page.tsx
import { getPlayersIndex } from "@/lib/data";
import PlayersTableClient from "./PlayersTableClient";

export default function PlayersPage() {
  const players = getPlayersIndex("2026-27");

  return (
    <div className="space-y-6">
      <div className="border-b border-surface-border pb-5">
        <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
          Players Overview
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Interactive data grid across all active 2026-27 NBA players. Filter by position, search, and click any column header to sort by role, volume, or regularized impact (EPM).
        </p>
      </div>

      <PlayersTableClient initialPlayers={players} />
    </div>
  );
}