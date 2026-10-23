import fs from "fs";
import path from "path";
import Link from "next/link";
import { notFound } from "next/navigation";
import PlayerClientView from "./PlayerClientView";

type Props = {
  params: Promise<{ id: string }>;
};

export default async function PlayerPage({ params }: Props) {
  // Next.js 15/16 requires awaiting params
  const { id } = await params;

  const filePath = path.join(process.cwd(), "data", "processed", "players", `${id}.json`);

  if (!fs.existsSync(filePath)) {
    notFound();
  }

  const fileContent = fs.readFileSync(filePath, "utf-8");
  const playerData = JSON.parse(fileContent);

  return (
    <div className="max-w-6xl mx-auto px-6 py-10 font-sans">
      {/* Breadcrumb Navigation */}
      <div className="text-xs font-mono text-zinc-500 mb-6 flex items-center gap-2">
        <Link href="/" className="hover:text-zinc-300">Leaderboard</Link>
        <span>/</span>
        <span className="text-zinc-300">{playerData.profile.PLAYER_NAME}</span>
      </div>

      {/* Player Header Banner */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end pb-8 border-b border-zinc-800/80 gap-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-medium tracking-tight text-white">{playerData.profile.PLAYER_NAME}</h1>
            <span className="bg-zinc-900 border border-zinc-800 text-zinc-400 font-mono text-xs px-2.5 py-1 rounded">
              {playerData.profile.TEAM_ABBREVIATION}
            </span>
          </div>
          <p className="text-xs text-zinc-500 font-mono mt-2">
            Player ID: {playerData.profile.PLAYER_ID} • {playerData.profile.GP} Games Analyzed
          </p>
        </div>

        {/* Core Season Stat Cards */}
        <div className="grid grid-cols-4 gap-3 text-center">
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">PTS</div>
            <div className="text-lg font-bold text-white font-mono">{playerData.profile.PTS}</div>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">REB</div>
            <div className="text-lg font-bold text-white font-mono">{playerData.profile.REB}</div>
          </div>
          <div className="bg-zinc-900/50 border border-zinc-800/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-500 uppercase font-mono">AST</div>
            <div className="text-lg font-bold text-white font-mono">{playerData.profile.AST}</div>
          </div>
          <div className="bg-zinc-900/80 border border-zinc-700/80 px-4 py-2.5 rounded-lg">
            <div className="text-[10px] text-zinc-400 uppercase font-mono">HIR</div>
            <div className="text-lg font-bold text-white font-mono">{playerData.profile.HIR}</div>
          </div>
        </div>
      </header>

      {/* Interactive Client Component (Filtering & Game Logs) */}
      <PlayerClientView data={playerData} />
    </div>
  );
}