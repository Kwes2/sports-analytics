// app/team/[abbrev]/page.tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTeamProfile, getTeamsIndex } from "@/lib/data";
import { ArrowLeft } from "lucide-react";
import TeamProfileClient from "./TeamProfileClient";

export async function generateStaticParams() {
  const teams = getTeamsIndex("2026-27");
  return teams.map((t) => ({
    abbrev: t.team_abbrev.toLowerCase(),
  }));
}

interface Props {
  params: Promise<{ abbrev: string }>;
}

export default async function TeamPage({ params }: Props) {
  const { abbrev } = await params;
  const team = getTeamProfile(abbrev, "2026-27") || getTeamProfile(abbrev, "2025-26");

  if (!team) {
    return (
      <div className="py-20 text-center space-y-4">
        <h2 className="text-xl font-bold text-white">Team Not Found</h2>
        <p className="text-gray-400 text-xs font-mono">
          Could not locate team {abbrev.toUpperCase()} in the database.
        </p>
        <Link
          href="/teams"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-accent hover:underline"
        >
          <ArrowLeft className="h-4 w-4" /> Return to Teams Overview
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link
        href="/teams"
        className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-gray-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="h-4 w-4 text-accent" /> Back to Teams Overview
      </Link>

      <TeamProfileClient team={team} />
    </div>
  );
}