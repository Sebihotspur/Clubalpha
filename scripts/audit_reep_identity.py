#!/usr/bin/env python3
"""Measure the frozen REEP FotMob bridge against Clubalpha's current universe."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.identity import (  # noqa: E402
    attach_v1_identities,
    build_entity_index,
    build_fotmob_index,
    build_redirect_index,
    build_typed_provider_bridge_indexes,
    coverage_summary,
    identity_scope_summary,
    redirect_target,
    resolve_fotmob_entities,
    v1_coverage_summary,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def csv_rows(path: Path) -> Iterable[dict[str, Any]]:
    if path.suffix == ".gz":
        with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in materialized:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(materialized)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, path: Path, *, refresh: bool) -> None:
    """Download one pinned source file atomically with bounded retries."""

    if path.exists() and not refresh:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    errors: list[str] = []
    for attempt in range(1, 4):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Clubalpha/0.1 (+https://github.com/Sebihotspur/Clubalpha)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as out:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
            temporary.replace(path)
            return
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            if attempt < 3:
                time.sleep(float(2**attempt))
    raise RuntimeError(f"REEP download failed for {url}: {'; '.join(errors)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config/reep-identity-pilot.json",
    )
    parser.add_argument(
        "--foundation-dir",
        type=Path,
        default=ROOT / "data/processed/foundation",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data/cache/reep-v0",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/processed/identity",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=ROOT / "reports/identity-coverage.json",
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    config = load_json(args.config)
    source = config["source"]
    required = {
        "squads": args.foundation_dir / "squads.jsonl",
        "teams": args.foundation_dir / "teams.json",
    }
    missing = [f"{label}: {path}" for label, path in required.items() if not path.exists()]
    if missing:
        raise SystemExit("Missing foundation inputs:\n" + "\n".join(missing))

    print("[1/6] Cache the pinned REEP v0 and v1 snapshots")
    source_paths: dict[str, Path] = {}
    for filename, url in source["files"].items():
        path = args.cache_dir / filename
        download(url, path, refresh=args.refresh)
        source_paths[filename] = path

    v1 = source["v1"]
    v1_cache = args.cache_dir.parent / "reep-v1" / v1["release_stamp"]
    v1_paths: dict[str, Path] = {}
    for filename, url in v1["files"].items():
        path = v1_cache / filename
        download(url, path, refresh=args.refresh)
        v1_paths[filename] = path

    print("[2/6] Build exact frozen FotMob bridge indexes")
    player_index = build_fotmob_index(csv_rows(source_paths["people.csv"]), entity_type="player")
    team_index = build_fotmob_index(csv_rows(source_paths["teams.csv"]), entity_type="team")

    squads = load_jsonl(required["squads"])
    teams = load_json(required["teams"])
    provider_fields = config["provider_fields"]
    common = {
        "provider_fields": provider_fields,
        "source_release": source["release"],
        "source_commit": source["commit"],
    }

    print("[3/6] Resolve players and teams without fuzzy fallback")
    players = resolve_fotmob_entities(
        squads,
        player_index,
        entity_type="player",
        target_id="player_id",
        target_name="player",
        **common,
    )
    team_rows = resolve_fotmob_entities(
        teams,
        team_index,
        entity_type="team",
        target_id="team_id",
        target_name="name",
        **common,
    )
    print("[4/6] Hand exact legacy rows into the current typed v1 register")
    wanted_by_type = {
        "player": {
            str(row["bridges"][v1["handoff_provider"]])
            for row in players
            if row["resolution"]["status"] == "exact"
            and row["bridges"].get(v1["handoff_provider"])
        },
        "team": {
            str(row["bridges"][v1["handoff_provider"]])
            for row in team_rows
            if row["resolution"]["status"] == "exact"
            and row["bridges"].get(v1["handoff_provider"])
        },
    }
    bridge_indexes = build_typed_provider_bridge_indexes(
        csv_rows(v1_paths["bridges.csv.gz"]),
        provider=v1["handoff_provider"],
        namespaces_by_type={
            entity_type: set(namespaces)
            for entity_type, namespaces in v1["namespaces"].items()
        },
        wanted_by_type=wanted_by_type,
    )
    redirects = build_redirect_index(csv_rows(v1_paths["redirects.csv.gz"]))
    requested_ids = {
        candidate["reep_id"]
        for index in bridge_indexes.values()
        for candidates in index.values()
        for candidate in candidates
    }
    resolved_ids = {
        resolved
        for requested in requested_ids
        for resolved, _ in [redirect_target(requested, redirects)]
        if resolved is not None
    }
    entities = build_entity_index(csv_rows(v1_paths["entities.csv.gz"]), resolved_ids)
    players = attach_v1_identities(
        players,
        bridge_indexes,
        entities,
        redirects,
        release_stamp=v1["release_stamp"],
        handoff_provider=v1["handoff_provider"],
    )
    team_rows = attach_v1_identities(
        team_rows,
        bridge_indexes,
        entities,
        redirects,
        release_stamp=v1["release_stamp"],
        handoff_provider=v1["handoff_provider"],
    )

    teams_by_id = {int(team["team_id"]): team for team in teams}
    player_pairs = list(zip(squads, players))
    team_pairs = list(zip(teams, team_rows))

    def player_scope(predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        return identity_scope_summary(
            [
                identity
                for squad, identity in player_pairs
                if predicate(teams_by_id.get(int(squad["team_id"]), {}))
            ]
        )

    def team_scope(predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        return identity_scope_summary(
            [identity for team, identity in team_pairs if predicate(team)]
        )

    scopes = {
        "players": {
            "premier_league": player_scope(
                lambda team: bool(team.get("premier_league_2026_27"))
            ),
            "ucl_direct": player_scope(
                lambda team: team.get("ucl_status") == "direct_league_phase"
            ),
            "ucl_playoff": player_scope(
                lambda team: team.get("ucl_status") == "playoff_contender"
            ),
            "ucl_any": player_scope(lambda team: bool(team.get("ucl_status"))),
        },
        "teams": {
            "premier_league": team_scope(
                lambda team: bool(team.get("premier_league_2026_27"))
            ),
            "ucl_direct": team_scope(
                lambda team: team.get("ucl_status") == "direct_league_phase"
            ),
            "ucl_playoff": team_scope(
                lambda team: team.get("ucl_status") == "playoff_contender"
            ),
            "ucl_any": team_scope(lambda team: bool(team.get("ucl_status"))),
        },
        "note": "Competition scopes overlap; a Premier League club may also appear in UCL.",
    }

    print("[5/6] Write ignored crosswalks")
    write_jsonl(args.output_dir / "player_crosswalk.jsonl", players)
    write_jsonl(args.output_dir / "team_crosswalk.jsonl", team_rows)

    print("[6/6] Write the tracked coverage decision")
    metadata = load_json(source_paths["meta.json"])
    audit = {
        "version": config["version"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "legacy_v0": {
                "repository": source["repository"],
                "commit": source["commit"],
                "release": source["release"],
                "status": source["status"],
                "license": source["license"],
                "metadata": metadata,
                "sha256": {
                    filename: sha256_file(path) for filename, path in source_paths.items()
                },
            },
            "current_v1": {
                "release_stamp": v1["release_stamp"],
                "schema_version": v1["schema_version"],
                "license": v1["license"],
                "handoff_provider": v1["handoff_provider"],
                "namespaces": v1["namespaces"],
                "sha256": {
                    filename: sha256_file(path) for filename, path in v1_paths.items()
                },
            },
        },
        "policy": config["policy"],
        "players": {
            "legacy_fotmob_bridge": coverage_summary(players, provider_fields),
            "current_v1_handoff": v1_coverage_summary(players),
        },
        "teams": {
            "legacy_fotmob_bridge": coverage_summary(team_rows, provider_fields),
            "current_v1_handoff": v1_coverage_summary(team_rows),
        },
        "coverage_by_scope": scopes,
        "decision": {
            "runtime_dependency": False,
            "status": "selective_validator",
            "reason": (
                "The exact v0 FotMob bridge plus typed Transfermarkt handoff can validate "
                "the covered subset against current v1, but incomplete direct coverage "
                "prevents a canonical or required dependency."
            ),
            "v1_handoff": (
                "Rows carrying a Transfermarkt bridge are candidates for a separately "
                "versioned REEP v1 resolution pass; v0 Reep IDs must never be reused."
            ),
        },
    }
    write_json(args.audit, audit)

    print(
        f"Players: {audit['players']['legacy_fotmob_bridge']['exact_matches']}/"
        f"{audit['players']['legacy_fotmob_bridge']['universe']} legacy exact; "
        f"{audit['players']['current_v1_handoff']['exact_v1_matches']} current v1"
    )
    print(
        f"Teams: {audit['teams']['legacy_fotmob_bridge']['exact_matches']}/"
        f"{audit['teams']['legacy_fotmob_bridge']['universe']} legacy exact; "
        f"{audit['teams']['current_v1_handoff']['exact_v1_matches']} current v1"
    )
    print(f"Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
