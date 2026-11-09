"""Read-only normalization for public Kalshi EPL market data."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


VERSION = "clubalpha_kalshi_readonly_v1"


TEAM_MARKET_ALIASES = {
    "afc bournemouth": "bournemouth",
    "brighton hove albion": "brighton",
    "coventry city": "coventry",
    "hull city": "hull city",
    "newcastle united": "newcastle",
    "tottenham hotspur": "tottenham",
}


def normalized_team(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    words = [word for word in text.split() if word not in {"fc", "afc"}]
    return " ".join(words)


def market_team_name(team: str) -> str:
    normalized = normalized_team(team)
    return TEAM_MARKET_ALIASES.get(normalized, normalized)


def market_matches_team(market: dict[str, Any], team: str) -> bool:
    title = normalized_team(str(market.get("title") or ""))
    return title == f"{market_team_name(team)} wins"


def group_fixture_markets(
    markets: list[dict[str, Any]], fixture: dict[str, Any]
) -> dict[str, dict[str, Any]] | None:
    by_event: dict[str, list[dict[str, Any]]] = {}
    for market in markets:
        by_event.setdefault(str(market.get("event_ticker") or ""), []).append(market)

    matches = []
    for event_ticker, event_markets in by_event.items():
        home = next(
            (
                market
                for market in event_markets
                if market_matches_team(market, str(fixture["home_team"]))
            ),
            None,
        )
        away = next(
            (
                market
                for market in event_markets
                if market_matches_team(market, str(fixture["away_team"]))
            ),
            None,
        )
        draw = next(
            (
                market
                for market in event_markets
                if normalized_team(str(market.get("title") or ""))
                == "tie is the result"
            ),
            None,
        )
        if home and draw and away:
            matches.append(
                {
                    "event_ticker": event_ticker,
                    "home_win": home,
                    "draw": draw,
                    "away_win": away,
                }
            )
    if len(matches) > 1:
        raise ValueError(
            f"multiple Kalshi events matched {fixture['home_team']} vs "
            f"{fixture['away_team']}"
        )
    return matches[0] if matches else None


def decimal_field(market: dict[str, Any], name: str) -> float | None:
    value = market.get(f"{name}_dollars")
    if value is None:
        value = market.get(name)
        if value is not None:
            return float(value) / 100.0
    return float(value) if value is not None else None


def float_field(market: dict[str, Any], name: str) -> float:
    value = market.get(f"{name}_fp")
    if value is None:
        value = market.get(name)
    return float(value or 0.0)


def summarize_market(market: dict[str, Any]) -> dict[str, Any]:
    best_bid = decimal_field(market, "yes_bid")
    best_ask = decimal_field(market, "yes_ask")
    ask_size = float_field(market, "yes_ask_size")
    return {
        "ticker": str(market.get("ticker") or ""),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "midpoint": (
            (best_bid + best_ask) / 2.0
            if best_bid is not None and best_ask is not None
            else None
        ),
        "spread": (
            best_ask - best_bid
            if best_bid is not None and best_ask is not None
            else None
        ),
        "top_ask_contracts": ask_size,
        "top_ask_notional": best_ask * ask_size if best_ask is not None else None,
        "volume_contracts": float_field(market, "volume"),
        "open_interest_contracts": float_field(market, "open_interest"),
        "close_time": market.get("close_time"),
        "status": market.get("status"),
    }

