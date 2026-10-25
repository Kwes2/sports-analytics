"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import Link from "next/link";
import { PlayerIndexItem } from "@/types/analytics";
import { Search, ArrowUpDown, ChevronUp, ChevronDown, Settings2 } from "lucide-react";

type SortField = keyof PlayerIndexItem | "self_creation_rate" | "rim_pressure_rate";

const AVAILABLE_COLUMNS = [
  { id: "minutes_per_game", label: "MPG" },
  { id: "pts_per_100", label: "PTS/100" },
  { id: "ast_per_100", label: "AST/100" },
  { id: "reb_per_100", label: "REB/100" },
  { id: "usage_pct", label: "Usage %" },
  { id: "true_shooting_pct", label: "True Shooting %" },
  { id: "net_epm", label: "Net Impact" },
  { id: "offensive_epm", label: "Offensive Impact" },
  { id: "defensive_epm", label: "Defensive Impact" },
  { id: "self_creation_rate", label: "Self-Creation %" },
  { id: "rim_pressure_rate", label: "Rim Attack %" },
];

export default function PlayersTableClient({
  initialPlayers,
}: {
  initialPlayers: PlayerIndexItem[];
}) {
  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("net_epm");
  const [sortAsc, setSortAsc] = useState(false);
  
  const [showColumnsMenu, setShowColumnsMenu] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
    new Set(["minutes_per_game", "pts_per_100", "usage_pct", "true_shooting_pct", "net_epm", "rim_pressure_rate"])
  );
  
  const menuRef = useRef<HTMLDivElement>(null);

  // Close columns menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowColumnsMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false); // Default descending for stats
    }
  };

  const toggleColumn = (colId: string) => {
    const next = new Set(visibleColumns);
    if (next.has(colId)) next.delete(colId);
    else next.add(colId);
    setVisibleColumns(next);
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
        let valA: any = (a as any)[sortField];
        let valB: any = (b as any)[sortField];

        // Handle nested percentile fallbacks
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
      {/* Controls Bar */}
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

        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          {/* Position Filters */}
          <div className="flex items-center gap-1">
            {["ALL", "GUARD", "FORWARD", "CENTER"].map((pos) => (
              <button
                key={pos}
                onClick={() => setPositionFilter(pos)}
                className={`rounded-lg px-3 py-1.5 transition-colors ${
                  positionFilter === pos
                    ? "bg-amber-400 text-black font-bold"
                    : "bg-surface border border-surface-border text-gray-400 hover:text-white"
                }`}
              >
                {pos}
              </button>
            ))}
          </div>

          {/* Columns Dropdown */}
          <div className="relative ml-2" ref={menuRef}>
            <button
              onClick={() => setShowColumnsMenu(!showColumnsMenu)}
              className="flex items-center gap-1.5 rounded-lg bg-surface border border-surface-border px-3 py-1.5 text-gray-300 hover:text-white hover:bg-surface-elevated transition-colors"
            >
              <Settings2 className="h-4 w-4" /> Columns
            </button>
            {showColumnsMenu && (
              <div className="absolute right-0 mt-2 w-56 rounded-xl border border-surface-border bg-[#0B0F17] p-3 shadow-2xl z-50">
                <div className="space-y-2 max-h-64 overflow-y-auto pr-2">
                  {AVAILABLE_COLUMNS.map((col) => (
                    <label key={col.id} className="flex items-center gap-2 cursor-pointer group">
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                          visibleColumns.has(col.id)
                            ? "bg-emerald-500 border-emerald-500"
                            : "bg-transparent border-gray-500 group-hover:border-gray-300"
                        }`}
                      >
                        {visibleColumns.has(col.id) && <span className="text-black text-[10px] font-black">✓</span>}
                      </div>
                      <input
                        type="checkbox"
                        className="hidden"
                        checked={visibleColumns.has(col.id)}
                        onChange={() => toggleColumn(col.id)}
                      />
                      <span className="text-gray-300 group-hover:text-white transition-colors">{col.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono whitespace-nowrap">
            <thead className="border-b border-surface-border bg-surface-elevated text-gray-400 select-none">
              <tr>
                <th className="px-4 py-3 font-semibold text-white cursor-pointer sticky left-0 bg-surface-elevated z-10" onClick={() => handleSort("player_name")}>
                  <div className="flex items-center gap-1">Player <SortIcon field="player_name" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-4 py-3 text-left">Archetype</th>
                
                {AVAILABLE_COLUMNS.map(col => (
                  visibleColumns.has(col.id) && (
                    <th key={col.id} className="px-3 py-3 text-right cursor-pointer hover:text-gray-200" onClick={() => handleSort(col.id as SortField)}>
                      <div className="flex items-center justify-end gap-1">
                        {col.label} <SortIcon field={col.id as SortField} current={sortField} asc={sortAsc} />
                      </div>
                    </th>
                  )
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50 text-gray-300">
              {filteredPlayers.slice(0, 100).map((p) => {
                const netEpm = p.net_epm;
                const offEpm = p.offensive_epm;
                const defEpm = p.defensive_epm;
                
                return (
                  <tr key={p.player_id} className="hover:bg-surface-elevated/40 transition-colors group">
                    <td className="px-4 py-2.5 font-medium text-white flex items-center gap-3 sticky left-0 bg-surface group-hover:bg-[#111827] z-10 border-r border-transparent">
                      <img
                        src={p.headshot_url}
                        alt={p.player_name}
                        className="h-8 w-8 rounded-full bg-surface-elevated object-cover border border-surface-border"
                        loading="lazy"
                        onError={(e) => { (e.target as HTMLElement).style.display = "none"; }}
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
                    <td className="px-4 py-2.5 text-left">
                      {p.archetype ? (
                        <span className="inline-block rounded bg-surface-elevated px-2 py-0.5 text-[10px] font-medium text-gray-300 border border-surface-border truncate max-w-[170px]">
                          {p.archetype}
                        </span>
                      ) : (
                        <span className="text-gray-600">-</span>
                      )}
                    </td>

                    {/* Dynamic Columns */}
                    {visibleColumns.has("minutes_per_game") && <td className="px-3 py-2.5 text-right">{p.minutes_per_game}</td>}
                    {visibleColumns.has("pts_per_100") && <td className="px-3 py-2.5 text-right font-bold text-white">{p.pts_per_100}</td>}
                    {visibleColumns.has("ast_per_100") && <td className="px-3 py-2.5 text-right">{p.ast_per_100}</td>}
                    {visibleColumns.has("reb_per_100") && <td className="px-3 py-2.5 text-right">{p.reb_per_100}</td>}
                    {visibleColumns.has("usage_pct") && <td className="px-3 py-2.5 text-right">{p.usage_pct}%</td>}
                    {visibleColumns.has("true_shooting_pct") && (
                      <td className="px-3 py-2.5 text-right">{p.true_shooting_pct ? `${(p.true_shooting_pct * 100).toFixed(1)}%` : "-"}</td>
                    )}
                    {visibleColumns.has("net_epm") && (
                      <td className="px-3 py-2.5 text-right font-bold"><ColorValue val={netEpm} /></td>
                    )}
                    {visibleColumns.has("offensive_epm") && (
                      <td className="px-3 py-2.5 text-right font-bold"><ColorValue val={offEpm} /></td>
                    )}
                    {visibleColumns.has("defensive_epm") && (
                      <td className="px-3 py-2.5 text-right font-bold"><ColorValue val={defEpm} /></td>
                    )}
                    {visibleColumns.has("self_creation_rate") && (
                      <td className="px-3 py-2.5 text-right">
                        {p.percentile_ranks.self_creation !== null && p.percentile_ranks.self_creation !== undefined
                          ? `${p.percentile_ranks.self_creation.toFixed(0)}th`
                          : "-"}
                      </td>
                    )}
                    {visibleColumns.has("rim_pressure_rate") && (
                      <td className="px-3 py-2.5 text-right">
                        {p.percentile_ranks.rim_pressure !== null && p.percentile_ranks.rim_pressure !== undefined
                          ? `${p.percentile_ranks.rim_pressure.toFixed(0)}th`
                          : "-"}
                      </td>
                    )}
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

function ColorValue({ val }: { val: number | null | undefined }) {
  if (val === null || val === undefined) return <span className="text-gray-600">-</span>;
  return (
    <span className={val > 0 ? "text-emerald" : val < 0 ? "text-crimson" : "text-gray-400"}>
      {val > 0 ? `+${val.toFixed(1)}` : val.toFixed(1)}
    </span>
  );
}