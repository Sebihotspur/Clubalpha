#!/usr/bin/env python3
"""Collect the previous-season matches the club-filtered layers never see.

Runs in two phases. Detection reads each current squad player's FotMob career
history and reconciles the appearances it reports against the match rows
already held, producing an exact per-player shortfall. Collection then fetches
only the fixtures needed to close those gaps and keeps only the rows belonging
to the players being backfilled.

Detection is cheap and cacheable, so ``--detect-only`` gives a defensible
picture of the problem's size before any collection requests are spent.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from clubalpha.fotmob import FotMobClient, flatten_match_player_stats  # noqa: E402
from clubalpha.player_quality_v2 import scoring_position  # noqa: E402
from clubalpha.transfer_backfill import (  # noqa: E402
    backfill_coverage,
    build_competition_aliases,
    expected_ledger,
    filter_backfill_rows,
    find_gaps,
    held_appearances,
    player_gap_summary,
    select_team_fixtures,
    targets_by_competition,
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--foundation-dir", type=Path, default=ROOT / "data/processed/foundation")
    parser.add_argument("--domestic-dir", type=Path, default=ROOT / "data/processed/domestic_history")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed/transfer_backfill")
    parser.add_argument("--audit", type=Path, default=ROOT / "reports/transfer-backfill-coverage.json")
    parser.add_argument("--season", default="2025/2026")
    parser.add_argument(
        "--quality-config",
        type=Path,
        default=ROOT / "config/player-quality-clubalpha-v2.json",
        help="Supplies the competition-id aliases used to compare ledger and held rows.",
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--detect-only", action="store_true", help="Reconcile gaps without collecting.")
    parser.add_argument("--request-interval", type=float, default=0.25)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit-players", type=int, default=None)
    parser.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="Stop after this many backfill match fetches; the audit records the cut-off.",
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 6:
        raise SystemExit("--workers must be between 1 and 6")

    squads_path = args.foundation_dir / "squads.jsonl"
    if not squads_path.exists():
        raise SystemExit("Missing foundation squads.jsonl; run pull_fotmob_foundation.py first.")

    squads = load_jsonl(squads_path)
    # FotMob reports a competition under one id in career history and another
    # in match rows. Without collapsing them, complete data reads as absent.
    aliases = build_competition_aliases(load_json(args.quality_config))
    held_rows = [
        *load_jsonl(args.foundation_dir / "historical_match_player_stats.jsonl"),
        *load_jsonl(args.domestic_dir / "match_player_stats.jsonl"),
    ]
    held_by_player: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in held_rows:
        if row.get("player_id") is not None:
            held_by_player[int(row["player_id"])].append(row)
    already_held_keys = {
        (row.get("match_id"), int(row["player_id"]))
        for row in held_rows
        if row.get("player_id") is not None
    }

    eligible = [
        squad
        for squad in squads
        if scoring_position(squad.get("position"), squad.get("squad_group"))
    ]
    if args.limit_players:
        eligible = eligible[: args.limit_players]

    cache_dir = ROOT / "data/cache/fotmob"
    client = FotMobClient(cache_dir, refresh=args.refresh, request_interval=args.request_interval)

    print(f"[1/4] Reconcile career history for {len(eligible)} squad players")
    worker_state = threading.local()

    def worker_client() -> FotMobClient:
        existing = getattr(worker_state, "client", None)
        if existing is None:
            existing = FotMobClient(
                cache_dir, refresh=args.refresh, request_interval=args.request_interval
            )
            worker_state.client = existing
        return existing

    def reconcile(squad: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        player_id = int(squad["player_id"])
        try:
            payload = worker_client().player(player_id)
        except RuntimeError as exc:
            return None, {"player_id": player_id, "player": squad.get("player"), "error": str(exc)}
        ledger = expected_ledger(payload, args.season)
        if not ledger:
            return None, None
        gaps = find_gaps(
            ledger, held_appearances(held_by_player.get(player_id, []), aliases), aliases
        )
        return (
            player_gap_summary(player_id, squad.get("player"), squad.get("team_id"), gaps),
            None,
        )

    summaries: list[dict[str, Any]] = []
    detection_errors: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for number, (summary, error) in enumerate(executor.map(reconcile, eligible), 1):
            if error:
                detection_errors.append(error)
            elif summary:
                summaries.append(summary)
            if number == 1 or number % 100 == 0 or number == len(eligible):
                print(f"  player {number:04d}/{len(eligible):04d}")

    with_gaps = [row for row in summaries if row["missing_appearances"] > 0]
    multi_club = [row for row in summaries if row["multi_club_season"]]
    print(
        f"      {len(multi_club)} multi-club seasons, {len(with_gaps)} players with a shortfall, "
        f"{sum(row['missing_appearances'] for row in with_gaps)} appearances missing"
    )

    batches = targets_by_competition(summaries)
    print(f"[2/4] {len(batches)} competition-seasons hold the missing fixtures")

    collected: list[dict[str, Any]] = []
    fixtures_selected: list[dict[str, Any]] = []
    competition_errors: list[dict[str, Any]] = []
    detail_errors: list[dict[str, Any]] = []
    truncated = False

    if not args.detect_only and batches:
        print("[3/4] Collect missing fixtures, keeping only backfilled players")
        for number, ((league_id, season), batch) in enumerate(sorted(batches.items()), 1):
            print(
                f"  competition {number:03d}/{len(batches):03d}: "
                f"{batch['league']} ({len(batch['team_ids'])} clubs, {len(batch['player_ids'])} players)"
            )
            try:
                payload = client.league(league_id, season)
            except (RuntimeError, ValueError) as exc:
                competition_errors.append(
                    {"league_id": league_id, "league": batch["league"], "season": season, "error": str(exc)}
                )
                continue

            fixtures = select_team_fixtures(payload, set(batch["team_ids"]))
            fixtures_selected.extend(fixtures)
            wanted = {int(value) for value in batch["player_ids"]}
            competition = {
                "league_id": league_id,
                "league": batch["league"],
                "season": season,
            }

            for fixture in fixtures:
                if args.max_matches is not None and len(collected) >= args.max_matches:
                    truncated = True
                    break
                try:
                    rows = flatten_match_player_stats(client.match(fixture["match_id"]))
                except RuntimeError as exc:
                    detail_errors.append({"match_id": fixture["match_id"], "error": str(exc)})
                    continue
                kept = filter_backfill_rows(rows, wanted, competition, already_held_keys)
                for row in kept:
                    already_held_keys.add((row.get("match_id"), int(row["player_id"])))
                collected.extend(kept)
            if truncated:
                break
    else:
        print("[3/4] Detection only; no collection requests spent")

    print("[4/4] Write datasets and coverage audit")
    counts = {
        "match_player_rows": write_jsonl(args.output_dir / "match_player_stats.jsonl", collected),
        "fixtures_selected": write_jsonl(args.output_dir / "fixtures.jsonl", fixtures_selected),
        "gap_summaries": write_jsonl(args.output_dir / "gap_summaries.jsonl", summaries),
    }

    coverage = backfill_coverage(summaries, collected)
    audit = {
        "version": "transfer_backfill_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": args.season,
        "source": "FotMob public web data",
        "source_status": "unofficial_undocumented",
        "sampling_policy": (
            "Every competition a current squad player appeared in last season, including domestic "
            "cups; collected rows are filtered to the backfilled players only."
        ),
        "detect_only": bool(args.detect_only),
        "truncated_by_max_matches": truncated,
        "counts": counts,
        "coverage": coverage,
        "competition_batches": [
            {
                "league_id": batch["league_id"],
                "league": batch["league"],
                "season": batch["season"],
                "team_ids": sorted(batch["team_ids"]),
                "players": len(batch["player_ids"]),
            }
            for batch in sorted(batches.values(), key=lambda item: str(item["league"]))
        ],
        "detection_errors": detection_errors[:50],
        "detection_error_count": len(detection_errors),
        "competition_errors": competition_errors,
        "match_detail_errors": detail_errors[:50],
        "match_detail_error_count": len(detail_errors),
        "warnings": [
            "Collected rows are player-filtered; opponents in a backfilled match are deliberately discarded.",
            "Competitions FotMob reports without a league id cannot be resolved to a fixture list and remain missing.",
            "Career-history appearance counts come from the same provider as the match sample and are not independent verification.",
        ],
    }
    write_json(args.output_dir / "coverage.json", audit)
    write_json(args.audit, audit)

    print(json.dumps({**counts, **{k: coverage[k] for k in ("multi_club_players", "players_with_gaps", "players_backfilled")}}, indent=2))
    return 0 if not competition_errors and not detail_errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
