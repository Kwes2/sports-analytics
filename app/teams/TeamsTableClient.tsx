"use client";

import { useState, useMemo, useRef, useEffect } from "react";
import Link from "next/link";
import { TeamIndexItem } from "@/types/analytics";
import { ArrowUpDown, ChevronUp, ChevronDown, Settings2 } from "lucide-react";

type SortField = keyof TeamIndexItem;

const AVAILABLE_COLUMNS = [
  { id: "pace", label: "Pace" },
  { id: "offensive_rating", label: "Offensive Rating" },
  { id: "defensive_rating", label: "Defensive Rating" },
  { id: "net_rating", label: "Net Rating" },
  { id: "overall_elo", label: "Overall Power Index" },
  { id: "offensive_elo", label: "Offense Power Index" },
  { id: "defensive_elo", label: "Defense Power Index" },
];

export default function TeamsTableClient({
  initialTeams,
}: {
  initialTeams: TeamIndexItem[];
}) {
  const [conferenceFilter, setConferenceFilter] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("net_rating");
  const [sortAsc, setSortAsc] = useState(false);

  const [showColumnsMenu, setShowColumnsMenu] = useState(false);
  const [visibleColumns, setVisibleColumns] = useState<Set<string>>(
    new Set(["pace", "offensive_rating", "defensive_rating", "net_rating", "overall_elo"])
  );
  
  const menuRef = useRef<HTMLDivElement>(null);

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
      setSortAsc(field === "defensive_rating"); // lower DRTG is better
    }
  };

  const toggleColumn = (colId: string) => {
    const next = new Set(visibleColumns);
    if (next.has(colId)) next.delete(colId);
    else next.add(colId);
    setVisibleColumns(next);
  };

  const filteredTeams = useMemo(() => {
    return initialTeams
      .filter((t) => {
        if (conferenceFilter === "ALL") return true;
        return t.conference.toUpperCase() === conferenceFilter;
      })
      .sort((a, b) => {
        let valA: any = a[sortField];
        let valB: any = b[sortField];

        if (typeof valA === "string") {
          return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return sortAsc ? valA - valB : valB - valA;
      });
  }, [initialTeams, conferenceFilter, sortField, sortAsc]);

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-1.5 font-mono text-xs">
          {["ALL", "EAST", "WEST"].map((conf) => (
            <button
              key={conf}
              onClick={() => setConferenceFilter(conf)}
              className={`rounded-lg px-4 py-2 transition-colors ${
                conferenceFilter === conf
                  ? "bg-amber-400 text-black font-bold"
                  : "bg-surface border border-surface-border text-gray-400 hover:text-white"
              }`}
            >
              {conf === "ALL" ? "ALL TEAMS" : `${conf}ERN CONFERENCE`}
            </button>
          ))}
        </div>

        {/* Columns Dropdown */}
        <div className="relative font-mono text-xs" ref={menuRef}>
          <button
            onClick={() => setShowColumnsMenu(!showColumnsMenu)}
            className="flex items-center gap-1.5 rounded-lg bg-surface border border-surface-border px-3 py-2 text-gray-300 hover:text-white hover:bg-surface-elevated transition-colors"
          >
            <Settings2 className="h-4 w-4" /> Columns
          </button>
          {showColumnsMenu && (
            <div className="absolute right-0 mt-2 w-64 rounded-xl border border-surface-border bg-[#0B0F17] p-3 shadow-2xl z-50">
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
                    <span className="text-gray-300 group-hover:text-white transition-colors truncate">
                      {col.label}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono whitespace-nowrap">
            <thead className="border-b border-surface-border bg-surface-elevated text-gray-400 select-none">
              <tr>
                <th className="px-4 py-3 font-semibold text-white cursor-pointer sticky left-0 bg-surface-elevated z-10" onClick={() => handleSort("team_name")}>
                  <div className="flex items-center gap-1">Team <SortIcon field="team_name" current={sortField} asc={sortAsc} /></div>
                </th>
                
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
              {filteredTeams.map((t, rank) => {
                const net = t.net_rating;
                return (
                  <tr key={t.team_id} className="hover:bg-surface-elevated/40 transition-colors group">
                    <td className="px-4 py-3 font-medium text-white flex items-center gap-3 sticky left-0 bg-surface group-hover:bg-[#111827] z-10 border-r border-transparent">
                      <span className="text-[11px] text-gray-500 w-4">{rank + 1}</span>
                      <img
                        src={t.logo_url}
                        alt={t.team_abbrev}
                        className="h-7 w-7 object-contain"
                        loading="lazy"
                      />
                      <div>
                        <Link
                          href={`/team/${t.team_abbrev}`}
                          className="hover:text-accent hover:underline font-semibold block"
                        >
                          {t.team_name}
                        </Link>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {t.conference} · {t.division}
                        </span>
                      </div>
                    </td>
                    
                    {visibleColumns.has("pace") && <td className="px-3 py-3 text-right font-medium">{t.pace}</td>}
                    {visibleColumns.has("offensive_rating") && <td className="px-3 py-3 text-right">{t.offensive_rating}</td>}
                    {visibleColumns.has("defensive_rating") && <td className="px-3 py-3 text-right">{t.defensive_rating}</td>}
                    {visibleColumns.has("net_rating") && (
                      <td className="px-3 py-3 text-right font-bold">
                        <span className={net > 0 ? "text-emerald" : net < 0 ? "text-crimson" : "text-gray-400"}>
                          {net > 0 ? `+${net.toFixed(1)}` : net.toFixed(1)}
                        </span>
                      </td>
                    )}
                    {visibleColumns.has("overall_elo") && <td className="px-3 py-3 text-right font-black text-white">{t.overall_elo.toFixed(1)}</td>}
                    {visibleColumns.has("offensive_elo") && <td className="px-3 py-3 text-right text-gray-400">{t.offensive_elo.toFixed(1)}</td>}
                    {visibleColumns.has("defensive_elo") && <td className="px-3 py-3 text-right text-gray-400">{t.defensive_elo.toFixed(1)}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SortIcon({ field, current, asc }: { field: SortField; current: SortField; asc: boolean }) {
  if (field !== current) return <ArrowUpDown className="h-3 w-3 text-gray-600 opacity-60" />;
  return asc ? <ChevronUp className="h-3 w-3 text-accent" /> : <ChevronDown className="h-3 w-3 text-accent" />;
}