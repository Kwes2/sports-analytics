// app/teams/TeamsTableClient.tsx
"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { TeamIndexItem, Conference } from "@/types/analytics";
import { ArrowUpDown, ChevronUp, ChevronDown, Shield } from "lucide-react";

type SortField =
  | "team_name"
  | "pace"
  | "offensive_rating"
  | "defensive_rating"
  | "net_rating"
  | "overall_elo"
  | "offensive_elo"
  | "defensive_elo";

export default function TeamsTableClient({
  initialTeams,
}: {
  initialTeams: TeamIndexItem[];
}) {
  const [conferenceFilter, setConferenceFilter] = useState<string>("ALL");
  const [sortField, setSortField] = useState<SortField>("net_rating");
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      // For defensive rating, lower is better, so default ascending
      setSortAsc(field === "defensive_rating");
    }
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
      {/* Conference Filter Tabs */}
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

      {/* Main Table */}
      <div className="overflow-hidden rounded-xl border border-surface-border bg-surface">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="border-b border-surface-border bg-surface-elevated text-gray-400 select-none">
              <tr>
                <th className="px-4 py-3 font-semibold text-white cursor-pointer" onClick={() => handleSort("team_name")}>
                  <div className="flex items-center gap-1">Team <SortIcon field="team_name" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("pace")}>
                  <div className="flex items-center justify-end gap-1">PACE <SortIcon field="pace" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("offensive_rating")}>
                  <div className="flex items-center justify-end gap-1">ORTG <SortIcon field="offensive_rating" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("defensive_rating")}>
                  <div className="flex items-center justify-end gap-1">DRTG <SortIcon field="defensive_rating" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer text-accent font-bold" onClick={() => handleSort("net_rating")}>
                  <div className="flex items-center justify-end gap-1">NET RTG <SortIcon field="net_rating" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer text-amber-400 font-bold" onClick={() => handleSort("overall_elo")}>
                  <div className="flex items-center justify-end gap-1">OVERALL ELO <SortIcon field="overall_elo" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("offensive_elo")}>
                  <div className="flex items-center justify-end gap-1">OFF ELO <SortIcon field="offensive_elo" current={sortField} asc={sortAsc} /></div>
                </th>
                <th className="px-3 py-3 text-right cursor-pointer" onClick={() => handleSort("defensive_elo")}>
                  <div className="flex items-center justify-end gap-1">DEF ELO <SortIcon field="defensive_elo" current={sortField} asc={sortAsc} /></div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50 text-gray-300">
              {filteredTeams.map((t, rank) => {
                const net = t.net_rating;
                const elo = t.overall_elo;
                return (
                  <tr key={t.team_id} className="hover:bg-surface-elevated/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-white flex items-center gap-3">
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
                    <td className="px-3 py-3 text-right font-medium">{t.pace}</td>
                    <td className="px-3 py-3 text-right">{t.offensive_rating}</td>
                    <td className="px-3 py-3 text-right">{t.defensive_rating}</td>
                    <td className="px-3 py-3 text-right font-bold">
                      <span className={net > 0 ? "text-emerald" : net < 0 ? "text-crimson" : "text-gray-400"}>
                        {net > 0 ? `+${net.toFixed(1)}` : net.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right font-black text-amber-400">
                      {elo.toFixed(1)}
                    </td>
                    <td className="px-3 py-3 text-right text-gray-400">{t.offensive_elo.toFixed(1)}</td>
                    <td className="px-3 py-3 text-right text-gray-400">{t.defensive_elo.toFixed(1)}</td>
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