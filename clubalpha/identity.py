"""Exact identity-crosswalk helpers for the REEP coverage pilot.

Clubalpha remains FotMob-first. REEP v0 is a frozen, optional bridge seed that
can attach other provider IDs to a known FotMob entity. It must never replace a
FotMob ID, silently merge a duplicate, or fall back to a name-only guess.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from clubalpha.fotmob import normalize_name


def external_id(value: Any) -> str | None:
    """Normalize an external identifier without changing its semantics."""

    if value is None or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    return normalized or None


def build_fotmob_index(
    rows: Iterable[dict[str, Any]],
    *,
    entity_type: str,
) -> dict[str, list[dict[str, Any]]]:
    """Index legacy REEP rows by FotMob ID while preserving collisions."""

    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if entity_type == "player" and str(row.get("type") or "") != "player":
            continue
        key = external_id(row.get("key_fotmob"))
        if key is not None:
            index[key].append(row)
    return dict(index)


def _name_agreement(target: dict[str, Any], source: dict[str, Any], target_name: str) -> bool:
    wanted = normalize_name(target.get(target_name))
    candidates = {
        normalize_name(source.get("name")),
        normalize_name(source.get("full_name")),
    }
    candidates.discard("")
    return bool(wanted and wanted in candidates)


def _dob_conflict(target: dict[str, Any], source: dict[str, Any]) -> bool:
    target_dob = external_id(target.get("date_of_birth"))
    source_dob = external_id(source.get("date_of_birth"))
    return bool(target_dob and source_dob and target_dob != source_dob)


def resolve_fotmob_entities(
    targets: Iterable[dict[str, Any]],
    index: dict[str, list[dict[str, Any]]],
    *,
    entity_type: str,
    target_id: str,
    target_name: str,
    provider_fields: dict[str, str],
    source_release: str,
    source_commit: str,
) -> list[dict[str, Any]]:
    """Resolve a Clubalpha universe through exact FotMob IDs only.

    A unique provider-ID match is accepted unless a known date of birth
    contradicts it. Duplicate IDs and contradictions are quarantined. Names
    are diagnostic only and can never create a match.
    """

    resolved: list[dict[str, Any]] = []
    for target in targets:
        fotmob_id = external_id(target.get(target_id))
        candidates = index.get(fotmob_id or "", [])
        flags: list[str] = []
        source: dict[str, Any] | None = None

        if fotmob_id is None:
            status = "missing_fotmob_id"
        elif not candidates:
            status = "unmatched"
        elif len(candidates) > 1:
            status = "ambiguous_provider_id"
            flags.append("duplicate_legacy_fotmob_bridge")
        else:
            source = candidates[0]
            if entity_type == "player" and _dob_conflict(target, source):
                status = "conflict"
                flags.append("date_of_birth_conflict")
            else:
                status = "exact"
                if not _name_agreement(target, source, target_name):
                    flags.append("name_differs_on_exact_provider_id")

        bridges = {
            provider: external_id(source.get(field)) if source else None
            for provider, field in provider_fields.items()
        }
        resolved.append(
            {
                "entity_type": entity_type,
                "clubalpha_identity": (
                    f"fotmob:{entity_type}:{fotmob_id}" if fotmob_id is not None else None
                ),
                "fotmob_id": fotmob_id,
                "fotmob_name": target.get(target_name),
                "resolution": {
                    "status": status,
                    "method": "exact_provider_id" if status in {"exact", "conflict"} else None,
                    "candidate_count": len(candidates),
                    "quality_flags": flags,
                },
                "legacy_reep": {
                    "reep_id": external_id(source.get("reep_id")) if source else None,
                    "label": source.get("name") if source else None,
                    "date_of_birth": source.get("date_of_birth") if source else None,
                    "source_release": source_release,
                    "source_commit": source_commit,
                    "status": "frozen_v0_seed_only",
                },
                "bridges": bridges,
            }
        )
    return resolved


def coverage_summary(
    rows: list[dict[str, Any]],
    provider_fields: dict[str, str],
) -> dict[str, Any]:
    """Summarize exact coverage, quarantines, and downstream bridge reach."""

    statuses = Counter(row["resolution"]["status"] for row in rows)
    flags = Counter(
        flag
        for row in rows
        for flag in row["resolution"].get("quality_flags") or []
    )
    exact = [row for row in rows if row["resolution"]["status"] == "exact"]
    total = len(rows)
    return {
        "universe": total,
        "statuses": dict(sorted(statuses.items())),
        "exact_matches": len(exact),
        "exact_coverage_pct": round(100.0 * len(exact) / total, 1) if total else 0.0,
        "quality_flags": dict(sorted(flags.items())),
        "provider_coverage_among_exact": {
            provider: {
                "entities": sum(1 for row in exact if row["bridges"].get(provider)),
                "pct": round(
                    100.0 * sum(1 for row in exact if row["bridges"].get(provider)) / len(exact),
                    1,
                )
                if exact
                else 0.0,
            }
            for provider in provider_fields
        },
    }


def build_typed_provider_bridge_indexes(
    rows: Iterable[dict[str, Any]],
    *,
    provider: str,
    namespaces_by_type: dict[str, set[str]],
    wanted_by_type: dict[str, set[str]],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Build several entity-type indexes in one pass over the large bridge file."""

    output: dict[str, dict[str, list[dict[str, str]]]] = {
        entity_type: defaultdict(list) for entity_type in namespaces_by_type
    }
    namespace_to_type = {
        namespace: entity_type
        for entity_type, namespaces in namespaces_by_type.items()
        for namespace in namespaces
    }
    for row in rows:
        if row.get("provider") != provider:
            continue
        namespace = external_id(row.get("namespace"))
        entity_type = namespace_to_type.get(namespace or "")
        external = external_id(row.get("external_id"))
        if entity_type is None or external not in wanted_by_type.get(entity_type, set()):
            continue
        candidate = {
            "namespace": str(namespace),
            "external_id": str(external),
            "reep_id": str(row["reep_id"]),
        }
        bucket = output[entity_type][str(external)]
        if candidate not in bucket:
            bucket.append(candidate)
    return {
        entity_type: dict(index)
        for entity_type, index in output.items()
    }


def build_redirect_index(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index the v1 redirect and tombstone ledger."""

    return {
        str(row["from_id"]): {
            "to_id": external_id(row.get("to_id")),
            "reason": row.get("reason"),
        }
        for row in rows
        if external_id(row.get("from_id")) is not None
    }


def redirect_target(
    reep_id: str,
    redirects: dict[str, dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Follow redirects safely; an empty target is an explicit tombstone."""

    current = reep_id
    chain: list[dict[str, Any]] = []
    visited: set[str] = set()
    while current in redirects:
        if current in visited:
            return None, [*chain, {"from_id": current, "reason": "redirect_cycle"}]
        visited.add(current)
        item = redirects[current]
        chain.append({"from_id": current, **item})
        if item["to_id"] is None:
            return None, chain
        current = str(item["to_id"])
    return current, chain


def build_entity_index(
    rows: Iterable[dict[str, Any]],
    wanted_reep_ids: set[str],
) -> dict[str, dict[str, Any]]:
    """Load only current v1 entities reachable from the pilot's bridge rows."""

    return {
        str(row["reep_id"]): row
        for row in rows
        if str(row.get("reep_id") or "") in wanted_reep_ids
    }


def attach_v1_identities(
    rows: list[dict[str, Any]],
    bridge_indexes: dict[str, dict[str, list[dict[str, str]]]],
    entities: dict[str, dict[str, Any]],
    redirects: dict[str, dict[str, Any]],
    *,
    release_stamp: str,
    handoff_provider: str = "transfermarkt",
) -> list[dict[str, Any]]:
    """Attach current v1 identities through an exact typed provider handoff."""

    output: list[dict[str, Any]] = []
    for row in rows:
        legacy_status = row["resolution"]["status"]
        handoff_id = external_id(row["bridges"].get(handoff_provider))
        index = bridge_indexes.get(row["entity_type"], {})
        candidates = index.get(handoff_id or "", [])
        requested: str | None = None
        resolved: str | None = None
        chain: list[dict[str, Any]] = []

        if legacy_status != "exact":
            status = "not_eligible"
        elif handoff_id is None:
            status = "missing_handoff_id"
        elif not candidates:
            status = "unmatched"
        elif len(candidates) > 1:
            status = "ambiguous_provider_id"
        else:
            requested = candidates[0]["reep_id"]
            resolved, chain = redirect_target(requested, redirects)
            if resolved is None:
                status = "tombstoned"
            else:
                entity = entities.get(resolved)
                if entity is None:
                    status = "entity_missing"
                elif entity.get("entity_type") != row["entity_type"]:
                    status = "entity_type_conflict"
                elif entity.get("status") != "active":
                    status = "entity_not_active"
                else:
                    status = "exact"

        entity = entities.get(resolved or "")
        output.append(
            {
                **row,
                "reep_v1": {
                    "status": status,
                    "release_stamp": release_stamp,
                    "handoff_provider": handoff_provider,
                    "handoff_external_id": handoff_id,
                    "candidate_count": len(candidates),
                    "requested_reep_id": requested,
                    "reep_id": resolved if status == "exact" else None,
                    "entity_status": entity.get("status") if entity else None,
                    "label": entity.get("label") if entity else None,
                    "redirect_chain": chain,
                },
            }
        )
    return output


def v1_coverage_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure the current v1 handoff against both eligible and total rows."""

    statuses = Counter(row["reep_v1"]["status"] for row in rows)
    eligible = [
        row
        for row in rows
        if row["resolution"]["status"] == "exact"
        and row["reep_v1"].get("handoff_external_id") is not None
    ]
    exact = [row for row in rows if row["reep_v1"]["status"] == "exact"]
    return {
        "universe": len(rows),
        "eligible_exact_legacy_rows": len(eligible),
        "exact_v1_matches": len(exact),
        "exact_pct_of_eligible": (
            round(100.0 * len(exact) / len(eligible), 1) if eligible else 0.0
        ),
        "exact_pct_of_universe": (
            round(100.0 * len(exact) / len(rows), 1) if rows else 0.0
        ),
        "statuses": dict(sorted(statuses.items())),
    }


def identity_scope_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact legacy and current coverage for an overlapping competition scope."""

    total = len(rows)
    legacy_exact = sum(1 for row in rows if row["resolution"]["status"] == "exact")
    v1_exact = sum(1 for row in rows if row.get("reep_v1", {}).get("status") == "exact")
    return {
        "universe": total,
        "legacy_exact": legacy_exact,
        "legacy_exact_pct": round(100.0 * legacy_exact / total, 1) if total else 0.0,
        "current_v1_exact": v1_exact,
        "current_v1_exact_pct": round(100.0 * v1_exact / total, 1) if total else 0.0,
    }
