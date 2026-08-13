"""Prepare or run the cross-reference structural assessment benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.cross_reference_benchmark import (
    audit_pair_availability,
    load_approved_references,
    score_cross_reference_pairs,
    select_cross_reference_pairs,
    write_cross_reference_outputs,
)
from onestroke_model.perturbation_benchmark import (
    BenchmarkInputError,
    load_reference_cache,
)
from onestroke_model.reproducibility import (
    build_run_manifest,
    exact_command,
    utc_now_iso,
    write_run_manifest,
)


def main() -> None:
    started_at = utc_now_iso()
    parser = argparse.ArgumentParser(
        description="Build score-independent cross-reference pairs and score them when cache exists."
    )
    parser.add_argument(
        "--reference-manifest",
        default="references/calli_tongji_beta_manifest.csv",
    )
    parser.add_argument(
        "--cache-index",
        default="references/cache/segformer_b2_v1/index.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/cross_reference",
    )
    parser.add_argument("--seed", type=int, default=20260811)
    parser.add_argument("--negative-pairs", type=int, default=50)
    parser.add_argument(
        "--require-cache",
        action="store_true",
        help="Fail instead of writing a blocked pair-selection package when cache is absent.",
    )
    args = parser.parse_args()

    references = load_approved_references(args.reference_manifest)
    availability = audit_pair_availability(references)
    pairs = select_cross_reference_pairs(
        references,
        seed=args.seed,
        negative_pairs=args.negative_pairs,
    )
    scores = None
    input_metadata = {
        "reference_manifest": str(Path(args.reference_manifest).resolve()),
        "selection_seed": args.seed,
        "negative_pair_target": args.negative_pairs,
        "selection_uses_scores": False,
    }
    try:
        cache_metadata, cached = load_reference_cache(args.cache_index)
    except BenchmarkInputError as exc:
        if args.require_cache:
            raise SystemExit(str(exc)) from exc
        input_metadata["cache_status"] = "BLOCKED"
        input_metadata["cache_error"] = str(exc)
    else:
        input_metadata["cache_status"] = "PASS"
        input_metadata["cache"] = cache_metadata
        scores = score_cross_reference_pairs(pairs, cached)
    report = write_cross_reference_outputs(
        args.output_dir,
        availability=availability,
        pairs=pairs,
        scores=scores,
        input_metadata=input_metadata,
    )
    write_run_manifest(
        args.output_dir,
        build_run_manifest(
            experiment_name="onestroke_cross_reference_v1",
            status="COMPLETE" if scores is not None else "BLOCKED",
            started_at=started_at,
            ended_at=utc_now_iso(),
            command=exact_command(),
            seed=args.seed,
            input_paths=[args.reference_manifest, args.cache_index],
            additional={
                "formal_paper_run": scores is not None,
                "pair_type_counts": report["pair_type_counts"],
                "cache_error": input_metadata.get("cache_error"),
                "cache_model_version": input_metadata.get("cache", {}).get(
                    "model_version"
                ),
                "cache_checkpoint_sha256": input_metadata.get("cache", {}).get(
                    "checkpoint_sha256"
                ),
            },
        ),
    )
    print(
        json.dumps(
            {
                "formal_results_available": report["formal_results_available"],
                "pair_type_counts": report["pair_type_counts"],
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
