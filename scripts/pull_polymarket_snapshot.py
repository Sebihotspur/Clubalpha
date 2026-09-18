#!/usr/bin/env python3
"""Collect a no-auth, read-only Polymarket snapshot for one PL slate."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.fixture_calibration import calibrate_fixture_forecast  # noqa: E402
from clubalpha.polymarket_readonly import (  # noqa: E402
    VERSION,
    event_matches_fixture,
    market_tokens,
    no_vig_probabilities,
    summarize_book,
)


GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def get_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Clubalpha/0.1 (+https://github.com/Sebihotspur/Clubalpha)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def market_for_team(markets: list[dict[str, Any]], team: str) -> dict[str, Any]:
    team_words = {word.lower() for word in team.replace("&", " ").split() if len(word) > 3}
    candidates = []
    for market in markets:
        question = str(market.get("question") or "").lower()
        if "end in a draw" in question:
            continue
        score = sum(word in question for word in team_words)
        if score:
            candidates.append((score, market))
    if not candidates:
        raise ValueError(f"no Polymarket winner market found for {team}")
    return max(candidates, key=lambda row: row[0])[1]


def yes_token(market: dict[str, Any]) -> str:
    return market_tokens(market)["Yes"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contextual", type=Path, required=True)
    parser.add_argument("--fixture-calibration", type=Path, required=True)
    parser.add_argument("--fixture-calibration-config", type=Path, required=True)
    parser.add_argument("--prematch-load", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    context_rows = load_jsonl(args.contextual)
    fixtures = [row["fixture"] for row in context_rows]
    start = min(row["kickoff_utc"] for row in fixtures)[:10] + "T00:00:00Z"
    end = max(row["kickoff_utc"] for row in fixtures)[:10] + "T23:59:59Z"
    query = urllib.parse.urlencode(
        {
            "tag_id": 306,
            "active": "true",
            "closed": "false",
            "limit": 100,
            "end_date_min": start,
            "end_date_max": end,
        }
    )
    events = get_json(f"{GAMMA}/events?{query}")
    base_events = [
        row
        for row in events
        if " - " not in str(row.get("title") or "") and len(row.get("markets") or []) == 3
    ]
    event_by_match = {}
    for fixture in fixtures:
        matches = [row for row in base_events if event_matches_fixture(row, fixture)]
        if len(matches) == 1:
            event_by_match[int(fixture["match_id"])] = matches[0]

    token_ids = set()
    prepared = []
    for row in context_rows:
        fixture = row["fixture"]
        event = event_by_match.get(int(fixture["match_id"]))
        if event is None:
            prepared.append((row, None, None))
            continue
        markets = event["markets"]
        draw_market = next(
            market for market in markets if "end in a draw" in market["question"].lower()
        )
        winner_markets = {
            "home_win": market_for_team(markets, fixture["home_team"]),
            "draw": draw_market,
            "away_win": market_for_team(markets, fixture["away_team"]),
        }
        more = get_json(f"{GAMMA}/events?" + urllib.parse.urlencode({"slug": event["slug"] + "-more-markets"}))
        total_market = None
        if more:
            total_market = next(
                (
                    market
                    for market in more[0].get("markets") or []
                    if market.get("sportsMarketType") == "totals"
                    and float(market.get("line") or -1) == 2.5
                ),
                None,
            )
        for market in winner_markets.values():
            token_ids.add(yes_token(market))
        if total_market:
            token_ids.update(market_tokens(total_market).values())
        prepared.append((row, {"event": event, "markets": winner_markets}, total_market))

    def book(token_id: str) -> tuple[str, dict[str, Any]]:
        query = urllib.parse.urlencode({"token_id": token_id})
        return token_id, summarize_book(get_json(f"{CLOB}/book?{query}"))

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        books = dict(executor.map(book, sorted(token_ids)))

    calibration_artifact = load_json(args.fixture_calibration)
    calibration_config = load_json(args.fixture_calibration_config)
    load_by_team = {
        row["team"]: row for row in load_json(args.prematch_load)["teams"]
    }
    output = []
    for context, market_bundle, total_market in prepared:
        fixture = context["fixture"]
        calibrated = calibrate_fixture_forecast(
            {
                "fixture": fixture,
                "predicted_xg": context["contextual"]["predicted_xg"],
                "probabilities": context["contextual"]["probabilities"],
            },
            calibration_artifact,
            calibration_config,
        )
        model = calibrated["probabilities"]
        football = context["contextual"]["probabilities"]
        row = {
            "fixture": fixture,
            "football_baseline": {
                "predicted_xg": context["contextual"]["predicted_xg"],
                "home_win": football["home_win"],
                "draw": football["draw"],
                "away_win": football["away_win"],
                "over_2_5": football["over"]["2.5"],
                "under_2_5": football["under"]["2.5"],
            },
            "model": {
                "home_win": model["home_win"],
                "draw": model["draw"],
                "away_win": model["away_win"],
                "over_2_5": model["over"]["2.5"],
                "under_2_5": model["under"]["2.5"],
            },
            "prematch_load": {
                "home": load_by_team[fixture["home_team"]]["risk"],
                "away": load_by_team[fixture["away_team"]]["risk"],
            },
            "market_available": market_bundle is not None,
            "one_x_two": None,
            "over_under_2_5": None,
        }
        if market_bundle:
            outcome_books = {
                key: books[yes_token(market)]
                for key, market in market_bundle["markets"].items()
            }
            midpoints = {
                key: value["midpoint"]
                for key, value in outcome_books.items()
                if value["midpoint"] is not None
            }
            no_vig = no_vig_probabilities(midpoints) if len(midpoints) == 3 else None
            row["one_x_two"] = {
                "event_id": market_bundle["event"]["id"],
                "event_slug": market_bundle["event"]["slug"],
                "event_liquidity": float(market_bundle["event"].get("liquidity") or 0),
                "event_volume": float(market_bundle["event"].get("volume") or 0),
                "outcomes": {
                    key: {
                        "book": outcome_books[key],
                        "model_probability": row["model"][key],
                        "market_no_vig_probability": no_vig[key] if no_vig else None,
                        "edge_vs_best_ask": (
                            row["model"][key] - outcome_books[key]["best_ask"]
                            if outcome_books[key]["best_ask"] is not None
                            else None
                        ),
                    }
                    for key in ("home_win", "draw", "away_win")
                },
            }
        if total_market:
            tokens = market_tokens(total_market)
            over_book = books[tokens["Over"]]
            under_book = books[tokens["Under"]]
            row["over_under_2_5"] = {
                "market_id": total_market["id"],
                "market_slug": total_market["slug"],
                "reported_liquidity": float(total_market.get("liquidity") or 0),
                "reported_volume": float(total_market.get("volume") or 0),
                "over": {
                    "book": over_book,
                    "model_probability": row["model"]["over_2_5"],
                    "edge_vs_best_ask": (
                        row["model"]["over_2_5"] - over_book["best_ask"]
                        if over_book["best_ask"] is not None
                        else None
                    ),
                },
                "under": {
                    "book": under_book,
                    "model_probability": row["model"]["under_2_5"],
                    "edge_vs_best_ask": (
                        row["model"]["under_2_5"] - under_book["best_ask"]
                        if under_book["best_ask"] is not None
                        else None
                    ),
                },
            }
        row["decision_boundaries"] = {
            "read_only": True,
            "wallet_used": False,
            "credentials_used": False,
            "trading_endpoint_present": False,
            "probability_validated": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        }
        output.append(row)

    payload = {
        "version": VERSION,
        "status": "read_only_market_observation",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "events": GAMMA,
            "order_books": CLOB,
            "authentication": "none",
        },
        "fixtures": output,
        "decision_boundaries": {
            "writes_external_state": False,
            "can_place_orders": False,
            "capital_deployment_ready": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve().relative_to(ROOT)),
                "fixtures": len(output),
                "events_found": sum(row["market_available"] for row in output),
                "totals_found": sum(row["over_under_2_5"] is not None for row in output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
