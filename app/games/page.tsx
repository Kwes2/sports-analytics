"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import gamesData from "../../data/processed/summary_games.json";
import { Search, ChevronRight } from "lucide-react";

type GameSummary = {
  game_id: string;
  game_date: string;
  matchup: string;
  teams: { TEAM_ABBREVIATION: string; PTS: number }[];
};

export default function GamesPage() {
  const [search, setSearch] = useState("");

  const games: GameSummary[] = (gamesData.games as GameSummary[]) || [];

  const filteredGames = useMemo(() => {
    return games.filter((g) => {
      const matchSearch = g.matchup.toLowerCase().includes(search.toLowerCase());
      const teamSearch = g.teams.some((t) =>
        t.TEAM_ABBREVIATION.toLowerCase().includes(search.toLowerCase())
      );
      return matchSearch || teamSearch;
    });
  }, [games, search]);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 font-sans">
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end pb-8 border-b border-zinc-800/80 gap-4">
        <div>
          <div className="text-xs uppercase tracking-widest text-zinc-500 font-mono mb-1">Matchup Intelligence</div>
          <h1 className="text-2xl font-medium tracking-tight text-white">Games & Box Scores</h1>
        </div>
        <div className="text-xs text-zinc-500 font-mono">
          {games.length} Games Logged • Updated {gamesData.last_updated}
        </div>
      </header>

      <div className="mt-8 space-y-6">
        {/* Search */}
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-600" />
          <input
            type="text"
            placeholder="Filter by team or matchup..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-zinc-900/60 border border-zinc-800 text-xs rounded-md pl-8 pr-3 py-2 text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-600 transition"
          />
        </div>

        {/* Game Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredGames.map((game) => {
            const teamA = game.teams[0];
            const teamB = game.teams[1];
            const teamAWins = (teamA?.PTS || 0) > (teamB?.PTS || 0);

            return (
              <Link
                key={game.game_id}
                href={`/game/${game.game_id}`}
                className="p-5 border border-zinc-800/80 bg-zinc-900/20 hover:bg-zinc-900/50 hover:border-zinc-700 transition rounded-lg flex flex-col justify-between group"
              >
                <div className="flex justify-between items-center text-xs text-zinc-500 font-mono mb-3">
                  <span>{game.game_date}</span>
                  <span className="text-[11px] text-zinc-600 group-hover:text-zinc-300 transition flex items-center gap-1">
                    Full Box Score <ChevronRight className="w-3 h-3" />
                  </span>
                </div>

                {/* Score Line */}
                <div className="space-y-2 font-mono">
                  <div className="flex justify-between items-center">
                    <span className={`text-sm font-sans font-medium ${teamAWins ? "text-white" : "text-zinc-400"}`}>
                      {teamA?.TEAM_ABBREVIATION}
                    </span>
                    <span className={`text-base font-bold ${teamAWins ? "text-white" : "text-zinc-500"}`}>
                      {teamA?.PTS}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className={`text-sm font-sans font-medium ${!teamAWins ? "text-white" : "text-zinc-400"}`}>
                      {teamB?.TEAM_ABBREVIATION}
                    </span>
                    <span className={`text-base font-bold ${!teamAWins ? "text-white" : "text-zinc-500"}`}>
                      {teamB?.PTS}
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>

        {filteredGames.length === 0 && (
          <div className="p-8 border border-zinc-800/60 rounded-lg text-center text-zinc-500 text-xs font-mono">
            No games found matching "{search}"
          </div>
        )}
      </div>
    </div>
  );
}