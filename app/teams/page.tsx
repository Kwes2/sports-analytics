// app/teams/page.tsx
import { getTeamsIndex } from "@/lib/data";
import TeamsTableClient from "./TeamsTableClient";

export default function TeamsPage() {
  const teams = getTeamsIndex("2026-27");

  return (
    <div className="space-y-6">
      <div className="border-b border-surface-border pb-5">
        <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
          Teams Overview & Elo Ratings
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Complete 30-team ratings table. Compare possession-adjusted 2-way efficiency (ORTG/DRTG), 1,000-centered Elo ratings, and pace across the active 2026-27 season.
        </p>
      </div>

      <TeamsTableClient initialTeams={teams} />
    </div>
  );
}