"use client";

import React, { useState, useMemo } from "react";
import metricsData from "../data/processed/latest_metrics.json";
import { Search, Trophy, BarChart3, FlaskConical, ArrowUpDown, Flame, Activity } from "lucide-react";
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
  AST_TOV: number;
  CUSTOM_IMPACT: number;
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"leaderboard" | "visuals" | "metrics">("leaderboard");
  const [search, setSearch] = useState("");
  const [selectedTeam, setSelectedTeam] = useState("ALL");
  const [sortField, setSortField] = useState<keyof Player>("CUSTOM_IMPACT");
  const [sortAsc, setSortAsc] = useState(false);

  const players: Player[] = (metricsData.players as Player[]) || [];

  // Unique Teams List
  const teams = useMemo(() => {
    const list = Array.from(new Set(players.map((p) => p.TEAM_ABBREVIATION))).sort();
    return ["ALL", ...list];
  }, [players]);

  // Filtered & Sorted Players
  const filteredPlayers = useMemo(() => {
    return players
      .filter((p) => {
        const matchesSearch = p.PLAYER_NAME.toLowerCase().includes(search.toLowerCase());
        const matchesTeam = selectedTeam === "ALL" || p.TEAM_ABBREVIATION === selectedTeam;
        return matchesSearch && matchesTeam;
      })
      .sort((a, b) => {
        const valA = a[sortField];
        const valB = b[sortField];
        if (typeof valA === "number" && typeof valB === "number") {
          return sortAsc ? valA - valB : valB - valA;
        }
        return 0;
      });
  }, [players, search, selectedTeam, sortField, sortAsc]);

  const handleSort = (field: keyof Player) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      {/* Top Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between pb-8 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-2 bg-blue-600/10 text-blue-400 rounded-lg border border-blue-500/20">
              <Activity className="w-6 h-6" />
            </span>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">CourtIQ Analytics</h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Season {metricsData.season_year} • Last Updated: <span className="text-slate-300 font-mono">{metricsData.last_updated}</span>
          </p>
        </div>

        {/* Global Summary Badges */}
        <div className="flex items-center gap-3">
          <div className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 text-right">
            <div className="text-xs text-slate-400 font-medium">Active Players</div>
            <div className="text-lg font-bold text-white font-mono">{metricsData.total_players}</div>
          </div>
          <div className="bg-blue-950/40 border border-blue-800/40 rounded-xl px-4 py-2 text-right">
            <div className="text-xs text-blue-400 font-medium">Metric Engine</div>
            <div className="text-lg font-bold text-blue-300">v2.0 Active</div>
          </div>
        </div>
      </header>

      {/* Modern Navigation Tabs */}
      <div className="flex space-x-1 border-b border-slate-800 mt-6 pb-2">
        <button
          onClick={() => setActiveTab("leaderboard")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "leaderboard"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <Trophy className="w-4 h-4" /> Leaderboard
        </button>
        <button
          onClick={() => setActiveTab("visuals")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "visuals"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <BarChart3 className="w-4 h-4" /> Visualizations
        </button>
        <button
          onClick={() => setActiveTab("metrics")}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "metrics"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <FlaskConical className="w-4 h-4" /> Metric Formula Lab
        </button>
      </div>

      {/* === TAB 1: LEADERBOARD === */}
      {activeTab === "leaderboard" && (
        <section className="mt-6 space-y-4">
          {/* Controls Bar */}
          <div className="flex flex-col sm:flex-row gap-3 justify-between items-center bg-slate-900/60 p-3 rounded-xl border border-slate-800">
            <div className="relative w-full sm:w-72">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search player name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <span className="text-xs text-slate-400 font-medium">Team:</span>
              <select
                value={selectedTeam}
                onChange={(e) => setSelectedTeam(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-slate-200 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {teams.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/30">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/80 text-xs font-semibold uppercase text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3.5">Player</th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("TEAM_ABBREVIATION")}>
                    Team
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("GP")}>
                    GP
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("MIN")}>
                    MIN
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("PTS")}>
                    PTS
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("REB")}>
                    REB
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("AST")}>
                    AST
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("TS_PCT")}>
                    TS%
                  </th>
                  <th className="px-3 py-3.5 cursor-pointer hover:text-white" onClick={() => handleSort("AST_TOV")}>
                    AST/TO
                  </th>
                  <th
                    className="px-4 py-3.5 cursor-pointer bg-blue-950/30 text-blue-400 hover:text-blue-300 font-bold"
                    onClick={() => handleSort("CUSTOM_IMPACT")}
                  >
                    <div className="flex items-center gap-1">
                      <span>Impact Score</span>
                      <ArrowUpDown className="w-3.5 h-3.5" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs sm:text-sm">
                {filteredPlayers.slice(0, 50).map((player, idx) => (
                  <tr key={player.PLAYER_ID} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-sans font-medium text-white flex items-center gap-2">
                      <span className="text-slate-500 font-mono text-xs w-5">{idx + 1}.</span>
                      {player.PLAYER_NAME}
                    </td>
                    <td className="px-3 py-3 text-slate-400">{player.TEAM_ABBREVIATION}</td>
                    <td className="px-3 py-3">{player.GP}</td>
                    <td className="px-3 py-3">{player.MIN}</td>
                    <td className="px-3 py-3 font-semibold text-slate-100">{player.PTS}</td>
                    <td className="px-3 py-3">{player.REB}</td>
                    <td className="px-3 py-3">{player.AST}</td>
                    <td className="px-3 py-3 text-emerald-400">{player.TS_PCT}%</td>
                    <td className="px-3 py-3">{player.AST_TOV}</td>
                    <td className="px-4 py-3 bg-blue-950/20 font-bold text-blue-400">{player.CUSTOM_IMPACT}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 text-right">Showing top 50 filtered results</p>
        </section>
      )}

      {/* === TAB 2: VISUALIZATIONS === */}
      {activeTab === "visuals" && (
        <section className="mt-6 bg-slate-900/40 p-6 rounded-2xl border border-slate-800 space-y-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Flame className="w-5 h-5 text-blue-500" /> True Shooting % vs. Custom Impact Score
            </h2>
            <p className="text-sm text-slate-400">Hover over any point to inspect player stats.</p>
          </div>

          <div className="h-[450px] w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" dataKey="TS_PCT" name="TS%" unit="%" stroke="#64748b" domain={[20, 100]} />
                <YAxis type="number" dataKey="CUSTOM_IMPACT" name="Impact" stroke="#64748b" />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ payload }) => {
                    if (payload && payload.length) {
                      const data = payload[0].payload as Player;
                      return (
                        <div className="bg-slate-950 p-3 rounded-lg border border-slate-700 shadow-xl text-xs space-y-1">
                          <p className="font-bold text-sm text-white">{data.PLAYER_NAME} ({data.TEAM_ABBREVIATION})</p>
                          <p className="text-blue-400 font-semibold">Impact Score: {data.CUSTOM_IMPACT}</p>
                          <p className="text-emerald-400">True Shooting: {data.TS_PCT}%</p>
                          <p className="text-slate-400">PTS: {data.PTS} | REB: {data.REB} | AST: {data.AST}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter name="Players" data={filteredPlayers} fill="#3b82f6" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* === TAB 3: METRIC FORMULA LAB === */}
      {activeTab === "metrics" && (
        <section className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800 space-y-3">
            <div className="flex items-center gap-2 text-blue-400 font-bold">
              <FlaskConical className="w-5 h-5" /> Custom Impact Metric
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Synthesizes overall on-court output, balancing offensive creation against turnovers and rewarding defensive disruptiveness.
            </p>
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 font-mono text-xs text-blue-300">
              CUSTOM_IMPACT = PTS + (1.2 × REB) + (1.5 × AST) + (2.0 × STL) + (2.0 × BLK) - (1.5 × TOV)
            </div>
          </div>

          <div className="bg-slate-900/40 p-6 rounded-2xl border border-slate-800 space-y-3">
            <div className="flex items-center gap-2 text-emerald-400 font-bold">
              <Activity className="w-5 h-5" /> True Shooting Percentage (TS%)
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Measures shooting efficiency taking into account 2-point field goals, 3-point field goals, and free throws.
            </p>
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 font-mono text-xs text-emerald-300">
              TS% = PTS / (2 × (FGA + 0.44 × FTA)) × 100
            </div>
          </div>
        </section>
      )}
    </div>
  );
}