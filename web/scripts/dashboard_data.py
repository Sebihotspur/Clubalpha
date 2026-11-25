"""Small display payload assembled from the newest existing artifacts."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

LEDGER_MARKETS = ("one_x_two", "over_under_2_5")
PNL_AVERAGE_DAYS = 5
MATCH_DAY_ZONE = ZoneInfo("America/New_York")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def scoreline(result):
    return f"{result['final_home_goals']}–{result['final_away_goals']}"


def fixture_slates(artifacts):
    """Use the newest saved pre-kickoff decision per fixture and append results."""
    slates = {}
    results = {}
    result_streams = set()
    for path in sorted((artifacts / "matchweek_research").glob("*/decisions.json")):
        doc = read_json(path)
        if doc.get("summary", {}).get("capital_deployment_ready"):
            raise ValueError(f"dashboard is paper only: {path}")
        freeze = timestamp(doc["generated_at_utc"])
        fixtures = slates.setdefault(int(doc["round"]), {})
        result_streams.update(
            artifacts.parent / Path(source).with_name("results.jsonl")
            for source in doc.get("provenance", {})
            if source.startswith("artifacts/contextual_interaction/")
            and source.endswith("/predictions.jsonl")
        )
        for row in doc["fixtures"]:
            match_id = int(row["match_id"])
            if freeze >= timestamp(row["kickoff_utc"]):
                continue
            old = fixtures.get(match_id)
            if old is None or freeze > old[0]:
                fixtures[match_id] = (
                    freeze, row, bool(row["final_call_eligible"]),
                )
    for path in sorted(result_streams):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            result = json.loads(line)
            match_id = int(result["match_id"])
            old = results.setdefault(match_id, result)
            if scoreline(old) != scoreline(result):
                raise ValueError(f"conflicting settled score for {match_id}")
    output = []
    for round_number, fixtures in sorted(slates.items(), reverse=True):
        if not fixtures:
            continue
        rows = []
        for match_id, (freeze, row, final) in fixtures.items():
            side, total = row["side_decision"], row["total_decision"]
            result = results.get(match_id)
            rows.append({
                **{key: row[key] for key in ("home_team", "away_team", "kickoff_utc")},
                "match_id": match_id,
                "frozen_at": freeze.isoformat(),
                "final_forecast": final,
                "probabilities": {key: row["calibrated_probabilities"][key]
                                  for key in ("home_win", "draw", "away_win")},
                "predicted_xg": row["calibrated_predicted_xg"],
                "side_call": side["call"],
                "side_leader": side["leader"],
                "over_probability": total["over_probability"],
                "total_call": total["call"],
                "score": scoreline(result) if result else None,
                "actual_side": result["outcome"] if result else None,
                "actual_over": (result["final_home_goals"] + result["final_away_goals"] > 2)
                if result else None,
            })
        rows.sort(key=lambda row: (row["kickoff_utc"], row["home_team"]))
        settled = [row for row in rows if row["score"] is not None]
        output.append({
            "round": round_number,
            "fixtures": rows,
            "settled": len(settled),
            "updated_at": max(timestamp(row["frozen_at"]) for row in rows).isoformat(),
            "provisional": any(not row["final_forecast"] for row in rows if not row["score"]),
            "leader_hits": sum(row["side_leader"] == row["actual_side"] for row in settled),
            "total_direction_hits": sum((row["over_probability"] >= 0.5) == row["actual_over"]
                                        for row in settled),
        })
    return output


def paper_entry_reason(position, decisions):
    """Describe an existing paper entry using only information saved by capture."""
    chance = position.get("model_probability")
    ask = position.get("captured_best_ask")
    if chance is None or ask is None:
        return None
    reasons = []
    capture = position.get("price_captured_at_utc")
    market = position.get("market")
    if capture and market == "over_under_2_5":
        cutoff = timestamp(capture)
        kickoff = timestamp(position["kickoff_utc"])
        for doc in decisions:
            if not timestamp(doc["generated_at_utc"]) <= cutoff < kickoff:
                continue
            fixture = next(
                (row for row in doc["fixtures"] if row["match_id"] == position["match_id"]),
                None,
            )
            if not fixture or timestamp(fixture["kickoff_utc"]) != kickoff:
                continue
            total = fixture["total_decision"]
            if (total["call"] != position["outcome"]
                    or abs(total["call_probability"] - chance) > 1e-6):
                continue
            xg = fixture["calibrated_predicted_xg"]["total"]
            others = [
                row["calibrated_predicted_xg"]["total"]
                for row in doc["fixtures"] if row is not fixture
            ]
            if others and position["outcome"] == "over_2_5" and xg > max(others):
                reasons.append("We expected more goals here than in any other match that week.")
            elif others and position["outcome"] == "under_2_5" and xg < min(others):
                reasons.append("We expected fewer goals here than in any other match that week.")
            break
    if not reasons and chance > 0.5 and market == "over_under_2_5":
        goals = "three goals or more" if position["outcome"] == "over_2_5" else "two goals or fewer"
        reasons.append(f"We thought {goals} were more likely than not.")
    edge = chance - ask
    reduced = position.get("position_size_multiplier", 1) < 1
    if 0 < edge < 0.05:
        reasons.append(
            "The price only gave us a small advantage, so we kept the paper bet small."
            if reduced else "The price gave us a small advantage."
        )
    elif edge > 0:
        reasons.append("We thought the outcome was more likely than the price suggested.")
        if reduced:
            reasons.append("We kept the paper bet small.")
    else:
        reasons.append("The saved price didn't give us an advantage.")
    return " ".join(reasons)


def paper_book(artifacts, legacy):
    saved = {}
    for path in sorted((artifacts / "paper_performance").glob("*/ledger.json")):
        doc = read_json(path)
        for position in doc["books"]["official_paper"]:
            key = position["selection_id"]
            if key not in saved:
                saved[key] = dict(position)
            elif position["settled"] and not saved[key]["settled"]:
                original = saved[key]
                entry_fields = ("captured_best_ask", "captured_source", "official_stake_units")
                if all(original[field] == position[field] for field in entry_fields):
                    original.update({field: position[field] for field in (
                        "settled", "won", "score", "official_gross_pnl_units",
                    )})
    reference = {
        position["selection_id"]: position["paper_risk_units"]
        for position in legacy.get("positions", [])
    }
    fields = ("fixture", "kickoff_utc", "outcome", "captured_best_ask", "captured_source",
              "model_probability", "official_stake_units", "settled", "won",
              "official_gross_pnl_units", "score")
    decisions = sorted(
        (read_json(path) for path in (artifacts / "matchweek_research").glob("*/decisions.json")),
        key=lambda doc: timestamp(doc["generated_at_utc"]),
        reverse=True,
    )
    return sorted(
        [
            {
                **{key: row.get(key) for key in fields},
                "risk_reference": reference.get(key),
                "entry_reason": paper_entry_reason(row, decisions),
            }
            for key, row in saved.items()
        ],
        key=lambda row: row["kickoff_utc"],
        reverse=True,
    )


def accuracy(hits, settled):
    if not 0 <= hits <= settled:
        raise ValueError("invalid matchweek accuracy counts")
    return {
        "hits": hits,
        "misses": settled - hits,
        "settled": settled,
        "hit_rate": round(hits / settled, 6) if settled else None,
    }


def pnl_history(positions, pnl_key):
    """Group settled P&L by fixture day, without mixing paper and benchmark."""
    by_day = defaultdict(lambda: [Decimal(0), 0])
    pending = 0
    for row in positions:
        if not row["settled"]:
            pending += 1
            continue
        day = timestamp(row["kickoff_utc"]).astimezone(MATCH_DAY_ZONE).date().isoformat()
        by_day[day][0] += Decimal(str(row[pnl_key]))
        by_day[day][1] += 1

    running = Decimal(0)
    window = []
    points = []
    for day, (daily_pnl, count) in sorted(by_day.items()):
        running += daily_pnl
        window.append(running)
        if len(window) > PNL_AVERAGE_DAYS:
            window.pop(0)
        points.append({
            "date": day,
            "settled_positions": count,
            "day_pnl": float(daily_pnl),
            "running_pnl": float(running),
            "moving_average": float(round(sum(window) / PNL_AVERAGE_DAYS, 6))
            if len(window) == PNL_AVERAGE_DAYS else None,
        })
    return {
        "points": points,
        "settled_positions": sum(point["settled_positions"] for point in points),
        "pending_positions": pending,
        "current_pnl": float(running),
    }


def matchweek_record(weeks, official):
    history = []
    for _, row in sorted(weeks.items(), reverse=True):
        basis = row.get("basis")
        if basis is None:
            if row["markets"]["one_x_two"]["label"] == "1X2 promoted calls":
                basis = "selective_calls"
            elif row.get("counts_toward_promotion_gate"):
                basis = "official_archive"
            else:
                basis = "full_slate"
        history.append({
            "matchweek": row["matchweek"],
            "fixtures": row["fixtures"],
            "settled": row["settled"],
            "markets": {
                key: {
                    "label": row["markets"][key]["label"],
                    **accuracy(row["markets"][key]["hits"], row["markets"][key]["settled"]),
                }
                for key in LEDGER_MARKETS
            },
            "basis": basis,
            "model_directions": row.get("model_directions"),
        })
    selective = [week for week in history if week["basis"] == "selective_calls"]
    return history, {
        "from_matchweek": min((week["matchweek"] for week in selective), default=None),
        "markets": {
            key: accuracy(
                sum(week["markets"][key]["hits"] for week in selective),
                sum(week["markets"][key]["settled"] for week in selective),
            )
            for key in LEDGER_MARKETS
        },
        "official_archive_1x2": accuracy(official["hits"], official["matches_logged"]),
    }


def build_dashboard(root, legacy):
    artifacts = root / "artifacts"
    slates = fixture_slates(artifacts)
    # Keep all earlier published hit-rate records, including their original denominators.
    weeks = {row["matchweek"]: row for row in legacy["ledger"]["matchweeks"]}
    for slate in slates:
        settled = [row for row in slate["fixtures"] if row["score"] is not None]
        sides = [row for row in settled if row["side_call"] != "pass"]
        totals = [row for row in settled if row["total_call"] != "pass"]
        week = weeks.setdefault(slate["round"], {
            "matchweek": slate["round"],
            "settled": slate["settled"],
            "fixtures": len(slate["fixtures"]),
            "basis": "selective_calls",
            "markets": {
                "one_x_two": {"label": "1X2 calls", "settled": len(sides),
                              "hits": sum(row["side_call"] == row["actual_side"] for row in sides)},
                "over_under_2_5": {"label": "O/U 2.5 calls", "settled": len(totals),
                                   "hits": sum((row["total_call"] == "over_2_5") == row["actual_over"]
                                               for row in totals)},
            },
        })
        weeks[slate["round"]] = {
            **week,
            "model_directions": {
                "side": slate["leader_hits"], "total": slate["total_direction_hits"],
            } if slate["settled"] else None,
        }
    matchweeks, record = matchweek_record(weeks, legacy["ledger"])
    captures = [
        read_json(path) for path in (artifacts / "ucl_research").glob("*/scoreboard.json")
    ]
    reviews = [
        read_json(path) for path in (root / "reports").glob("ucl-matchday-*-review.json")
    ]
    review = max(reviews, key=lambda row: (int(row["matchday"]), row["as_of"]))
    scored = max(
        (row for row in reviews if row.get("forecast_settlement")),
        key=lambda row: int(row["matchday"]),
        default=review,
    )
    captures.append({
        "matchday": review["matchday"],
        "captured_at_utc": review["generated_at_utc"],
        "source_url": "https://www.fotmob.com/leagues/42/matches/champions-league",
        "fixtures": [
            {
                **{key: row[key] for key in ("home_team", "away_team", "kickoff_utc")},
                "score": f"{row['score']['home']}–{row['score']['away']}"
                if row["status"] == "completed" else None,
                "status": "final" if row["status"] == "completed" else "scheduled",
            }
            for row in review["matches"]
        ],
    })
    scoreboard = max(captures, key=lambda row: (
        int(row["matchday"]), sum(item["status"] == "final" for item in row["fixtures"]),
        timestamp(row["captured_at_utc"]),
    ))
    rollup = max((artifacts / "paper_performance").glob("*/bankroll.json"), default=None)
    simulation = read_json(rollup)["simulation"] if rollup else None
    positions = paper_book(artifacts, legacy["paper_portfolio"])
    return {
        "premier_league": slates[:2],
        "matchweeks": matchweeks,
        "forecast_record": record,
        "paper": {
            "positions": positions,
            "standardized_bankroll": simulation["ending_bankroll"] if simulation else None,
            "pnl": {
                "moving_average_days": PNL_AVERAGE_DAYS,
                "official": pnl_history(positions, "official_gross_pnl_units"),
                "simulation": pnl_history(
                    simulation["positions"] + simulation.get("pending", []),
                    "gross_pnl_units",
                ) if simulation else None,
            },
        },
        "ucl": {
            **scoreboard,
            "last_forecast_review": {
                "matchday": scored["matchday"],
                "settlement": scored.get("forecast_settlement"),
            },
        },
    }
