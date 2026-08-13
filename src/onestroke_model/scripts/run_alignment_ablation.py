"""Run or preregister the benchmark-only alignment ablation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.alignment_ablation import (
    run_alignment_ablation,
    write_alignment_ablation_outputs,
)
from onestroke_model.perturbation_benchmark import (
    BenchmarkInputError,
    collect_runtime_metadata,
    load_reference_cache,
    synthetic_references,
)
from onestroke_model.reproducibility import (
    build_run_manifest,
    exact_command,
    utc_now_iso,
    write_run_manifest,
)


def main() -> None:
    started_at = utc_now_iso()
    parser = argparse.ArgumentParser(description="Compare no, constrained, and wide alignment.")
    parser.add_argument(
        "--cache-index",
        default="references/cache/segformer_b2_v1/index.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/alignment_ablation",
    )
    parser.add_argument("--synthetic-smoke", action="store_true")
    parser.add_argument("--synthetic-canvas-size", type=int, default=160)
    args = parser.parse_args()

    metadata = collect_runtime_metadata()
    rows = None
    baselines = None
    if args.synthetic_smoke:
        source_metadata, references = synthetic_references(args.synthetic_canvas_size)
        metadata.update(source_metadata)
        metadata["formal_paper_run"] = False
        metadata["warning"] = "Synthetic smoke numbers must not enter the paper."
        rows, baselines = run_alignment_ablation(references, progress=True)
    else:
        try:
            source_metadata, references = load_reference_cache(args.cache_index)
        except BenchmarkInputError as exc:
            metadata["formal_paper_run"] = False
            metadata["cache_status"] = "BLOCKED"
            metadata["cache_error"] = str(exc)
        else:
            metadata.update(source_metadata)
            metadata["formal_paper_run"] = True
            metadata["cache_status"] = "PASS"
            rows, baselines = run_alignment_ablation(references, progress=True)

    report = write_alignment_ablation_outputs(
        args.output_dir,
        rows=rows,
        baselines=baselines,
        input_metadata=metadata,
    )
    write_run_manifest(
        args.output_dir,
        build_run_manifest(
            experiment_name="onestroke_alignment_ablation_v1",
            status=(
                "SMOKE"
                if args.synthetic_smoke
                else ("COMPLETE" if rows is not None else "BLOCKED")
            ),
            started_at=started_at,
            ended_at=utc_now_iso(),
            command=exact_command(),
            seed="deterministic_sha256_internal",
            input_paths=[] if args.synthetic_smoke else [args.cache_index],
            additional={
                "formal_paper_run": bool(metadata.get("formal_paper_run")),
                "cache_error": metadata.get("cache_error"),
                "cache_model_version": metadata.get("model_version"),
                "cache_checkpoint_sha256": metadata.get("checkpoint_sha256"),
            },
        ),
    )
    print(
        json.dumps(
            {
                "formal_results_available": report["formal_results_available"],
                "output_dir": str(Path(args.output_dir).resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
