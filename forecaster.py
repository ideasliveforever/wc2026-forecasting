import google.generativeai as genai
import re
import time
import numpy as np
from typing import Dict, List, Optional
from config import config
from math_engine import (
    poisson_over, poisson_under, btts_probability,
    clean_sheet_probability, apply_confidence_ceiling,
    market_anchor_adjust, or_probability, and_probability
)
from question_classifier import classify_question, QuestionProfile
from sofascore_collector import SofaScoreCollector
from base_rates import get_base_rates, get_tier, get_confederation, WC_BASE_RATES
from market_data import MarketDataCollector

try:
    from team_aliases import resolve_team
except ImportError:
    def resolve_team(name):
        return name.lower().strip()

try:
    from player_data import PLAYER_SOT, PLAYER_MINUTES, PLAYER_DATA_QUALITY, PLAYER_POSITION
except ImportError:
    PLAYER_SOT = {}
    PLAYER_MINUTES = {}
    PLAYER_DATA_QUALITY = {}
    PLAYER_POSITION = {}

try:
    from referee_data import REFEREE
except ImportError:
    REFEREE = {"name": "", "yellows_per_game": 0, "reds_per_game": 0, "penalties_per_game": 0}

try:
    from match_context import CONTEXT
except ImportError:
    CONTEXT = {}

try:
    from elo_data import elo_win_prob
except ImportError:
    elo_win_prob = None

genai.configure(api_key=config.GEMINI_API_KEY)


SYSTEM_PROMPT = """You are a calibrated sports probability superforecaster for the FIFA World Cup 2026.

CRITICAL: RBP rewards being closer to outcome than crowd. Don't be extreme without evidence.

RULES (140+ questions):
- Player props resolve NO 79%. Output 15-25% for unknowns, 35-45% for CONFIRMED STARTERS.
- Offside 2+ resolves YES 31%. Output 32-42%. NEVER above 48%.
- Penalty OR red resolves YES ~15%. Output 20-28%.
- 4+ cards ~50%. Output 42-50%.
- Single team 5+ corners ~35%. NEVER above 55%.
- Favorites win only 43% in WC.
- Fouls comparison: unpredictable. Stay 40-60%.
- AND questions: multiply P(A) × P(B). Output 25-35%.
- Total goals: NEVER below 20%.
- NEVER be extreme without Kalshi backing.

STAGE DISCOUNT:
- Group MD1: λ × 0.88
- Group MD2: λ × 0.95
- Group MD3 must-win: λ × 1.05
- Group MD3 dead rubber: λ × 0.82

Output ONLY a single integer 1-99."""


CROWD_BIAS = {
    "player_goal": {"target_min": 0.12, "target_max": 0.30},
    "player_sot": {"target_min": 0.15, "target_max": 0.35},
    "score_or_assist": {"target_min": 0.12, "target_max": 0.30},
    "offsides_2plus": {"target_min": 0.28, "target_max": 0.45},
    "penalty_or_red": {"target_min": 0.18, "target_max": 0.28},
    "cards_4plus": {"target_min": 0.40, "target_max": 0.52},
    "team_score_half_strong": {"target_min": 0.48, "target_max": 0.62},
    "team_score_half_weak": {"target_min": 0.35, "target_max": 0.50},
    "underdog_more": {"target_min": 0.25, "target_max": 0.42},
    "favorite_more_sot": {"target_min": 0.52, "target_max": 0.68},
}

STAGE_DISCOUNT = {
    "group_md1": 0.88,
    "group_md2": 0.95,
    "group_md3_must_win": 1.05,
    "group_md3_dead_rubber": 0.82,
    "round_of_16": 0.90,
    "quarter_final": 0.82,
    "semi_final": 0.82,
    "final": 0.82,
}


class Forecaster:

    def __init__(self):
        self.sofascore = SofaScoreCollector()
        self.markets = MarketDataCollector()
        self.model = genai.GenerativeModel(
            model_name=config.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.15,
                max_output_tokens=200,
            ),
        )
        self._kalshi_player_markets = {}

    def forecast_match(self, match_name, markets, research):
        teams = self._parse_teams(match_name)
        if len(teams) < 2:
            teams = [match_name.lower(), "unknown"]

        print(f"\n  [1] MARKETS — Checking Kalshi...")
        all_kalshi = self.markets.get_all_match_markets(match_name)

        # Cache player scoring markets
        self._kalshi_player_markets = {}
        if all_kalshi:
            for keyword, info in all_kalshi.items():
                kw = keyword.lower()
                if not any(w in kw for w in ["win", "corner", "card", "foul",
                                              "over", "under", "total", "half",
                                              "both", "match", "three", "two"]):
                    self._kalshi_player_markets[kw] = info.get("probability", 0)

        print(f"\n  [2] REFEREE")
        if REFEREE.get("name") and REFEREE.get("yellows_per_game", 0) > 0:
            print(f"      {REFEREE['name']}: {REFEREE['yellows_per_game']} yellows/g, "
                  f"{REFEREE['reds_per_game']} reds/g, "
                  f"{REFEREE['penalties_per_game']} pens/g")
        else:
            print(f"      No referee data")

        print(f"\n  [3] CONTEXT")
        self._print_context()

        print(f"\n  [4] DATA — Fetching team stats...")
        team_a_stats = self.sofascore.get_team_averages(teams[0])
        if not team_a_stats:
            team_a_stats = get_base_rates(teams[0])
            print(f"      {teams[0]}: → base rates ({get_confederation(teams[0])}, tier {get_tier(teams[0])})")

        time.sleep(2)

        team_b_stats = self.sofascore.get_team_averages(teams[1])
        if not team_b_stats:
            team_b_stats = get_base_rates(teams[1])
            print(f"      {teams[1]}: → base rates ({get_confederation(teams[1])}, tier {get_tier(teams[1])})")

        if CONTEXT.get("team_a_data_from_weak_opps"):
            team_a_stats = self._apply_qualifier_discount(team_a_stats)
            print(f"      {teams[0]}: qualifier discount (-35%)")
        if CONTEXT.get("team_b_data_from_weak_opps"):
            team_b_stats = self._apply_qualifier_discount(team_b_stats)
            print(f"      {teams[1]}: qualifier discount (-35%)")

        self._print_stats(teams, team_a_stats, team_b_stats)

        if elo_win_prob:
            p = elo_win_prob(teams[0], teams[1])
            if p:
                print(f"\n      ELO: {teams[0]} win = {p:.0%} | {teams[1]} win = {1-p:.0%}")

        print(f"\n  [5] FORECASTING {len(markets)} questions...")
        results = []
        for market in markets:
            profile = classify_question(market.question)
            # Get crowd probability if available on market object
            crowd_prob = getattr(market, 'crowd_probability', None)
            result = self._forecast_single(
                market, profile, team_a_stats, team_b_stats, teams,
                research, match_name, all_kalshi, crowd_prob
            )
            results.append(result)
            time.sleep(4)

        results = self._cross_validate(results)
        return results

    def _forecast_single(self, market, profile, team_a, team_b, teams,
                         research, match_name, all_kalshi, crowd_prob=None):

        # A) Kalshi
        market_info = None
        if all_kalshi:
            market_info = self.markets._match_question(market.question, all_kalshi)
            if not market_info and profile.is_under:
                over_keywords = self._invert_question(market.question)
                for kw in over_keywords:
                    market_info = self.markets._match_question(kw, all_kalshi)
                    if market_info:
                        market_info = dict(market_info)
                        market_info["anchor"] = 1 - market_info["anchor"]
                        market_info["inverted"] = True
                        break

        # AND QUESTION GUARD
        if profile.is_and_question and market_info:
            market_info = dict(market_info)
            market_info["is_sharp"] = False
            market_info["anchor"] = market_info["anchor"] * 0.45

        # B) Math
        math_est = self._math_estimate(profile, team_a, team_b, teams)

        # C) LLM
        llm_est = None
        if math_est is None:
            llm_est = self._llm_reason(market.question, profile, team_a, team_b, teams, market_info)

        # D) Combine
        has_real_data = ("sofascore" in str(team_a.get("source", "")) or
                        "sofascore" in str(team_b.get("source", "")))
        has_kalshi = market_info is not None

        if market_info and market_info.get("is_sharp"):
            anchor = market_info["anchor"]
            best_est = math_est if math_est is not None else llm_est

            if best_est is None:
                final = anchor
            else:
                gap = best_est - anchor
                if abs(gap) < 0.08:
                    final = anchor
                else:
                    final = 0.80 * anchor + 0.20 * best_est

            source = "SHARP"

        elif market_info:
            anchor = market_info["anchor"]
            best_est = math_est if math_est is not None else llm_est
            if best_est is not None:
                blended = 0.60 * anchor + 0.40 * best_est
                final = market_anchor_adjust(anchor, blended)
            else:
                final = anchor
            source = "market"

        elif math_est is not None:
            final = math_est
            source = "math" if has_real_data else "math_base"

        elif llm_est is not None:
            final = llm_est
            source = "llm" if has_real_data else "llm_base"

        else:
            final = self._honest_uncertainty(profile)
            source = "base_rate"

        # E) HARD CAPS — set the envelope
        final = self._apply_hard_caps(final, profile, teams)

        # F) CROWD BIAS — adjust within envelope (not for market-sourced)
        if source not in ["SHARP", "market"]:
            final = self._apply_crowd_bias(final, profile, teams)

        # G) HARD CAPS AGAIN — clamp if bias violated envelope
        final = self._apply_hard_caps(final, profile, teams)

        # H) CONVICTION + CROWD-AWARE SIZING + DEVIATION GOVERNOR
        conviction = self._calculate_conviction(profile, market_info, math_est, llm_est)
        final = self._crowd_adjust(final, crowd_prob, conviction)
        final = self._deviation_governor(final, crowd_prob, market_info, conviction)

        # I) ANTI-EXTREME — don't go extreme without Kalshi
        final = self._anti_extreme_filter(final, profile, has_kalshi)

        # J) Data quality cap
        if source == "base_rate":
            final = max(0.30, min(0.65, final))
        elif source in ["math_base", "llm_base"]:
            final = max(0.20, min(0.78, final))

        final = max(0.03, min(0.97, final))
        final_pct = max(1, min(99, int(round(final * 100))))
        
        print(f"        [{profile.category}|comp={profile.is_comparison}|pp={profile.is_player_prop}|half={profile.is_half_specific}] math={math_est} → final={final_pct}% src={source}")

        return {
            "market_id": market.id,
            "question": market.question,
            "probability": final_pct,
            "category": profile.category,
            "source": source,
            "math_estimate": f"{math_est:.0%}" if math_est else None,
            "market_anchor": f"{market_info['anchor']:.0%}" if market_info else None,
            "market_vol": f"${market_info['volume']:,.0f}" if market_info else None,
            "is_half_specific": profile.is_half_specific,
        }

    # ═══════════════════════════════════════════════════════════════
    # NEW: Conviction + Crowd-Aware Sizing + Deviation Governor
    # ═══════════════════════════════════════════════════════════════

    def _calculate_conviction(self, profile, market_info, math_est, llm_est):
        """How confident are we in our estimate vs crowd?"""
        score = 0.0

        if market_info and market_info.get("is_sharp"):
            score += 0.45

        if math_est is not None:
            score += 0.20

        if llm_est is not None:
            score += 0.10

        if profile.category in ["winner", "goals", "btts"]:
            score += 0.10

        return min(score, 1.0)

    def _crowd_adjust(self, estimate, crowd_prob, conviction):
        """Size our deviation from crowd based on conviction."""
        if crowd_prob is None:
            return estimate

        delta = estimate - crowd_prob
        adjusted = crowd_prob + conviction * delta
        return adjusted

    def _deviation_governor(self, estimate, crowd_prob, market_info, conviction):
        """Never deviate >15pts from crowd without sharp Kalshi backing."""
        if crowd_prob is None:
            return estimate

        if market_info and market_info.get("is_sharp"):
            return estimate

        delta = estimate - crowd_prob

        if abs(delta) <= 0.15:
            return estimate

        excess = abs(delta) - 0.15
        shrink = 0.5 + conviction * 0.5
        adjusted_delta = np.sign(delta) * (0.15 + excess * shrink)

        return crowd_prob + adjusted_delta

    # ═══════════════════════════════════════════════════════════════
    # EXISTING: Anti-extreme, hard caps, crowd bias, etc.
    # ═══════════════════════════════════════════════════════════════

    def _anti_extreme_filter(self, estimate, profile, has_kalshi):
        """Without Kalshi, stay 25-68%. Proven edges exempted."""
        if has_kalshi:
            return estimate

        q = profile.raw_question.lower()

        if profile.category in ["player_goal", "score_or_assist"]:
            return max(0.12, estimate)
        if profile.category == "sot" and profile.is_player_prop:
            return max(0.15, estimate)
        if "penalty" in q and ("or" in q and "red" in q):
            return max(0.18, estimate)
        if profile.category == "offsides":
            return max(0.20, estimate)

        estimate = max(0.25, estimate)
        estimate = min(0.68, estimate)
        return estimate

    def _get_stage_discount(self):
        if CONTEXT.get("is_group_opener"):
            return STAGE_DISCOUNT["group_md1"]
        elif CONTEXT.get("is_dead_rubber"):
            return STAGE_DISCOUNT["group_md3_dead_rubber"]
        elif CONTEXT.get("is_must_win"):
            return STAGE_DISCOUNT["group_md3_must_win"]
        return STAGE_DISCOUNT.get("group_md2", 0.95)

    def _apply_hard_caps(self, estimate, profile, teams):
        q = profile.raw_question.lower()

        if profile.is_and_question:
            estimate = max(estimate, 0.25)
            estimate = min(estimate, 0.38)
            if profile.is_half_specific:
                estimate = min(estimate, 0.30)

        if profile.category == "offsides" and profile.is_over_under:
            if profile.threshold >= 2.5:
                estimate = min(estimate, 0.35)
            elif profile.threshold >= 1.5:
                estimate = min(estimate, 0.48)

        if profile.category == "cards" and profile.is_over_under:
            if profile.threshold >= 4.5:
                estimate = min(estimate, 0.38)
            elif profile.threshold >= 3.5:
                estimate = max(estimate, 0.40)
                estimate = min(estimate, 0.52)

        if profile.category in ["player_goal", "score_or_assist"]:
            estimate = min(estimate, 0.30)

        if profile.category == "sot" and profile.is_player_prop:
            smart_cap = self._player_sot_smart_cap(profile)
            estimate = min(estimate, smart_cap)

        if "penalty" in q and ("or" in q and "red" in q):
            ref_pen = REFEREE.get("penalties_per_game", 0.28) or 0.28
            if ref_pen >= 0.35:
                estimate = min(estimate, 0.35)
            else:
                estimate = min(estimate, 0.28)

        if profile.is_comparison:
            more_pos = q.find("more")
            if more_pos > 0:
                before_more = q[:more_pos]
                asking_team = None
                other_team = None
                if teams[0] in before_more:
                    asking_team = teams[0]
                    other_team = teams[1]
                elif teams[1] in before_more:
                    asking_team = teams[1]
                    other_team = teams[0]

                if asking_team and other_team:
                    asking_tier = get_tier(asking_team)
                    other_tier = get_tier(other_team)

                    if profile.category == "fouls":
                        estimate = max(estimate, 0.38)
                        estimate = min(estimate, 0.62)
                    elif asking_tier == other_tier:
                        estimate = max(estimate, 0.40)
                        estimate = min(estimate, 0.55)
                    elif asking_tier > other_tier:
                        estimate = min(estimate, 0.42)
                        if estimate > 0.38:
                            estimate = estimate * 0.45 + 0.34 * 0.55

        if profile.category == "winner" and "draw" not in q:
            estimate = min(estimate, 0.78)

        if profile.category == "corners" and profile.is_over_under and not profile.is_comparison:
            is_single_team = (teams[0] in q or teams[1] in q) and "total" not in q
            if is_single_team:
                if profile.threshold >= 6.5:
                    estimate = min(estimate, 0.28)
                elif profile.threshold >= 5.5:
                    estimate = min(estimate, 0.40)
                elif profile.threshold >= 4.5:
                    estimate = min(estimate, 0.55)

        if profile.category == "goals" and profile.is_over_under:
            estimate = max(estimate, 0.20)

        if estimate > 0.68:
            if profile.category == "winner":
                pass
            else:
                t0_tier = get_tier(teams[0])
                t1_tier = get_tier(teams[1])
                tier_gap = abs(t0_tier - t1_tier)
                if tier_gap >= 2:
                    estimate = min(estimate, 0.73)
                else:
                    estimate = min(estimate, 0.68)

        return estimate

    def _player_sot_smart_cap(self, profile):
        q = profile.raw_question.lower()

        scoring_prob = None
        for keyword, prob in self._kalshi_player_markets.items():
            name_parts = [w for w in q.split() if len(w) > 3 and w.isalpha()
                         and w not in ["will", "have", "least", "shot", "target",
                                       "more", "than", "the", "second", "half",
                                       "first", "match", "game"]]
            for part in name_parts:
                if part in keyword:
                    scoring_prob = prob
                    break
            if scoring_prob:
                break

        if scoring_prob is None:
            for pname, sot_per_90 in PLAYER_SOT.items():
                if pname in q:
                    scoring_prob = min(0.35, 1 - np.exp(-sot_per_90 * 0.23))
                    break

        if scoring_prob is None:
            for pname, pos in PLAYER_POSITION.items():
                if pname in q:
                    if pos in ["striker", "ST", "CF"]:
                        scoring_prob = 0.18
                    elif pos in ["winger", "LW", "RW"]:
                        scoring_prob = 0.14
                    elif pos in ["midfielder", "CAM", "CM"]:
                        scoring_prob = 0.08
                    else:
                        scoring_prob = 0.05
                    break

        if scoring_prob is None:
            scoring_prob = 0.12

        is_half = profile.is_half_specific

        if scoring_prob <= 0.08:
            cap = 0.22 if not is_half else 0.15
        elif scoring_prob <= 0.12:
            cap = 0.30 if not is_half else 0.20
        elif scoring_prob <= 0.14:
            cap = 0.33 if not is_half else 0.22
        elif scoring_prob <= 0.17:
            cap = 0.35 if not is_half else 0.25
        elif scoring_prob <= 0.25:
            cap = 0.35 if not is_half else 0.30
        elif scoring_prob <= 0.35:
            cap = 0.45 if not is_half else 0.38
        else:
            cap = 0.55 if not is_half else 0.45

        if hasattr(profile, 'threshold') and profile.threshold >= 1.5:
            cap *= 0.55

        return cap

    def _apply_crowd_bias(self, estimate, profile, teams):
        q = profile.raw_question.lower()

        if profile.category in ["player_goal", "score_or_assist"]:
            bias = CROWD_BIAS["player_goal"]
            empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
            adjusted = 0.45 * estimate + 0.55 * empirical_mid
            return max(bias["target_min"], min(bias["target_max"], adjusted))

        if profile.category == "sot" and profile.is_player_prop:
            confirmed = CONTEXT.get("confirmed_starters", [])
            is_confirmed = any(name in q for name in confirmed)

            if is_confirmed:
                adjusted = 0.50 * estimate + 0.50 * 0.38
                return max(0.35, min(0.55, adjusted))
            else:
                bias = CROWD_BIAS["player_sot"]
                empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
                adjusted = 0.45 * estimate + 0.55 * empirical_mid
                return max(bias["target_min"], min(bias["target_max"], adjusted))

        if profile.category == "offsides" and profile.is_over_under:
            if abs(profile.threshold - 1.5) < 0.6:
                bias = CROWD_BIAS["offsides_2plus"]
                empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
                adjusted = 0.55 * estimate + 0.45 * empirical_mid
                return max(bias["target_min"], min(bias["target_max"], adjusted))

        if "penalty" in q and ("or" in q and "red" in q):
            bias = CROWD_BIAS["penalty_or_red"]
            empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
            return max(bias["target_min"], min(bias["target_max"], estimate * 0.65))

        if profile.category == "cards" and profile.is_over_under:
            if abs(profile.threshold - 3.5) < 0.6:
                bias = CROWD_BIAS["cards_4plus"]
                empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
                adjusted = 0.55 * estimate + 0.45 * empirical_mid
                return max(bias["target_min"], min(bias["target_max"], adjusted))

        if profile.category == "goals" and not profile.is_over_under and profile.is_half_specific:
            scoring_team = None
            opponent = None
            if teams[0] in q:
                scoring_team = teams[0]
                opponent = teams[1]
            elif teams[1] in q:
                scoring_team = teams[1]
                opponent = teams[0]

            if scoring_team:
                scorer_tier = get_tier(scoring_team)
                opponent_tier = get_tier(opponent)
                is_strong = (scorer_tier <= 2) or (scorer_tier <= 3 and opponent_tier >= scorer_tier + 1)

                if is_strong:
                    bias = CROWD_BIAS["team_score_half_strong"]
                    return max(bias["target_min"], min(bias["target_max"], estimate))
                else:
                    bias = CROWD_BIAS["team_score_half_weak"]
                    empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
                    adjusted = 0.50 * estimate + 0.50 * empirical_mid
                    return max(bias["target_min"], min(bias["target_max"], adjusted))

        if profile.is_comparison:
            more_pos = q.find("more")
            if more_pos > 0:
                before_more = q[:more_pos]
                asking_team = None
                other_team = None
                if teams[0] in before_more:
                    asking_team = teams[0]
                    other_team = teams[1]
                elif teams[1] in before_more:
                    asking_team = teams[1]
                    other_team = teams[0]

                if asking_team and other_team:
                    asking_tier = get_tier(asking_team)
                    other_tier = get_tier(other_team)

                    if profile.category == "fouls":
                        return max(0.40, min(0.60, estimate))

                    if asking_tier == other_tier:
                        return max(0.42, min(0.55, estimate))

                    if asking_tier > other_tier:
                        bias = CROWD_BIAS["underdog_more"]
                        empirical_mid = (bias["target_min"] + bias["target_max"]) / 2
                        adjusted = 0.40 * estimate + 0.60 * empirical_mid
                        return max(bias["target_min"], min(bias["target_max"], adjusted))

                    elif asking_tier < other_tier:
                        if "shot" in q or "sot" in q:
                            bias = CROWD_BIAS["favorite_more_sot"]
                            return max(bias["target_min"], min(bias["target_max"], estimate))
                        else:
                            return max(0.48, min(0.65, estimate))

            return estimate

        if profile.category == "winner" and "draw" not in q:
            if estimate > 0.55:
                return estimate - 0.07

        if profile.category == "sot" and profile.is_over_under and profile.is_half_specific:
            if not profile.is_player_prop:
                return estimate * 0.90

        return estimate

    def _llm_reason(self, question, profile, team_a, team_b, teams, market_info):
        data_block = f"""MATCH: {teams[0]} vs {teams[1]}
TEAM A ({teams[0]}): Goals/90: {team_a.get('goals_per_90', '?')} | Conceded/90: {team_a.get('goals_conceded_per_90', '?')} | SOT/90: {team_a.get('shots_on_target_per_90', '?')} | Corners/90: {team_a.get('corners_per_90', '?')} | Fouls/90: {team_a.get('fouls_committed_per_90', '?')} | Yellows/90: {team_a.get('yellow_cards_per_90', '?')} | Offsides/90: {team_a.get('offsides_per_90', '?')} | Tier: {get_tier(teams[0])} | {get_confederation(teams[0])} | Source: {team_a.get('source', '?')}
TEAM B ({teams[1]}): Goals/90: {team_b.get('goals_per_90', '?')} | Conceded/90: {team_b.get('goals_conceded_per_90', '?')} | SOT/90: {team_b.get('shots_on_target_per_90', '?')} | Corners/90: {team_b.get('corners_per_90', '?')} | Fouls/90: {team_b.get('fouls_committed_per_90', '?')} | Yellows/90: {team_b.get('yellow_cards_per_90', '?')} | Offsides/90: {team_b.get('offsides_per_90', '?')} | Tier: {get_tier(teams[1])} | {get_confederation(teams[1])} | Source: {team_b.get('source', '?')}"""

        if REFEREE.get("yellows_per_game", 0) > 0:
            data_block += f"\nREF: {REFEREE['name']} — {REFEREE['yellows_per_game']} yellows/g, {REFEREE['reds_per_game']} reds/g, {REFEREE['penalties_per_game']} pens/g"

        context_notes = []
        if CONTEXT.get("is_group_opener"):
            context_notes.append("Group opener (λ×0.88)")
        if CONTEXT.get("is_must_win"):
            context_notes.append("Must-win (λ×1.05)")
        if CONTEXT.get("is_dead_rubber"):
            context_notes.append("Dead rubber (λ×0.82)")
        if CONTEXT.get("team_a_deep_block"):
            context_notes.append(f"{teams[0]} deep block")
        if CONTEXT.get("team_b_deep_block"):
            context_notes.append(f"{teams[1]} deep block")
        if CONTEXT.get("team_a_high_line"):
            context_notes.append(f"{teams[0]} high line")
        if CONTEXT.get("team_b_high_line"):
            context_notes.append(f"{teams[1]} high line")
        if context_notes:
            data_block += "\nCONTEXT: " + " | ".join(context_notes)

        if market_info:
            data_block += f"\nKALSHI: {market_info['anchor']:.0%}"

        player_notes = []
        for pname, sot in PLAYER_SOT.items():
            if pname in question.lower():
                player_notes.append(f"SOT/90: {sot}")
        for pname, pos in PLAYER_POSITION.items():
            if pname in question.lower():
                player_notes.append(f"Position: {pos}")
        if player_notes:
            data_block += "\nPLAYER: " + " | ".join(player_notes)

        prompt = f"""{data_block}

QUESTION: {question}
CATEGORY: {profile.category}
HALF: {"1st half" if profile.half == 1 else "2nd half" if profile.half == 2 else "Full time"}

Integer 1-99:"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                match = re.search(r'(\d+)', text)
                if match:
                    val = int(match.group(1))
                    return max(0.01, min(0.99, val / 100.0))
                return None
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "retry" in error_str.lower() or "limit" in error_str.lower() or "quota" in error_str.lower():
                    wait = 30 * (attempt + 1)
                    print(f"        ⏳ Rate limited. Waiting {wait}s... ({attempt+1}/{max_retries})")
                    time.sleep(wait)
                else:
                    print(f"        LLM error: {e}")
                    return None
        print(f"        ❌ LLM failed after {max_retries} retries")
        return None

    def _math_estimate(self, profile, team_a, team_b, teams):
        a_goals = team_a.get("goals_per_90", 1.2)
        b_goals = team_b.get("goals_per_90", 1.0)
        a_concede = team_a.get("goals_conceded_per_90", 1.0)
        b_concede = team_b.get("goals_conceded_per_90", 1.2)
        lambda_a = (a_goals + b_concede) / 2
        lambda_b = (b_goals + a_concede) / 2

        stage_mult = self._get_stage_discount()
        lambda_a *= stage_mult
        lambda_b *= stage_mult

        hf = 1.0
        if profile.is_half_specific:
            hf = config.HALF_1_FACTOR if profile.half == 1 else config.HALF_2_FACTOR

        if profile.category == "winner" and "draw" not in profile.raw_question.lower():
            q = profile.raw_question.lower()
            if elo_win_prob:
                if teams[0] in q:
                    p = elo_win_prob(teams[0], teams[1])
                elif teams[1] in q:
                    p = elo_win_prob(teams[1], teams[0])
                else:
                    p = None
                if p:
                    return self._cap(p)
            return None

        if profile.category == "goals" and profile.is_over_under:
            total_lambda = (lambda_a + lambda_b) * hf
            if profile.is_under:
                return self._cap(poisson_under(total_lambda, profile.threshold))
            return self._cap(poisson_over(total_lambda, profile.threshold))

        elif profile.category == "goals" and not profile.is_over_under and not profile.is_player_prop:
            q = profile.raw_question.lower()
            if teams[0] in q:
                lam = lambda_a * hf
            elif teams[1] in q:
                lam = lambda_b * hf
            else:
                return None
            return self._cap(1 - np.exp(-lam))

        elif profile.category == "btts":
            p_a = 1 - np.exp(-(lambda_a * hf))
            p_b = 1 - np.exp(-(lambda_b * hf))
            return self._cap(p_a * p_b)

        elif profile.category == "clean_sheet":
            q = profile.raw_question.lower()
            if teams[0] in q:
                return self._cap(np.exp(-(lambda_b * hf)))
            elif teams[1] in q:
                return self._cap(np.exp(-(lambda_a * hf)))
            return None

        elif profile.category == "corners":
            a_c = team_a.get("corners_per_90", 4.8)
            b_c = team_b.get("corners_per_90", 4.5)
            if profile.is_over_under:
                q = profile.raw_question.lower()
                if teams[0] in q and teams[1] not in q:
                    lam = a_c * hf
                elif teams[1] in q and teams[0] not in q:
                    lam = b_c * hf
                else:
                    lam = (a_c + b_c) * hf
                if profile.is_under:
                    return self._cap(poisson_under(lam, profile.threshold))
                return self._cap(poisson_over(lam, profile.threshold))
            elif profile.is_comparison:
                return self._comparison_math(a_c * hf, b_c * hf, profile, teams)
            return None

        elif profile.category == "cards" and profile.is_over_under:
            if REFEREE.get("yellows_per_game", 0) > 0:
                total = (REFEREE["yellows_per_game"] + REFEREE.get("reds_per_game", 0)) * hf
            else:
                a_cards = team_a.get("yellow_cards_per_90", 2.0)
                b_cards = team_b.get("yellow_cards_per_90", 2.0)
                total = (a_cards + b_cards) * hf * 0.85
            if CONTEXT.get("is_group_opener"):
                total *= 1.05
            if profile.is_under:
                return self._cap(poisson_under(total, profile.threshold))
            return self._cap(poisson_over(total, profile.threshold))

        elif profile.category == "fouls" and profile.is_over_under:
            a_f = team_a.get("fouls_committed_per_90", 13.0)
            b_f = team_b.get("fouls_committed_per_90", 13.0)
            total = (a_f + b_f) * hf
            if profile.is_under:
                return self._cap(poisson_under(total, profile.threshold))
            return self._cap(poisson_over(total, profile.threshold))

        elif profile.category == "sot" and profile.is_over_under:
            a_sot = team_a.get("shots_on_target_per_90", 4.0)
            b_sot = team_b.get("shots_on_target_per_90", 3.5)
            q = profile.raw_question.lower()

            if teams[0] in q and teams[1] not in q:
                lam = a_sot * hf
            elif teams[1] in q and teams[0] not in q:
                lam = b_sot * hf
            else:
                lam = (a_sot + b_sot) * hf

            if profile.is_under:
                return self._cap(poisson_under(lam, profile.threshold))
            return self._cap(poisson_over(lam, profile.threshold))

        elif profile.category == "sot" and profile.is_comparison:
            a_sot = team_a.get("shots_on_target_per_90", 4.0)
            b_sot = team_b.get("shots_on_target_per_90", 3.5)
            return self._comparison_math(a_sot * hf, b_sot * hf, profile, teams)

        elif profile.category == "offsides" and profile.is_over_under:
            a_off = team_a.get("offsides_per_90", 2.0)
            b_off = team_b.get("offsides_per_90", 2.0)
            q = profile.raw_question.lower()
            if teams[0] in q:
                lam = a_off * hf
            elif teams[1] in q:
                lam = b_off * hf
            else:
                lam = (a_off + b_off) * hf
            if CONTEXT.get("team_b_high_line") and teams[0] in q:
                lam *= 1.20
            if CONTEXT.get("team_a_high_line") and teams[1] in q:
                lam *= 1.20
            if profile.is_under:
                return self._cap(poisson_under(lam, profile.threshold))
            return self._cap(poisson_over(lam, profile.threshold))

        elif profile.category == "penalty" and not profile.is_or_question:
            lam = REFEREE.get("penalties_per_game", 0.28) or 0.28
            return self._cap(1 - np.exp(-lam))

        return None

    def _comparison_math(self, lambda_x, lambda_y, profile, teams):
        q = profile.raw_question.lower()
        more_pos = q.find("more")
        if more_pos > 0:
            before_more = q[:more_pos]
            if teams[1] in before_more:
                lx, ly = lambda_y, lambda_x
            elif teams[0] in before_more:
                lx, ly = lambda_x, lambda_y
            else:
                lx, ly = lambda_x, lambda_y
        else:
            lx, ly = lambda_x, lambda_y

        avg = (lx + ly) / 2
        p_equal = 0.13 if avg < 3 else 0.09

        if (lx + ly) > 0:
            p_x_more = lx / (lx + ly) - p_equal / 2
        else:
            p_x_more = 0.50

        return max(0.20, min(0.75, p_x_more))

    def _honest_uncertainty(self, profile):
        if profile.category == "goals":
            if profile.is_over_under:
                if abs(profile.threshold - 2.5) < 0.6:
                    return 0.48 if not profile.is_under else 0.52
                elif abs(profile.threshold - 1.5) < 0.6:
                    return 0.72 if not profile.is_under else 0.28
                elif abs(profile.threshold - 3.5) < 0.6:
                    return 0.28 if not profile.is_under else 0.72
            return 0.45
        elif profile.category == "btts":
            return 0.45
        elif profile.category == "cards":
            return 0.45
        elif profile.category == "corners":
            return 0.48
        elif profile.category == "sot":
            if profile.is_player_prop:
                return 0.22
            return 0.50
        elif profile.category == "offsides":
            return 0.36
        elif profile.category == "winner":
            return 0.35
        elif profile.category == "penalty":
            return 0.22
        elif profile.category in ["score_or_assist", "player_goal"]:
            return 0.20
        elif profile.category == "fouls":
            return 0.50
        return 0.50

    def _apply_qualifier_discount(self, stats):
        discounted = dict(stats)
        for key in ["goals_per_90", "shots_on_target_per_90", "corners_per_90"]:
            if key in discounted and isinstance(discounted[key], (int, float)):
                discounted[key] = round(discounted[key] * 0.65, 2)
        for key in ["goals_conceded_per_90"]:
            if key in discounted and isinstance(discounted[key], (int, float)):
                discounted[key] = round(discounted[key] * 1.35, 2)
        discounted["source"] = discounted.get("source", "") + " (qual_disc)"
        return discounted

    def _cap(self, value):
        return float(max(0.03, min(0.95, value)))

    def _invert_question(self, question):
        q = question.lower()
        inverted = []
        fewer_match = re.search(r'(\d+)\s+or\s+fewer', q)
        if fewer_match:
            n = int(fewer_match.group(1))
            inverted.append(f"over {n}.5 goals")
            inverted.append(f"over {n + 0.5} goals")
            inverted.append(f"over {n}")
            inverted.append(f"over 2.5 goals")
            inverted.append(f"over 2.5")
        if "under" in q:
            inverted.append(q.replace("under", "over"))
        return inverted

    def _cross_validate(self, results):
        for i in range(len(results)):
            for j in range(i + 1, len(results)):
                if results[i]["category"] != results[j]["category"]:
                    continue
                q1 = results[i]["question"].lower()
                q2 = results[j]["question"].lower()
                is_pair = (("over" in q1 and "under" in q2) or
                          ("under" in q1 and "over" in q2) or
                          ("or more" in q1 and "or fewer" in q2) or
                          ("or fewer" in q1 and "or more" in q2))
                if is_pair:
                    total = results[i]["probability"] + results[j]["probability"]
                    if abs(total - 100) > 2:
                        ratio = results[i]["probability"] / max(total, 1)
                        results[i]["probability"] = int(round(ratio * 100))
                        results[j]["probability"] = 100 - results[i]["probability"]

        winner_results = [r for r in results if r["category"] == "winner"]
        if len(winner_results) == 3:
            total = sum(r["probability"] for r in winner_results)
            if abs(total - 100) > 3:
                for r in winner_results:
                    r["probability"] = int(round(r["probability"] * 100 / total))
                diff = 100 - sum(r["probability"] for r in winner_results)
                if diff != 0:
                    winner_results[0]["probability"] += diff

        return results

    def _print_context(self):
        active = []
        if CONTEXT.get("is_group_opener"):
            active.append("Group opener (λ×0.88)")
        if CONTEXT.get("is_must_win"):
            active.append("Must-win (λ×1.05)")
        if CONTEXT.get("is_dead_rubber"):
            active.append("Dead rubber (λ×0.82)")
        if CONTEXT.get("team_a_high_line"):
            active.append("Team A high line")
        if CONTEXT.get("team_b_high_line"):
            active.append("Team B high line")
        if CONTEXT.get("team_a_deep_block"):
            active.append("Team A deep block")
        if CONTEXT.get("team_b_deep_block"):
            active.append("Team B deep block")
        if CONTEXT.get("team_a_key_absence"):
            active.append("Team A key absence")
        if CONTEXT.get("team_b_key_absence"):
            active.append("Team B key absence")
        if CONTEXT.get("team_a_data_from_weak_opps"):
            active.append("Team A weak opp data")
        if CONTEXT.get("team_b_data_from_weak_opps"):
            active.append("Team B weak opp data")
        starters = CONTEXT.get("confirmed_starters", [])
        if starters:
            active.append(f"Confirmed starters: {', '.join(starters)}")
        if active:
            for a in active:
                print(f"      • {a}")
        else:
            print(f"      No context factors set")

    def _print_stats(self, teams, a, b):
        print(f"\n      {'Stat':<20} {teams[0][:14]:>14} {teams[1][:14]:>14}")
        print(f"      {'─' * 50}")
        rows = [
            ("Goals/90", "goals_per_90"),
            ("Conceded/90", "goals_conceded_per_90"),
            ("Corners/90", "corners_per_90"),
            ("Fouls/90", "fouls_committed_per_90"),
            ("Yellows/90", "yellow_cards_per_90"),
            ("SOT/90", "shots_on_target_per_90"),
            ("Offsides/90", "offsides_per_90"),
        ]
        for label, key in rows:
            va = a.get(key, "?")
            vb = b.get(key, "?")
            sa = f"{va:.1f}" if isinstance(va, (int, float)) else "?"
            sb = f"{vb:.1f}" if isinstance(vb, (int, float)) else "?"
            print(f"      {label:<20} {sa:>14} {sb:>14}")
        src_a = a.get("source", "?")[:14]
        src_b = b.get("source", "?")[:14]
        print(f"      {'Source':<20} {src_a:>14} {src_b:>14}")

    def _parse_teams(self, match_name):
        for sep in [" vs ", " v ", " versus ", " - "]:
            if sep in match_name:
                raw = [p.strip() for p in match_name.split(sep)[:2]]
                return [resolve_team(t) for t in raw]
        return [resolve_team(match_name)]