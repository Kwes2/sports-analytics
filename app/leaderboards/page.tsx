// app/leaderboards/page.tsx
import { getLeaderboards } from "@/lib/data";
import LeaderboardsClient from "./LeaderboardsClient";

export default function LeaderboardsPage() {
  const leaderboards = getLeaderboards("2026-27");

  return (
    <div className="space-y-6">
      <div className="border-b border-surface-border pb-5">
        <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
          Skill Matrix & Leaderboards
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Pre-sorted Top-20 league leaderboards across advanced empirical skills: regularized impact (EPM), shot creation, rim attack frequency, playmaking load, and defensive disruption.
        </p>
      </div>

      <LeaderboardsClient leaderboards={leaderboards} />
    </div>
  );
}