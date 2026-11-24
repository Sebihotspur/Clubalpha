"""Execution-aware paper gate downstream of frozen football decisions."""

from __future__ import annotations

from datetime import datetime
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
    scaled = config.get("scaled_paper") or {}
    if scaled.get("enabled"):
        if min(
            float(scaled["minimum_raw_edge"]),
            float(scaled["full_size_edge_net_of_execution"]),
            float(scaled["maximum_bankroll_fraction"]),
        ) <= 0:
            raise ValueError("scaled-paper thresholds must be positive")
        if not float(scaled["maximum_bankroll_fraction"]) <= 0.01:
            raise ValueError("scaled paper cannot increase the 1% risk ceiling")
        if set(scaled["stage_size_cap"]) != {"provisional", "final"}:
            raise ValueError("scaled-paper stage caps are incomplete")
        if any(
            not 0 < float(value) <= 1
            for value in scaled["stage_size_cap"].values()
        ):
            raise ValueError("scaled-paper stage caps must be inside (0, 1]")
        if float(scaled["stage_size_cap"]["provisional"]) > 0.25:
            raise ValueError("provisional paper cannot exceed quarter size")
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


def _market_entry(
    row: dict[str, Any], market: str, outcome: str
) -> dict[str, Any] | None:
    if market == "one_x_two":
        bundle = row.get("one_x_two")
        return ((bundle or {}).get("outcomes") or {}).get(outcome)
    if market == "over_under_2_5":
        bundle = row.get("over_under_2_5")
        key = "over" if outcome == "over_2_5" else "under"
        return (bundle or {}).get(key)
    raise ValueError(f"unsupported market: {market}")


def _no_vig_probability(
    row: dict[str, Any], market: str, outcome: str
) -> float | None:
    entry = _market_entry(row, market, outcome)
    if not entry:
        return None
    if entry.get("market_no_vig_probability") is not None:
        return float(entry["market_no_vig_probability"])
    if market != "over_under_2_5":
        return None
    bundle = row.get("over_under_2_5") or {}
    over_midpoint = ((bundle.get("over") or {}).get("book") or {}).get("midpoint")
    under_midpoint = ((bundle.get("under") or {}).get("book") or {}).get("midpoint")
    if over_midpoint is None or under_midpoint is None:
        return None
    denominator = float(over_midpoint) + float(under_midpoint)
    if denominator <= 0:
        return None
    value = float(over_midpoint) if outcome == "over_2_5" else float(under_midpoint)
    return value / denominator


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
        entry = _market_entry(row, market, outcome) if row else None
        book = (entry or {}).get("book")
        if not book or book.get("best_ask") is None:
            continue
        ask = float(book["best_ask"])
        raw_edge = probability - ask
        no_vig = _no_vig_probability(row, market, outcome)
        output.append(
            {
                "source": source,
                "best_bid": book.get("best_bid"),
                "best_ask": ask,
                "spread": book.get("spread"),
                "top_ask_notional": book.get("top_ask_notional"),
                "market_no_vig_probability": (
                    round(no_vig, 6) if no_vig is not None else None
                ),
                "model_vs_market_no_vig": (
                    round(probability - no_vig, 6)
                    if no_vig is not None
                    else None
                ),
                "raw_edge": round(raw_edge, 6),
                "execution_cost_reserve": execution,
                "uncertainty_reserve": uncertainty,
                "edge_after_reserves": round(
                    raw_edge - execution - uncertainty, 6
                ),
            }
        )
    return sorted(output, key=lambda row: (row["best_ask"], row["source"]))


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.utcoffset() is not None else None


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
    decision_frozen_at_utc: str | None = None,
    kickoff_utc: str | None = None,
    source_captures: dict[str, str] | None = None,
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
    standard_paper_eligible = all(gates.values())
    scaled_config = config.get("scaled_paper") or {}
    capture_value = (source_captures or {}).get(best["source"]) if best else None
    freeze = _timestamp(decision_frozen_at_utc)
    capture = _timestamp(capture_value)
    kickoff = _timestamp(kickoff_utc)
    prematch_snapshot = bool(
        freeze and capture and kickoff and freeze <= capture < kickoff
    )
    approval = None
    if stage == "provisional" and best and prematch_snapshot:
        for entry in scaled_config.get("approved_provisional_entries", []):
            recorded = _timestamp(entry["recorded_at_utc"])
            if (
                entry["match_id"] == match_id
                and entry["market"] == market
                and entry["outcome"] == outcome
                and entry["source"] == best["source"]
                and entry["best_ask"] == best["best_ask"]
                and _timestamp(entry["captured_at_utc"]) == capture
                and recorded
                and capture <= recorded < kickoff
            ):
                approval = entry
                break
    scaled_required_gates = (
        "price_available",
        "football_call",
        "spread",
        "top_ask_depth",
        "cross_book_consensus",
    )
    usable_edge = (
        max(
            0.0,
            float(best["raw_edge"])
            - float(config["edge"]["execution_cost_reserve"]),
        )
        if best
        else 0.0
    )
    size_multiplier = 0.0
    scaled_paper_eligible = False
    if (
        not standard_paper_eligible
        and scaled_config.get("enabled")
        and prematch_snapshot
        and (gates["final_refresh"] or approval)
        and all(gates[key] for key in scaled_required_gates)
    ):
        full_size_edge = float(
            scaled_config["full_size_edge_net_of_execution"]
        )
        stage_cap = float(scaled_config["stage_size_cap"][stage])
        size_multiplier = min(stage_cap, usable_edge / full_size_edge)
        scaled_paper_eligible = bool(
            best
            and float(best["raw_edge"])
            >= float(scaled_config["minimum_raw_edge"])
            and size_multiplier > 0
        )
    paper_eligible = standard_paper_eligible or scaled_paper_eligible
    if standard_paper_eligible:
        paper_tier = "full_size"
        size_multiplier = 1.0
    elif scaled_paper_eligible:
        paper_tier = f"scaled_{stage}"
    else:
        paper_tier = None
        size_multiplier = 0.0
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
    if standard_paper_eligible:
        reason = "paper_gate_passed"
    elif scaled_paper_eligible:
        reason = "scaled_paper_gate_passed"
    else:
        reason = "paper_gate_failed"
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
        "market_no_vig_probability": (
            best["market_no_vig_probability"] if best else None
        ),
        "model_vs_market_no_vig": (
            best["model_vs_market_no_vig"] if best else None
        ),
        "model_vs_executable_ask": best["raw_edge"] if best else None,
        "cross_book_ask_gap": (
            round(cross_book_gap, 6) if cross_book_gap is not None else None
        ),
        "gates": gates,
        "standard_paper_eligible": standard_paper_eligible,
        "scaled_paper_eligible": scaled_paper_eligible,
        "paper_eligible": paper_eligible,
        "paper_tier": paper_tier,
        "paper_entry_recorded_at_utc": (
            approval["recorded_at_utc"] if scaled_paper_eligible and approval else None
        ),
        "price_captured_at_utc": capture_value,
        "position_size_multiplier": round(size_multiplier, 6),
        "paper_bankroll_fraction": (
            round(
                size_multiplier
                * float(scaled_config["maximum_bankroll_fraction"]),
                8,
            )
            if paper_eligible and scaled_config.get("enabled")
            else None
        ),
        "sizing_edge_net_of_execution": (
            round(usable_edge, 6) if best else None
        ),
        "reason": reason,
        "real_capital_eligible": False,
    }


def build_market_gate(
    decisions: dict[str, Any],
    market_snapshots: list[dict[str, Any]],
    config: dict[str, Any],
    discretionary_overlay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_config(config)
    snapshots = snapshot_index(market_snapshots)
    source_captures = {
        snapshot_source(snapshot): snapshot["captured_at_utc"]
        for snapshot in market_snapshots
    }
    stage = str(decisions["refresh_gate"]["stage"])
    overlays = {}
    if discretionary_overlay:
        if discretionary_overlay.get("status") != "discretionary_overlay_scored":
            raise ValueError("discretionary overlay must be scored before market gating")
        overlays = {
            (int(fixture["match_id"]), selection["market"]): selection
            for fixture in discretionary_overlay["fixtures"]
            for selection in fixture["selections"]
        }
    fixtures = []
    for decision in decisions["fixtures"]:
        side = decision["side_decision"]
        total = decision["total_decision"]
        match_id = int(decision["match_id"])
        chronology = {
            "decision_frozen_at_utc": decisions.get("generated_at_utc"),
            "kickoff_utc": decision["kickoff_utc"],
            "source_captures": source_captures,
        }
        over_probability = float(total["over_probability"])
        total_direction = "over_2_5" if over_probability >= 0.5 else "under_2_5"
        total_probability = max(over_probability, 1.0 - over_probability)
        side_overlay = overlays.get((match_id, "one_x_two"))
        total_overlay = overlays.get((match_id, "over_under_2_5"))
        side_call = (
            str(side_overlay["effective_call"])
            if side_overlay and side_overlay["overlay_active"]
            else str(side["call"])
        )
        side_probability = (
            float(side_overlay["effective_probability"])
            if side_overlay and side_overlay["overlay_active"]
            else float(side["leader_probability"])
        )
        total_call = (
            str(total_overlay["effective_call"])
            if total_overlay and total_overlay["overlay_active"]
            else str(total["call"])
        )
        effective_total_probability = (
            float(total_overlay["effective_probability"])
            if total_overlay and total_overlay["overlay_active"]
            else total_probability
        )
        side_gate = evaluate_selection(
            match_id=match_id,
            market="one_x_two",
            football_call=side_call,
            diagnostic_outcome=str(side["leader"]),
            probability=side_probability,
            stage=stage,
            final_call_eligible=bool(decision["final_call_eligible"]),
            snapshots=snapshots,
            config=config,
            **chronology,
        )
        total_gate = evaluate_selection(
            match_id=match_id,
            market="over_under_2_5",
            football_call=total_call,
            diagnostic_outcome=total_direction,
            probability=effective_total_probability,
            stage=stage,
            final_call_eligible=bool(decision["final_call_eligible"]),
            snapshots=snapshots,
            config=config,
            **chronology,
        )
        side_gate["systematic_probability"] = side["leader_probability"]
        side_gate["systematic_call"] = side["call"]
        side_gate["call_origin"] = (
            side_overlay["call_origin"]
            if side_overlay and side_overlay["overlay_active"]
            else "systematic"
        )
        side_gate["discretionary_overlay_active"] = bool(
            side_overlay and side_overlay["overlay_active"]
        )
        total_gate["systematic_probability"] = round(total_probability, 6)
        total_gate["systematic_call"] = total["call"]
        total_gate["call_origin"] = (
            total_overlay["call_origin"]
            if total_overlay and total_overlay["overlay_active"]
            else "systematic"
        )
        total_gate["discretionary_overlay_active"] = bool(
            total_overlay and total_overlay["overlay_active"]
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
        "source_captures": source_captures,
        "summary": {
            "fixtures": len(fixtures),
            "football_side_calls": sum(
                row["side"]["football_call"] != "pass" for row in fixtures
            ),
            "football_total_calls": sum(
                row["total"]["football_call"] != "pass" for row in fixtures
            ),
            "paper_positions": sum(len(row["paper_positions"]) for row in fixtures),
            "scaled_paper_positions": sum(
                row[kind]["scaled_paper_eligible"]
                for row in fixtures
                for kind in ("side", "total")
            ),
            "raw_edge_diagnostics": sum(
                row["gates"]["minimum_raw_edge"] for row in selections
            ),
            "active_discretionary_overlays": sum(
                row[kind]["discretionary_overlay_active"]
                for row in fixtures
                for kind in ("side", "total")
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

