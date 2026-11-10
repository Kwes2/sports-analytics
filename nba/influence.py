import numpy as np

class InfluenceEngine:
    def __init__(self, active_players, baseline_engine, merged_pair_ledger, all_games_stints=None):
        self.active_players = active_players
        self.baseline_engine = baseline_engine
        self.merged_pair_ledger = merged_pair_ledger
        self.all_games_stints = all_games_stints if all_games_stints else []
        self.player_influences = {}
        
        self._calculate_decomposed_rapm()

    def _calculate_decomposed_rapm(self):
        """
        Solves for true isolated Offensive and Defensive impact using 
        Ridge-Regularized Adjusted Plus-Minus (RAPM) over all 10 players on the court.
        """
        if not self.all_games_stints:
            # Fallback if stints list wasn't provided
            for aid in self.active_players.keys():
                self.player_influences[aid] = {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0}
            return

        unique_players = sorted(list(self.active_players.keys()))
        player_to_idx = {pid: i for i, pid in enumerate(unique_players)}
        n_players = len(unique_players)
        
        # Columns: [Intercept, Offensive Players (N), Defensive Players (N)]
        total_cols = 1 + (2 * n_players)
        
        X_rows = []
        y_rows = []
        w_rows = []

        for sr in self.all_games_stints:
            poss = float(sr.get("poss", 0.0))
            if poss <= 0:
                continue
            
            h_lineup = sr.get("home_lineup", [])
            a_lineup = sr.get("away_lineup", [])
            
            if len(h_lineup) != 5 or len(a_lineup) != 5:
                continue

            h_pts = int(sr.get("home_pts", 0))
            a_pts = int(sr.get("away_pts", 0))

            home_ortg = (h_pts / poss) * 100.0
            away_ortg = (a_pts / poss) * 100.0

            # Row 1: Home Offense vs Away Defense
            row_home_off = np.zeros(total_cols)
            row_home_off[0] = 1.0  # Intercept (League Baseline)
            for p in h_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    row_home_off[1 + player_to_idx[pid]] += 1.0  # +1 for Home Offense
            for p in a_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    row_home_off[1 + n_players + player_to_idx[pid]] -= 1.0  # -1 for Away Defense

            X_rows.append(row_home_off)
            y_rows.append(home_ortg)
            w_rows.append(poss)

            # Row 2: Away Offense vs Home Defense
            row_away_off = np.zeros(total_cols)
            row_away_off[0] = 1.0  # Intercept
            for p in a_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    row_away_off[1 + player_to_idx[pid]] += 1.0  # +1 for Away Offense
            for p in h_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    row_away_off[1 + n_players + player_to_idx[pid]] -= 1.0  # -1 for Home Defense

            X_rows.append(row_away_off)
            y_rows.append(away_ortg)
            w_rows.append(poss)

        if not X_rows:
            for aid in self.active_players.keys():
                self.player_influences[aid] = {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0}
            return

        X = np.array(X_rows)
        y = np.array(y_rows)
        W = np.diag(np.array(w_rows))

        # Solve Ridge Regression with unpenalized intercept
        LAMBDA_REG = 3500.0
        
        XTW = X.T @ W
        XTWX = XTW @ X
        
        Lambda_mat = np.zeros((total_cols, total_cols))
        np.fill_diagonal(Lambda_mat[1:, 1:], LAMBDA_REG)
        
        try:
            beta = np.linalg.solve(XTWX + Lambda_mat, XTW @ y)
        except np.linalg.LinAlgError:
            # Fallback if matrix is completely singular (rare in large samples)
            beta = np.zeros(total_cols)

        # Extract ORAPM and DRAPM for every player
        for aid in self.active_players.keys():
            if aid in player_to_idx:
                idx = player_to_idx[aid]
                orapm = float(beta[1 + idx])
                drapm = float(beta[1 + n_players + idx])
                net_rapm = orapm + drapm
                
                self.player_influences[aid] = {
                    "orapm": round(orapm, 2),
                    "drapm": round(drapm, 2),
                    "net_rapm": round(net_rapm, 2)
                }
            else:
                self.player_influences[aid] = {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0}

    attr = property(lambda self: self.player_influences)

    def get_influence(self, player_id):
        return self.player_influences.get(str(player_id), {
            "orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0
        })