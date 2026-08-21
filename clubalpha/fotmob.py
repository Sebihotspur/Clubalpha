"""Small, cached FotMob client and normalization helpers.

FotMob's public web feeds are undocumented. Keep every endpoint in this module
so an upstream path or response change has one repair point.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


WEB_BASE = "https://www.fotmob.com"
DATA_BASE = "https://data.fotmob.com"


def normalize_name(value: Any) -> str:
    """Return a conservative comparison key for names."""

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _display_number(value: Any) -> float | None:
    """Read the leading number from a FotMob team-stat display value.

    Team cards sometimes expose values such as ``"460 (87%)"`` instead of a
    numeric JSON value. The player-stat feed keeps the numerator and
    denominator separately, but the team feed does not, so preserving the
    leading count is the least lossy normalization available.
    """

    numeric = _number(value)
    if numeric is not None:
        return numeric
    match = re.match(r"^\s*(-?\d+(?:[.,]\d+)?)", str(value or ""))
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _display_percentage(value: Any) -> float | None:
    match = re.search(r"\((-?\d+(?:\.\d+)?)%\)", str(value or ""))
    return float(match.group(1)) if match else None


class FotMobClient:
    """Read FotMob JSON with retries, rate limiting, and a filesystem cache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        refresh: bool = False,
        request_interval: float = 0.25,
        timeout: float = 30.0,
    ) -> None:
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.request_interval = max(0.0, request_interval)
        self.timeout = timeout
        self._last_request_at = 0.0
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "Accept": "application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Clubalpha/0.1 (+https://github.com/Sebihotspur/Clubalpha)",
        }

    def _cache_path(self, cache_key: str) -> Path:
        clean = re.sub(r"[^a-zA-Z0-9_.-]+", "_", cache_key).strip("_")
        if not clean:
            clean = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{clean}.json"

    def get_json(self, url: str, cache_key: str) -> Any:
        cache_path = self._cache_path(cache_key)
        if cache_path.exists() and not self.refresh:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        errors: list[str] = []
        for attempt in range(1, 4):
            wait = self.request_interval - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(url, headers=self._headers())
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    if response.headers.get("Content-Encoding", "").lower() == "gzip" or body.startswith(b"\x1f\x8b"):
                        body = gzip.decompress(body)
                    payload = json.loads(body)
                self._last_request_at = time.monotonic()
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                return payload
            except (OSError, ValueError, urllib.error.URLError) as exc:
                self._last_request_at = time.monotonic()
                errors.append(f"attempt {attempt}: {exc}")
                if attempt < 3:
                    time.sleep(float(2**attempt))
        raise RuntimeError(f"FotMob request failed for {url}: {'; '.join(errors)}")

    def league(self, league_id: int, season: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"id": league_id, "ccode3": "USA", "season": season})
        return self.get_json(
            f"{WEB_BASE}/api/data/leagues?{query}",
            f"league_{league_id}_{season.replace('/', '-')}",
        )

    def team(self, team_id: int) -> dict[str, Any]:
        query = urllib.parse.urlencode({"id": team_id, "ccode3": "USA"})
        return self.get_json(f"{WEB_BASE}/api/data/teams?{query}", f"team_{team_id}")

    def player(self, player_id: int) -> dict[str, Any]:
        query = urllib.parse.urlencode({"id": player_id})
        return self.get_json(f"{WEB_BASE}/api/data/playerData?{query}", f"player_{player_id}")

    def match(self, match_id: int) -> dict[str, Any]:
        query = urllib.parse.urlencode({"matchId": match_id, "ccode3": "USA"})
        return self.get_json(f"{WEB_BASE}/api/data/matchDetails?{query}", f"match_{match_id}")

    def matches_on(self, date_yyyymmdd: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"date": date_yyyymmdd, "ccode3": "USA"})
        return self.get_json(f"{WEB_BASE}/api/data/matches?{query}", f"matches_{date_yyyymmdd}")

    def search(self, term: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"term": term, "lang": "en"})
        payload = self.get_json(
            f"{WEB_BASE}/api/data/search/suggest?{query}",
            f"search_{normalize_name(term).replace(' ', '_')}",
        )
        suggestions: list[dict[str, Any]] = []
        for group in payload if isinstance(payload, list) else []:
            suggestions.extend(group.get("suggestions") or [])
        return suggestions

    def resolve_team(self, name: str, aliases: Iterable[str] = ()) -> dict[str, Any] | None:
        targets = {normalize_name(name), *(normalize_name(alias) for alias in aliases)}
        terms = [name, *aliases]
        candidates: dict[str, dict[str, Any]] = {}
        for term in terms:
            for row in self.search(term):
                if row.get("type") != "team":
                    continue
                candidates[str(row.get("id"))] = row
            exact = next(
                (row for row in candidates.values() if normalize_name(row.get("name")) in targets),
                None,
            )
            if exact:
                return exact

        def score(row: dict[str, Any]) -> tuple[int, int]:
            candidate = normalize_name(row.get("name"))
            exact = int(candidate in targets)
            partial = int(any(candidate in target or target in candidate for target in targets))
            return exact, partial

        ranked = sorted(candidates.values(), key=score, reverse=True)
        if not ranked or score(ranked[0]) == (0, 0):
            return None
        return ranked[0]

    def season_stats_manifest(self, league_payload: dict[str, Any], season: str) -> dict[str, Any]:
        links = (league_payload.get("stats") or {}).get("seasonStatLinks") or []
        link = next((row for row in links if row.get("Name") == season), None)
        if not link:
            raise ValueError(f"No FotMob season-stat link for {season}")
        relative = str(link["RelativePath"]).lstrip("/")
        return self.get_json(
            f"{DATA_BASE}/{relative}",
            f"stats_manifest_{link['TemplateId']}_{link['TournamentId']}",
        )

    def stat_leaderboard(self, stat_location: str, cache_key: str) -> dict[str, Any]:
        return self.get_json(stat_location, cache_key)


def league_matches(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return ((payload.get("fixtures") or {}).get("allMatches") or [])


def league_table_teams(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for block in payload.get("table") or []:
        rows = ((((block or {}).get("data") or {}).get("table") or {}).get("all") or [])
        if rows:
            return rows
    return []


def team_fixtures(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return ((((payload.get("fixtures") or {}).get("allFixtures") or {}).get("fixtures")) or [])


def team_squad(payload: dict[str, Any]) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for group in ((payload.get("squad") or {}).get("squad") or []):
        group_name = group.get("title")
        for member in group.get("members") or []:
            if group_name == "coach" or member.get("excludeFromRanking") is True:
                continue
            members.append({**member, "squadGroup": group_name})
    return members


def normalize_fixture(row: dict[str, Any], *, source_scope: str) -> dict[str, Any]:
    status = row.get("status") or {}
    home = row.get("home") or {}
    away = row.get("away") or {}
    tournament = row.get("tournament") or {}
    return {
        "match_id": int(row["id"]),
        "source": "fotmob",
        "source_scope": source_scope,
        "competition_id": tournament.get("leagueId") or row.get("leagueId"),
        "competition": tournament.get("name") or row.get("leagueName"),
        "round": row.get("roundName") or row.get("round"),
        "kickoff_utc": status.get("utcTime") or row.get("matchDate"),
        "home_team_id": int(home["id"]) if home.get("id") is not None else row.get("homeTeamId"),
        "home_team": home.get("name") or row.get("homeTeamName"),
        "away_team_id": int(away["id"]) if away.get("id") is not None else row.get("awayTeamId"),
        "away_team": away.get("name") or row.get("awayTeamName"),
        "score": status.get("scoreStr"),
        "started": bool(status.get("started")),
        "finished": bool(status.get("finished")),
        "cancelled": bool(status.get("cancelled")),
    }


def clip_fixture_to_as_of(row: dict[str, Any], as_of: str) -> dict[str, Any]:
    """Keep known future schedules without leaking later scores or status."""

    kickoff = str(row.get("kickoff_utc") or "")[:10]
    if not kickoff or kickoff <= as_of:
        return row
    return {
        **row,
        "score": None,
        "started": False,
        "finished": False,
        "cancelled": False,
    }


MATCH_TEAM_STAT_KEYS = {
    "expected_goals": "expected_goals",
    "shots_on_target": "ShotsOnTarget",
    "big_chances": "big_chance",
    "total_shots": "total_shots",
    "touches_opp_box": "touches_opp_box",
    "possession_pct": "BallPossesion",
    "passes": "passes",
    "accurate_passes": "accurate_passes",
    "own_half_passes": "own_half_passes",
    "opposition_half_passes": "opposition_half_passes",
    "long_balls_completed": "long_balls_accurate",
    "crosses_completed": "accurate_crosses",
    "expected_goals_open_play": "expected_goals_open_play",
    "expected_goals_set_play": "expected_goals_set_play",
    "tackles": "matchstats.headers.tackles",
    "interceptions": "interceptions",
}

MATCH_TEAM_PERCENTAGE_KEYS = {
    "pass_accuracy_pct": "accurate_passes",
    "long_ball_accuracy_pct": "long_balls_accurate",
    "cross_accuracy_pct": "accurate_crosses",
}


def _match_score(value: Any) -> tuple[float | None, float | None]:
    match = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)", str(value or ""))
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def _match_team_stat_pairs(
    payload: dict[str, Any],
) -> dict[str, tuple[float | None, float | None]]:
    output: dict[str, tuple[float | None, float | None]] = {}
    periods = ((((payload.get("content") or {}).get("stats") or {}).get("Periods")) or {})
    groups = (((periods.get("All") or {}).get("stats")) or [])
    for group in groups:
        for item in group.get("stats") or []:
            key = item.get("key")
            values = item.get("stats")
            if not key or not isinstance(values, list) or len(values) < 2:
                continue
            pair = (_display_number(values[0]), _display_number(values[1]))
            if pair == (None, None):
                continue
            current = output.get(str(key))
            if current is None or sum(value is not None for value in pair) > sum(
                value is not None for value in current
            ):
                output[str(key)] = pair
    return output


def _match_team_stat_percentage_pairs(
    payload: dict[str, Any],
) -> dict[str, tuple[float | None, float | None]]:
    output: dict[str, tuple[float | None, float | None]] = {}
    periods = ((((payload.get("content") or {}).get("stats") or {}).get("Periods")) or {})
    groups = (((periods.get("All") or {}).get("stats")) or [])
    for group in groups:
        for item in group.get("stats") or []:
            key = item.get("key")
            values = item.get("stats")
            if not key or not isinstance(values, list) or len(values) < 2:
                continue
            pair = (_display_percentage(values[0]), _display_percentage(values[1]))
            if pair == (None, None):
                continue
            output[str(key)] = pair
    return output


def _estimated_attempts(completed: float | None, accuracy_pct: float | None) -> float | None:
    """Approximate attempts when FotMob publishes only completions and a rounded rate."""

    if completed is None or accuracy_pct is None or accuracy_pct <= 0:
        return None
    return completed * 100.0 / accuracy_pct


def flatten_match_team_stats(
    match_payload: dict[str, Any], fixture: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return one normalized team-stat row for each side of a fixture.

    FotMob title rows can repeat a metric key with two null values, so only
    numeric pairs replace an existing pair. A score-only card remains useful,
    but all unavailable performance metrics stay explicitly missing.
    """

    general = match_payload.get("general") or {}
    header_teams = ((match_payload.get("header") or {}).get("teams")) or []
    stat_pairs = _match_team_stat_pairs(match_payload)
    percentage_pairs = _match_team_stat_percentage_pairs(match_payload)
    score_pair = _match_score(fixture.get("score"))
    if len(header_teams) >= 2:
        header_score = (
            _number(header_teams[0].get("score")),
            _number(header_teams[1].get("score")),
        )
        if header_score != (None, None):
            score_pair = header_score

    general_home = general.get("homeTeam") or {}
    general_away = general.get("awayTeam") or {}
    sides = [
        {
            "team_id": fixture.get("home_team_id") or general_home.get("id"),
            "team": fixture.get("home_team") or general_home.get("name"),
            "opponent_id": fixture.get("away_team_id") or general_away.get("id"),
            "opponent": fixture.get("away_team") or general_away.get("name"),
            "venue": "home",
            "for_index": 0,
            "against_index": 1,
        },
        {
            "team_id": fixture.get("away_team_id") or general_away.get("id"),
            "team": fixture.get("away_team") or general_away.get("name"),
            "opponent_id": fixture.get("home_team_id") or general_home.get("id"),
            "opponent": fixture.get("home_team") or general_home.get("name"),
            "venue": "away",
            "for_index": 1,
            "against_index": 0,
        },
    ]
    rows: list[dict[str, Any]] = []
    for side in sides:
        if side["team_id"] is None or side["opponent_id"] is None:
            continue
        row: dict[str, Any] = {
            "match_id": int(fixture["match_id"]),
            "source": "fotmob",
            "source_scope": fixture.get("source_scope"),
            "competition_id": fixture.get("competition_id") or general.get("leagueId"),
            "competition": fixture.get("competition") or general.get("leagueName"),
            "kickoff_utc": fixture.get("kickoff_utc")
            or general.get("matchTimeUTCDate")
            or general.get("matchTimeUTC"),
            "team_id": int(side["team_id"]),
            "team": side["team"],
            "opponent_id": int(side["opponent_id"]),
            "opponent": side["opponent"],
            "venue": side["venue"],
            "cache_detail_available": bool(match_payload),
            "goals_for": score_pair[side["for_index"]],
            "goals_against": score_pair[side["against_index"]],
        }
        for canonical, source_key in MATCH_TEAM_STAT_KEYS.items():
            pair = stat_pairs.get(source_key, (None, None))
            row[f"{canonical}_for"] = pair[side["for_index"]]
            row[f"{canonical}_against"] = pair[side["against_index"]]
        for canonical, source_key in MATCH_TEAM_PERCENTAGE_KEYS.items():
            pair = percentage_pairs.get(source_key, (None, None))
            row[f"{canonical}_for"] = pair[side["for_index"]]
            row[f"{canonical}_against"] = pair[side["against_index"]]
        for prefix, completed_key, accuracy_key in (
            ("long_balls", "long_balls_completed", "long_ball_accuracy_pct"),
            ("crosses", "crosses_completed", "cross_accuracy_pct"),
        ):
            for direction in ("for", "against"):
                row[f"{prefix}_attempted_est_{direction}"] = _estimated_attempts(
                    row.get(f"{completed_key}_{direction}"),
                    row.get(f"{accuracy_key}_{direction}"),
                )
        row["detailed_metric_count"] = sum(
            row.get(f"{key}_for") is not None for key in MATCH_TEAM_STAT_KEYS
        )
        rows.append(row)
    return rows


def normalize_team_snapshot(
    payload: dict[str, Any], *, team_id: int, team: str | None, snapshot_date: str
) -> dict[str, Any]:
    """Normalize the current coach and squad identity from one team page."""

    coach: dict[str, Any] | None = None
    player_ids: list[int] = []
    for group in ((payload.get("squad") or {}).get("squad") or []):
        for member in group.get("members") or []:
            if member.get("id") is None:
                continue
            if group.get("title") == "coach":
                if coach is None:
                    coach = {
                        "coach_id": int(member["id"]),
                        "coach": member.get("name"),
                    }
            elif member.get("excludeFromRanking") is not True:
                player_ids.append(int(member["id"]))
    return {
        "source": "fotmob",
        "snapshot_date": snapshot_date,
        "team_id": int(team_id),
        "team": team,
        "current_coach": coach,
        "squad_player_ids": sorted(set(player_ids)),
    }


def normalize_manager_history(
    payload: dict[str, Any], *, team_id: int, team: str | None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in ((payload.get("history") or {}).get("coachHistory") or []):
        if item.get("id") is None:
            continue
        rows.append(
            {
                "source": "fotmob",
                "team_id": int(team_id),
                "team": team,
                "coach_id": int(item["id"]),
                "coach": item.get("name"),
                "season": item.get("season"),
                "competition_id": item.get("leagueId"),
                "competition": item.get("leagueName"),
                "wins": item.get("win"),
                "draws": item.get("draw"),
                "losses": item.get("loss"),
                "points_per_game": item.get("pointsPerGame"),
            }
        )
    return rows


def normalize_transfer_events(
    payload: dict[str, Any], *, team_id: int, team: str | None
) -> list[dict[str, Any]]:
    """Normalize confirmed incoming and outgoing transfers from a team page."""

    rows: list[dict[str, Any]] = []
    sections = ((payload.get("transfers") or {}).get("data") or {})
    for section, direction in (("Players in", "in"), ("Players out", "out")):
        for item in sections.get(section) or []:
            if item.get("playerId") is None or item.get("contractExtension") is True:
                continue
            effective = item.get("fromDate") or item.get("transferDate")
            counterparty_id = item.get("fromClubId") if direction == "in" else item.get("toClubId")
            counterparty = item.get("fromClubFullName") if direction == "in" else item.get("toClubFullName")
            fee = item.get("fee") or {}
            transfer_type = item.get("transferType") or {}
            rows.append(
                {
                    "source": "fotmob",
                    "team_id": int(team_id),
                    "team": team,
                    "direction": direction,
                    "player_id": int(item["playerId"]),
                    "player": item.get("name"),
                    "position": (item.get("position") or {}).get("label"),
                    "effective_date": str(effective)[:10] if effective else None,
                    "reported_at_utc": item.get("transferDate"),
                    "counterparty_id": int(counterparty_id) if counterparty_id is not None else None,
                    "counterparty": counterparty,
                    "transfer_type": transfer_type.get("text") or transfer_type.get("localizationKey"),
                    "on_loan": bool(item.get("onLoan")),
                    "fee_eur": fee.get("value"),
                    "market_value_eur": item.get("marketValue"),
                }
            )
    return rows


def flatten_match_player_stats(match_payload: dict[str, Any]) -> list[dict[str, Any]]:
    general = match_payload.get("general") or {}
    output: list[dict[str, Any]] = []
    content = match_payload.get("content") or {}
    players = content.get("playerStats") or {}
    shots = (content.get("shotmap") or {}).get("shots")
    shotmap_goals: dict[int, int] = {}
    shotmap_non_penalty_goals: dict[int, int] = {}
    if isinstance(shots, list):
        for shot in shots:
            if (
                shot.get("eventType") != "Goal"
                or shot.get("isOwnGoal") is True
                or shot.get("playerId") is None
                or shot.get("period") == "PenaltyShootout"
            ):
                continue
            player_id = int(shot["playerId"])
            shotmap_goals[player_id] = shotmap_goals.get(player_id, 0) + 1
            if shot.get("situation") != "Penalty":
                shotmap_non_penalty_goals[player_id] = (
                    shotmap_non_penalty_goals.get(player_id, 0) + 1
                )
    match_events = (((content.get("matchFacts") or {}).get("events") or {}).get("events"))
    event_goals: dict[int, int] = {}
    event_non_penalty_goals: dict[int, int] = {}
    if isinstance(match_events, list):
        for event in match_events:
            if (
                event.get("type") != "Goal"
                or event.get("ownGoal") is True
                or event.get("playerId") is None
                or event.get("isPenaltyShootoutEvent") is True
            ):
                continue
            player_id = int(event["playerId"])
            event_goals[player_id] = event_goals.get(player_id, 0) + 1
            is_penalty = (
                event.get("goalDescriptionKey") == "penalty"
                or event.get("suffixKey") == "penalties_short"
                or str(event.get("goalDescription") or "").lower() == "penalty"
            )
            if not is_penalty:
                event_non_penalty_goals[player_id] = (
                    event_non_penalty_goals.get(player_id, 0) + 1
                )
    for player in players.values():
        metrics: dict[str, Any] = {}
        for section in player.get("stats") or []:
            for title, item in (section.get("stats") or {}).items():
                key = item.get("key") or normalize_name(title).replace(" ", "_")
                stat = item.get("stat") or {}
                if "value" not in stat and "total" not in stat:
                    continue
                metrics[key] = {
                    "value": stat.get("value"),
                    "total": stat.get("total"),
                    "type": stat.get("type"),
                }
        if not metrics:
            continue
        player_id = int(player["id"])
        listed_goals = _number((metrics.get("goals") or {}).get("value")) or 0.0
        # The season leaderboard's penalty split can cover a different scope
        # after an in-league transfer or a promotion play-off. Derive NPG from
        # this match's shot map only when its goal count reconciles to the
        # player's official match card.
        if isinstance(shots, list) and abs(shotmap_goals.get(player_id, 0) - listed_goals) < 0.01:
            metrics["non_penalty_goals"] = {
                "value": shotmap_non_penalty_goals.get(player_id, 0),
                "total": None,
                "type": "integer",
                "derived_from": "shotmap",
            }
        elif (
            isinstance(match_events, list)
            and abs(event_goals.get(player_id, 0) - listed_goals) < 0.01
        ):
            metrics["non_penalty_goals"] = {
                "value": event_non_penalty_goals.get(player_id, 0),
                "total": None,
                "type": "integer",
                "derived_from": "match_events",
            }
        output.append(
            {
                "match_id": int(general.get("matchId")),
                "competition_id": general.get("leagueId"),
                "competition": general.get("leagueName"),
                "kickoff_utc": general.get("matchTimeUTCDate") or general.get("matchTimeUTC"),
                "player_id": player_id,
                "player": player.get("name"),
                "team_id": int(player["teamId"]),
                "team": player.get("teamName"),
                "is_goalkeeper": bool(player.get("isGoalkeeper")),
                "metrics": metrics,
            }
        )
    return output


def normalize_stat_rows(
    leaderboard: dict[str, Any],
    *,
    competition_id: int,
    competition: str,
    season: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for top_list in leaderboard.get("TopLists") or []:
        stat_name = top_list.get("StatName")
        for row in top_list.get("StatList") or []:
            participant_id = row.get("ParticiantId")  # FotMob's field is misspelled upstream.
            output.append(
                {
                    "competition_id": competition_id,
                    "competition": competition,
                    "season": season,
                    "metric": stat_name,
                    "metric_title": top_list.get("Title"),
                    "participant_id": int(participant_id) if participant_id is not None else None,
                    "participant": row.get("ParticipantName"),
                    "team_id": int(row["TeamId"]) if row.get("TeamId") is not None else None,
                    "team": row.get("TeamName"),
                    "value": row.get("StatValue"),
                    "sub_value": row.get("SubStatValue"),
                    "minutes": row.get("MinutesPlayed"),
                    "matches": row.get("MatchesPlayed"),
                    "rank": row.get("Rank"),
                    "positions": row.get("Positions") or [],
                }
            )
    return output
