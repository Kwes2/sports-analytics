class BaselineEngine:
    def __init__(self, active_players, player_game_stints_history, team_game_ledgers):
        self.active_players = active_players
        self.player_game_stints_history = player_game_stints_history
        self.team_game_ledgers = team_game_ledgers
        self.player_baselines = {}
        self.team_baselines = {}
        self._compute_team_baselines()
        self._compute_player_baselines()

    def _compute_team_baselines(self):
        """Computes rolling team baselines directly from on-court points and possessions."""
        for tid, ledger in self.team_game_ledgers.items():
            recent_games = ledger[-30:]
            if not recent_games:
                continue

            tot_pts = sum(g["pts"] for g in recent_games)
            tot_opp_pts = sum(g["opp_pts"] for g in recent_games)
            tot_fga = sum(g["fga"] for g in recent_games)
            tot_to = sum(g["to"] for g in recent_games)
            tot_fta = sum(g["fta"] for g in recent_games)
            tot_oreb = sum(g["oreb"] for g in recent_games)

            poss = 0.96 * (tot_fga + tot_to + 0.44 * tot_fta - tot_oreb)
            ortg_base = (tot_pts / poss * 100.0) if poss > 0 else 112.0
            drtg_base = (tot_opp_pts / poss * 100.0) if poss > 0 else 112.0

            self.team_baselines[str(tid)] = {
                "ortg": ortg_base,
                "drtg": drtg_base,
                "net_rtg": ortg_base - drtg_base
            }

    def _compute_player_baselines(self):
        """
        Computes each player's TRUE on-court personal baseline across their last 30 games.
        Personal Baseline = (Points scored while on court / Possessions while on court) * 100
        """
        for aid, p in self.active_players.items():
            team_id = str(p.get("team_id", ""))
            t_base = self.team_baselines.get(team_id, {"ortg": 112.0, "drtg": 112.0, "net_rtg": 0.0})

            # Get player's on-court stint history across their games
            stint_games = self.player_game_stints_history.get(aid, [])
            recent_stints = stint_games[-30:]  # Last 30 games of on-court action

            tot_poss = sum(g.get("poss", 0.0) for g in recent_stints)
            tot_pts_for = sum(g.get("pts_for", 0) for g in recent_stints)
            tot_pts_against = sum(g.get("pts_against", 0) for g in recent_stints)

            # Fallback to team baseline if player has less than 100 possessions on court
            if tot_poss < 100.0:
                self.player_baselines[aid] = {
                    "ortg": t_base["ortg"],
                    "drtg": t_base["drtg"],
                    "net_rtg": t_base["net_rtg"],
                    "poss": tot_poss,
                    "is_fallback": True
                }
            else:
                # Pure empirical personal baseline
                p_ortg = (tot_pts_for / tot_poss) * 100.0
                p_drtg = (tot_pts_against / tot_poss) * 100.0

                self.player_baselines[aid] = {
                    "ortg": p_ortg,
                    "drtg": p_drtg,
                    "net_rtg": p_ortg - p_drtg,
                    "poss": tot_poss,
                    "is_fallback": False
                }

    def get_baseline(self, player_id):
        return self.player_baselines.get(str(player_id), {
            "ortg": 112.0, "drtg": 112.0, "net_rtg": 0.0, "is_fallback": True
        })