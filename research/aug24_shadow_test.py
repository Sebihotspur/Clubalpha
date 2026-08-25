#!/usr/bin/env python3
"""Build an in-memory 2026-08-24 Premier League shadow snapshot."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clubalpha.club_form import build_club_forms, score_match_observations  # noqa: E402
from clubalpha.fixture_state import build_fixture_states, lineup_quality  # noqa: E402
from clubalpha.fotmob import (  # noqa: E402
    FotMobClient,
    clip_fixture_to_as_of,
    flatten_match_player_stats,
    flatten_match_team_stats,
    league_matches,
    league_table_teams,
    normalize_fixture,
    team_squad,
)
from clubalpha.historical_fixtures import (  # noqa: E402
    build_historical_fixture_intelligence,
    dedupe_team_match_rows,
)
from clubalpha.prediction_lab import (  # noqa: E402
    build_prediction_slate,
    fit_component_scale_artifact,
    fit_goal_model_artifact,
)
from clubalpha.squad_selection import build_squad_selection_priors  # noqa: E402


AS_OF = date(2026, 8, 24)
AS_OF_TEXT = AS_OF.isoformat()
SCALE_AS_OF = date(2026, 8, 11)
SCALE_AS_OF_TEXT = SCALE_AS_OF.isoformat()


def _squad_group(position):
    primary = str(position or "").split(",", 1)[0].strip().upper()
    if primary == "GK":
        return "keepers"
    if primary in {"CB", "LB", "LWB", "RB", "RWB"}:
        return "defenders"
    if primary in {"DM", "CDM", "CM", "AM", "CAM", "LM", "RM"}:
        return "midfielders"
    if primary in {"LW", "RW", "ST", "CF"}:
        return "attackers"
    return None


def reconstruct_squads_to_as_of(squads, teams, transfer_events, as_of):
    """Reverse later transfers from a newer roster snapshot.

    The foundation roster was retrieved after this calibration cutoff.  A
    historical scale artifact must not inherit those later memberships or the
    later injury snapshot, so transfers with a later effective date are
    unwound in reverse order and all availability fields are cleared.
    """

    team_names = {int(row["team_id"]): row["name"] for row in teams}
    target_ids = {
        int(row["team_id"])
        for row in teams
        if row.get("premier_league_2026_27")
    }
    roster = {
        (int(row["team_id"]), int(row["player_id"])): {**row, "injury": None}
        for row in squads
    }
    later = [
        row
        for row in transfer_events
        if int(row.get("team_id") or -1) in target_ids
        and str(row.get("effective_date") or "") > as_of.isoformat()
    ]
    later.sort(
        key=lambda row: (
            str(row.get("effective_date") or ""),
            str(row.get("reported_at_utc") or ""),
        ),
        reverse=True,
    )
    removed_later_arrivals = 0
    restored_later_departures = 0
    for event in later:
        team_id = int(event["team_id"])
        player_id = int(event["player_id"])
        key = (team_id, player_id)
        if event.get("direction") == "in":
            if roster.pop(key, None) is not None:
                removed_later_arrivals += 1
        elif event.get("direction") == "out":
            if key not in roster:
                roster[key] = {
                    "team_id": team_id,
                    "team": team_names.get(team_id) or event.get("team"),
                    "player_id": player_id,
                    "player": event.get("player"),
                    "squad_group": _squad_group(event.get("position")),
                    "position": event.get("position"),
                    "shirt_number": None,
                    "country_code": None,
                    "age": None,
                    "date_of_birth": None,
                    "height_cm": None,
                    "injury": None,
                }
                restored_later_departures += 1
    reconstructed = sorted(
        roster.values(),
        key=lambda row: (
            int(row["team_id"]),
            str(row.get("player") or ""),
            int(row["player_id"]),
        ),
    )
    return reconstructed, {
        "source_roster_manifest_as_of": "2026-08-18",
        "reconstructed_to_as_of": as_of.isoformat(),
        "later_transfer_events_reversed": len(later),
        "later_arrivals_removed": removed_later_arrivals,
        "later_departures_restored": restored_later_departures,
        "later_injury_snapshot_used": False,
        "method": "reverse_effective_dated_transfer_events",
    }


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def replace_by_key(old_rows, new_rows, key):
    new_keys = {key(row) for row in new_rows}
    return [row for row in old_rows if key(row) not in new_keys] + list(new_rows)


def directional_row(state):
    fixture = state["fixture"]
    component_edges = {}
    for component in (
        "club_form",
        "player_quality_lineup",
        "historical_residual",
    ):
        component_edges[component] = round(
            float(state["home"]["components"][component]["effective_signal_z"])
            - float(state["away"]["components"][component]["effective_signal_z"]),
            6,
        )
    votes = {
        key: 1 if value > 0 else -1 if value < 0 else 0
        for key, value in component_edges.items()
    }
    vote_total = sum(votes.values())
    lean = (
        fixture["home_team"]
        if vote_total > 0
        else fixture["away_team"]
        if vote_total < 0
        else None
    )
    winning_sign = 1 if vote_total > 0 else -1 if vote_total < 0 else 0
    support = sum(value == winning_sign for value in votes.values()) if winning_sign else 0
    return {
        "match_id": fixture["match_id"],
        "kickoff_utc": fixture["kickoff_utc"],
        "fixture": f"{fixture['home_team']} vs {fixture['away_team']}",
        "home_team": fixture["home_team"],
        "away_team": fixture["away_team"],
        "component_edges": component_edges,
        "component_votes": {
            key: (
                fixture["home_team"]
                if value > 0
                else fixture["away_team"]
                if value < 0
                else None
            )
            for key, value in votes.items()
        },
        "lean": lean,
        "support": support,
        "competition_baseline_xg": state["goal_model_handoff"][
            "competition_baseline"
        ],
        "lineup_priors_complete": state["decision_boundaries"][
            "lineup_priors_complete"
        ],
    }


def main():
    foundation_dir = ROOT / "data/processed/foundation_dynamics"
    domestic_dir = ROOT / "data/processed/domestic_history_dynamics"
    deep_dir = ROOT / "data/processed/deep_history"

    foundation_config = load_json(ROOT / "config/foundation.json")
    form_config = load_json(ROOT / "config/club-form-v1.json")
    selection_config = load_json(ROOT / "config/squad-selection-prior-v1.json")
    historical_config = load_json(ROOT / "config/historical-fixtures-v2.json")
    fixture_config = load_json(ROOT / "config/fixture-state-v1.json")
    prediction_config = load_json(ROOT / "config/prediction-lab-v0.json")
    player_config = load_json(ROOT / "config/player-quality-clubalpha-v2.json")

    premier_league = next(
        row
        for row in foundation_config["competitions"]
        if row["key"] == "premier_league_current"
    )
    client = FotMobClient(
        Path("/private/tmp/clubalpha-fotmob-aug24"),
        refresh=False,
        request_interval=0.15,
    )
    league_payload = client.league(
        int(premier_league["fotmob_id"]), premier_league["season"]
    )
    selected_season = (league_payload.get("details") or {}).get("selectedSeason")
    if selected_season != premier_league["season"]:
        raise RuntimeError(
            f"FotMob returned {selected_season!r}; expected {premier_league['season']!r}"
        )

    live_pl_fixtures = []
    for source in league_matches(league_payload):
        fixture = clip_fixture_to_as_of(
            normalize_fixture(source, source_scope="premier_league_current"),
            AS_OF_TEXT,
        )
        fixture["competition_id"] = int(premier_league["fotmob_id"])
        fixture["competition"] = premier_league["name"]
        live_pl_fixtures.append(fixture)

    completed = [
        row
        for row in live_pl_fixtures
        if row["finished"] and str(row.get("kickoff_utc") or "")[:10] <= AS_OF_TEXT
    ]
    current_player_rows = []
    current_team_rows = []
    observed = []
    for fixture in completed:
        payload = client.match(int(fixture["match_id"]))
        player_rows = flatten_match_player_stats(payload)
        team_rows = flatten_match_team_stats(payload, fixture)
        current_player_rows.extend(player_rows)
        current_team_rows.extend(team_rows)
        home = next(row for row in team_rows if row["venue"] == "home")
        observed.append(
            {
                "match_id": fixture["match_id"],
                "fixture": f"{fixture['home_team']} vs {fixture['away_team']}",
                "kickoff_utc": fixture["kickoff_utc"],
                "score": fixture["score"],
                "home_xg": home.get("expected_goals_for"),
                "away_xg": home.get("expected_goals_against"),
            }
        )

    old_teams = load_json(foundation_dir / "teams.json")
    old_squads = load_jsonl(foundation_dir / "squads.jsonl")
    live_table = {int(row["id"]): row for row in league_table_teams(league_payload)}
    pl_ids = set(live_table)
    teams = []
    for team in old_teams:
        team_id = int(team["team_id"])
        if team_id in live_table:
            source = live_table[team_id]
            teams.append(
                {
                    **team,
                    "name": source.get("name") or team.get("name"),
                    "short_name": source.get("shortName") or team.get("short_name"),
                    "premier_league_2026_27": True,
                }
            )
        else:
            teams.append(team)

    live_squads = []
    for team_id in sorted(pl_ids):
        team = next(row for row in teams if int(row["team_id"]) == team_id)
        payload = client.team(team_id)
        details = payload.get("details") or {}
        if details.get("name"):
            team["name"] = details["name"]
        for member in team_squad(payload):
            live_squads.append(
                {
                    "team_id": team_id,
                    "team": team["name"],
                    "player_id": int(member["id"]),
                    "player": member.get("name"),
                    "squad_group": member.get("squadGroup"),
                    "position": member.get("positionIdsDesc"),
                    "shirt_number": member.get("shirtNumber"),
                    "country_code": member.get("ccode"),
                    "age": member.get("age"),
                    "date_of_birth": member.get("dateOfBirth"),
                    "height_cm": member.get("height"),
                    "injury": member.get("injury"),
                }
            )
    squads = [row for row in old_squads if int(row["team_id"]) not in pl_ids]
    squads.extend(live_squads)

    old_selections = load_jsonl(
        ROOT / "data/processed/squad_selection_prior/squad_selection_prior.jsonl"
    )
    grade_path = Path(
        "/Users/sebasospina/Clubalpha/data/processed/"
        "player_quality_v2/player_grades.jsonl"
    )
    if grade_path.exists():
        grades = load_jsonl(grade_path)
        grade_source = str(grade_path)
    else:
        grades_by_player = {}
        for selection in old_selections:
            for player in selection.get("players") or []:
                grades_by_player[int(player["player_id"])] = {
                    "player_id": int(player["player_id"]),
                    "alpha_ability_z": player.get("alpha_ability_z"),
                    "minutes": (player.get("evidence") or {}).get(
                        "previous_season_minutes", 0.0
                    ),
                }
        grades = list(grades_by_player.values())
        grade_source = "reconstructed_from_2026-08-18_selection_prior"

    old_form_observations = load_jsonl(
        ROOT / "data/processed/club_form/team_match_observations.jsonl"
    )
    old_current_players = load_jsonl(
        foundation_dir / "current_match_player_stats.jsonl"
    )
    preseason_players = load_jsonl(
        foundation_dir / "preseason_match_player_stats.jsonl"
    )
    old_fixtures = load_jsonl(foundation_dir / "fixtures.jsonl")
    base_history_rows = dedupe_team_match_rows(
        load_jsonl(deep_dir / "match_team_stats.jsonl"),
        load_jsonl(foundation_dir / "historical_match_team_stats.jsonl"),
        load_jsonl(foundation_dir / "current_match_team_stats.jsonl"),
        load_jsonl(domestic_dir / "match_team_stats.jsonl"),
    )
    league_policy = player_config[
        historical_config["league_strength"]["policy_key"]
    ]

    # The component scales come from an earlier dated snapshot. Later statuses
    # are clipped before target selection so an August 18 result cannot make a
    # fixture disappear from an August 11 reconstruction. Later transfers and
    # availability are also removed from the calibration inputs.
    transfer_events = load_jsonl(foundation_dir / "transfer_events.jsonl")
    scale_squads, scale_roster_provenance = reconstruct_squads_to_as_of(
        old_squads,
        old_teams,
        transfer_events,
        SCALE_AS_OF,
    )
    scale_form_observations = [
        row
        for row in old_form_observations
        if str(row.get("kickoff_utc") or "")[:10] <= SCALE_AS_OF_TEXT
    ]
    scale_scored_form, _ = score_match_observations(
        scale_form_observations, SCALE_AS_OF, form_config
    )
    scale_forms, _ = build_club_forms(
        scale_scored_form,
        old_teams,
        scale_squads,
        grades,
        SCALE_AS_OF,
        form_config,
    )
    scale_selections = build_squad_selection_priors(
        old_teams,
        scale_squads,
        grades,
        old_current_players,
        preseason_players,
        SCALE_AS_OF,
        selection_config,
    )
    scale_fixtures = [
        clip_fixture_to_as_of(dict(row), SCALE_AS_OF_TEXT) for row in old_fixtures
    ]
    scale_historical, scale_scored_history, _ = (
        build_historical_fixture_intelligence(
            scale_fixtures,
            base_history_rows,
            SCALE_AS_OF,
            historical_config,
            league_policy,
        )
    )
    scale_manifest = {
        "historical_fixtures_version": historical_config["version"],
        "as_of": SCALE_AS_OF_TEXT,
        "outputs": {
            "fixtures": len(scale_historical),
            "historical_team_match_rows": len(scale_scored_history),
        },
    }
    scale_states = build_fixture_states(
        scale_historical,
        scale_forms,
        scale_selections,
        scale_scored_history,
        fixture_config,
        historical_config,
        scale_manifest,
    )
    scale_artifact = fit_component_scale_artifact(
        scale_states, prediction_config
    )
    scale_artifact["input_provenance"] = {
        **scale_roster_provenance,
        "player_grade_source": grade_source,
        "player_grade_rows": len(grades),
        "post_cutoff_transfer_records_used_for_reconstruction": True,
        "post_cutoff_match_rows_used": False,
        "post_cutoff_outcomes_used": False,
    }
    scale_artifact["quality_flags"] = sorted(
        set(
            [
                *scale_artifact.get("quality_flags", []),
                "historical_roster_reconstructed_from_transfer_log",
            ]
        )
    )

    form_observations = replace_by_key(
        old_form_observations,
        current_team_rows,
        lambda row: (int(row["match_id"]), int(row["team_id"])),
    )
    scored_form, _ = score_match_observations(form_observations, AS_OF, form_config)
    forms, _ = build_club_forms(scored_form, teams, squads, grades, AS_OF, form_config)

    all_current_players = replace_by_key(
        old_current_players,
        current_player_rows,
        lambda row: (int(row["match_id"]), int(row["player_id"])),
    )
    selections = build_squad_selection_priors(
        teams,
        squads,
        grades,
        all_current_players,
        preseason_players,
        AS_OF,
        selection_config,
    )

    fixtures = [
        row
        for row in old_fixtures
        if row.get("source_scope") != "premier_league_current"
    ] + live_pl_fixtures
    history_rows = dedupe_team_match_rows(
        base_history_rows,
        current_team_rows,
    )
    historical, scored_history, _ = build_historical_fixture_intelligence(
        fixtures,
        history_rows,
        AS_OF,
        historical_config,
        league_policy,
    )
    historical_manifest = {
        "historical_fixtures_version": historical_config["version"],
        "as_of": AS_OF_TEXT,
        "outputs": {
            "fixtures": len(historical),
            "historical_team_match_rows": len(scored_history),
        },
    }
    states = build_fixture_states(
        historical,
        forms,
        selections,
        scored_history,
        fixture_config,
        historical_config,
        historical_manifest,
        scale_artifact,
    )

    old_states = load_jsonl(ROOT / "data/processed/fixture_state/fixture_states.jsonl")
    goal_model_artifact = fit_goal_model_artifact(
        old_states,
        observed,
        scale_artifact,
        prediction_config,
        trained_through=AS_OF_TEXT,
    )
    old_by_match = {
        int(row["fixture"]["match_id"]): directional_row(row)
        for row in old_states
        if row["fixture"].get("source_scope") == "premier_league_current"
    }
    new_pl = [
        directional_row(row)
        for row in states
        if row["fixture"].get("source_scope") == "premier_league_current"
    ]
    next_round = [row for row in new_pl if row["kickoff_utc"][:10] <= "2026-08-31"]
    next_round_ids = {int(row["match_id"]) for row in next_round}
    prediction_states = [
        row
        for row in states
        if int(row["fixture"]["match_id"]) in next_round_ids
    ]
    predictions = build_prediction_slate(
        prediction_states,
        scale_artifact,
        goal_model_artifact,
        prediction_config,
    )
    comparisons = []
    for row in next_round:
        old = old_by_match.get(int(row["match_id"]))
        comparisons.append(
            {
                **row,
                "old_lean": old.get("lean") if old else None,
                "old_support": old.get("support") if old else None,
                "lean_changed": bool(old and old.get("lean") != row.get("lean")),
                "component_edge_changes": {
                    key: round(
                        row["component_edges"][key] - old["component_edges"][key], 6
                    )
                    if old
                    else None
                    for key in row["component_edges"]
                },
            }
        )

    forms_by_team = {int(row["team_id"]): row for row in forms}
    selections_by_team = {int(row["team_id"]): row for row in selections}
    old_forms = {
        int(row["team_id"]): row
        for row in load_jsonl(ROOT / "data/processed/club_form/club_form.jsonl")
    }
    old_selections_by_team = {int(row["team_id"]): row for row in old_selections}
    team_scores = []
    for team_id in sorted(pl_ids):
        form = forms_by_team[team_id]
        selection = lineup_quality(selections_by_team.get(team_id), fixture_config)
        old_form = old_forms[team_id]
        old_selection = lineup_quality(old_selections_by_team.get(team_id), fixture_config)
        team_scores.append(
            {
                "team_id": team_id,
                "team": form["team"],
                "form_z": form["overall_form_z"],
                "form_change": round(
                    float(form["overall_form_z"]) - float(old_form["overall_form_z"]), 4
                ),
                "attack_z": form["attack_z"],
                "defense_z": form["defense_z"],
                "projected_xi_z": selection["projected_quality_z"],
                "projected_xi_change": round(
                    float(selection["projected_quality_z"])
                    - float(old_selection["projected_quality_z"]),
                    4,
                ),
                "lineup_confidence": selection["confidence"],
                "lineup_prior_ready": selection["lineup_prior_ready"],
                "current_competitive_matches": form["evidence"][
                    "current_competitive_matches"
                ],
            }
        )
    form_rank = {
        row["team"]: rank
        for rank, row in enumerate(
            sorted(team_scores, key=lambda item: -float(item["form_z"])), 1
        )
    }
    alpha_rank = {
        row["team"]: rank
        for rank, row in enumerate(
            sorted(team_scores, key=lambda item: -float(item["projected_xi_z"])), 1
        )
    }
    for row in team_scores:
        row["form_rank"] = form_rank[row["team"]]
        row["alpha_rank"] = alpha_rank[row["team"]]
        row["comparison_rank"] = (row["form_rank"] + row["alpha_rank"]) / 2
    team_scores.sort(key=lambda item: (item["comparison_rank"], item["form_rank"]))

    report = {
        "prediction_version": prediction_config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "as_of": AS_OF_TEXT,
        "source": "FotMob live web data plus frozen Clubalpha historical evidence",
        "counts": {
            "live_pl_fixtures": len(live_pl_fixtures),
            "completed_pl_matches": len(completed),
            "current_player_rows": len(current_player_rows),
            "current_team_rows": len(current_team_rows),
            "live_pl_squad_players": len(live_squads),
            "historical_rows": len(scored_history),
            "fixture_states": len(states),
            "next_round_pl_fixtures": len(next_round),
            "scale_training_fixture_states": len(scale_states),
            "scale_training_fixture_sides": scale_artifact[
                "training_fixture_sides"
            ],
            "goal_training_matches": goal_model_artifact["training_matches"],
            "shadow_predictions": len(predictions),
            "lineup_priors_complete": sum(
                row["lineup_priors_complete"] for row in next_round
            ),
        },
        "observed_opening_round": observed,
        "team_scores": team_scores,
        "next_round": comparisons,
        "component_scale_artifact": scale_artifact,
        "goal_model_artifact": goal_model_artifact,
        "predictions": predictions,
        "decision_boundaries": {
            "component_scale_artifact_present": True,
            "goal_calibration_present": True,
            "shadow_predictions_ready": True,
            "probabilities_validated": False,
            "market_ready": False,
            "capital_deployment_ready": False,
        },
    }
    output_dir = ROOT / "artifacts/prediction_lab/2026-08-24"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "component-scales.json").write_text(
        json.dumps(scale_artifact, ensure_ascii=False, indent=2) + "\n"
    )
    (output_dir / "goal-model.json").write_text(
        json.dumps(goal_model_artifact, ensure_ascii=False, indent=2) + "\n"
    )
    (output_dir / "predictions.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in predictions
        )
    )
    output = output_dir / "report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["counts"], indent=2))
    print(output)


if __name__ == "__main__":
    main()
