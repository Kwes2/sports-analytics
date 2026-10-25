// app/game/[id]/page.tsx
import Link from "next/link";
import { getGamesFeed, getSingleGameData } from "@/lib/data";
import { ArrowLeft, Trophy, Zap, Flame } from "lucide-react";

export async function generateStaticParams() {
  const games = getGamesFeed("2026-27");
  if (games.length === 0) {
    return [{ id: "0022600006" }]; // Fallback dummy ID to satisfy Next.js static validator
  }
  return games.map((g) => ({
    id: g.game_id,
  }));
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function GameDetailPage({ params }: Props) {
  const { id } = await params;
  const gameData = getSingleGameData(id, "2026-27");
  const games = getGamesFeed("2026-27");
  const summary = games.find((g) => g.game_id === id);

  if (!summary || !gameData) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-xl font-bold text-white">Game Not Found</h2>
        <p className="text-gray-400 mt-2">Could not locate game ID {id} in the database.</p>
        <Link href="/" className="mt-4 inline-flex items-center gap-1.5 text-accent hover:underline">
          <ArrowLeft className="h-4 w-4" /> Return to Games Feed
        </Link>
      </div>
    );
  }

  const { pbp_events, player_boxscore } = gameData;
  const homeTid = summary.home_team.id;
  const awayTid = summary.away_team.id;

  const homePlayers = player_boxscore.filter((p) => Number(p.TEAM_ID) === homeTid);
  const awayPlayers = player_boxscore.filter((p) => Number(p.TEAM_ID) === awayTid);

  // Extract Scoring Runs (8-0+) from PBP
  let currentRunTeam: number | null = null;
  let currentRunPts = 0;
  const runs: Array<{ team_id: number; pts: number }> = [];

  let prevH = 0;
  let prevA = 0;

  for (const ev of pbp_events) {
    const sh = ev.score_home;
    const sa = ev.score_away;
    if (sh && !isNaN(Number(sh)) && sa && !isNaN(Number(sa))) {
      const curH = Number(sh);
      const curA = Number(sa);
      const diffH = curH - prevH;
      const diffA = curA - prevA;

      if (diffH > 0 || diffA > 0) {
        const scoringTeam = diffH > 0 ? homeTid : awayTid;
        const pts = diffH > 0 ? diffH : diffA;

        if (scoringTeam === currentRunTeam) {
          currentRunPts += pts;
        } else {
          if (currentRunTeam && currentRunPts >= 8) {
            runs.push({ team_id: currentRunTeam, pts: currentRunPts });
          }
          currentRunTeam = scoringTeam;
          currentRunPts = pts;
        }
        prevH = curH;
        prevA = curA;
      }
    }
  }
  if (currentRunTeam && currentRunPts >= 8) {
    runs.push({ team_id: currentRunTeam, pts: currentRunPts });
  }

  const homeWon = summary.home_team.win;

  return (
    <div className="space-y-8">
      {/* Back Button */}
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-gray-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="h-4 w-4 text-accent" /> Back to Games Feed
      </Link>

      {/* Scoreboard Banner */}
      <div className="overflow-hidden rounded-2xl border border-surface-border bg-surface p-6 sm:p-8">
        <div className="flex items-center justify-between border-b border-surface-border/80 pb-4 text-xs font-mono text-gray-400">
          <span>{summary.game_date}</span>
          <span className="flex items-center gap-1.5 bg-surface-elevated px-2.5 py-1 rounded border border-surface-border text-white">
            <Zap className="h-3.5 w-3.5 text-amber-400" />
            {summary.pace} Possessions / 48m
          </span>
        </div>

        <div className="grid grid-cols-1 gap-6 py-6 sm:grid-cols-3 sm:items-center">
          {/* Away Team */}
          <div className="flex flex-col items-center sm:items-start space-y-2">
            <div className="flex items-center gap-3">
              <img
                src={`https://cdn.nba.com/logos/nba/${awayTid}/global/L/logo.svg`}
                alt={summary.away_team.abbrev}
                className="h-12 w-12 object-contain"
              />
              <div>
                <h2 className="text-xl font-black text-white">{summary.away_team.name}</h2>
                <span className="text-xs font-mono text-gray-400">{summary.away_team.abbrev} (Away)</span>
              </div>
            </div>
            {!homeWon && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-gold">
                <Trophy className="h-3.5 w-3.5" /> WINNER
              </span>
            )}
          </div>

          {/* Scores */}
          <div className="flex items-center justify-center gap-6 text-center font-mono">
            <span className={`text-4xl sm:text-5xl font-black ${!homeWon ? "text-white" : "text-gray-400"}`}>
              {summary.away_team.score}
            </span>
            <span className="text-2xl text-gray-600">-</span>
            <span className={`text-4xl sm:text-5xl font-black ${homeWon ? "text-white" : "text-gray-400"}`}>
              {summary.home_team.score}
            </span>
          </div>

          {/* Home Team */}
          <div className="flex flex-col items-center sm:items-end space-y-2">
            <div className="flex items-center gap-3 flex-row-reverse sm:flex-row">
              <div className="text-right">
                <h2 className="text-xl font-black text-white">{summary.home_team.name}</h2>
                <span className="text-xs font-mono text-gray-400">{summary.home_team.abbrev} (Home)</span>
              </div>
              <img
                src={`https://cdn.nba.com/logos/nba/${homeTid}/global/L/logo.svg`}
                alt={summary.home_team.abbrev}
                className="h-12 w-12 object-contain"
              />
            </div>
            {homeWon && (
              <span className="inline-flex items-center gap-1 text-xs font-bold text-gold">
                <Trophy className="h-3.5 w-3.5" /> WINNER
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Game Momentum & Scoring Runs */}
      <div className="rounded-xl border border-surface-border bg-surface p-6">
        <h3 className="text-base font-bold text-white flex items-center gap-2 mb-4">
          <Flame className="h-4 w-4 text-crimson" /> Unanswered Scoring Runs (8-0+)
        </h3>
        {runs.length === 0 ? (
          <p className="text-xs text-gray-500 font-mono">No unanswered runs of 8+ points occurred in this game.</p>
        ) : (
          <div className="flex flex-wrap gap-2.5">
            {runs.map((r, i) => {
              const teamAbbrev = r.team_id === homeTid ? summary.home_team.abbrev : summary.away_team.abbrev;
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-lg bg-surface-elevated border border-surface-border px-3 py-2 text-xs font-mono"
                >
                  <img
                    src={`https://cdn.nba.com/logos/nba/${r.team_id}/global/L/logo.svg`}
                    alt={teamAbbrev}
                    className="h-4 w-4 object-contain"
                  />
                  <span className="font-bold text-white">{teamAbbrev}</span>
                  <span className="text-crimson font-black">+{r.pts}-0 RUN</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Player Box Scores */}
      <div className="space-y-6">
        <BoxScoreTable
          teamName={summary.away_team.name}
          teamAbbrev={summary.away_team.abbrev}
          teamId={awayTid}
          players={awayPlayers}
        />

        <BoxScoreTable
          teamName={summary.home_team.name}
          teamAbbrev={summary.home_team.abbrev}
          teamId={homeTid}
          players={homePlayers}
        />
      </div>
    </div>
  );
}

function BoxScoreTable({
  teamName,
  teamAbbrev,
  teamId,
  players,
}: {
  teamName: string;
  teamAbbrev: string;
  teamId: number;
  players: any[];
}) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface overflow-hidden">
      <div className="flex items-center gap-3 border-b border-surface-border bg-surface-elevated/50 px-5 py-3">
        <img
          src={`https://cdn.nba.com/logos/nba/${teamId}/global/L/logo.svg`}
          alt={teamAbbrev}
          className="h-5 w-5 object-contain"
        />
        <h3 className="text-sm font-bold text-white tracking-wide">{teamName} Box Score</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="border-b border-surface-border bg-surface-elevated text-gray-400">
            <tr>
              <th className="px-4 py-2.5 font-semibold text-white">Player</th>
              <th className="px-3 py-2.5 text-right">MIN</th>
              <th className="px-3 py-2.5 text-right">PTS</th>
              <th className="px-3 py-2.5 text-right">REB</th>
              <th className="px-3 py-2.5 text-right">AST</th>
              <th className="px-3 py-2.5 text-right">STL</th>
              <th className="px-3 py-2.5 text-right">BLK</th>
              <th className="px-3 py-2.5 text-right">FG</th>
              <th className="px-3 py-2.5 text-right">3PT</th>
              <th className="px-3 py-2.5 text-right">FT</th>
              <th className="px-3 py-2.5 text-right">+/-</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-border/50 text-gray-300">
            {players.map((p) => {
              const pm = Number(p.PLUS_MINUS || 0);
              return (
                <tr key={p.PLAYER_ID} className="hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-4 py-2.5 font-medium text-white flex items-center gap-2">
                    <Link
                      href={`/player/${p.PLAYER_ID}`}
                      className="hover:text-accent hover:underline truncate max-w-[150px]"
                    >
                      {p.PLAYER_NAME}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 text-right">{Math.round(p.MIN)}</td>
                  <td className="px-3 py-2.5 text-right font-bold text-white">{p.PTS}</td>
                  <td className="px-3 py-2.5 text-right">{p.REB}</td>
                  <td className="px-3 py-2.5 text-right">{p.AST}</td>
                  <td className="px-3 py-2.5 text-right">{p.STL}</td>
                  <td className="px-3 py-2.5 text-right">{p.BLK}</td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {p.FGM}-{p.FGA}
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {p.FG3M}-{p.FG3A}
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {p.FTM}-{p.FTA}
                  </td>
                  <td className={`px-3 py-2.5 text-right font-semibold ${pm > 0 ? "text-emerald" : pm < 0 ? "text-crimson" : "text-gray-400"}`}>
                    {pm > 0 ? `+${pm}` : pm}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}