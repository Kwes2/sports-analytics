// app/player/[id]/page.tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getPlayerProfile, getPlayersIndex } from "@/lib/data";
import { ArrowLeft } from "lucide-react";
import PlayerProfileClient from "./PlayerProfileClient";

export async function generateStaticParams() {
  const players = getPlayersIndex("2026-27");
  if (players.length === 0) {
    return [{ id: "2544" }]; // Fallback dummy ID for LeBron James
  }
  return players.slice(0, 50).map((p) => ({
    id: String(p.player_id),
  }));
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PlayerPage({ params }: Props) {
  const { id } = await params;
  const player = getPlayerProfile(id, "2026-27") || getPlayerProfile(id, "2025-26");

  if (!player) {
    return (
      <div className="py-20 text-center space-y-4">
        <h2 className="text-xl font-bold text-white">Player Profile Not Found</h2>
        <p className="text-gray-400 text-xs font-mono">
          Could not locate player ID {id} in either 2026-27 or 2025-26 records.
        </p>
        <Link
          href="/players"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-accent hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> Return to Players Directory
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link
        href="/players"
        className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-gray-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="h-4 w-4 text-accent" /> Back to Players Directory
      </Link>

      <PlayerProfileClient player={player} />
    </div>
  );
}