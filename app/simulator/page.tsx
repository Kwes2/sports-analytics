// app/simulator/page.tsx
import { getTeamsIndex, getMatchupSimulation } from "@/lib/data";
import SimulatorClient from "./SimulatorClient";

export default function SimulatorPage() {
  const teams = getTeamsIndex("2026-27");
  // Default featured simulation: Boston vs Los Angeles Lakers
  const defaultSimulation = getMatchupSimulation("BOS", "LAL", "2026-27") || getMatchupSimulation("BOS", "LAL", "2025-26");

  return (
    <div className="space-y-6">
      <div className="border-b border-surface-border pb-5">
        <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
          Game Night Matchup Simulator
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Tactical head-to-head matchup engine. Pit any two NBA teams against each other to calculate projected scores, 1,000-centered Elo win probabilities, and tactical clash edges.
        </p>
      </div>

      <SimulatorClient teams={teams} initialSimulation={defaultSimulation} />
    </div>
  );
}