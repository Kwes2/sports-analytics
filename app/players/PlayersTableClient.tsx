// app/players/PlayersTableClient.tsx
"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { PlayerIndexItem, PositionGroup } from "@/types/analytics";
import { Search, ArrowUpDown, ChevronUp, ChevronDown } from "lucide-react";

type SortField =
  | "player_name"
  | "minutes_per_game"
  | "pts_per_100"
  | "ast_per_100"
  | "reb_per_100"
  | "usage_pct"
  | "true_shooting_pct"
  | "net_epm"
  | "self_creation_rate"
  | "rim_pressure_rate";

export default function PlayersTableClient({
  initialPlayers,
}: {
  initialPlayers: PlayerIndexItem[];
}) {
  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("net_epm");
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const filteredPlayers = useMemo(() => {
    return initialPlayers
      .filter((p) => {
        const matchesSearch =
          p.player_name.toLowerCase().includes(search.toLowerCase()) ||
          p.team_abbrev.toLowerCase().includes(search.toLowerCase());
        const matchesPosition =
          positionFilter === "ALL" || p.position.toUpperCase() === positionFilter;
        return matchesSearch && matchesPosition;
      })
      .sort((a, b) => {
        let valA: any = a[sortField as keyof PlayerIndexItem];
        let valB: any = b[sortField as keyof PlayerIndexItem];

        // Handle nested percentile fallback
        if (sortField === "self_creation_rate") {
          valA = a.percentile_ranks.self_creation ?? -999;
          valB = b.percentile_ranks.self_creation ?? -999;
        } else if (sortField === "rim_pressure_rate") {
          valA = a.percentile_ranks.rim_pressure ?? -999;
          valB = b.percentile_ranks.rim_pressure ?? -999;
        }

        if (valA === null || valA === undefined) valA = -999;
        if (valB === null || valB === undefined) valB = -999;

        if (typeof valA === "string") {
          return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return sortAsc ? valA - valB : valB - valA;
      });
  }, [initialPlayers, search, positionFilter, sortField, sortAsc]);

  return (
    <div className="space-y-4">
      {/* Search and Filters Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search players or teams..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-surface py-2 pl-9 pr-4 text-xs font-mono text-white placeholder-gray-500 focus:border-accent focus:outline-none"
          />
        </div>

        {/* Position Filter Pills */}
        <div className="flex items-center gap-1.5 font-mono text-xs">
          {["ALL", "GUARD", "FORWARD", "CENTER"].map((pos) => (
            <button
              key={pos}
              onClick={() => setPositionFilter(pos)}
              className={`rounded-lg px-3 py-1.5 transition-colors ${
                positionFilter === pos
                  ? "bg-accent text-black font-bold"
                  : "bg-surface border border-surface-border text-gray-400 hover:text-white"
              }`}
            >
              {pos}
            </button>
          ))}
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-surface-border bg-surface-elevated text-gray-400 select-none">
              <tr>
                <th className="px-4 py-3 font-semibold text-white cursor-pointer" onClick={() => handleSort("player_name")}>
                  <div className="flex items-center gap-1">Player <SortIcon field="player_name" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("minutes_per_game")}>
                  <div className="flex items-center justify-end gap-1">MPG <SortIcon field="minutes_per_game" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("pts_per_100")}>
                  <div className="flex items-center justify-end gap-1">PTS/100 <SortIcon field="pts_per_100" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("ast_per_100")}>
                  <div className="flex items-center justify-end gap-1">AST/100 <SortIcon field="ast_per_100" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("reb_per_100")}>
                  <div className="flex items-center justify-end gap-1">REB/100 <SortIcon field="reb_per_100" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("usage_pct")}>
                  <div className="flex items-center justify-end gap-1">USG% <SortIcon field="usage_pct" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("true_shooting_pct")}>
                  <div className="flex items-center justify-end gap-1">TS% <SortIcon field="true_shooting_pct" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer text-accent" onClick={() => handleSort("net_epm")}>
                  <div className="flex items-center justify-end gap-1 font-bold">NET EPM <SortIcon field="net_epm" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-4 py-3 text-left">Archetype</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50 text-gray-300">
              {filteredPlayers.slice(0, 100).map((p) => {
                const epm = p.net_epm;
                return (
                  <tr key={p.player_id} className="hover:bg-surface-elevated/40 transition-colors">
                    <td className="px-4 py-2.5 font-medium text-white flex items-center gap-3">
                      <img
                        src={p.headshot_url}
                        alt={p.player_name}
                        className="h-8 w-8 rounded-full bg-surface-elevated object-cover border border-surface-border"
                        loading="lazy"
                        onError={(e) => {
                          (e.target as HTMLElement).style.display = "none";
                        }}
                      />
                      <div>
                        <Link href={`/player/${p.player_id}`} className="hover:text-accent hover:underline font-semibold block">
                          {p.player_name}
                        </Link>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {p.team_abbrev} · {p.position}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right">{p.minutes_per_game}</td>
                    <td className="px-3 py-2.5 text-right font-bold text-white">{p.pts_per_100}</td>
                    <td className="px-3 py-2.5 text-right">{p.ast_per_100}</td>
                    <td className="px-3 py-2.5 text-right">{p.reb_per_100}</td>
                    <td className="px-3 py-2.5 text-right">{p.usage_pct}%</td>
                    <td className="px-3 py-2.5 text-right">
                      {p.true_shooting_pct ? `${(p.true_shooting_pct * 100).toFixed(1)}%` : "-"}
                    </td>
                    <td className="px-3 py-2.5 text-right font-bold">
                      {epm !== null && epm !== undefined ? (
                        <span className={epm > 0 ? "text-emerald" : epm < 0 ? "text-crimson" : "text-gray-400"}>
                          {epm > 0 ? `+${epm.toFixed(1)}` : epm.toFixed(1)}
                        </span>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-left">
                      {p.archetype ? (
                        <span className="inline-block rounded bg-surface-elevated px-2 py-0.5 text-[10px] font-medium text-gray-300 border border-surface-border truncate max-w-[170px]">
                          {p.archetype}
                        </span>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="border-t border-surface-border bg-surface-elevated/40 px-4 py-3 text-xs text-gray-500 font-mono">
          Showing {Math.min(100, filteredPlayers.length)} of {filteredPlayers.length} players
        </div>
      </div>
    </div>
  );
}

function SortIcon({ field, current, asc }: { field: SortField; current: SortField; asc: boolean }) {
  if (field !== current) return <ArrowUpDown className="h-3 w-3 text-gray-600 opacity-60" />;
  return asc ? <ChevronUp className="h-3 w-3 text-accent" /> : <ChevronDown className="h-3 w-3 text-accent" />;
}