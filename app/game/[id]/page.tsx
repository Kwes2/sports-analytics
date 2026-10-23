import fs from "fs";
import path from "path";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Trophy } from "lucide-react";

type Props = {
  params: Promise<{ id: string }>;
};

type BoxScorePlayer = {
  PLAYER_ID: number;
  PLAYER_NAME: string;
  TEAM_ABBREVIATION: string;
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

export default async function GameDetailPage({ params }: Props) {
  const { id } = await params;

  const gameFilePath = path.join(process.cwd(), "data", "processed", "games", `${id}.json`);

  if (!fs.existsSync(gameFilePath)) {
    notFound();
  }

  const gameData = JSON.parse(fs.readFileSync(gameFilePath, "utf-8"));
  const teamA = gameData.teams[0];
  const teamB = gameData.teams[1];

  const boxScore: BoxScorePlayer[] = gameData.box_score || [];
  const playersA = boxScore.filter((p) => p.TEAM_ABBREVIATION === teamA?.TEAM_ABBREVIATION);
  const playersB = boxScore.filter((p) => p.TEAM_ABBREVIATION === teamB?.TEAM_ABBREVIATION);

  // Determine Game MVP by highest Holistic Impact Rating (HIR)
  const mvp = [...boxScore].sort((a, b) => b.HIR - a.HIR)[0];

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 font-sans">
      {/* Breadcrumb */}
      <div className="text-xs font-mono text-zinc-500 mb-6 flex items-center gap-2">
        <Link href="/games" className="hover:text-zinc-300">Games</Link>
        <span>/</span>
        <span className="text-zinc-300">{gameData.matchup} ({gameData.game_date})</span>
      </div>

      {/* Final Score Banner */}
      <header className="border border-zinc-800/80 bg-zinc-900/30 p-6 rounded-xl flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-8">
          <div className="text-center">
            <Link href={`/team/${teamA?.TEAM_ABBREVIATION}`} className="text-2xl font-bold text-white hover:underline">
              {teamA?.TEAM_ABBREVIATION}
            </Link>
            <div className="text-3xl font-mono font-bold text-white mt-1">{teamA?.PTS}</div>
          </div>

          <div className="text-xs font-mono text-zinc-600 uppercase">FINAL</div>

          <div className="text-center">
            <Link href={`/team/${teamB?.TEAM_ABBREVIATION}`} className="text-2xl font-bold text-white hover:underline">
              {teamB?.TEAM_ABBREVIATION}
            </Link>
            <div className="text-3xl font-mono font-bold text-white mt-1">{teamB?.PTS}</div>
          </div>
        </div>

        {/* Game MVP Badge */}
        {mvp && (
          <div className="border border-zinc-800 bg-zinc-950/80 px-4 py-3 rounded-lg flex items-center gap-3">
            <Trophy className="w-5 h-5 text-amber-400" />
            <div>
              <div className="text-[10px] uppercase font-mono text-zinc-500">Game Top Impact Rating</div>
              <div className="text-sm font-medium text-white">
                <Link href={`/player/${mvp.PLAYER_ID}`} className="hover:underline">
                  {mvp.PLAYER_NAME}
                </Link>{" "}
                <span className="text-xs font-mono text-zinc-500">({mvp.TEAM_ABBREVIATION})</span>
              </div>
              <div className="text-xs font-mono text-zinc-400">
                {mvp.PTS} PTS • {mvp.REB} REB • {mvp.AST} AST • <span className="text-white font-bold">{mvp.HIR} HIR</span>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Box Scores */}
      <div className="mt-10 space-y-10">
        {/* Team A Box Score */}
        <BoxScoreTable teamAbbr={teamA?.TEAM_ABBREVIATION} players={playersA} />

        {/* Team B Box Score */}
        <BoxScoreTable teamAbbr={teamB?.TEAM_ABBREVIATION} players={playersB} />
      </div>
    </div>
  );
}

function BoxScoreTable({ teamAbbr, players }: { teamAbbr: string; players: BoxScorePlayer[] }) {
  const sorted = [...players].sort((a, b) => b.HIR - a.HIR);

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center">
        <h2 className="text-base font-semibold text-white">
          <Link href={`/team/${teamAbbr}`} className="hover:underline">
            {teamAbbr}
          </Link>{" "}
          <span className="text-xs font-mono text-zinc-500 font-normal">Box Score</span>
        </h2>
        <span className="text-xs font-mono text-zinc-500">Ranked by HIR</span>
      </div>

      <div className="overflow-x-auto border border-zinc-800/80 rounded-lg">
        <table className="w-full text-left text-xs text-zinc-400">
          <thead className="bg-zinc-900/40 text-zinc-500 uppercase tracking-wider font-mono text-[10px] border-b border-zinc-800/80">
            <tr>
              <th className="py-2.5 px-3">Player</th>
              <th className="py-2.5 px-2">MIN</th>
              <th className="py-2.5 px-2">PTS</th>
              <th className="py-2.5 px-2">REB</th>
              <th className="py-2.5 px-2">AST</th>
              <th className="py-2.5 px-2">STL</th>
              <th className="py-2.5 px-2">BLK</th>
              <th className="py-2.5 px-2">TOV</th>
              <th className="py-2.5 px-2">FG</th>
              <th className="py-2.5 px-2">3PT</th>
              <th className="py-2.5 px-2">TS%</th>
              <th className="py-2.5 px-3 text-white bg-zinc-900/60 font-semibold">HIR</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 font-mono text-xs tabular-nums">
            {sorted.map((p) => (
              <tr key={p.PLAYER_ID} className="hover:bg-zinc-900/30 transition-colors">
                <td className="py-2.5 px-3 font-sans font-medium text-zinc-200">
                  <Link href={`/player/${p.PLAYER_ID}`} className="hover:underline hover:text-white transition">
                    {p.PLAYER_NAME}
                  </Link>
                </td>
                <td className="py-2.5 px-2">{p.MIN}</td>
                <td className="py-2.5 px-2 font-semibold text-zinc-100">{p.PTS}</td>
                <td className="py-2.5 px-2">{p.REB}</td>
                <td className="py-2.5 px-2">{p.AST}</td>
                <td className="py-2.5 px-2">{p.STL}</td>
                <td className="py-2.5 px-2">{p.BLK}</td>
                <td className="py-2.5 px-2 text-zinc-500">{p.TOV}</td>
                <td className="py-2.5 px-2 text-zinc-500">{p.FGM}/{p.FGA}</td>
                <td className="py-2.5 px-2 text-zinc-500">{p.FG3M}/{p.FG3A}</td>
                <td className="py-2.5 px-2">{p.TS_PCT}%</td>
                <td className="py-2.5 px-3 font-bold text-white bg-zinc-900/20">{p.HIR}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}