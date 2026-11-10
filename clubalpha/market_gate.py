"""Execution-aware paper gate downstream of frozen football decisions."""

from __future__ import annotations

from typing import Any


VERSION = "clubalpha_market_gate_v1"


def validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != VERSION:
        raise ValueError("market-gate version is not supported")
    edge = config["edge"]
    if min(
        float(edge["minimum_raw_edge"]),
        float(edge["execution_cost_reserve"]),
        float(edge["minimum_edge_after_reserves"]),
    ) < 0:
        raise ValueError("market-gate edge thresholds cannot be negative")
    if set(edge["uncertainty_reserve"]) != {"provisional", "final"}:
        raise ValueError("market-gate uncertainty stages are incomplete")
    boundaries = config["locked_boundaries"]
    if any(value is not False for value in boundaries.values()):
        raise ValueError("market gate weakens a locked boundary")


def snapshot_source(snapshot: dict[str, Any]) -> str:
    version = str(snapshot.get("version") or "")
    if "polymarket" in version:
        return "polymarket"
    if "kalshi" in version:
        return "kalshi"
    raise ValueError(f"unsupported market snapshot version: {version}")


def snapshot_index(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[int, dict[str, Any]]]:
    output: dict[str, dict[int, dict[str, Any]]] = {}
    for snapshot in snapshots:
        source = snapshot_source(snapshot)
        if source in output:
            raise ValueError(f"duplicate {source} market snapshot")
        output[source] = {
            int(row["fixture"]["match_id"]): row for row in snapshot["fixtures"]
        }
    return output


def _book_for(
    row: dict[str, Any], market: str, outcome: str
) -> dict[str, Any] | None:
    if market == "one_x_two":
        bundle = row.get("one_x_two")
        return ((bundle or {}).get("outcomes") or {}).get(outcome, {}).get("book")
    if market == "over_under_2_5":
        bundle = row.get("over_under_2_5")
        key = "over" if outcome == "over_2_5" else "under"
        return ((bundle or {}).get(key) or {}).get("book")
    raise ValueError(f"unsupported market: {market}")


def _candidates(
    match_id: int,
    market: str,
    outcome: str,
    probability: float,
    snapshots: dict[str, dict[int, dict[str, Any]]],
    config: dict[str, Any],
    stage: str,
) -> list[dict[str, Any]]:
    edge_config = config["edge"]
    uncertainty = float(edge_config["uncertainty_reserve"][stage])
    execution = float(edge_config["execution_cost_reserve"])
    output = []
    for source, rows in snapshots.items():
        row = rows.get(match_id)
        book = _book_for(row, market, outcome) if row else None
        if not book or book.get("best_ask") is None:
            continue
        ask = float(book["best_ask"])
        raw_edge = probability - ask
        output.append(
            {
                "source": source,
                "best_bid": book.get("best_bid"),
                "best_ask": ask,
                "spread": book.get("spread"),
                "top_ask_notional": book.get("top_ask_notional"),
                "raw_edge": round(raw_edge, 6),
                "execution_cost_reserve": execution,
                "uncertainty_reserve": uncertainty,
                "edge_after_reserves": round(
                    raw_edge - execution - uncertainty, 6
                ),
            }
        )
    return sorted(output, key=lambda row: (row["best_ask"], row["source"]))


def evaluate_selection(
    *,
    match_id: int,
    market: str,
    football_call: str,
    diagnostic_outcome: str,
    probability: float,
    stage: str,
    final_call_eligible: bool,
    snapshots: dict[str, dict[int, dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    validate_config(config)
    if stage not in {"provisional", "final"}:
        raise ValueError("market-gate stage must be provisional or final")
    outcome = football_call if football_call != "pass" else diagnostic_outcome
    candidates = _candidates(
        match_id,
        market,
        outcome,
        float(probability),
        snapshots,
        config,
        stage,
    )
    execution = config["execution"]
    executable = [
        row
        for row in candidates
        if row["spread"] is not None
        and float(row["spread"]) <= float(execution["maximum_spread"])
        and row["top_ask_notional"] is not None
        and float(row["top_ask_notional"])
        >= float(execution["minimum_top_ask_notional"])
    ]
    best = executable[0] if executable else (candidates[0] if candidates else None)
    asks = [row["best_ask"] for row in candidates]
    cross_book_gap = max(asks) - min(asks) if len(asks) > 1 else None
    gates = {
        "price_available": best is not None,
        "football_call": football_call != "pass",
        "final_refresh": stage == "final" and bool(final_call_eligible),
        "minimum_raw_edge": bool(
            best
            and best["raw_edge"] >= float(config["edge"]["minimum_raw_edge"])
        ),
        "minimum_edge_after_reserves": bool(
            best
            and best["edge_after_reserves"]
            >= float(config["edge"]["minimum_edge_after_reserves"])
        ),
        "spread": bool(
            best
            and best["spread"] is not None
            and float(best["spread"]) <= float(execution["maximum_spread"])
        ),
        "top_ask_depth": bool(
            best
            and best["top_ask_notional"] is not None
            and float(best["top_ask_notional"])
            >= float(execution["minimum_top_ask_notional"])
        ),
        "cross_book_consensus": bool(
            cross_book_gap is None
            or cross_book_gap <= float(execution["maximum_cross_book_ask_gap"])
        ),
    }
    paper_eligible = all(gates.values())
    refusal_order = (
        ("price_available", "no_executable_price"),
        ("football_call", "football_layer_pass"),
        ("final_refresh", "final_refresh_incomplete"),
        ("minimum_raw_edge", "raw_edge_below_gate"),
        ("minimum_edge_after_reserves", "edge_consumed_by_reserves"),
        ("spread", "spread_above_gate"),
        ("top_ask_depth", "top_ask_depth_below_gate"),
        ("cross_book_consensus", "cross_book_prices_disagree"),
    )
    reason = "paper_gate_passed"
    for gate, refusal in refusal_order:
        if not gates[gate]:
            reason = refusal
            break
    return {
        "market": market,
        "football_call": football_call,
        "evaluated_outcome": outcome,
        "diagnostic_only": football_call == "pass",
        "model_probability": round(float(probability), 6),
        "books": candidates,
        "best_execution": best,
        "cross_book_ask_gap": (
            round(cross_book_gap, 6) if cross_book_gap is not None else None
        ),
        "gates": gates,
        "paper_eligible": paper_eligible,
        "reason": reason,
        "real_capital_eligible": False,
    }


def build_market_gate(
    decisions: dict[str, Any],
    market_snapshots: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    validate_config(config)
    snapshots = snapshot_index(market_snapshots)
    stage = str(decisions["refresh_gate"]["stage"])
    fixtures = []
    for decision in decisions["fixtures"]:
        side = decision["side_decision"]
        total = decision["total_decision"]
        over_probability = float(total["over_probability"])
        total_direction = "over_2_5" if over_probability >= 0.5 else "under_2_5"
        total_probability = max(over_probability, 1.0 - over_probability)
        side_gate = evaluate_selection(
            match_id=int(decision["match_id"]),
            market="one_x_two",
            football_call=str(side["call"]),
            diagnostic_outcome=str(side["leader"]),
            probability=float(side["leader_probability"]),
            stage=stage,
            final_call_eligible=bool(decision["final_call_eligible"]),
            snapshots=snapshots,
            config=config,
        )
        total_gate = evaluate_selection(
            match_id=int(decision["match_id"]),
            market="over_under_2_5",
            football_call=str(total["call"]),
            diagnostic_outcome=total_direction,
            probability=total_probability,
            stage=stage,
            final_call_eligible=bool(decision["final_call_eligible"]),
            snapshots=snapshots,
            config=config,
        )
        fixtures.append(
            {
                "match_id": decision["match_id"],
                "fixture": decision["fixture"],
                "kickoff_utc": decision["kickoff_utc"],
                "side": side_gate,
                "total": total_gate,
                "paper_positions": [
                    row
                    for row in (side_gate, total_gate)
                    if row["paper_eligible"]
                ],
            }
        )
    selections = [
        row[kind] for row in fixtures for kind in ("side", "total")
    ]
    price_quality_gates = (
        "price_available",
        "minimum_raw_edge",
        "minimum_edge_after_reserves",
        "spread",
        "top_ask_depth",
        "cross_book_consensus",
    )
    return {
        "version": VERSION,
        "status": "shadow_paper_only",
        "as_of": decisions["as_of"],
        "round": decisions["round"],
        "stage": stage,
        "source_captures": {
            snapshot_source(snapshot): snapshot["captured_at_utc"]
            for snapshot in market_snapshots
        },
        "summary": {
            "fixtures": len(fixtures),
            "football_side_calls": sum(
                row["side"]["football_call"] != "pass" for row in fixtures
            ),
            "football_total_calls": sum(
                row["total"]["football_call"] != "pass" for row in fixtures
            ),
            "paper_positions": sum(len(row["paper_positions"]) for row in fixtures),
            "raw_edge_diagnostics": sum(
                row["gates"]["minimum_raw_edge"] for row in selections
            ),
            "price_quality_diagnostics": sum(
                all(row["gates"][gate] for gate in price_quality_gates)
                for row in selections
            ),
            "real_positions": 0,
        },
        "fixtures": fixtures,
        "decision_boundaries": {
            "price_can_promote_football_pass": False,
            "automatic_real_capital_authorization": False,
            "frozen_model_probabilities_changed": False,
        },
    }

