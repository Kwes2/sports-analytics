import fs from "fs";
import path from "path";
import Link from "next/link";
import { notFound } from "next/navigation";

type Props = {
  params: Promise<{ abbrev: string }>;
};

type RosterPlayer = {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  HIR: number;
  PTS: number;
  MIN: number;
};

type GameSummary = {
  game_id: string;
  game_date: string;
  matchup: string;
  teams: { TEAM_ABBREVIATION: string; PTS: number }[];
};

export default async function TeamPage({ params }: Props) {
  const { abbrev } = await params;
  const upperAbbrev = abbrev.toUpperCase();

  const teamFilePath = path.join(process.cwd(), "data", "processed", "teams", `${upperAbbrev}.json`);
  const gamesFilePath = path.join(process.cwd(), "data", "processed", "summary_games.json");

  if (!fs.existsSync(teamFilePath)) {
    notFound();
  }

  const teamData = JSON.parse(fs.readFileSync(teamFilePath, "utf-8"));
  const allGames: GameSummary[] = fs.existsSync(gamesFilePath)
    ? JSON.parse(fs.readFileSync(gamesFilePath, "utf-8")).games || []
    : [];

  // Filter games involving this franchise
  const teamGames = allGames.filter((g) =>
    g.teams.some((t) => t.TEAM_ABBREVIATION === upperAbbrev)
  );

  const roster: RosterPlayer[] = (teamData.roster as RosterPlayer[]).sort((a, b) => b.HIR - a.HIR);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 font-sans">
      {/* Breadcrumb */}
      <div className="text-xs font-mono text-zinc-500 mb-6 flex items-center gap-2">
        <Link href="/teams" className="hover:text-zinc-300">Standings</Link>
        <span>/</span>
        <span className="text-zinc-300">{upperAbbrev}</span>
      </div>

      {/* Team Header Banner */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end pb-8 border-b border-zinc-800/80 gap-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-medium tracking-tight text-white">{upperAbbrev}</h1>
            <span className="bg-zinc-900 border border-zinc-800 text-zinc-400 font-mono text-xs px-2.5 py-1 rounded">
              Franchise Hub
            </span>
          </div>
          <p className="text-xs text-zinc-500 font-mono mt-2">
            Record: {teamData.profile.W}W - {teamData.profile.L}L • Win%: {(teamData.profile.WIN_PCT * 100).toFixed(1)}%
          </p>
        </div>

        {/* Record Cards */}
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">Games</div>
            <div className="text-lg font-bold text-white font-mono">{teamData.profile.GP}</div>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">Wins</div>
            <div className="text-lg font-bold text-emerald-400 font-mono">{teamData.profile.W}</div>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">Losses</div>
            <div className="text-lg font-bold text-rose-400 font-mono">{teamData.profile.L}</div>
          </div>
        </div>
      </header>

      {/* Grid: Roster on Left, Recent Schedule on Right */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Roster Table (2 cols) */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-medium text-white">Active Roster & Impact Matrix</h2>
            <span className="text-xs text-zinc-500 font-mono">Ranked by Holistic Impact</span>
          </div>

          <div className="overflow-x-auto border border-zinc-800/80 rounded-lg">
            <table className="w-full text-left text-xs text-zinc-400">
              <thead className="bg-zinc-900/40 text-zinc-500 uppercase tracking-wider font-mono text-[10px] border-b border-zinc-800/80">
                <tr>
                  <th className="py-2.5 px-3">Player</th>
                  <th className="py-2.5 px-3">MIN</th>
                  <th className="py-2.5 px-3">PTS</th>
                  <th className="py-2.5 px-3 text-white bg-zinc-900/60 font-semibold">HIR</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 font-mono text-xs tabular-nums">
                {roster.map((player) => (
                  <tr key={player.PLAYER_ID} className="hover:bg-zinc-900/30 transition-colors">
                    <td className="py-2.5 px-3 font-sans font-medium text-zinc-200">
                      <Link
                        href={`/player/${player.PLAYER_ID}`}
                        className="hover:underline hover:text-white transition"
                      >
                        {player.PLAYER_NAME}
                      </Link>
                    </td>
                    <td className="py-2.5 px-3">{player.MIN}</td>
                    <td className="py-2.5 px-3 text-zinc-200 font-semibold">{player.PTS}</td>
                    <td className="py-2.5 px-3 font-bold text-white bg-zinc-900/20">{player.HIR}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Matchups Schedule (1 col) */}
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-white">Matchup Log</h2>

          <div className="space-y-2">
            {teamGames.map((game) => {
              const myTeam = game.teams.find((t) => t.TEAM_ABBREVIATION === upperAbbrev);
              const oppTeam = game.teams.find((t) => t.TEAM_ABBREVIATION !== upperAbbrev);
              const isWin = (myTeam?.PTS || 0) > (oppTeam?.PTS || 0);

              return (
                <Link
                    key={game.game_id}
                    href={`/game/${game.game_id}`}
                    className="p-3.5 border border-zinc-800/80 bg-zinc-900/20 hover:bg-zinc-900/50 hover:border-zinc-700 transition rounded-lg flex items-center justify-between font-mono text-xs cursor-pointer block"
                    >
                  <div>
                    <div className="text-zinc-500 text-[10px]">{game.game_date}</div>
                    <div className="text-zinc-300 font-sans mt-0.5">{game.matchup}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-bold ${isWin ? "text-emerald-400" : "text-rose-400"}`}>
                      {isWin ? "W" : "L"} {myTeam?.PTS} - {oppTeam?.PTS}
                    </div>
                  </div>
                </Link>
              );
            })}

            {teamGames.length === 0 && (
              <div className="p-4 border border-zinc-800/60 rounded-lg text-xs text-zinc-500 font-mono">
                No recent matches recorded.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}