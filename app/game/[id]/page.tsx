// app/game/[id]/page.tsx
import Link from "next/link";
import { getGamesFeed, getSingleGameData } from "@/lib/data";
import { ArrowLeft, Trophy, Zap } from "lucide-react";

export async function generateStaticParams() {
  const games = getGamesFeed("2026-27");
  if (games.length === 0) {
    return [{ id: "0022600006" }];
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

  const { player_boxscore } = gameData;
  const homeTid = summary.home_team.id;
  const awayTid = summary.away_team.id;

  const homePlayers = player_boxscore.filter((p: any) => Number(p.team_id) === homeTid || Number(p.TEAM_ID) === homeTid);
  const awayPlayers = player_boxscore.filter((p: any) => Number(p.team_id) === awayTid || Number(p.TEAM_ID) === awayTid);

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
            {players.map((p: any) => {
              const pm = Number(p.plus_minus || p.PLUS_MINUS || 0);
              const pId = p.player_id || p.PLAYER_ID;
              const pName = p.player_name || p.PLAYER_NAME;
              const pMin = Math.round(Number(p.min || p.MIN || 0));
              const pPts = p.pts || p.PTS || 0;
              const pReb = p.reb || p.REB || 0;
              const pAst = p.ast || p.AST || 0;
              const pStl = p.stl || p.STL || 0;
              const pBlk = p.blk || p.BLK || 0;
              const pFgm = p.fgm || p.FGM || 0;
              const pFga = p.fga || p.FGA || 0;
              const pFg3m = p.fg3m || p.FG3M || 0;
              const pFg3a = p.fg3a || p.FG3A || 0;
              const pFtm = p.ftm || p.FTM || 0;
              const pFta = p.fta || p.FTA || 0;

              return (
                <tr key={pId} className="hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-4 py-2.5 font-medium text-white flex items-center gap-2">
                    <Link
                      href={`/player/${pId}`}
                      className="hover:text-accent hover:underline truncate max-w-[150px]"
                    >
                      {pName}
                    </Link>
                  </td>
                  <td className="px-3 py-2.5 text-right">{pMin}</td>
                  <td className="px-3 py-2.5 text-right font-bold text-white">{pPts}</td>
                  <td className="px-3 py-2.5 text-right">{pReb}</td>
                  <td className="px-3 py-2.5 text-right">{pAst}</td>
                  <td className="px-3 py-2.5 text-right">{pStl}</td>
                  <td className="px-3 py-2.5 text-right">{pBlk}</td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {pFgm}-{pFga}
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    pFg3m-{pFg3a}
                  </td>
                  <td className="px-3 py-2.5 text-right text-gray-400">
                    {pFtm}-{pFta}
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