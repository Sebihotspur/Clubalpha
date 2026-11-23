"""Reconstruct and then track a price-aware Clubalpha paper bankroll."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


VERSION = "clubalpha_bankroll_simulation_v1"
OUTCOMES = ("home_win", "draw", "away_win")


def validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != VERSION:
        raise ValueError("bankroll-simulation version is not supported")
    if float(config["starting_bankroll"]) <= 0:
        raise ValueError("starting bankroll must be positive")
    if not 0 < float(
        config["risk"]["maximum_fraction_of_current_bankroll_per_position"]
    ) <= 1:
        raise ValueError("position fraction must be inside (0, 1]")
    if any(value is not False for value in config["locked_boundaries"].values()):
        raise ValueError("bankroll simulation weakens a locked boundary")


def source_name(snapshot: dict[str, Any]) -> str:
    version = str(snapshot.get("version") or "")
    if "polymarket" in version:
        return "polymarket"
    if "kalshi" in version:
        return "kalshi"
    raise ValueError(f"unsupported market snapshot: {version}")


def _round(snapshot: dict[str, Any]) -> int:
    rounds = {
        int(row["fixture"].get("round") or 11) for row in snapshot["fixtures"]
    }
    if len(rounds) != 1:
        raise ValueError("market snapshot spans multiple rounds")
    return rounds.pop()


def _book(
    row: dict[str, Any], market: str, outcome: str
) -> dict[str, Any] | None:
    if market == "one_x_two":
        return (
            (((row.get("one_x_two") or {}).get("outcomes") or {}).get(outcome) or {})
            .get("book")
        )
    key = "over" if outcome == "over_2_5" else "under"
    return (((row.get("over_under_2_5") or {}).get(key) or {}).get("book"))


def _selections(model: dict[str, Any]) -> list[tuple[str, str, float]]:
    leader = max(OUTCOMES, key=lambda key: float(model[key]))
    over = float(model["over_2_5"])
    total_outcome = "over_2_5" if over >= 0.5 else "under_2_5"
    return [
        ("one_x_two", leader, float(model[leader])),
        ("over_under_2_5", total_outcome, max(over, 1.0 - over)),
    ]


def _won(outcome: str, result: dict[str, Any]) -> bool:
    if outcome == "over_2_5":
        return int(result["final_home_goals"]) + int(result["final_away_goals"]) > 2
    if outcome == "under_2_5":
        return int(result["final_home_goals"]) + int(result["final_away_goals"]) < 3
    return result["outcome"] == outcome


def build_candidates(
    snapshots: list[dict[str, Any]],
    results: list[dict[str, Any]],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_config(config)
    by_round_source = {}
    for snapshot in snapshots:
        key = (_round(snapshot), source_name(snapshot))
        if key in by_round_source:
            raise ValueError(f"duplicate snapshot for round/source: {key}")
        by_round_source[key] = snapshot
    result_by_id = {int(row["match_id"]): row for row in results}
    candidates = []
    counters = defaultdict(int)
    fixture_ids = set()
    for round_number in sorted({key[0] for key in by_round_source}):
        documents = {
            source: snapshot
            for (round_value, source), snapshot in by_round_source.items()
            if round_value == round_number
        }
        indexed = {
            source: {
                int(row["fixture"]["match_id"]): row
                for row in snapshot["fixtures"]
            }
            for source, snapshot in documents.items()
        }
        match_ids = set().union(*(set(rows) for rows in indexed.values()))
        for match_id in match_ids:
            fixture_ids.add(match_id)
            primary = indexed.get("polymarket", {}).get(match_id)
            if primary is None:
                primary = next(
                    rows[match_id] for rows in indexed.values() if match_id in rows
                )
            model = primary["model"]
            if "over_2_5" not in model:
                raise ValueError("primary snapshot lacks total probabilities")
            for market, outcome, probability in _selections(model):
                counters["forecast_directions"] += 1
                books = []
                for source, rows in indexed.items():
                    row = rows.get(match_id)
                    book = _book(row, market, outcome) if row else None
                    if not book or book.get("best_ask") is None:
                        continue
                    spread = book.get("spread")
                    depth = float(book.get("top_ask_notional") or 0.0)
                    if spread is None or float(spread) > float(
                        config["execution"]["maximum_spread"]
                    ) + 1e-9:
                        continue
                    if depth < float(
                        config["execution"]["minimum_top_ask_notional"]
                    ):
                        continue
                    books.append(
                        {
                            "source": source,
                            "best_ask": float(book["best_ask"]),
                            "spread": float(spread),
                            "top_ask_notional": depth,
                        }
                    )
                if not books:
                    counters["excluded_no_executable_book"] += 1
                    continue
                best = min(
                    books,
                    key=lambda row: (
                        row["best_ask"],
                        -row["top_ask_notional"],
                        row["source"],
                    ),
                )
                edge = probability - best["best_ask"]
                if edge + 1e-9 < float(
                    config["selection"]["minimum_model_edge"]
                ):
                    counters["excluded_edge_below_gate"] += 1
                    continue
                result = result_by_id.get(match_id)
                candidates.append(
                    {
                        "position_id": f"{match_id}:{market}:{outcome}",
                        "round": round_number,
                        "match_id": match_id,
                        "fixture": (
                            f"{primary['fixture']['home_team']} vs "
                            f"{primary['fixture']['away_team']}"
                        ),
                        "kickoff_utc": primary["fixture"]["kickoff_utc"],
                        "market": market,
                        "outcome": outcome,
                        "model_probability": round(probability, 6),
                        "source": best["source"],
                        "best_ask": best["best_ask"],
                        "spread": best["spread"],
                        "top_ask_notional": best["top_ask_notional"],
                        "raw_model_edge": round(edge, 6),
                        "settled": result is not None,
                        "won": _won(outcome, result) if result else None,
                        "score": (
                            f"{result['final_home_goals']}-{result['final_away_goals']}"
                            if result
                            else None
                        ),
                    }
                )
    coverage = {
        "rounds": sorted({key[0] for key in by_round_source}),
        "fixtures_with_prices": len(fixture_ids),
        "fixtures_with_results": sum(match_id in result_by_id for match_id in fixture_ids),
        "fixtures_pending": sum(match_id not in result_by_id for match_id in fixture_ids),
        **dict(counters),
        "value_candidates": len(candidates),
    }
    return candidates, coverage


def simulate_bankroll(
    candidates: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    validate_config(config)
    bankroll = float(config["starting_bankroll"])
    starting = bankroll
    peak = bankroll
    maximum_drawdown = 0.0
    settled = [row for row in candidates if row["settled"]]
    pending = [row for row in candidates if not row["settled"]]
    by_kickoff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in settled:
        by_kickoff[row["kickoff_utc"]].append(row)
    positions = []
    round_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for kickoff in sorted(by_kickoff):
        batch_bankroll = bankroll
        batch_pnl = 0.0
        for candidate in sorted(
            by_kickoff[kickoff], key=lambda row: (row["match_id"], row["market"])
        ):
            desired = float(
                config["risk"]["maximum_fraction_of_current_bankroll_per_position"]
            ) * batch_bankroll
            stake = min(desired, float(candidate["top_ask_notional"]))
            pnl = (
                stake * (1.0 / float(candidate["best_ask"]) - 1.0)
                if candidate["won"]
                else -stake
            )
            row = {
                **candidate,
                "bankroll_before_kickoff_batch": round(batch_bankroll, 6),
                "desired_stake_units": round(desired, 6),
                "paper_stake_units": round(stake, 6),
                "gross_pnl_units": round(pnl, 6),
            }
            positions.append(row)
            round_rows[int(candidate["round"])].append(row)
            batch_pnl += pnl
        bankroll += batch_pnl
        peak = max(peak, bankroll)
        maximum_drawdown = max(maximum_drawdown, (peak - bankroll) / peak)
    total_stake = sum(row["paper_stake_units"] for row in positions)
    total_pnl = sum(row["gross_pnl_units"] for row in positions)
    by_round = []
    for round_number in sorted(round_rows):
        rows = round_rows[round_number]
        stake = sum(row["paper_stake_units"] for row in rows)
        pnl = sum(row["gross_pnl_units"] for row in rows)
        by_round.append(
            {
                "round": round_number,
                "positions": len(rows),
                "wins": sum(row["won"] is True for row in rows),
                "losses": sum(row["won"] is False for row in rows),
                "stake_units": round(stake, 6),
                "gross_pnl_units": round(pnl, 6),
                "gross_roi_on_stake": round(pnl / stake, 6) if stake else None,
            }
        )
    return {
        "starting_bankroll": starting,
        "ending_bankroll": round(bankroll, 6),
        "gross_pnl_units": round(total_pnl, 6),
        "return_on_starting_bankroll": round(total_pnl / starting, 6),
        "total_stake_units": round(total_stake, 6),
        "gross_roi_on_stake": round(total_pnl / total_stake, 6)
        if total_stake
        else None,
        "maximum_drawdown": round(maximum_drawdown, 6),
        "settled_positions": len(positions),
        "pending_positions": len(pending),
        "wins": sum(row["won"] is True for row in positions),
        "losses": sum(row["won"] is False for row in positions),
        "by_round": by_round,
        "positions": positions,
        "pending": pending,
    }


def build_bankroll_artifact(
    snapshots: list[dict[str, Any]],
    results: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    candidates, coverage = build_candidates(snapshots, results, config)
    simulation = simulate_bankroll(candidates, config)
    return {
        "version": VERSION,
        "status": "historical_reconstruction_then_forward_locked",
        "coverage": coverage,
        "strategy": {
            "starting_bankroll": config["starting_bankroll"],
            "position_fraction": config["risk"][
                "maximum_fraction_of_current_bankroll_per_position"
            ],
            "minimum_model_edge": config["selection"]["minimum_model_edge"],
            "maximum_spread": config["execution"]["maximum_spread"],
            "minimum_top_ask_notional": config["execution"][
                "minimum_top_ask_notional"
            ],
            "stake_capped_by_top_ask_notional": True,
            "price_rule": "lowest executable ask among timestamped books",
        },
        "simulation": simulation,
        "decision_boundaries": {
            "historical_strategy_defined_after_early_results": True,
            "missing_prices_backfilled": False,
            "post_kickoff_prices_used": False,
            "fees_and_slippage_included": False,
            "real_capital_authorized": False,
        },
    }

