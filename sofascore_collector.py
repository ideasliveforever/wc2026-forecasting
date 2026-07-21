import requests
import time
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class MatchStats:
    corners: int = 0
    fouls: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    shots_on_target: int = 0
    shots_total: int = 0
    offsides: int = 0
    goals: int = 0
    goals_conceded: int = 0
    possession: float = 0.0


class SofaScoreCollector:
    """Primary data source. Pulls actual match stats from SofaScore."""

    BASE = "https://api.sofascore.com/api/v1"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        self._team_id_cache = {}

    def get_team_averages(self, team_name, last_n=6):
        """
        Get per-game averages from last N matches.
        Returns None if team not found → triggers base rate fallback.
        """
        team_id = self._find_team_id(team_name)
        if not team_id:
            return None

        matches = self._get_recent_matches(team_id, last_n)
        if not matches:
            return None

        all_stats = []
        for match in matches:
            stats = self._get_match_stats(match["event_id"], team_id, match)
            if stats:
                all_stats.append(stats)
            time.sleep(1.5)

        if not all_stats:
            return None

        n = len(all_stats)
        averages = {
            "team": team_name,
            "source": "sofascore",
            "matches_sampled": n,
            "goals_per_90": round(sum(s.goals for s in all_stats) / n, 2),
            "goals_conceded_per_90": round(sum(s.goals_conceded for s in all_stats) / n, 2),
            "corners_per_90": round(sum(s.corners for s in all_stats) / n, 2),
            "fouls_committed_per_90": round(sum(s.fouls for s in all_stats) / n, 2),
            "yellow_cards_per_90": round(sum(s.yellow_cards for s in all_stats) / n, 2),
            "red_cards_per_90": round(sum(s.red_cards for s in all_stats) / n, 2),
            "shots_on_target_per_90": round(sum(s.shots_on_target for s in all_stats) / n, 2),
            "shots_total_per_90": round(sum(s.shots_total for s in all_stats) / n, 2),
            "offsides_per_90": round(sum(s.offsides for s in all_stats) / n, 2),
            "possession_avg": round(sum(s.possession for s in all_stats) / n, 1),
        }

        print(f"    SofaScore: {team_name} → {n} matches sampled")
        return averages

    def _find_team_id(self, team_name):
        """Search for team ID on SofaScore."""
        if team_name.lower() in self._team_id_cache:
            return self._team_id_cache[team_name.lower()]

        search_terms = [team_name, f"{team_name} national"]

        for term in search_terms:
            try:
                resp = self.session.get(
                    f"{self.BASE}/search/teams/{term}/1",
                    timeout=10,
                )
                time.sleep(1)

                if resp.status_code != 200:
                    continue

                data = resp.json()
                teams = data.get("teams", [])

                for team in teams:
                    name = team.get("name", "").lower()
                    team_type = team.get("type", "")

                    # Prefer national teams
                    if (team_name.lower() in name or name in team_name.lower()):
                        team_id = team.get("id")
                        self._team_id_cache[team_name.lower()] = team_id
                        return team_id

            except Exception:
                continue

        return None

    def _get_recent_matches(self, team_id, last_n):
        """Get last N completed matches."""
        try:
            resp = self.session.get(
                f"{self.BASE}/team/{team_id}/events/last/0",
                timeout=10,
            )
            time.sleep(1)

            if resp.status_code != 200:
                return []

            data = resp.json()
            events = data.get("events", [])

            completed = []
            for event in events:
                status = event.get("status", {})
                if status.get("type") == "finished":
                    completed.append({
                        "event_id": event["id"],
                        "home_team_id": event.get("homeTeam", {}).get("id"),
                        "away_team_id": event.get("awayTeam", {}).get("id"),
                        "home_score": event.get("homeScore", {}).get("current", 0),
                        "away_score": event.get("awayScore", {}).get("current", 0),
                    })

            return completed[-last_n:]

        except Exception:
            return []

    def _get_match_stats(self, event_id, team_id, match_info):
        """Get detailed stats for one match."""
        try:
            # Determine if our team was home or away
            is_home = (match_info.get("home_team_id") == team_id)

            stats = MatchStats()
            stats.goals = match_info["home_score"] if is_home else match_info["away_score"]
            stats.goals_conceded = match_info["away_score"] if is_home else match_info["home_score"]

            # Get detailed statistics
            resp = self.session.get(
                f"{self.BASE}/event/{event_id}/statistics",
                timeout=10,
            )

            if resp.status_code != 200:
                # Still return basic goal data even without detailed stats
                return stats

            data = resp.json()
            statistics = data.get("statistics", [])

            for period in statistics:
                # Only use "ALL" period (full match), not per-half
                period_name = period.get("period", "").upper()
                if period_name not in ["ALL", ""]:
                    continue

                groups = period.get("groups", [])
                for group in groups:
                    items = group.get("statisticsItems", [])
                    for item in items:
                        name = item.get("name", "").lower()
                        home_val = self._parse_val(item.get("home", "0"))
                        away_val = self._parse_val(item.get("away", "0"))
                        our_val = home_val if is_home else away_val

                        if "corner" in name:
                            stats.corners = our_val
                        elif name == "fouls" or name == "total fouls":
                            stats.fouls = our_val
                        elif "yellow card" in name:
                            stats.yellow_cards = our_val
                        elif "red card" in name:
                            stats.red_cards = our_val
                        elif "shots on target" in name or name == "on target":
                            stats.shots_on_target = our_val
                        elif name == "total shots" or name == "shots":
                            stats.shots_total = our_val
                        elif "offside" in name:
                            stats.offsides = our_val
                        elif "possession" in name:
                            stats.possession = our_val

            return stats

        except Exception:
            return None

    def _parse_val(self, val):
        """Parse stat value from API response."""
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            val = val.replace("%", "").strip()
            try:
                return int(float(val))
            except:
                return 0
        return 0