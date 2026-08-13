"""Run the paired feedback diagnostic on a real approved reference cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from onestroke_model.feedback_diagnostic_benchmark import (
    run_feedback_diagnostic,
    write_feedback_diagnostic_outputs,
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache-index",
        default="references/cache/segformer_b2_v1/index.json",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/feedback_diagnostic",
    )
    parser.add_argument("--limit-per-style", type=int, default=0)
    args = parser.parse_args()
    output = Path(args.output_dir)
    try:
        input_metadata, references = load_reference_cache(
            args.cache_index,
            limit_per_style=args.limit_per_style,
        )
    except BenchmarkInputError as exc:
        output.mkdir(parents=True, exist_ok=True)
        (output / "BLOCKED.md").write_text(
            f"# Feedback Diagnostic Blocked\n\n{exc}\n",
            encoding="utf-8",
        )
        write_run_manifest(
            output,
            build_run_manifest(
                experiment_name="onestroke_feedback_diagnostic_v1",
                status="BLOCKED",
                started_at=started_at,
                ended_at=utc_now_iso(),
                command=exact_command(),
                seed="deterministic_sha256_internal",
                input_paths=[args.cache_index],
                additional={"formal_paper_run": False, "blocking_error": str(exc)},
            ),
        )
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return
    rows = run_feedback_diagnostic(references)
    (output / "BLOCKED.md").unlink(missing_ok=True)
    report = write_feedback_diagnostic_outputs(
        output,
        rows,
        input_metadata=input_metadata,
    )
    write_run_manifest(
        output,
        build_run_manifest(
            experiment_name="onestroke_feedback_diagnostic_v1",
            status="COMPLETE",
            started_at=started_at,
            ended_at=utc_now_iso(),
            command=exact_command(),
            seed="deterministic_sha256_internal",
            input_paths=[args.cache_index],
            additional={
                "formal_paper_run": args.limit_per_style == 0,
                "selected_references": input_metadata["selected_references"],
                "ground_truth_type": "deterministic_perturbation_labels",
                "cache_model_version": input_metadata.get("model_version"),
                "cache_checkpoint_sha256": input_metadata.get(
                    "checkpoint_sha256"
                ),
            },
        ),
    )
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "selected_references": input_metadata["selected_references"],
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
