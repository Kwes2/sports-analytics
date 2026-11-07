class StintTracker:
    def __init__(self, home_starters, away_starters, home_team_id, away_team_id):
        self.home_team_id = str(home_team_id)
        self.away_team_id = str(away_team_id)

        # Active 5-man on-court sets
        self.home_on_court = set(str(p) for p in home_starters)
        self.away_on_court = set(str(p) for p in away_starters)

        self.current_period = 1

        # Stint accumulators
        self.home_pts_stint = 0
        self.away_pts_stint = 0
        self.home_poss_stint = 0.0
        self.away_poss_stint = 0.0

    def process_play(self, play, player_pairs_ledger, player_stints_ledger, db_stints_collector=None, event_id=None, date_str=None):
        txt = play.get("text", "").lower()
        period = play.get("period", {}).get("number", 1)
        team_id = str(play.get("team", {}).get("id", ""))

        # 1. Period change trigger: commit stint before switching quarters
        if period != self.current_period:
            self.commit_stint(player_pairs_ledger, player_stints_ledger, db_stints_collector, event_id, date_str)
            self.current_period = period

        # 2. Track scoring points by team
        is_scoring = play.get("scoringPlay", False)
        score_val = play.get("scoreValue", 0)

        if is_scoring and score_val > 0:
            if team_id == self.home_team_id:
                self.home_pts_stint += score_val
            elif team_id == self.away_team_id:
                self.away_pts_stint += score_val

        # 3. Exact Possession Tracking
        if "defensive rebound" in txt or ("rebound" in txt and "offensive" not in txt):
            if team_id == self.home_team_id:
                self.away_poss_stint += 1.0
            elif team_id == self.away_team_id:
                self.home_poss_stint += 1.0

        elif "turnover" in txt or "lost ball" in txt or "bad pass" in txt or "traveling" in txt or "shot clock turnover" in txt:
            if team_id == self.home_team_id:
                self.home_poss_stint += 1.0
            elif team_id == self.away_team_id:
                self.away_poss_stint += 1.0

        elif "makes free throw" in txt and ("2 of 2" in txt or "3 of 3" in txt or "1 of 1" in txt or "technical" in txt):
            if team_id == self.home_team_id:
                self.home_poss_stint += 1.0
            elif team_id == self.away_team_id:
                self.away_poss_stint += 1.0

        elif is_scoring and ("jumper" in txt or "layup" in txt or "dunk" in txt or "three point" in txt or "shot" in txt):
            if team_id == self.home_team_id:
                self.home_poss_stint += 1.0
            elif team_id == self.away_team_id:
                self.away_poss_stint += 1.0

        # 4. Substitution Trigger: Commit stint, then update active lineup
        if "substitutions" in play.get("type", {}).get("text", "").lower() or "enters the game" in txt:
            participants = play.get("participants", [])
            if len(participants) >= 2:
                in_player = str(participants[0].get("athlete", {}).get("id", ""))
                out_player = str(participants[1].get("athlete", {}).get("id", ""))

                if in_player and out_player:
                    self.commit_stint(player_pairs_ledger, player_stints_ledger, db_stints_collector, event_id, date_str)

                    if out_player in self.home_on_court:
                        self.home_on_court.discard(out_player)
                        self.home_on_court.add(in_player)
                    elif out_player in self.away_on_court:
                        self.away_on_court.discard(out_player)
                        self.away_on_court.add(in_player)

    def commit_stint(self, player_pairs_ledger, player_stints_ledger, db_stints_collector=None, event_id=None, date_str=None):
        stint_poss = (self.home_poss_stint + self.away_poss_stint) / 2.0
        if stint_poss <= 0 and self.home_pts_stint == 0 and self.away_pts_stint == 0:
            return
        if stint_poss <= 0:
            stint_poss = 0.5

        home_list = list(self.home_on_court)
        away_list = list(self.away_on_court)

        # 1. Update individual on-court stats (used to build their personal baseline)
        for hp in home_list:
            if hp not in player_stints_ledger:
                player_stints_ledger[hp] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_stints_ledger[hp]["pts_for"] += self.home_pts_stint
            player_stints_ledger[hp]["pts_against"] += self.away_pts_stint
            player_stints_ledger[hp]["poss"] += stint_poss

        for ap in away_list:
            if ap not in player_stints_ledger:
                player_stints_ledger[ap] = {"pts_for": 0, "pts_against": 0, "poss": 0.0}
            player_stints_ledger[ap]["pts_for"] += self.away_pts_stint
            player_stints_ledger[ap]["pts_against"] += self.home_pts_stint
            player_stints_ledger[ap]["poss"] += stint_poss

        # 2. Update Teammates
        for i in range(len(home_list)):
            for j in range(i + 1, len(home_list)):
                p1, p2 = home_list[i], home_list[j]
                self._log_pair(player_pairs_ledger, p1, p2, self.home_pts_stint, self.away_pts_stint, stint_poss, is_teammate=True)
                self._log_pair(player_pairs_ledger, p2, p1, self.home_pts_stint, self.away_pts_stint, stint_poss, is_teammate=True)

        for i in range(len(away_list)):
            for j in range(i + 1, len(away_list)):
                p1, p2 = away_list[i], away_list[j]
                self._log_pair(player_pairs_ledger, p1, p2, self.away_pts_stint, self.home_pts_stint, stint_poss, is_teammate=True)
                self._log_pair(player_pairs_ledger, p2, p1, self.away_pts_stint, self.home_pts_stint, stint_poss, is_teammate=True)

        # 3. Update Opponents
        for hp in home_list:
            for ap in away_list:
                self._log_pair(player_pairs_ledger, hp, ap, self.home_pts_stint, self.away_pts_stint, stint_poss, is_teammate=False)
                self._log_pair(player_pairs_ledger, ap, hp, self.away_pts_stint, self.home_pts_stint, stint_poss, is_teammate=False)

        # 4. Save to Database Collector if provided
        if db_stints_collector is not None and event_id and date_str:
            import json
            db_stints_collector.append((
                event_id, date_str,
                json.dumps(home_list),
                json.dumps(away_list),
                self.home_pts_stint, self.away_pts_stint,
                stint_poss
            ))

        # Reset accumulators
        self.home_pts_stint = 0
        self.away_pts_stint = 0
        self.home_poss_stint = 0.0
        self.away_poss_stint = 0.0

    def _log_pair(self, ledger, p_main, p_target, pts_for, pts_against, poss, is_teammate):
        if p_main not in ledger:
            ledger[p_main] = {"teammates": {}, "opponents": {}}

        group = "teammates" if is_teammate else "opponents"
        if p_target not in ledger[p_main][group]:
            ledger[p_main][group][p_target] = {"poss": 0.0, "pts_for": 0, "pts_against": 0}

        ledger[p_main][group][p_target]["poss"] += poss
        ledger[p_main][group][p_target]["pts_for"] += pts_for
        ledger[p_main][group][p_target]["pts_against"] += pts_against