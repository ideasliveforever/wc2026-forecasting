import requests
import re
import time
from typing import Dict, Optional
from config import config

try:
    from kalshi_markets import MATCH_MARKETS, ALL_TICKERS
except ImportError:
    MATCH_MARKETS = {}
    ALL_TICKERS = []


class MarketDataCollector:

    BASE = "https://external-api.kalshi.com/trade-api/v2"

    def __init__(self):
        self.headers = {"Authorization": f"Bearer {config.KALSHI_API_KEY}"}
        self._fetched = None

    def reset_cache(self):
        """Call between matches if running multiple."""
        self._fetched = None

    def get_all_match_markets(self, match_name: str = "") -> Dict[str, Dict]:
        if self._fetched is not None:
            return self._fetched

        results = {}

        for keyword, ticker in MATCH_MARKETS.items():
            data = self._fetch(ticker)
            if data:
                data["keyword"] = keyword
                results[keyword] = data

        for ticker in ALL_TICKERS:
            if ticker not in [v.get("ticker") for v in results.values()]:
                data = self._fetch(ticker)
                if data:
                    results[data.get("title", ticker)] = data

        if results:
            sharp_count = sum(1 for m in results.values() if m.get("is_sharp"))
            print(f"    Kalshi: {len(results)} markets fetched ({sharp_count} sharp)")
            for keyword, info in results.items():
                sharp_tag = " ★SHARP" if info.get("is_sharp") else ""
                print(f"      {keyword}: {info['probability']:.0%} "
                      f"(bid={info['yes_bid']:.2f} ask={info['yes_ask']:.2f} "
                      f"vol=${info['volume']:,.0f}){sharp_tag}")
        else:
            print(f"    No Kalshi markets found")

        self._fetched = results
        return results

    def get_market_odds(self, match_name: str, question: str) -> Optional[Dict]:
        all_markets = self.get_all_match_markets(match_name)
        if not all_markets:
            return None
        return self._match_question(question, all_markets)

    def _fetch(self, ticker: str) -> Optional[Dict]:
        url = f"{self.BASE}/markets/{ticker}"
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            time.sleep(0.3)

            if r.status_code != 200:
                print(f"      ✗ {ticker}: HTTP {r.status_code}")
                return None

            market = r.json().get("market")
            if not market:
                return None

            yes_ask = float(market.get("yes_ask_dollars", "0") or "0")
            yes_bid = float(market.get("yes_bid_dollars", "0") or "0")
            no_ask = float(market.get("no_ask_dollars", "0") or "0")
            no_bid = float(market.get("no_bid_dollars", "0") or "0")
            volume = float(market.get("volume_fp", "0") or "0")
            title = market.get("title", "")
            subtitle = market.get("subtitle", "")

            if yes_ask <= 0:
                return None

            raw_sum = yes_ask + no_ask
            devigged = yes_ask / raw_sum if raw_sum > 0 else yes_ask

            is_sharp = volume >= config.SHARP_VOLUME_THRESHOLD
            is_medium = volume >= config.MEDIUM_VOLUME_THRESHOLD

            if is_sharp:
                confidence = "sharp"
            elif is_medium:
                confidence = "high"
            else:
                confidence = "medium"

            return {
                "ticker": ticker,
                "title": title,
                "subtitle": subtitle,
                "probability": devigged,
                "yes_bid": yes_bid,
                "yes_ask": yes_ask,
                "no_ask": no_ask,
                "no_bid": no_bid,
                "raw_sum": raw_sum,
                "vig_pct": round((raw_sum - 1) * 100, 1),
                "volume": volume,
                "is_sharp": is_sharp,
                "confidence": confidence,
                "source": "kalshi",
            }

        except Exception as e:
            print(f"      ✗ {ticker}: {e}")
            return None

    def _match_question(self, question: str, markets: Dict) -> Optional[Dict]:
        """Strict type matching + lower threshold."""
        q = question.lower()
        q_type = self._question_type(q)

        best = None
        best_score = 0

        for keyword, info in markets.items():
            kw = keyword.lower()
            kw_type = self._question_type(kw)

            if q_type != kw_type:
                continue

            score = 0
            if kw in q:
                score += 10
            kw_words = [w for w in kw.split() if len(w) > 2]
            for w in kw_words:
                if w in q:
                    score += 2

            # Check threshold numbers match
            kw_num = re.search(r'(\d+\.?\d*)', kw)
            q_num = re.search(r'(\d+\.?\d*)', q)
            if kw_num and q_num:
                if abs(float(kw_num.group(1)) - float(q_num.group(1))) < 0.6:
                    score += 3

            if score > best_score:
                best_score = score
                best = info

        if best and best_score >= 3:
            return {
                "anchor": best["probability"],
                "source": "kalshi",
                "confidence": best["confidence"],
                "is_sharp": best.get("is_sharp", False),
                "volume": best.get("volume", 0),
                "vig_pct": best.get("vig_pct", 0),
                "title": best.get("title", ""),
            }
        return None

    def _question_type(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["win", "winner", "draw", "tie", "winning", "beat"]):
            return "winner"
        if "corner" in t:
            return "corners"
        if "card" in t or "booking" in t:
            return "cards"
        if "foul" in t:
            return "fouls"
        if "offside" in t:
            return "offsides"
        if "shot" in t or "sot" in t:
            return "sot"
        if "btts" in t or "both teams score" in t or "both teams to score" in t:
            return "btts"
        if ("score" in t and "assist" in t) or "score or" in t:
            return "score_assist"
        if "score a goal" in t or "to score" in t:
            return "player_goal"
        if any(w in t for w in ["over", "under", "total goals", "or fewer", "or more", "goal"]):
            return "goals"
        if "score" in t:
            return "goals"
        return "other"
