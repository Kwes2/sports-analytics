"use client";

import React, { useState, useMemo } from "react";
import metricsData from "../data/processed/latest_metrics.json";
import { Search, ArrowUpDown, ChevronDown } from "lucide-react";
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

type Player = {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  TEAM_ABBREVIATION: string;
  GP: number;
  MIN: number;
  PTS: number;
  REB: number;
  AST: number;
  STL: number;
  BLK: number;
  TOV: number;
  TS_PCT: number;
  FGI: number;
  DDR: number;
  HIR: number;
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"table" | "chart" | "docs">("table");
  const [search, setSearch] = useState("");
  const [teamFilter, setTeamFilter] = useState("ALL");
  const [sortField, setSortField] = useState<keyof Player>("HIR");
  const [sortAsc, setSortAsc] = useState(false);

  const players = (metricsData.players as Player[]) || [];

  const teams = useMemo(() => {
    return ["ALL", ...Array.from(new Set(players.map((p) => p.TEAM_ABBREVIATION))).sort()];
  }, [players]);

  const filtered = useMemo(() => {
    return players
      .filter((p) => {
        const matchesName = p.PLAYER_NAME.toLowerCase().includes(search.toLowerCase());
        const matchesTeam = teamFilter === "ALL" || p.TEAM_ABBREVIATION === teamFilter;
        return matchesName && matchesTeam;
      })
      .sort((a, b) => {
        const valA = a[sortField];
        const valB = b[sortField];
        if (typeof valA === "number" && typeof valB === "number") {
          return sortAsc ? valA - valB : valB - valA;
        }
        return 0;
      });
  }, [players, search, teamFilter, sortField, sortAsc]);

  const handleSort = (field: keyof Player) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 antialiased font-sans">
      <div className="max-w-6xl mx-auto px-6 py-12">
        {/* Minimal Header */}
        <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end pb-8 border-b border-zinc-800/80 gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-1">CourtIQ — Intelligence Hub</div>
            <h1 className="text-2xl font-medium tracking-tight text-white">NBA Performance Matrix</h1>
          </div>
          <div className="text-xs text-zinc-500 font-mono">
            {metricsData.season_year} Season • Updated {metricsData.last_updated}
          </div>
        </header>

        {/* Understated Nav Tabs */}
        <div className="flex space-x-6 border-b border-zinc-900 mt-6 text-sm">
          <button
            onClick={() => setActiveTab("table")}
            className={`pb-3 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === "table" ? "border-zinc-200 text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Leaderboard
          </button>
          <button
            onClick={() => setActiveTab("chart")}
            className={`pb-3 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === "chart" ? "border-zinc-200 text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Scatter Plot
          </button>
          <button
            onClick={() => setActiveTab("docs")}
            className={`pb-3 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === "docs" ? "border-zinc-200 text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Definitions
          </button>
        </div>

        {/* === TAB 1: MINIMALIST TABLE === */}
        {activeTab === "table" && (
          <div className="mt-8 space-y-4">
            {/* Filter Row */}
            <div className="flex flex-col sm:flex-row gap-3 justify-between">
              <div className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-600" />
                <input
                  type="text"
                  placeholder="Filter by name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="w-full bg-zinc-900/60 border border-zinc-800 text-xs rounded-md pl-8 pr-3 py-2 text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600 transition"
                />
              </div>

              <div className="flex items-center gap-2">
                <select
                  value={teamFilter}
                  onChange={(e) => setTeamFilter(e.target.value)}
                  className="bg-zinc-900/60 border border-zinc-800 text-xs rounded-md px-3 py-2 text-zinc-300 focus:outline-none focus:border-zinc-600 transition"
                >
                  {teams.map((t) => (
                    <option key={t} value={t}>
                      {t === "ALL" ? "All Franchises" : t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto border border-zinc-800/80 rounded-lg">
              <table className="w-full text-left text-xs text-zinc-400">
                <thead className="bg-zinc-900/40 text-zinc-500 uppercase tracking-wider font-mono text-[10px] border-b border-zinc-800/80">
                  <tr>
                    <th className="py-3 px-4 font-medium text-zinc-400">Player</th>
                    <th className="py-3 px-3 font-medium">Team</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("MIN")}>MIN</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("PTS")}>PTS</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("REB")}>REB</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("AST")}>AST</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("TS_PCT")}>TS%</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("FGI")}>FGI</th>
                    <th className="py-3 px-3 font-medium cursor-pointer hover:text-zinc-200" onClick={() => handleSort("DDR")}>DDR</th>
                    <th className="py-3 px-4 font-semibold text-white cursor-pointer bg-zinc-900/60 hover:bg-zinc-900" onClick={() => handleSort("HIR")}>
                      <div className="flex items-center gap-1.5">
                        <span>HIR</span>
                        <ArrowUpDown className="w-3 h-3 text-zinc-400" />
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 font-mono text-xs tabular-nums">
                  {filtered.slice(0, 100).map((player, idx) => (
                    <tr key={player.PLAYER_ID} className="hover:bg-zinc-900/30 transition-colors">
                      <td className="py-3 px-4 font-sans font-medium text-zinc-200 flex items-center gap-2">
                        <span className="text-zinc-600 text-[11px] w-5 font-mono">{idx + 1}</span>
                        {player.PLAYER_NAME}
                      </td>
                      <td className="py-3 px-3 text-zinc-500 font-sans">{player.TEAM_ABBREVIATION}</td>
                      <td className="py-3 px-3">{player.MIN}</td>
                      <td className="py-3 px-3 text-zinc-200 font-semibold">{player.PTS}</td>
                      <td className="py-3 px-3">{player.REB}</td>
                      <td className="py-3 px-3">{player.AST}</td>
                      <td className="py-3 px-3">{player.TS_PCT}%</td>
                      <td className="py-3 px-3">{player.FGI}</td>
                      <td className="py-3 px-3">{player.DDR}</td>
                      <td className="py-3 px-4 font-bold text-white bg-zinc-900/30">{player.HIR}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="text-[11px] text-zinc-600 font-mono text-right">Displaying {Math.min(filtered.length, 100)} of {filtered.length} entries</div>
          </div>
        )}

        {/* === TAB 2: MINIMALIST VISUALIZATION === */}
        {activeTab === "chart" && (
          <div className="mt-8 border border-zinc-800/80 rounded-lg p-6 bg-zinc-950">
            <div className="mb-4">
              <h2 className="text-sm font-medium text-white">Efficiency vs. Holistic Impact</h2>
              <p className="text-xs text-zinc-500 mt-0.5">True Shooting Percentage plotted against Holistic Impact Rating (HIR).</p>
            </div>
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="2 2" stroke="#27272a" opacity={0.6} />
                  <XAxis type="number" dataKey="TS_PCT" name="TS%" stroke="#52525b" tick={{ fontSize: 11, fill: '#71717a' }} domain={[30, 90]} />
                  <YAxis type="number" dataKey="HIR" name="HIR" stroke="#52525b" tick={{ fontSize: 11, fill: '#71717a' }} />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload || !payload.length) return null;
                      const d = payload[0].payload as Player;
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 p-2.5 rounded shadow-2xl text-[11px] font-mono space-y-1">
                          <div className="font-sans font-semibold text-white">{d.PLAYER_NAME} ({d.TEAM_ABBREVIATION})</div>
                          <div className="text-zinc-300">HIR: <span className="text-white font-bold">{d.HIR}</span></div>
                          <div className="text-zinc-400">TS%: {d.TS_PCT}%</div>
                          <div className="text-zinc-500 text-[10px]">{d.PTS} PTS | {d.REB} REB | {d.AST} AST</div>
                        </div>
                      );
                    }}
                  />
                  <Scatter name="Players" data={filtered} fill="#e4e4e7" opacity={0.7} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* === TAB 3: MINIMAL DEFINITIONS === */}
        {activeTab === "docs" && (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-5 border border-zinc-800/80 rounded-lg space-y-2">
              <div className="text-xs uppercase tracking-wider font-mono text-zinc-400">Holistic Impact (HIR)</div>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Weights raw box scores with heavier rewards for defensive playmaking (stocks) and severe penalties for turnovers.
              </p>
              <div className="font-mono text-[10px] text-zinc-400 bg-zinc-900/60 p-2 rounded border border-zinc-800">
                PTS + 1.2·REB + 1.5·AST + 2.5·STL + 2.2·BLK - 2.0·TOV
              </div>
            </div>

            <div className="p-5 border border-zinc-800/80 rounded-lg space-y-2">
              <div className="text-xs uppercase tracking-wider font-mono text-zinc-400">Floor General (FGI)</div>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Measures pure point guard play: playmaking creation volume while penalizing ball loss.
              </p>
              <div className="font-mono text-[10px] text-zinc-400 bg-zinc-900/60 p-2 rounded border border-zinc-800">
                (AST × 2.2) - (TOV × 1.8) + (PTS × 0.2)
              </div>
            </div>

            <div className="p-5 border border-zinc-800/80 rounded-lg space-y-2">
              <div className="text-xs uppercase tracking-wider font-mono text-zinc-400">Defensive Disruption (DDR)</div>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Pace-neutral defensive impact. Calculates total stocks (steals + blocks) normalized per 36 minutes of play.
              </p>
              <div className="font-mono text-[10px] text-zinc-400 bg-zinc-900/60 p-2 rounded border border-zinc-800">
                ((STL + BLK) / MIN) × 36
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}