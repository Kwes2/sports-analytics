"use client";

import React, { useState, useMemo } from "react";
import { Filter, RotateCcw } from "lucide-react";

type GameLog = {
  GAME_ID: string;
  GAME_DATE: string;
  MATCHUP: string;
  WL: string;
  MIN: number;
  PTS: number;
  REB: number;
  AST: number;
  STL: number;
  BLK: number;
  TOV: number;
  FGM: number;
  FGA: number;
  FG3M: number;
  FG3A: number;
  FTM: number;
  FTA: number;
  TS_PCT: number;
  FGI: number;
  DDR: number;
  HIR: number;
};

export default function PlayerClientView({ data }: { data: any }) {
  const allLogs: GameLog[] = data.game_logs || [];

  // Filter States
  const [selectedOpponent, setSelectedOpponent] = useState("ALL");
  const [selectedResult, setSelectedResult] = useState("ALL");
  const [minMinutes, setMinMinutes] = useState(0);

  // Extract all opponent teams from matchup strings (e.g. "BOS @ DET" or "DET vs. BOS")
  const opponents = useMemo(() => {
    const oppSet = new Set<string>();
    allLogs.forEach((log) => {
      const parts = log.MATCHUP.split(/[@vs\.]+/);
      if (parts.length >= 2) {
        const opp = parts[parts.length - 1].trim();
        if (opp) oppSet.add(opp);
      }
    });
    return ["ALL", ...Array.from(oppSet).sort()];
  }, [allLogs]);

  // Filtered Logs
  const filteredLogs = useMemo(() => {
    return allLogs.filter((log) => {
      const matchesOpp = selectedOpponent === "ALL" || log.MATCHUP.includes(selectedOpponent);
      const matchesWL = selectedResult === "ALL" || log.WL === selectedResult;
      const matchesMin = log.MIN >= minMinutes;
      return matchesOpp && matchesWL && matchesMin;
    });
  }, [allLogs, selectedOpponent, selectedResult, minMinutes]);

  // Recalculate Averages based on currently filtered games
  const filteredAverages = useMemo(() => {
    if (!filteredLogs.length) return null;
    const len = filteredLogs.length;
    return {
      GP: len,
      PTS: (filteredLogs.reduce((acc, l) => acc + l.PTS, 0) / len).toFixed(1),
      REB: (filteredLogs.reduce((acc, l) => acc + l.REB, 0) / len).toFixed(1),
      AST: (filteredLogs.reduce((acc, l) => acc + l.AST, 0) / len).toFixed(1),
      HIR: (filteredLogs.reduce((acc, l) => acc + l.HIR, 0) / len).toFixed(1),
      TS_PCT: (filteredLogs.reduce((acc, l) => acc + l.TS_PCT, 0) / len).toFixed(1),
    };
  }, [filteredLogs]);

  const resetFilters = () => {
    setSelectedOpponent("ALL");
    setSelectedResult("ALL");
    setMinMinutes(0);
  };

  return (
    <div className="mt-8 space-y-6">
      {/* Rolling Form & Advanced Profiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-zinc-800/80 bg-zinc-900/30 p-4 rounded-lg">
          <div className="text-xs uppercase font-mono text-zinc-500 mb-1">Recent Trend (Last 5 Games)</div>
          <div className="font-mono text-sm text-zinc-200">
            {data.last_5_avg.PTS} PTS • {data.last_5_avg.REB} REB • {data.last_5_avg.AST} AST
          </div>
          <div className="text-xs font-mono text-zinc-500 mt-1">HIR: {data.last_5_avg.HIR} | TS: {data.last_5_avg.TS_PCT}%</div>
        </div>

        <div className="border border-zinc-800/80 bg-zinc-900/30 p-4 rounded-lg">
          <div className="text-xs uppercase font-mono text-zinc-500 mb-1">Playmaking Economy (FGI)</div>
          <div className="font-mono text-lg text-white font-semibold">{data.profile.FGI}</div>
          <div className="text-xs text-zinc-500 mt-1">Floor General playmaking creation rating</div>
        </div>

        <div className="border border-zinc-800/80 bg-zinc-900/30 p-4 rounded-lg">
          <div className="text-xs uppercase font-mono text-zinc-500 mb-1">Defensive Activity (DDR)</div>
          <div className="font-mono text-lg text-white font-semibold">{data.profile.DDR}</div>
          <div className="text-xs text-zinc-500 mt-1">Stocks (STL+BLK) per 36 minutes</div>
        </div>
      </div>

      {/* === DEEP FILTER BAR === */}
      <div className="border border-zinc-800/80 bg-zinc-900/40 p-4 rounded-lg space-y-3">
        <div className="flex items-center justify-between text-xs font-mono text-zinc-400">
          <div className="flex items-center gap-1.5 font-medium text-white">
            <Filter className="w-3.5 h-3.5 text-zinc-400" />
            <span>Interactive Split Filters</span>
          </div>
          {(selectedOpponent !== "ALL" || selectedResult !== "ALL" || minMinutes > 0) && (
            <button
              onClick={resetFilters}
              className="flex items-center gap-1 text-zinc-400 hover:text-white transition"
            >
              <RotateCcw className="w-3 h-3" /> Reset
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
          {/* Opponent Selector */}
          <div>
            <label className="text-[11px] text-zinc-500 font-mono block mb-1">Opponent</label>
            <select
              value={selectedOpponent}
              onChange={(e) => setSelectedOpponent(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 text-xs rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-zinc-600"
            >
              {opponents.map((opp) => (
                <option key={opp} value={opp}>
                  {opp === "ALL" ? "All Opponents" : `vs ${opp}`}
                </option>
              ))}
            </select>
          </div>

          {/* Outcome Filter */}
          <div>
            <label className="text-[11px] text-zinc-500 font-mono block mb-1">Game Result</label>
            <select
              value={selectedResult}
              onChange={(e) => setSelectedResult(e.target.value)}
              className="w-full bg-zinc-950 border border-zinc-800 text-xs rounded px-2.5 py-1.5 text-zinc-200 focus:outline-none focus:border-zinc-600"
            >
              <option value="ALL">All Outcomes</option>
              <option value="W">Wins Only</option>
              <option value="L">Losses Only</option>
            </select>
          </div>

          {/* Minutes Threshold */}
          <div>
            <div className="flex justify-between text-[11px] text-zinc-500 font-mono mb-1">
              <span>Min Minutes</span>
              <span className="text-zinc-300">{minMinutes}m+</span>
            </div>
            <input
              type="range"
              min="0"
              max="40"
              step="5"
              value={minMinutes}
              onChange={(e) => setMinMinutes(Number(e.target.value))}
              className="w-full accent-zinc-200 cursor-pointer"
            />
          </div>
        </div>

        {/* Dynamic Split Recalculation Notice */}
        {filteredAverages && (
          <div className="pt-2 border-t border-zinc-800/60 flex items-center justify-between text-xs font-mono">
            <span className="text-zinc-500">Filtered Averages ({filteredAverages.GP} games):</span>
            <span className="text-white font-medium">
              {filteredAverages.PTS} PTS • {filteredAverages.REB} REB • {filteredAverages.AST} AST • {filteredAverages.HIR} HIR • {filteredAverages.TS_PCT}% TS
            </span>
          </div>
        )}
      </div>

      {/* Game Logs Table */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-white">Game-by-Game Logs</h3>
        <div className="overflow-x-auto border border-zinc-800/80 rounded-lg">
          <table className="w-full text-left text-xs text-zinc-400">
            <thead className="bg-zinc-900/40 text-zinc-500 uppercase tracking-wider font-mono text-[10px] border-b border-zinc-800/80">
              <tr>
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Matchup</th>
                <th className="py-2.5 px-2">W/L</th>
                <th className="py-2.5 px-2">MIN</th>
                <th className="py-2.5 px-2">PTS</th>
                <th className="py-2.5 px-2">REB</th>
                <th className="py-2.5 px-2">AST</th>
                <th className="py-2.5 px-2">STL</th>
                <th className="py-2.5 px-2">BLK</th>
                <th className="py-2.5 px-2">TOV</th>
                <th className="py-2.5 px-2">TS%</th>
                <th className="py-2.5 px-3 font-semibold text-white bg-zinc-900/60">HIR</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-900 font-mono text-xs tabular-nums">
              {filteredLogs.map((log) => (
                <tr key={log.GAME_ID} className="hover:bg-zinc-900/30 transition-colors">
                  <td className="py-2.5 px-3 text-zinc-500">{String(log.GAME_DATE).slice(0, 10)}</td>
                  <td className="py-2.5 px-3 font-sans text-zinc-200">{log.MATCHUP}</td>
                  <td className={`py-2.5 px-2 font-bold ${log.WL === "W" ? "text-emerald-400" : "text-rose-400"}`}>
                    {log.WL}
                  </td>
                  <td className="py-2.5 px-2">{log.MIN}</td>
                  <td className="py-2.5 px-2 font-semibold text-zinc-100">{log.PTS}</td>
                  <td className="py-2.5 px-2">{log.REB}</td>
                  <td className="py-2.5 px-2">{log.AST}</td>
                  <td className="py-2.5 px-2">{log.STL}</td>
                  <td className="py-2.5 px-2">{log.BLK}</td>
                  <td className="py-2.5 px-2 text-zinc-500">{log.TOV}</td>
                  <td className="py-2.5 px-2">{log.TS_PCT}%</td>
                  <td className="py-2.5 px-3 font-bold text-white bg-zinc-900/20">{log.HIR}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}