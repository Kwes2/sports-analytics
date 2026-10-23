"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import teamsData from "../../data/processed/summary_teams.json";
import { Search, ArrowUpDown } from "lucide-react";

type TeamSummary = {
  TEAM_ABBREVIATION: string;
  GP: number;
  W: number;
  L: number;
  WIN_PCT: number;
  ROSTER_COUNT: number;
};

export default function TeamsPage() {
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<keyof TeamSummary>("WIN_PCT");
  const [sortAsc, setSortAsc] = useState(false);

  const teams: TeamSummary[] = (teamsData.teams as TeamSummary[]) || [];

  const filteredTeams = useMemo(() => {
    return teams
      .filter((t) => t.TEAM_ABBREVIATION.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        const valA = a[sortField];
        const valB = b[sortField];
        if (typeof valA === "number" && typeof valB === "number") {
          return sortAsc ? valA - valB : valB - valA;
        }
        return 0;
      });
  }, [teams, search, sortField, sortAsc]);

  const handleSort = (field: keyof TeamSummary) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 font-sans">
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end pb-8 border-b border-zinc-800/80 gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-1">Franchise Intelligence</div>
          <h1 className="text-2xl font-medium tracking-tight text-white">NBA League Standings</h1>
        </div>
        <div className="text-xs text-zinc-500 font-mono">
          30 Teams Analyzed • Updated {teamsData.last_updated}
        </div>
      </header>

      <div className="mt-8 space-y-4">
        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-600" />
          <input
            type="text"
            placeholder="Search franchise..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-zinc-900/60 border border-zinc-800 text-xs rounded-md pl-8 pr-3 py-2 text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600 transition"
          />
        </div>

        {/* Standings Table */}
        <div className="overflow-x-auto border border-zinc-800/80 rounded-lg">
          <table className="w-full text-left text-xs text-zinc-400">
            <thead className="bg-zinc-900/40 text-zinc-500 uppercase tracking-wider font-mono text-[10px] border-b border-zinc-800/80">
              <tr>
                <th className="py-3 px-4 font-medium text-zinc-400">Rank</th>
                <th className="py-3 px-4 font-medium text-zinc-400">Franchise</th>
                <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("GP")}>GP</th>
                <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("W")}>W</th>
                <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("L")}>L</th>
                <th className="py-3 px-4 font-semibold text-white cursor-pointer bg-zinc-900/60 hover:bg-zinc-900" onClick={() => handleSort("WIN_PCT")}>
                  <div className="flex items-center gap-1.5">
                    <span>WIN%</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-400" />
                  </div>
                </th>
                <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("ROSTER_COUNT")}>Roster Depth</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 font-mono text-xs tabular-nums">
              {filteredTeams.map((team, idx) => (
                <tr key={team.TEAM_ABBREVIATION} className="hover:bg-zinc-900/30 transition-colors">
                  <td className="py-3 px-4 text-zinc-600 w-12">{idx + 1}</td>
                  <td className="py-3 px-4 font-sans font-medium text-white">
                    <Link
                      href={`/team/${team.TEAM_ABBREVIATION}`}
                      className="hover:underline hover:text-zinc-300 transition-colors flex items-center gap-2"
                    >
                      <span className="font-mono text-xs bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded text-zinc-300">
                        {team.TEAM_ABBREVIATION}
                      </span>
                    </Link>
                  </td>
                  <td className="py-3 px-3">{team.GP}</td>
                  <td className="py-3 px-3 text-emerald-400 font-semibold">{team.W}</td>
                  <td className="py-3 px-3 text-rose-400">{team.L}</td>
                  <td className="py-3 px-4 font-bold text-white bg-zinc-900/30">
                    {(team.WIN_PCT * 100).toFixed(1)}%
                  </td>
                  <td className="py-3 px-3 text-zinc-500">{team.ROSTER_COUNT} active</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}