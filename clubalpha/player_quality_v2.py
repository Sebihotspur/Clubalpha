"""Clubalpha v2 Alpha Ability grades.

Five position populations, flat metric weights, league quality as an additive
z-offset taken from each match's opponent, per-position standardisation, and
minutes shrinkage.

This module is deliberately separate from ``player_quality``. That module holds
the locked WCALPHA v1 attacker and defender engine and must keep reproducing
its original scores for the parity tests; nothing here modifies it.

Like v1 this module is pure: it reads normalized rows supplied by the caller
and returns serializable dictionaries. It makes no network calls, and carries
no form, availability, or next-opponent information.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Iterable

from clubalpha.player_quality import (
    MATCH_SOURCE,
    SEASON_SOURCE,
    _feature,
    _metric_item,
    _number,
    _per90_feature,
    _sum_event,
    primary_position,
)


FULLBACK_POSITIONS = {"LB", "RB", "LWB", "RWB"}


def scoring_position(position: Any, squad_group: Any) -> str | None:
    """Map a current squad role to one of the five v2 peer populations.

    Three differences from v1: goalkeepers and midfielders now resolve instead
    of being dropped, and a fullback primary position wins over the listed
    squad group. FotMob files at least one wing-back under ``midfielders``, and
    grading a wing-back against central midfielders would measure them on
    metrics their role never asks for.

    CAM continues to resolve to FW, matching WCALPHA.
    """

    primary = primary_position(position)
    group = str(squad_group or "").lower()

    if group == "keepers" or primary == "GK":
        return "GK"
    if primary in FULLBACK_POSITIONS:
        return "FB"
    if group == "attackers" or primary == "CAM":
        return "FW"
    if group == "defenders":
        return "CB"
    if group == "midfielders":
        return "CM"
    return None


def resolved_formula(scoring_pos: str, config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return only the metric entries of a formula, dropping descriptive keys."""

    return {
        key: spec
        for key, spec in config["formulas"][scoring_pos].items()
        if isinstance(spec, dict) and "weight" in spec
    }


# ---------------------------------------------------------------------------
# League quality
# ---------------------------------------------------------------------------


def _offset_for_league_id(league_id: Any, config: dict[str, Any]) -> tuple[float, bool]:
    policy = config["league_quality"]
    key = policy["fotmob_league_id_to_key"].get(str(league_id))
    if key is None:
        return float(policy["default_offset"]), False
    return float(policy["offsets"][key]), True


def build_match_index(fixtures: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index fixtures so a player-match row can find its opponent."""

    index: dict[int, dict[str, Any]] = {}
    for fixture in fixtures:
        match_id = fixture.get("match_id")
        if match_id is None:
            continue
        index[int(match_id)] = {
            "home_team_id": fixture.get("home_team_id"),
            "away_team_id": fixture.get("away_team_id"),
            "competition_id": fixture.get("competition_id"),
        }
    return index


def match_league_offset(
    row: dict[str, Any],
    match_index: dict[int, dict[str, Any]],
    team_leagues: dict[int, Any],
    config: dict[str, Any],
) -> tuple[float, str]:
    """Offset for one player-match row, taken from the opponent's league.

    Resolution order: the opponent's domestic league, then the competition the
    match was played in, then the configured default. A continental or cup tie
    therefore inherits the strength of who was actually faced, so beating Real
    Madrid is not scored as equivalent to beating a fourth-tier cup side.
    """

    match_id = row.get("match_id")
    fixture = match_index.get(int(match_id)) if match_id is not None else None
    team_id = row.get("team_id")

    if fixture and team_id is not None:
        home, away = fixture.get("home_team_id"), fixture.get("away_team_id")
        opponent = None
        if home is not None and int(home) == int(team_id):
            opponent = away
        elif away is not None and int(away) == int(team_id):
            opponent = home
        if opponent is not None:
            opponent_league = team_leagues.get(int(opponent))
            if opponent_league is not None:
                offset, mapped = _offset_for_league_id(opponent_league, config)
                if mapped:
                    return offset, "opponent_league"

    offset, mapped = _offset_for_league_id(row.get("competition_id"), config)
    return offset, "competition" if mapped else "default"


def player_league_offset(
    rows: list[dict[str, Any]],
    match_index: dict[int, dict[str, Any]],
    team_leagues: dict[int, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Minutes-weighted league offset across every match a player appeared in.

    A player who spent part of the season elsewhere gets a blend of the leagues
    they actually played in, not the league of the club they now belong to.
    """

    weighted = 0.0
    minutes_total = 0.0
    sources: dict[str, float] = defaultdict(float)
    for row in rows:
        minutes = _number(((row.get("metrics") or {}).get("minutes_played") or {}).get("value")) or 0.0
        if minutes <= 0:
            continue
        offset, source = match_league_offset(row, match_index, team_leagues, config)
        weighted += offset * minutes
        minutes_total += minutes
        sources[source] += minutes

    if minutes_total <= 0:
        return {
            "offset": float(config["league_quality"]["default_offset"]),
            "minutes": 0.0,
            "resolution": {},
            "fully_resolved": False,
        }
    return {
        "offset": round(weighted / minutes_total, 6),
        "minutes": round(minutes_total, 3),
        "resolution": {
            key: round(100.0 * value / minutes_total, 1)
            for key, value in sorted(sources.items())
        },
        "fully_resolved": sources.get("default", 0.0) <= 0.0,
    }


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------


def _minutes(rows: list[dict[str, Any]]) -> float:
    return sum(
        _number(((row.get("metrics") or {}).get("minutes_played") or {}).get("value")) or 0.0
        for row in rows
    )


def _ratio_pct(
    rows: list[dict[str, Any]],
    keys: list[str],
    minimum_attempts: int,
) -> tuple[float | None, float, float]:
    """Attempt-weighted percentage, withheld below the minimum-attempts floor.

    A percentage on a tiny denominator is noise rather than skill: two of three
    crosses reads 67% and would otherwise outrank forty of eighty.
    """

    won = attempted = 0.0
    for row in rows:
        item = _metric_item(row.get("metrics") or {}, keys)
        if not item:
            continue
        value, total = _number(item.get("value")), _number(item.get("total"))
        if value is None or total is None:
            continue
        won += value
        attempted += total
    if attempted <= 0 or attempted < minimum_attempts:
        return None, won, attempted
    return 100.0 * won / attempted, won, attempted


def _competitions_supplying(rows: list[dict[str, Any]], key: str) -> set[tuple[Any, Any]]:
    return {
        (row.get("competition_id"), row.get("competition"))
        for row in rows
        if _number(((row.get("metrics") or {}).get(key) or {}).get("value")) is not None
    }


def _rate_over_supplying_competitions(
    rows: list[dict[str, Any]],
    key: str,
) -> tuple[float | None, float, float]:
    """Per-90 rate restricted to competitions that actually supply the field.

    A competition that never reports xG must not dilute an xG rate by
    contributing minutes with no possible numerator.
    """

    competitions = _competitions_supplying(rows, key)
    if not competitions:
        return None, 0.0, 0.0
    total = minutes = 0.0
    for row in rows:
        if (row.get("competition_id"), row.get("competition")) not in competitions:
            continue
        metrics = row.get("metrics") or {}
        total += _number((metrics.get(key) or {}).get("value")) or 0.0
        minutes += _number((metrics.get("minutes_played") or {}).get("value")) or 0.0
    if minutes <= 0:
        return None, total, minutes
    return total * 90.0 / minutes, total, minutes


def _non_penalty_goals(rows: list[dict[str, Any]]) -> tuple[float | None, list[str]]:
    """Non-penalty goals, only when every scoring match reconciled.

    Matches carrying a derived ``non_penalty_goals`` value were reconciled
    against the player's official goal count upstream. A match without one is
    acceptable only if the player did not score in it; otherwise the sample
    holds unclassified goals and the feature stays missing rather than guessing
    which of them were penalties.
    """

    flags: list[str] = []
    classified, unclassified = [], []
    for row in rows:
        item = (row.get("metrics") or {}).get("non_penalty_goals") or {}
        (classified if _number(item.get("value")) is not None else unclassified).append(row)

    if _sum_event(unclassified, "goals") > 0:
        flags.append("non_penalty_goals_unreconciled_match_shotmap")
        return None, flags
    if not classified:
        return (0.0, flags) if _sum_event(rows, "goals") <= 0 else (None, ["non_penalty_goals_unclassified"])
    return _sum_event(classified, "non_penalty_goals"), flags


def _peak_top_speed(rows: list[dict[str, Any]]) -> tuple[float | None, int]:
    speeds = [
        _number(((row.get("metrics") or {}).get("physical_metrics_topspeed") or {}).get("value"))
        for row in rows
    ]
    speeds = [value for value in speeds if value is not None]
    return (max(speeds), len(speeds)) if speeds else (None, 0)


def _leaderboard_rate(rows: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    weighted_events = minutes = 0.0
    competitions: set[str] = set()
    for row in (row for row in rows if row.get("metric") == metric):
        value, row_minutes = _number(row.get("value")), _number(row.get("minutes"))
        if value is None or row_minutes is None or row_minutes <= 0:
            continue
        weighted_events += value * row_minutes / 90.0
        minutes += row_minutes
        competitions.add(str(row.get("competition") or "Unknown"))
    if minutes <= 0:
        return None
    return _feature(
        weighted_events * 90.0 / minutes,
        unit="per90",
        source=SEASON_SOURCE,
        source_fields=[metric],
        numerator=weighted_events,
        denominator_minutes=minutes,
        note=f"Minutes-weighted across {', '.join(sorted(competitions))}",
    )


EVENT_NOTE = (
    "FotMob omits zero-valued event cards; absent player event keys in a "
    "complete detailed match are calculated as zero."
)


def build_features(
    rows: list[dict[str, Any]],
    season_rows: list[dict[str, Any]],
    scoring_pos: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Aggregate one player's match rows into the features their formula needs."""

    formula = resolved_formula(scoring_pos, config)
    minutes = _minutes(rows)
    features: dict[str, Any] = {}
    flags: list[str] = []

    for key, spec in formula.items():
        source = list(spec.get("source") or [])
        form = spec.get("form")

        if spec.get("unavailable") or not source:
            features[key] = None
            continue

        if form == "percentage":
            floor = int(spec.get("minimum_attempts", 0))
            pct, won, attempted = _ratio_pct(rows, source, floor)
            if pct is None and attempted > 0:
                flags.append(f"{key}_below_minimum_attempts")
            features[key] = _feature(
                pct,
                unit="percent",
                source=MATCH_SOURCE,
                source_fields=[f"{source[0]}.value", f"{source[0]}.total"],
                numerator=won,
                note=f"{int(attempted)} recorded attempts against a minimum of {floor}.",
            )

        elif form == "physical":
            value, samples = _peak_top_speed(rows)
            features[key] = _feature(
                value,
                unit="kmh",
                source=MATCH_SOURCE,
                source_fields=source,
                note=f"Peak of {samples} recorded match top speeds.",
            )

        elif key == "npg90":
            npg, npg_flags = _non_penalty_goals(rows)
            flags.extend(npg_flags)
            features[key] = (
                _per90_feature(
                    npg,
                    minutes,
                    source_fields=["shotmap.eventType/situation", "matchFacts.events fallback"],
                    note=(
                        "Derived from reconciled match shot maps with match goal events as a "
                        "fallback; penalties, own goals and shoot-out goals are excluded."
                    ),
                )
                if npg is not None
                else None
            )

        elif key == "xg90":
            rate, total, denom = _rate_over_supplying_competitions(rows, source[0])
            if rate is None and len(source) > 1:
                rate, total, denom = _rate_over_supplying_competitions(rows, source[1])
            features[key] = _feature(
                rate,
                unit="per90",
                source=MATCH_SOURCE,
                source_fields=source,
                numerator=total,
                denominator_minutes=denom,
                note="Restricted to competitions supplying the field so others cannot dilute the rate.",
            )

        elif key in {"axa90", "gxg90", "ga90"}:
            features[key] = _composite_rate(rows, key, source, minutes)

        elif key == "gprev90":
            total = _sum_event(rows, source[0])
            if not _competitions_supplying(rows, source[0]):
                fallback = spec.get("derived_fallback") or []
                if len(fallback) == 2:
                    total = _sum_event(rows, fallback[0]) - _sum_event(rows, fallback[1])
            features[key] = _per90_feature(
                total,
                minutes,
                source_fields=source,
                note=(
                    "Shot-quality adjusted. Save percentage is excluded because it measures the "
                    "same events without that adjustment."
                ),
            )

        elif spec.get("source_layer") == "season_leaderboard":
            features[key] = _leaderboard_rate(season_rows, source[0])

        else:
            features[key] = _per90_feature(
                _sum_event(rows, *source),
                minutes,
                source_fields=source,
                note=EVENT_NOTE,
            )

    return features, flags


def _composite_rate(
    rows: list[dict[str, Any]],
    key: str,
    source: list[str],
    minutes: float,
) -> dict[str, Any] | None:
    """Combine an actual-event rate with a matching expected-value rate.

    ``ga90`` sums two plain event counts over the same minutes. ``axa90`` and
    ``gxg90`` add an expected component whose denominator is restricted to the
    competitions that report it, so a league without xA contributes assists
    without dragging the expected half toward zero.
    """

    if key == "ga90":
        total = _sum_event(rows, source[0]) + _sum_event(rows, source[1])
        return _per90_feature(total, minutes, source_fields=source, note=EVENT_NOTE)

    base_key, expected_key = source[0], source[1]
    base_rate = (_sum_event(rows, base_key) * 90.0 / minutes) if minutes > 0 else None
    expected_rate, _, expected_minutes = _rate_over_supplying_competitions(rows, expected_key)
    if base_rate is None and expected_rate is None:
        return None
    return _feature(
        (base_rate or 0.0) + (expected_rate or 0.0),
        unit="per90",
        source=MATCH_SOURCE,
        source_fields=source,
        denominator_minutes=minutes,
        note=(
            f"{base_key} over {round(minutes, 1)} minutes; {expected_key} over "
            f"{round(expected_minutes, 1)} minutes from competitions supplying it."
        ),
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _qualifying(players: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """Players whose sample is large enough to define a reference distribution.

    Everyone still gets scored. This only decides who the yardstick is built
    from, so a ninety-minute cameo cannot widen the spread that every peer is
    then measured against.
    """

    floor = float(config["peer_method"]["peer_minimum_minutes"])
    return [row for row in players if float(row["sample"]["minutes"]) >= floor]


def _peer_distributions(
    population: list[dict[str, Any]],
    formula: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Mean and sample SD per metric, computed from unadjusted values.

    League quality is deliberately absent here. In v1 it multiplied the raw
    value before comparison, which ran backwards on inverted metrics and moved
    bounded percentages far harder than rates. In v2 it is a shift applied to
    the finished z-score, so the yardstick itself stays league-neutral.
    """

    distributions: dict[str, dict[str, float]] = {}
    minimum = int(config["peer_method"]["minimum_population"])
    for key, spec in formula.items():
        sign = -1.0 if spec["direction"] == "inverted" else 1.0
        values = [
            sign * raw
            for peer in population
            if (raw := _number(((peer.get("features") or {}).get(key) or {}).get("value"))) is not None
        ]
        if len(values) < minimum:
            continue
        distributions[key] = {
            "mean": statistics.mean(values),
            "sd": statistics.stdev(values) if len(values) > 1 else 1.0,
            "count": len(values),
        }
    return distributions


def score_player(
    player: dict[str, Any],
    distributions: dict[str, dict[str, float]],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    """Score one player against pre-computed positional distributions."""

    scoring_pos = player["scoring_position"]
    formula = resolved_formula(scoring_pos, config)
    clamp = float(config["peer_method"]["z_score_clamp"])
    offset = float(player["league_quality"]["offset"])

    weighted_sum = total_weight = 0.0
    confirmed = 0
    metric_scores: dict[str, Any] = {}

    for key, spec in formula.items():
        weight = float(spec["weight"])
        feature = (player.get("features") or {}).get(key)
        raw = _number((feature or {}).get("value"))
        distribution = distributions.get(key)

        if raw is None or distribution is None:
            metric_scores[key] = {
                "z": None,
                "confidence": "missing" if raw is None else "insufficient_pop",
                "weight": weight,
                "direction": spec["direction"],
            }
            continue

        sign = -1.0 if spec["direction"] == "inverted" else 1.0
        sd = distribution["sd"]
        base = 0.0 if sd < 0.001 else (sign * raw - distribution["mean"]) / sd
        z = max(-clamp, min(clamp, base + offset))

        metric_scores[key] = {
            "z": round(z, 3),
            "z_before_league": round(max(-clamp, min(clamp, base)), 3),
            "raw": raw,
            "peer_mean": round(distribution["mean"], 6),
            "peer_sample_sd": round(sd, 6),
            "peer_count": distribution["count"],
            "league_offset": offset,
            "weight": weight,
            "direction": spec["direction"],
            "form": spec.get("form"),
            "source": (feature or {}).get("source"),
        }
        weighted_sum += z * weight
        total_weight += weight
        confirmed += 1

    if total_weight <= 0:
        return None

    minutes = float(player["sample"]["minutes"])
    return {
        "formula_version": config["version"],
        "player_id": player["player_id"],
        "player": player["player"],
        "current_team_id": player["current_team_id"],
        "current_team": player["current_team"],
        "current_position": player["current_position"],
        "scoring_position": scoring_pos,
        "league_quality": player["league_quality"],
        "minutes": round(minutes, 3),
        "matches": player["sample"]["matches"],
        "composite_z": round(weighted_sum / total_weight, 4),
        "confirmed_metrics": confirmed,
        "total_metrics": len(formula),
        "coverage_pct": round(confirmed / len(formula) * 100.0, 1),
        "metrics": metric_scores,
        "quality_flags": player.get("quality_flags") or [],
    }


def score_population(
    player_features: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Grade every player, then place all five positions on one scale.

    Raw composites are not comparable across positions: attacking metrics have
    fat right tails while defensive metrics are bounded percentages, so forward
    grades span roughly twice the range of centre-back grades. Standardising
    each position to mean 0 and SD 1 makes a +1.0 forward and a +1.0 keeper the
    same statement, which is what the roll-up weights already assume.

    Shrinkage follows standardisation rather than preceding it, so that zero
    means "average for this position" and a thin sample is pulled toward its
    own positional average instead of toward an arbitrary point.
    """

    grades: list[dict[str, Any]] = []
    by_position: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in player_features:
        by_position[row["scoring_position"]].append(row)

    shrinkage_k = float(config["shrinkage"]["constant"])
    minutes_floor = float(config["peer_method"]["peer_minimum_minutes"])

    for scoring_pos, members in by_position.items():
        formula = resolved_formula(scoring_pos, config)
        reference = _qualifying(members, config) or members
        distributions = _peer_distributions(reference, formula, config)

        scored = [score_player(player, distributions, config) for player in members]
        scored = [row for row in scored if row is not None]
        if not scored:
            continue

        qualifying = [row["composite_z"] for row in scored if row["minutes"] >= minutes_floor]
        if len(qualifying) < 2:
            qualifying = [row["composite_z"] for row in scored]

        mean = statistics.mean(qualifying)
        sd = statistics.stdev(qualifying) if len(qualifying) > 1 else 1.0
        if sd < 0.001:
            sd = 1.0

        for row in scored:
            standardised = (row["composite_z"] - mean) / sd
            shrink = row["minutes"] / (row["minutes"] + shrinkage_k) if row["minutes"] > 0 else 0.0
            row["position_mean"] = round(mean, 6)
            row["position_sd"] = round(sd, 6)
            row["reference_players"] = len(qualifying)
            row["standardised_z"] = round(standardised, 3)
            row["shrinkage_weight"] = round(shrink, 3)
            row["alpha_ability_z"] = round(standardised * shrink, 3)
        grades.extend(scored)

    return grades


# ---------------------------------------------------------------------------
# Team roll-up
# ---------------------------------------------------------------------------


def team_ratings(
    grades: list[dict[str, Any]],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Weighted attack and defence ratings per club.

    Two ratings rather than one blend: goals scored and goals conceded are
    different questions answered by different players, and a single number
    cannot price a total. Position weights only — starter, rotation and squad
    role belong to Club Form and multiply in above this layer.
    """

    roll_up = config["roll_up"]
    buckets: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in grades:
        buckets[(row["current_team_id"], row["current_team"])].append(row)

    output: list[dict[str, Any]] = []
    for (team_id, team), members in buckets.items():
        record: dict[str, Any] = {
            "team_id": team_id,
            "team": team,
            "graded_players": len(members),
        }
        for side in ("attack", "defence"):
            weights = roll_up[side]
            weighted = total = 0.0
            for row in members:
                weight = float(weights.get(row["scoring_position"], 0.0))
                if weight <= 0:
                    continue
                weighted += row["alpha_ability_z"] * weight
                total += weight
            record[f"{side}_rating"] = round(weighted / total, 4) if total > 0 else None
            record[f"{side}_weight"] = round(total, 3)
        record["by_position"] = {
            pos: sum(1 for row in members if row["scoring_position"] == pos)
            for pos in sorted({row["scoring_position"] for row in members})
        }
        output.append(record)

    return sorted(output, key=lambda row: str(row["team"]))
