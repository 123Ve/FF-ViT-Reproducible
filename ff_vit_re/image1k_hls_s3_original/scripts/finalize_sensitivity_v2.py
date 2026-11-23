#!/usr/bin/env python3
"""Audit and publish the completed v2 sensitivity run after the v1-schema migration."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.sensitivity_v2 import (build_v2_identity, full_v2_identity,
                                    inherit_v1_shards, partition_v2_cases,
                                    rank_v2, stamp_legacy_affected_shards,
                                    v2_identity_digest,
                                    validate_affected_v2_shard)
from src.provenance import atomic_write_json, sha256_file
from src.sensitivity import (aggregate_shards, enumerate_experiments,
                             load_compatible_shard)


def main() -> None:
    root = ROOT
    v1 = root / "results/sensitivity"
    v2 = root / "results/sensitivity_v2"
    reports = root / "reports/sensitivity_v2"
    progress_path = root / "results/sensitivity_v2_progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    if progress.get("status") != "complete" or progress.get("completed") != 77:
        raise ValueError("full 77-case formal v2 run is not complete")
    expected = json.loads((root / "metadata/sensitivity_identity.json").read_text())
    identity_path = root / "metadata/sensitivity_v2_identity.json"
    frozen = json.loads(identity_path.read_text(encoding="utf-8"))
    legacy = build_v2_identity(expected, quant_path=root / "src/quant.py",
                               sensitivity_path=root / "src/sensitivity.py")
    current = full_v2_identity(expected, root=root)
    if frozen not in (legacy, current):
        raise ValueError("frozen v2 source or semantics identity is incompatible")
    ranking_path = root / "metadata/sensitivity_ranking_v2.json"
    ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
    order = tuple(ranking["low_sensitivity_order"])
    cases = enumerate_experiments(12, low_sensitivity_order=order)
    inherited, initial, cumulative = partition_v2_cases(cases)
    affected = initial + cumulative
    if (len(cases), len(inherited), len(affected)) != (77, 28, 49):
        raise ValueError("v2 case counts differ from frozen design")
    inherit_v1_shards(v1, v2, inherited, expected=expected,
                      manifest_path=root / "metadata/sensitivity_v2_inherited.json")
    layer_shards = {case.id: load_compatible_shard(v2 / f"{case.id}.json",
                    experiment_id=case.id, expected=expected, experiment=case)
                    for case in initial if case.id.endswith("whole-block")}
    if rank_v2(layer_shards, block_count=12) != order:
        raise ValueError("v2 ranking does not match corrected whole-block shards")

    migration_path = root / "metadata/sensitivity_v2_migration.json"
    if frozen == legacy:
        stamp_legacy_affected_shards(v1, v2, affected, expected=expected,
                                     v2_identity=current, manifest_path=migration_path)
    for case in affected:
        validate_affected_v2_shard(v2 / f"{case.id}.json", case=case,
                                   expected=expected, v2_identity=current)
    ranking["v2_identity"] = current
    ranking["original_run_identity_sha256"] = v2_identity_digest(legacy)
    atomic_write_json(ranking_path, ranking)
    aggregate_shards(v2, reports, cases, expected=expected)
    shard_hashes = {case.id: sha256_file(v2 / f"{case.id}.json") for case in cases}
    inherited_manifest = json.loads((root / "metadata/sensitivity_v2_inherited.json").read_text())
    if any(shard_hashes[name] != digest for name, digest in inherited_manifest["shards"].items()):
        raise ValueError("inherited v1 shard changed during v2 publication")
    shard_meta = {"schema_version": 2, "v2_identity": current,
                  "original_run_identity_sha256": v2_identity_digest(legacy),
                  "ranking": ranking, "shards": shard_hashes}
    atomic_write_json(root / "metadata/sensitivity_v2_shards.json", shard_meta)
    report_hashes = {path.name: sha256_file(path) for path in sorted(reports.glob("*_sensitivity.*"))}
    if len(report_hashes) != 9:
        raise ValueError("v2 report set is incomplete")
    atomic_write_json(reports / "PROVENANCE.json", {
        "schema_version": 2,
        "semantic_revision": current["semantic_revision"],
        "v2_identity": current,
        "original_run_identity_sha256": v2_identity_digest(legacy),
        "base_identity": expected,
        "formal_samples_per_case": 50_000,
        "case_count": 77,
        "inherited_byte_identical_count": 28,
        "corrected_rerun_count": 49,
        "low_sensitivity_order_v2": order,
        "inherited_v1_shard_sha256": inherited_manifest["shards"],
        "all_v2_shard_sha256": shard_hashes,
        "report_sha256": report_hashes,
        "migration_manifest_sha256": sha256_file(migration_path) if migration_path.exists() else None,
    })
    atomic_write_json(identity_path, current)
    progress["v2_identity"] = current
    progress["publication_status"] = "audited"
    atomic_write_json(progress_path, progress)
    print(json.dumps({"status": "audited", "cases": 77, "inherited": 28,
                      "rerun": 49, "order": order,
                      "v2_semantics_sha256": v2_identity_digest(current)}))


if __name__ == "__main__":
    main()
