#!/usr/bin/env python3
"""Collect a no-auth, read-only Kalshi snapshot for one PL slate."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.kalshi_readonly import (  # noqa: E402
    VERSION,
    group_fixture_markets,
    summarize_market,
)
from clubalpha.polymarket_readonly import no_vig_probabilities  # noqa: E402


API = "https://api.elections.kalshi.com/trade-api/v2"
GAME_SERIES = "KXEPLGAME"
TOTAL_SERIES = "KXEPLTOTAL"


def get_json(path: str, params: dict[str, Any] | None = None) -> Any:
    query = urllib.parse.urlencode(params or {})
    url = f"{API}{path}" + (f"?{query}" if query else "")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Clubalpha/0.1 (+https://github.com/Sebihotspur/Clubalpha)",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    game_markets = get_json(
        "/markets",
        {"series_ticker": GAME_SERIES, "status": "open", "limit": 1000},
    ).get("markets", [])
    total_markets = get_json(
        "/markets",
        {"series_ticker": TOTAL_SERIES, "status": "open", "limit": 1000},
    ).get("markets", [])
    series = get_json(f"/series/{GAME_SERIES}").get("series", {})

    fixtures = []
    for decision in decisions["fixtures"]:
        fixture = {
            "match_id": decision["match_id"],
            "fixture": decision["fixture"],
            "kickoff_utc": decision["kickoff_utc"],
            "home_team": decision["home_team"],
            "away_team": decision["away_team"],
        }
        model = {
            "home_win": decision["calibrated_probabilities"]["home_win"],
            "draw": decision["calibrated_probabilities"]["draw"],
            "away_win": decision["calibrated_probabilities"]["away_win"],
        }
        market_bundle = group_fixture_markets(game_markets, fixture)
        row = {
            "fixture": fixture,
            "model": model,
            "market_available": market_bundle is not None,
            "one_x_two": None,
            "over_under_2_5": None,
            "decision_boundaries": {
                "read_only": True,
                "wallet_used": False,
                "credentials_used": False,
                "trading_endpoint_present": False,
                "probability_validated": False,
                "market_ready": False,
                "capital_deployment_ready": False,
            },
        }
        if market_bundle:
            books = {
                key: summarize_market(market_bundle[key])
                for key in ("home_win", "draw", "away_win")
            }
            midpoints = {
                key: value["midpoint"]
                for key, value in books.items()
                if value["midpoint"] is not None
            }
            no_vig = no_vig_probabilities(midpoints) if len(midpoints) == 3 else None
            row["one_x_two"] = {
                "event_ticker": market_bundle["event_ticker"],
                "event_volume_contracts": sum(
                    book["volume_contracts"] for book in books.values()
                ),
                "event_open_interest_contracts": sum(
                    book["open_interest_contracts"] for book in books.values()
                ),
                "outcomes": {
                    key: {
                        "book": books[key],
                        "model_probability": model[key],
                        "market_no_vig_probability": no_vig[key] if no_vig else None,
                        "edge_vs_best_ask_before_fees": (
                            model[key] - books[key]["best_ask"]
                            if books[key]["best_ask"] is not None
                            else None
                        ),
                    }
                    for key in ("home_win", "draw", "away_win")
                },
            }
        fixtures.append(row)

    payload = {
        "version": VERSION,
        "status": "read_only_market_observation",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "api": API,
            "game_series": GAME_SERIES,
            "total_series": TOTAL_SERIES,
            "authentication": "none",
            "settlement_sources": series.get("settlement_sources", []),
            "fee_type": series.get("fee_type"),
            "fee_multiplier": series.get("fee_multiplier"),
        },
        "totals_status": {
            "open_markets_found": len(total_markets),
            "message": (
                "Kalshi EPL total-goals markets are not open for this slate yet."
                if not total_markets
                else "Open Kalshi EPL total-goals markets require fixture matching."
            ),
        },
        "fixtures": fixtures,
        "decision_boundaries": {
            "writes_external_state": False,
            "can_place_orders": False,
            "fees_included_in_edge": False,
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
                "fixtures": len(fixtures),
                "events_found": sum(row["market_available"] for row in fixtures),
                "totals_open": len(total_markets),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

