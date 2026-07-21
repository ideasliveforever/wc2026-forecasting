import requests
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from config import config


@dataclass
class Match:
    id: str
    name: str
    event_id: str
    opening_time: str
    closing_time: str
    open_market_count: int


@dataclass
class Market:
    id: str
    question: str
    event_type: str
    status: str
    match_id: str
    match_name: str
    closing_time: str
    lobby_id: str


@dataclass
class Prediction:
    id: str
    market_id: str
    lobby_id: str
    probability: int
    question: Optional[str] = None
    brier_score: Optional[float] = None
    market_status: Optional[str] = None
    created_date: Optional[str] = None


class SportsPredictClient:

    def __init__(self):
        self.base = config.SP_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.SPORTSPREDICT_API_KEY}",
            "Content-Type": "application/json",
        })
        self._event_id = None
        self._lobby_id = None

    def setup(self):
        print("  Connecting to SportsPredict API...")

        resp = self.session.get(f"{self.base}/events")
        if resp.status_code != 200:
            raise Exception(f"API returned {resp.status_code}: {resp.text[:200]}")

        events_data = resp.json()

        if isinstance(events_data, dict):
            events = events_data.get("events", events_data.get("data", [events_data]))
        elif isinstance(events_data, list):
            events = events_data
        else:
            events = []

        prob_event = None
        for e in events:
            title = e.get("title", e.get("name", "")).lower()
            if "probability" in title or "jump" in title:
                prob_event = e
                break

        if not prob_event:
            for e in events:
                if e.get("status") == "active":
                    prob_event = e
                    break

        if not prob_event and events:
            prob_event = events[0]

        if not prob_event:
            raise Exception("No events found! Check your API key.")

        self._event_id = prob_event["id"]
        print(f"  Found event: {prob_event.get('title', 'Unknown')}")

        resp2 = self.session.get(f"{self.base}/lobbies", params={"event_id": self._event_id})
        if resp2.status_code != 200:
            raise Exception(f"Lobbies API returned {resp2.status_code}: {resp2.text[:200]}")

        lobbies_data = resp2.json()

        if isinstance(lobbies_data, dict):
            lobbies = lobbies_data.get("lobbies", lobbies_data.get("data", [lobbies_data]))
        elif isinstance(lobbies_data, list):
            lobbies = lobbies_data
        else:
            lobbies = []

        if not lobbies:
            raise Exception("No lobby found!")

        lobby = lobbies[0]
        self._lobby_id = lobby.get("id", lobby.get("_id", ""))

        if not lobby.get("joined", False):
            print("  Joining lobby...")
            join_resp = self.session.post(f"{self.base}/lobbies/{self._lobby_id}/join")
            if join_resp.status_code == 409:
                print("  Already joined!")
            elif join_resp.status_code == 200:
                print("  Joined!")
            else:
                print(f"  Join response: {join_resp.status_code}")
        else:
            print(f"  Already in lobby: {lobby.get('name', 'Probability Cup')}")

        print(f"  Setup complete!")
        return self._event_id, self._lobby_id

    @property
    def event_id(self):
        if not self._event_id:
            self.setup()
        return self._event_id

    @property
    def lobby_id(self):
        if not self._lobby_id:
            self.setup()
        return self._lobby_id

    def get_matches(self) -> List[Match]:
        data = self._get("/matches", params={"event_id": self.event_id})

        if isinstance(data, dict):
            data = data.get("matches", data.get("data", []))

        return [
            Match(
                id=m["id"],
                name=m.get("name", ""),
                event_id=m.get("event_id", ""),
                opening_time=m.get("opening_time", ""),
                closing_time=m.get("closing_time", ""),
                open_market_count=m.get("open_market_count", 0),
            )
            for m in data
            if m.get("open_market_count", 0) > 0
        ]

    def get_markets_for_match(self, match_id: str) -> List[Market]:
        data = self._get("/markets", params={
            "lobby_id": self.lobby_id,
            "match_id": match_id,
        })

        if isinstance(data, dict):
            data = data.get("markets", data.get("data", []))

        markets = []
        for m in data:
            if m.get("status") == "open":
                match_info = m.get("match", {})
                markets.append(Market(
                    id=m["id"],
                    question=m.get("question", ""),
                    event_type=m.get("event_type", "probability"),
                    status=m.get("status", "open"),
                    match_id=match_info.get("id", match_id),
                    match_name=match_info.get("name", ""),
                    closing_time=match_info.get("closing_time", ""),
                    lobby_id=m.get("lobby_id", self.lobby_id),
                ))
        return markets

    def submit_predictions_batch(self, predictions: List[Dict]) -> Dict:
        results = {"total": 0, "succeeded": 0, "failed": 0, "details": []}

        for i in range(0, len(predictions), 50):
            chunk = predictions[i:i + 50]
            try:
                resp = self._post("/predictions/batch", json={"predictions": chunk})
                results["total"] += resp.get("total", len(chunk))
                results["succeeded"] += resp.get("succeeded", 0)
                results["failed"] += resp.get("failed", 0)
                results["details"].extend(resp.get("results", []))
            except Exception as e:
                results["total"] += len(chunk)
                results["failed"] += len(chunk)
                results["details"].append({"error": str(e)})

            if i + 50 < len(predictions):
                time.sleep(1)

        return results

    def submit_single_prediction(self, market_id: str, probability: int) -> Dict:
        probability = max(1, min(99, int(probability)))
        return self._post("/predictions", json={
            "market_id": market_id,
            "lobby_id": self.lobby_id,
            "probability": probability,
        })

    def update_prediction(self, prediction_id: str, probability: int) -> Dict:
        probability = max(1, min(99, int(probability)))
        return self._patch(f"/predictions/{prediction_id}", json={
            "probability": probability,
        })

    def get_my_predictions(self) -> List[Prediction]:
        data = self._get("/predictions", params={"lobby_id": self.lobby_id})

        if isinstance(data, dict):
            data = data.get("predictions", data.get("data", []))

        return [
            Prediction(
                id=p["id"],
                market_id=p["market_id"],
                lobby_id=p["lobby_id"],
                probability=p["probability"],
                question=p.get("question"),
                brier_score=p.get("brier_score"),
                market_status=p.get("market_status"),
                created_date=p.get("created_date"),
            )
            for p in data
        ]

    def get_results(self) -> List[Dict]:
        return self._get("/results", params={"lobby_id": self.lobby_id})

    def _get(self, path, params=None):
        resp = self.session.get(f"{self.base}{path}", params=params)
        self._handle_errors(resp)
        return resp.json()

    def _post(self, path, json=None):
        resp = self.session.post(f"{self.base}{path}", json=json)
        self._handle_errors(resp)
        return resp.json()

    def _patch(self, path, json=None):
        resp = self.session.patch(f"{self.base}{path}", json=json)
        self._handle_errors(resp)
        return resp.json()

    def _handle_errors(self, resp):
        if resp.status_code == 409:
            return
        if resp.status_code == 429:
            print("  Rate limited! Waiting 60s...")
            time.sleep(60)
            return
        if resp.status_code >= 400:
            raise Exception(f"API error {resp.status_code}: {resp.text[:300]}")