"""CLI for the OneStroke structure-score audit."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from onestroke_model.perturbation_benchmark import (
    collect_runtime_metadata,
    load_reference_cache,
    synthetic_references,
)
from onestroke_model.structure_score_audit_benchmark import (
    run_structure_score_audit,
    write_structure_score_audit_outputs,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit OneStroke structure-score aggregation on the same controlled "
            "mask perturbations used by the scoring benchmark."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--cache-index",
        type=Path,
        help="Local references/cache/.../index.json for a formal real-reference run.",
    )
    source.add_argument(
        "--synthetic-smoke",
        action="store_true",
        help="Run four deterministic synthetic fixtures. Never quote these numbers in a paper.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--style-id", action="append", default=[])
    parser.add_argument("--target-char", action="append", default=[])
    parser.add_argument(
        "--limit-per-style",
        type=int,
        default=0,
        help="Stable hash-selected dry-run limit. Keep zero for the formal paper run.",
    )
    parser.add_argument(
        "--synthetic-canvas-size",
        type=int,
        default=160,
        help="Canvas size for synthetic smoke fixtures only.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.limit_per_style < 0:
        raise SystemExit("--limit-per-style must be >= 0")

    if args.synthetic_smoke:
        if args.style_id or args.target_char or args.limit_per_style:
            raise SystemExit(
                "style/character/limit filters are only valid with --cache-index"
            )
        input_metadata, references = synthetic_references(args.synthetic_canvas_size)
        input_metadata = {
            **input_metadata,
            "formal_paper_run": False,
            "warning": "synthetic smoke results are implementation validation only",
        }
    else:
        assert args.cache_index is not None
        input_metadata, references = load_reference_cache(
            args.cache_index,
            style_ids=set(args.style_id) or None,
            target_chars=set(args.target_char) or None,
            limit_per_style=args.limit_per_style,
        )
        input_metadata = {
            **input_metadata,
            "formal_paper_run": args.limit_per_style == 0,
        }

    rows, coverage_rows = run_structure_score_audit(references)
    runtime = collect_runtime_metadata()
    core_path = Path(__file__).resolve().parents[1] / "structure_score_audit.py"
    benchmark_path = Path(__file__).resolve().parents[1] / "structure_score_audit_benchmark.py"
    runtime.update(
        {
            "structure_score_audit_sha256": _sha256(core_path),
            "structure_score_audit_benchmark_sha256": _sha256(benchmark_path),
        }
    )
    report = write_structure_score_audit_outputs(
        args.output_dir,
        rows,
        coverage_rows,
        input_metadata=input_metadata,
        runtime_metadata=runtime,
    )

    overall = {row["score_variant"]: row for row in report["score_variant_overall"]}
    invariants = report["invariants"]
    coverage = report["coverage"]
    print(f"wrote structure-score audit to {args.output_dir}")
    print(
        "v1 parity max abs error:",
        invariants["max_abs_v1_recompute_minus_production"],
    )
    print(
        "ink-IoU/alignment-objective max abs difference:",
        invariants["max_abs_ink_iou_minus_alignment_objective"],
    )
    print(
        "references with inactive directions:",
        f"{coverage['references_with_inactive_direction']}/{coverage['n_references']}",
    )
    print(
        "references without keypoints:",
        f"{coverage['references_without_keypoint_evidence']}/{coverage['n_references']}",
    )
    for name, row in overall.items():
        print(
            name,
            "nuisance_max_mean_drop=",
            row["max_severity_nuisance_mean_abs_drop"],
            "structural_max_mean_drop=",
            row["max_severity_structural_mean_drop"],
        )


if __name__ == "__main__":
    main()
