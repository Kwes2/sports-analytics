// app/page.tsx
import Link from "next/link";
import { getGamesFeed } from "@/lib/data";
import { ArrowRight, Trophy, Zap, Calendar } from "lucide-react";

export default function HomePage() {
  const games = getGamesFeed("2026-27");

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-surface-border pb-5">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
            Recent Games Feed
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            2026-27 Regular Season game cards ordered chronologically. Click any card to inspect full box scores, scoring runs, and advanced possession ratings.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-accent bg-surface-elevated border border-surface-border px-3 py-1.5 rounded-lg w-fit">
          <Calendar className="h-3.5 w-3.5" />
          <span>{games.length} Games Evaluated</span>
        </div>
      </div>

      {/* Game Cards Grid / Feed */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {games.map((g) => {
          const homeWon = g.home_team.win;
          const pointDiff = Math.abs(g.home_team.score - g.away_team.score);

          return (
            <Link
              key={g.game_id}
              href={`/game/${g.game_id}`}
              className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-surface-border bg-surface p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-accent hover:shadow-lg hover:shadow-accent/5"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between text-xs text-gray-400 border-b border-surface-border/60 pb-3 font-mono">
                <span>{g.game_date}</span>
                <span className="flex items-center gap-1 text-[11px] text-gray-400 bg-surface-elevated px-2 py-0.5 rounded border border-surface-border/80">
                  <Zap className="h-3 w-3 text-amber-400" />
                  {g.pace} Pace
                </span>
              </div>

              {/* Teams & Scores */}
              <div className="my-5 space-y-3">
                {/* Away Team */}
                <div className={`flex items-center justify-between ${!homeWon ? "font-bold text-white" : "text-gray-400"}`}>
                  <div className="flex items-center gap-3">
                    <img
                      src={`https://cdn.nba.com/logos/nba/${g.away_team.id}/global/L/logo.svg`}
                      alt={g.away_team.abbrev}
                      className="h-7 w-7 object-contain"
                      loading="lazy"
                    />
                    <div>
                      <span className="text-sm tracking-wide">{g.away_team.abbrev}</span>
                      <span className="block text-[11px] text-gray-500 font-normal truncate max-w-[130px]">{g.away_team.name}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {!homeWon && <Trophy className="h-3.5 w-3.5 text-gold" />}
                    <span className="font-mono text-xl">{g.away_team.score}</span>
                  </div>
                </div>

                {/* Home Team */}
                <div className={`flex items-center justify-between ${homeWon ? "font-bold text-white" : "text-gray-400"}`}>
                  <div className="flex items-center gap-3">
                    <img
                      src={`https://cdn.nba.com/logos/nba/${g.home_team.id}/global/L/logo.svg`}
                      alt={g.home_team.abbrev}
                      className="h-7 w-7 object-contain"
                      loading="lazy"
                    />
                    <div>
                      <span className="text-sm tracking-wide">{g.home_team.abbrev}</span>
                      <span className="block text-[11px] text-gray-500 font-normal truncate max-w-[130px]">{g.home_team.name}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {homeWon && <Trophy className="h-3.5 w-3.5 text-gold" />}
                    <span className="font-mono text-xl">{g.home_team.score}</span>
                  </div>
                </div>
              </div>

              {/* Card Footer */}
              <div className="flex items-center justify-between pt-3 border-t border-surface-border/60 text-xs">
                <span className="text-[11px] font-mono text-gray-400">
                  Margin: <span className="text-white font-semibold">+{pointDiff} PTS</span>
                </span>
                <span className="flex items-center gap-1 font-semibold text-accent transition-transform group-hover:translate-x-1">
                  Inspect Game <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}