"""Paper-performance accounting for frozen Clubalpha selections."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


VERSION = "clubalpha_paper_ledger_v1"


def validate_config(config: dict[str, Any]) -> None:
    if config.get("version") != VERSION:
        raise ValueError("paper-ledger version is not supported")
    if float(config["allocation"]["default_position_stake_units"]) <= 0:
        raise ValueError("paper position stake must be positive")
    if any(value is not False for value in config["locked_boundaries"].values()):
        raise ValueError("paper ledger weakens a locked boundary")


def _hit(outcome: str, result: dict[str, Any]) -> bool:
    if outcome == "over_2_5":
        return int(result["final_home_goals"]) + int(result["final_away_goals"]) > 2
    if outcome == "under_2_5":
        return int(result["final_home_goals"]) + int(result["final_away_goals"]) < 3
    return str(result["outcome"]) == outcome


def _selection(
    *,
    fixture: dict[str, Any],
    market: str,
    outcome: str,
    probability: float,
    best_execution: dict[str, Any] | None,
    result: dict[str, Any] | None,
    book: str,
    official_position: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    ask = float(best_execution["best_ask"]) if best_execution else None
    settled = result is not None
    won = _hit(outcome, result) if result else None
    counterfactual_pnl = None
    if settled and ask:
        counterfactual_pnl = (1.0 / ask - 1.0) if won else -1.0
    official_stake = (
        float(config["allocation"]["default_position_stake_units"])
        if official_position
        else 0.0
    )
    official_pnl = (
        round(counterfactual_pnl * official_stake, 6)
        if counterfactual_pnl is not None and official_position
        else None if official_position and not settled else 0.0
    )
    return {
        "selection_id": f"{fixture['match_id']}:{market}:{outcome}:{book}",
        "match_id": fixture["match_id"],
        "fixture": fixture["fixture"],
        "kickoff_utc": fixture["kickoff_utc"],
        "market": market,
        "outcome": outcome,
        "model_probability": round(float(probability), 6),
        "captured_source": best_execution.get("source") if best_execution else None,
        "captured_best_ask": ask,
        "book": book,
        "official_position": official_position,
        "official_stake_units": official_stake,
        "settled": settled,
        "won": won,
        "score": (
            f"{result['final_home_goals']}-{result['final_away_goals']}"
            if result
            else None
        ),
        "official_gross_pnl_units": official_pnl,
        "counterfactual_equal_stake_gross_pnl_units": (
            round(counterfactual_pnl, 6)
            if counterfactual_pnl is not None
            else None
        ),
    }


def _book_summary(rows: list[dict[str, Any]], *, counterfactual: bool) -> dict[str, Any]:
    settled = [row for row in rows if row["settled"]]
    if counterfactual:
        pnl = sum(
            float(row["counterfactual_equal_stake_gross_pnl_units"])
            for row in settled
            if row["counterfactual_equal_stake_gross_pnl_units"] is not None
        )
        stake = sum(
            1.0
            for row in settled
            if row["counterfactual_equal_stake_gross_pnl_units"] is not None
        )
    else:
        pnl = sum(float(row["official_gross_pnl_units"] or 0.0) for row in settled)
        stake = sum(float(row["official_stake_units"]) for row in settled)
    return {
        "selections": len(rows),
        "settled": len(settled),
        "pending": len(rows) - len(settled),
        "wins": sum(row["won"] is True for row in settled),
        "losses": sum(row["won"] is False for row in settled),
        "stake_units": round(stake, 6),
        "gross_pnl_units": round(pnl, 6),
        "gross_roi": round(pnl / stake, 6) if stake else None,
    }


def build_paper_ledger(
    decisions: dict[str, Any],
    market_gate: dict[str, Any],
    discretionary_queue: dict[str, Any],
    results: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    validate_config(config)
    results_by_id = {int(row["match_id"]): row for row in results}
    gate_by_id = {int(row["match_id"]): row for row in market_gate["fixtures"]}
    queue_by_id = {
        int(row["match_id"]): row for row in discretionary_queue["fixtures"]
    }
    decision_by_id = {int(row["match_id"]): row for row in decisions["fixtures"]}
    official = []
    raw_diagnostics = []
    discretionary = []
    model_accuracy = []
    for match_id, decision in decision_by_id.items():
        gate = gate_by_id[match_id]
        fixture = {
            "match_id": match_id,
            "fixture": decision["fixture"],
            "kickoff_utc": decision["kickoff_utc"],
        }
        result = results_by_id.get(match_id)
        for key, gate_key in (("side", "one_x_two"), ("total", "over_under_2_5")):
            row = gate[key]
            model_accuracy.append(
                _selection(
                    fixture=fixture,
                    market=gate_key,
                    outcome=row["evaluated_outcome"],
                    probability=row["systematic_probability"],
                    best_execution=row["best_execution"],
                    result=result,
                    book="model_accuracy_diagnostic",
                    official_position=False,
                    config=config,
                )
            )
            if row["paper_eligible"]:
                official.append(
                    _selection(
                        fixture=fixture,
                        market=gate_key,
                        outcome=row["football_call"],
                        probability=row["model_probability"],
                        best_execution=row["best_execution"],
                        result=result,
                        book="official_paper",
                        official_position=True,
                        config=config,
                    )
                )
            if row["gates"]["minimum_raw_edge"]:
                raw_diagnostics.append(
                    _selection(
                        fixture=fixture,
                        market=gate_key,
                        outcome=row["evaluated_outcome"],
                        probability=row["model_probability"],
                        best_execution=row["best_execution"],
                        result=result,
                        book="raw_price_diagnostic",
                        official_position=False,
                        config=config,
                    )
                )
        for selection in queue_by_id[match_id]["selections"]:
            if not selection["structurally_reviewable"]:
                continue
            key = "side" if selection["market"] == "one_x_two" else "total"
            gate_row = gate[key]
            discretionary.append(
                _selection(
                    fixture=fixture,
                    market=selection["market"],
                    outcome=selection["outcome"],
                    probability=selection["systematic_probability"],
                    best_execution=gate_row["best_execution"],
                    result=result,
                    book="discretionary_review_candidate",
                    official_position=False,
                    config=config,
                )
            )
    completed_fixtures = len(results_by_id)
    total_fixtures = len(decision_by_id)
    return {
        "version": VERSION,
        "status": "partial" if completed_fixtures < total_fixtures else "settled",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "round": decisions["round"],
        "coverage": {
            "fixtures": total_fixtures,
            "completed": completed_fixtures,
            "pending": total_fixtures - completed_fixtures,
        },
        "summary": {
            "official_paper": _book_summary(official, counterfactual=False),
            "raw_price_diagnostics": _book_summary(
                raw_diagnostics, counterfactual=True
            ),
            "discretionary_review_candidates": _book_summary(
                discretionary, counterfactual=True
            ),
            "model_side_accuracy": _book_summary(
                [row for row in model_accuracy if row["market"] == "one_x_two"],
                counterfactual=False,
            ),
            "model_total_accuracy": _book_summary(
                [
                    row
                    for row in model_accuracy
                    if row["market"] == "over_under_2_5"
                ],
                counterfactual=False,
            ),
        },
        "books": {
            "official_paper": official,
            "raw_price_diagnostics": raw_diagnostics,
            "discretionary_review_candidates": discretionary,
            "model_accuracy_diagnostics": model_accuracy,
        },
        "decision_boundaries": {
            "predictions_backfilled": False,
            "shadow_candidates_count_as_official_positions": False,
            "fees_and_slippage_in_gross_pnl": False,
            "real_capital_authorized": False,
        },
    }

