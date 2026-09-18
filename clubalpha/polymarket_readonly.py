"""Read-only normalization for public Polymarket market data."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


VERSION = "clubalpha_polymarket_readonly_v1"


def json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    return []


def market_tokens(market: dict[str, Any]) -> dict[str, str]:
    outcomes = json_list(market.get("outcomes"))
    tokens = json_list(market.get("clobTokenIds"))
    if len(outcomes) != len(tokens):
        raise ValueError("Polymarket outcomes and token ids do not reconcile")
    return {str(outcome): str(token) for outcome, token in zip(outcomes, tokens)}


def summarize_book(book: dict[str, Any], *, depth_cents: float = 0.02) -> dict[str, Any]:
    bids = [
        (float(row["price"]), float(row["size"])) for row in book.get("bids") or []
    ]
    asks = [
        (float(row["price"]), float(row["size"])) for row in book.get("asks") or []
    ]
    best_bid = max((row[0] for row in bids), default=None)
    best_ask = min((row[0] for row in asks), default=None)
    ask_limit = best_ask + depth_cents if best_ask is not None else None
    depth = sum(
        price * size
        for price, size in asks
        if ask_limit is not None and price <= ask_limit + 1e-12
    )
    top_size = next((size for price, size in asks if price == best_ask), None)
    return {
        "token_id": str(book.get("asset_id") or ""),
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
        "top_ask_shares": top_size,
        "top_ask_notional": (
            best_ask * top_size
            if best_ask is not None and top_size is not None
            else None
        ),
        "ask_notional_within_2c": depth,
        "minimum_order_size": float(book.get("min_order_size") or 0.0),
        "tick_size": float(book.get("tick_size") or 0.0),
    }


def normalized_team(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    words = [word for word in text.split() if word not in {"fc", "afc"}]
    return " ".join(words)


def event_matches_fixture(event: dict[str, Any], fixture: dict[str, Any]) -> bool:
    title = normalized_team(str(event.get("title") or ""))
    home = normalized_team(str(fixture["home_team"]))
    away = normalized_team(str(fixture["away_team"]))
    event_time = str(event.get("endDate") or "").replace(".000Z", "Z")
    fixture_time = str(fixture["kickoff_utc"]).replace(".000Z", "Z")
    return home in title and away in title and event_time == fixture_time


def no_vig_probabilities(midpoints: dict[str, float]) -> dict[str, float]:
    denominator = sum(midpoints.values())
    if denominator <= 0:
        raise ValueError("market midpoint sum must be positive")
    return {key: value / denominator for key, value in midpoints.items()}
