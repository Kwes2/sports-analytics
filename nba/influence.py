"""
influence.py - Solves for isolated Offensive and Defensive impact using 
Ridge-Regularized Adjusted Plus-Minus (RAPM) over all 10 players on the court.
Memory-optimized with Streaming Normal Equations:
Maintains a constant ~5 MB matrix footprint regardless of whether there are 
100 stints or 500,000 stints. Eliminates 512MB OOM crashes completely.
"""

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
        Solves (X^T W X + lambda*I) beta = X^T W y using streaming outer-product accumulation.
        Does NOT allocate an N x M matrix in memory; works directly in M x M (~5MB RAM).
        """
        if not self.all_games_stints or not self.active_players:
            for aid in self.active_players.keys():
                self.player_influences[aid] = {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0}
            return

        unique_players = sorted(list(self.active_players.keys()))
        player_to_idx = {pid: i for i, pid in enumerate(unique_players)}
        n_players = len(unique_players)
        
        # Columns: [0: Intercept, 1..N: Offense, N+1..2N: Defense]
        total_cols = 1 + (2 * n_players)
        
        # Allocate the M x M Normal Equation matrix directly (~4.8 MB for 1100 players)
        # A = X^T W X, b = X^T W y
        A = np.zeros((total_cols, total_cols), dtype=np.float32)
        b = np.zeros(total_cols, dtype=np.float32)

        stint_count = 0

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

            # -------------------------------------------------------------
            # Sub-stint 1: Home Offense vs Away Defense
            # -------------------------------------------------------------
            # Active indices: Intercept (0), 5 Home Offense (+1), 5 Away Defense (-1)
            active_h_off = []
            active_h_off.append((0, 1.0))
            for p in h_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    active_h_off.append((1 + player_to_idx[pid], 1.0))
            for p in a_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    active_h_off.append((1 + n_players + player_to_idx[pid], -1.0))

            # Stream accumulate outer product into A: A += w * (x * x^T)
            for col_i, val_i in active_h_off:
                b[col_i] += poss * val_i * home_ortg
                w_val_i = poss * val_i
                for col_j, val_j in active_h_off:
                    A[col_i, col_j] += w_val_i * val_j

            # -------------------------------------------------------------
            # Sub-stint 2: Away Offense vs Home Defense
            # -------------------------------------------------------------
            active_a_off = []
            active_a_off.append((0, 1.0))
            for p in a_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    active_a_off.append((1 + player_to_idx[pid], 1.0))
            for p in h_lineup:
                pid = str(p)
                if pid in player_to_idx:
                    active_a_off.append((1 + n_players + player_to_idx[pid], -1.0))

            for col_i, val_i in active_a_off:
                b[col_i] += poss * val_i * away_ortg
                w_val_i = poss * val_i
                for col_j, val_j in active_a_off:
                    A[col_i, col_j] += w_val_i * val_j

            stint_count += 1

        if stint_count == 0:
            for aid in self.active_players.keys():
                self.player_influences[aid] = {"orapm": 0.0, "drapm": 0.0, "net_rapm": 0.0}
            return

        # Add Ridge Regularization Penalty lambda (unpenalized intercept at index 0)
        # Scaled to sample size: LAMBDA_REG = 3000.0
        LAMBDA_REG = 3000.0
        for i in range(1, total_cols):
            A[i, i] += LAMBDA_REG

        # Solve (A + lambda*I) beta = b in 4.8MB RAM
        try:
            beta = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            try:
                # Fallback to pseudo-inverse if singular
                beta = np.linalg.lstsq(A, b, rcond=1e-4)[0]
            except Exception:
                beta = np.zeros(total_cols, dtype=np.float32)

        # Extract genuine decomposed ORAPM and DRAPM for every player
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