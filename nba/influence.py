class InfluenceEngine:
    def __init__(self, active_players, baseline_engine, merged_pair_ledger):
        self.active_players = active_players
        self.baseline_engine = baseline_engine
        self.merged_pair_ledger = merged_pair_ledger
        self.player_influences = {}
        self._calculate_influences()

    def _calculate_influences(self):
        """
        Calculates each player's influence by evaluating each teammate and opponent
        strictly against that co-player's OWN personal baseline.
        """
        for aid, p in self.active_players.items():
            pair_data = self.merged_pair_ledger.get(aid, {"teammates": {}, "opponents": {}})

            # ----------------------------------------------------
            # 1. Teammate Influence (Evaluated Independently per Teammate)
            # ----------------------------------------------------
            t_off_diff_sum = 0.0
            t_def_diff_sum = 0.0
            t_poss_total = 0.0

            for t_id, data in pair_data.get("teammates", {}).items():
                poss = data["poss"]
                # Minimum threshold of shared possessions to prevent 1-second anomalies
                if poss < 5.0:
                    continue

                actual_ortg = (data["pts_for"] / poss) * 100.0
                actual_drtg = (data["pts_against"] / poss) * 100.0

                # Get teammate's own personal baseline
                t_base = self.baseline_engine.get_baseline(t_id)

                # Did teammate perform better or worse than teammate's personal baseline?
                delta_off = actual_ortg - t_base["ortg"]
                delta_def = t_base["drtg"] - actual_drtg  # Positive = team allowed fewer points than baseline

                t_off_diff_sum += (delta_off * poss)
                t_def_diff_sum += (delta_def * poss)
                t_poss_total += poss

            if t_poss_total > 0:
                teammate_off_impact = round(t_off_diff_sum / t_poss_total, 2)
                teammate_def_impact = round(t_def_diff_sum / t_poss_total, 2)
                teammate_overall_impact = round(teammate_off_impact + teammate_def_impact, 2)
            else:
                teammate_off_impact = 0.0
                teammate_def_impact = 0.0
                teammate_overall_impact = 0.0

            # ----------------------------------------------------
            # 2. Opponent Influence (Evaluated Independently per Opponent)
            # ----------------------------------------------------
            o_suppression_sum = 0.0
            o_stress_sum = 0.0
            o_poss_total = 0.0

            for o_id, data in pair_data.get("opponents", {}).items():
                poss = data["poss"]
                if poss < 5.0:
                    continue

                # When facing this opponent:
                # Opponent's offensive output = points opponent scored against us
                opp_actual_ortg = (data["pts_against"] / poss) * 100.0
                # Opponent's defensive output = points we scored on opponent
                opp_actual_drtg = (data["pts_for"] / poss) * 100.0

                # Get opponent's own personal baseline
                o_base = self.baseline_engine.get_baseline(o_id)

                # Suppression: Did opponent score less than opponent's own personal baseline?
                delta_suppression = o_base["ortg"] - opp_actual_ortg
                # Stress: Did opponent's defense concede more than opponent's baseline?
                delta_stress = opp_actual_drtg - o_base["drtg"]

                o_suppression_sum += (delta_suppression * poss)
                o_stress_sum += (delta_stress * poss)
                o_poss_total += poss

            if o_poss_total > 0:
                opponent_off_impact = round(o_suppression_sum / o_poss_total, 2)
                opponent_def_impact = round(o_stress_sum / o_poss_total, 2)
                opponent_overall_impact = round(opponent_off_impact + opponent_def_impact, 2)
            else:
                opponent_off_impact = 0.0
                opponent_def_impact = 0.0
                opponent_overall_impact = 0.0

            # ----------------------------------------------------
            # 3. Master Metric: OverallImpact (50/50 balance)
            # ----------------------------------------------------
            overall_impact = round(0.5 * teammate_overall_impact + 0.5 * opponent_overall_impact, 2)

            self.player_influences[aid] = {
                "teammate_off_impact": teammate_off_impact,
                "teammate_def_impact": teammate_def_impact,
                "teammate_overall_impact": teammate_overall_impact,
                "opponent_off_impact": opponent_off_impact,
                "opponent_def_impact": opponent_def_impact,
                "opponent_overall_impact": opponent_overall_impact,
                "overall_impact": overall_impact
            }

    attr = property(lambda self: self.player_influences)

    def get_influence(self, player_id):
        return self.player_influences.get(str(player_id), {
            "teammate_off_impact": 0.0, "teammate_def_impact": 0.0, "teammate_overall_impact": 0.0,
            "opponent_off_impact": 0.0, "opponent_def_impact": 0.0, "opponent_overall_impact": 0.0,
            "overall_impact": 0.0
        })