import time
import json
import argparse
from datetime import datetime

from config import config
from api_client import SportsPredictClient
from forecaster import Forecaster


class ForecastingBot:

    def __init__(self, auto_submit=False):
        self.api = SportsPredictClient()
        self.forecaster = Forecaster()
        self.auto_submit = auto_submit
        self.all_results = []

    def run(self, match_filter=None):
        print("\n" + "=" * 70)
        print("  FORECAST BOT v2 — KALSHI + POISSON + LLM REASONING")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        self.api.setup()
        matches = self.api.get_matches()

        if match_filter:
            matches = [m for m in matches if match_filter.lower() in m.name.lower()]

        print(f"\n  Found {len(matches)} matches with open markets")

        all_predictions = []

        for idx, match in enumerate(matches, 1):
            print(f"\n{'═' * 70}")
            print(f"  MATCH {idx}/{len(matches)}: {match.name}")
            print(f"  Markets: {match.open_market_count}")
            print(f"{'═' * 70}")

            markets = self.api.get_markets_for_match(match.id)
            if not markets:
                print("  No open markets, skipping.")
                continue

            # Show all questions first
            print(f"\n  Questions:")
            for i, m in enumerate(markets, 1):
                print(f"    {i:2}. {m.question}")

            # No research — saves Tavily credits, not used anyway
            research = ""

            # Reset Kalshi cache between matches
            self.forecaster.markets.reset_cache()

            # Forecast
            results = self.forecaster.forecast_match(match.name, markets, research)

            # Display
            print(f"\n  ┌{'─' * 52}┬{'─' * 5}┬{'─' * 11}┐")
            print(f"  │ {'Question':<50} │ {'%':>3} │ {'Source':<9} │")
            print(f"  ├{'─' * 52}┼{'─' * 5}┼{'─' * 11}┤")
            for r in results:
                q = r["question"][:48] + ".." if len(r["question"]) > 50 else r["question"]
                print(f"  │ {q:<50} │ {r['probability']:>2}% │ {r['source']:<9} │")
            print(f"  └{'─' * 52}┴{'─' * 5}┴{'─' * 11}┘")

            for r in results:
                all_predictions.append({
                    "market_id": r["market_id"],
                    "lobby_id": markets[0].lobby_id,
                    "probability": r["probability"],
                })
                self.all_results.append({"match": match.name, **r})

            time.sleep(2)

        # Submit
        if all_predictions:
            if self.auto_submit:
                print(f"\n  Submitting {len(all_predictions)} predictions...")
                result = self.api.submit_predictions_batch(all_predictions)
                print(f"  ✓ {result['succeeded']}/{result['total']} submitted")
                if result["failed"]:
                    print(f"  ✗ {result['failed']} failed")
            else:
                print(f"\n  {len(all_predictions)} predictions ready.")
                print("  Run with --submit to auto-submit.")

        self._save()

    def _save(self):
        if not self.all_results:
            return

        output = [{
            "match": r.get("match"),
            "question": r.get("question"),
            "market_id": r.get("market_id"),
            "submit_probability": r.get("probability"),
            "category": r.get("category"),
            "source": r.get("source"),
            "math_estimate": r.get("math_estimate"),
            "market_anchor": r.get("market_anchor"),
            "is_half_specific": r.get("is_half_specific"),
            "timestamp": datetime.now().isoformat(),
        } for r in self.all_results]

        fname = f"predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(fname, "w") as f:
            json.dump(output, f, indent=2)
        with open("latest_predictions.json", "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n  Saved: {fname} ({len(output)} predictions)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--match", type=str, default=None)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=7200)
    args = parser.parse_args()

    bot = ForecastingBot(auto_submit=args.submit)

    if args.loop:
        while True:
            try:
                bot.run(match_filter=args.match)
                bot.all_results = []
                print(f"\n  Next run in {args.interval // 60} min...")
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n  Stopped.")
                break
            except Exception as e:
                print(f"  ERROR: {e}")
                time.sleep(120)
    else:
        bot.run(match_filter=args.match)


if __name__ == "__main__":
    main()