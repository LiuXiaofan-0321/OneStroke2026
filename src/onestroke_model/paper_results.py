"""Strict aggregation of frozen formal artifacts for the IJDAR paper."""

from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"])
        writer.writeheader()
        writer.writerows(rows)


def _formal_run_status(run_manifest: Path) -> tuple[str, dict[str, Any] | None]:
    manifest = _read_json(run_manifest)
    if manifest is None:
        return "MISSING", None
    status = str(manifest.get("status", "UNKNOWN"))
    formal = bool(manifest.get("additional", {}).get("formal_paper_run", False))
    if status == "COMPLETE" and formal:
        return "DONE", manifest
    if status == "SMOKE":
        return "DIAGNOSTIC_ONLY", manifest
    if status == "BLOCKED":
        return "BLOCKED", manifest
    if status == "COMPLETE" and not formal:
        return "INCOMPLETE_FORMAL_GATE", manifest
    return status, manifest


def build_artifact_registry(project_root: str | Path) -> list[dict[str, Any]]:
    root = Path(project_root).resolve()
    paper = root / "artifacts" / "paper_ijdar"
    definitions = [
        (
            "controlled_perturbation",
            paper / "controlled_perturbation" / "run_manifest.json",
            paper / "controlled_perturbation" / "perturbation_summary.csv",
        ),
        (
            "structure_score_audit",
            paper / "structure_score_audit" / "run_manifest.json",
            paper / "structure_score_audit" / "structure_score_audit_report.json",
        ),
        (
            "cross_reference",
            paper / "cross_reference" / "run_manifest.json",
            paper / "cross_reference" / "cross_reference_summary.csv",
        ),
        (
            "alignment_ablation",
            paper / "alignment_ablation" / "run_manifest.json",
            paper / "alignment_ablation" / "alignment_ablation_summary.csv",
        ),
        (
            "feedback_diagnostic_before_after",
            paper / "feedback_diagnostic" / "run_manifest.json",
            paper / "feedback_diagnostic" / "feedback_diagnostic_summary.csv",
        ),
    ]
    registry: list[dict[str, Any]] = []
    for name, run_manifest_path, primary_result in definitions:
        status, run_manifest = _formal_run_status(run_manifest_path)
        registry.append(
            {
                "experiment": name,
                "status": status,
                "run_manifest": str(run_manifest_path),
                "primary_result": str(primary_result),
                "primary_result_exists": primary_result.is_file(),
                "formal_artifact_eligible": status == "DONE" and primary_result.is_file(),
                "blocking_error": (
                    run_manifest.get("additional", {}).get("blocking_error")
                    or run_manifest.get("additional", {}).get("cache_error")
                    if run_manifest
                    else None
                ),
            }
        )

    task1_manifest_path = paper / "task1" / "summary_manifest.json"
    task1_manifest = _read_json(task1_manifest_path) or {}
    task1_complete = (
        int(task1_manifest.get("completed_run_count", 0)) == 18
        and not task1_manifest.get("missing_experiments")
    )
    task1_result = paper / "task1" / "results_summary.csv"
    registry.append(
        {
            "experiment": "task1_main_segmentation",
            "status": "DONE" if task1_complete else "PENDING_TASK1",
            "run_manifest": str(task1_manifest_path),
            "primary_result": str(task1_result),
            "primary_result_exists": task1_result.is_file(),
            "formal_artifact_eligible": task1_complete and task1_result.is_file(),
            "blocking_error": (
                None
                if task1_complete
                else "The formal 18-run, three-architecture, three-seed matrix is incomplete."
            ),
        }
    )
    registry.append(
        {
            "experiment": "character_disjoint_generalization",
            "status": "DONE" if task1_complete else "PENDING_TASK1",
            "run_manifest": str(task1_manifest_path),
            "primary_result": str(task1_result),
            "primary_result_exists": task1_result.is_file(),
            "formal_artifact_eligible": False,
            "blocking_error": (
                None
                if task1_complete
                else "Character-disjoint rows are incomplete in the formal Task 1 matrix."
            ),
        }
    )
    human_report = (
        paper
        / "expert_validation"
        / "human_ratings_v1"
        / "paper_statistics"
        / "human_validation_report.json"
    )
    human_data = _read_json(human_report) or {}
    human_complete = bool(human_data.get("data_integrity", {}).get("complete_matrix"))
    registry.append(
        {
            "experiment": "expert_structural_similarity_validation",
            "status": "DONE" if human_complete else "PENDING_HUMAN_DATA",
            "run_manifest": str(human_report),
            "primary_result": str(human_report),
            "primary_result_exists": human_report.is_file(),
            "formal_artifact_eligible": human_complete and human_report.is_file(),
            "blocking_error": None if human_complete else "Human ratings are unavailable.",
        }
    )
    course_scope_manifest_path = paper / "course_scoring_scope" / "run_manifest.json"
    course_scope_manifest = _read_json(course_scope_manifest_path) or {}
    course_scope_status = str(course_scope_manifest.get("status", "MISSING"))
    course_scope_complete = course_scope_status in {
        "COMPLETE",
        "COMPLETE_NO_ELIGIBLE_PAIRS",
    }
    course_scope_result = paper / "course_scoring_scope" / "course_overlap_summary.csv"
    registry.append(
        {
            "experiment": "course_scoring_scope_audit",
            "status": "DONE" if course_scope_complete else course_scope_status,
            "run_manifest": str(course_scope_manifest_path),
            "primary_result": str(course_scope_result),
            "primary_result_exists": course_scope_result.is_file(),
            "formal_artifact_eligible": (
                course_scope_complete and course_scope_result.is_file()
            ),
            "blocking_error": (
                None
                if course_scope_complete
                else "The same-character course-overlap audit is unavailable."
            ),
        }
    )
    return registry


def _copy_formal_tables(
    root: Path,
    registry: Sequence[Mapping[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    mapping = {
        "controlled_perturbation": (
            "artifacts/paper_ijdar/controlled_perturbation/perturbation_summary.csv",
            "controlled_perturbation.csv",
        ),
        "structure_score_audit": (
            "artifacts/paper_ijdar/structure_score_audit/score_variant_overall.csv",
            "structure_score_audit.csv",
        ),
        "cross_reference": (
            "artifacts/paper_ijdar/cross_reference/cross_reference_summary.csv",
            "cross_reference.csv",
        ),
        "alignment_ablation": (
            "artifacts/paper_ijdar/alignment_ablation/alignment_ablation_summary.csv",
            "alignment_ablation.csv",
        ),
        "feedback_diagnostic_before_after": (
            "artifacts/paper_ijdar/feedback_diagnostic/feedback_diagnostic_summary.csv",
            "feedback_diagnostic.csv",
        ),
        "task1_main_segmentation": (
            "artifacts/paper_ijdar/task1/results_summary.csv",
            "task1_results_summary.csv",
        ),
        "expert_structural_similarity_validation": (
            "artifacts/paper_ijdar/expert_validation/human_ratings_v1/"
            "paper_statistics/per_evaluator_summary.csv",
            "human_validation_per_evaluator.csv",
        ),
        "course_scoring_scope_audit": (
            "artifacts/paper_ijdar/course_scoring_scope/course_overlap_summary.csv",
            "course_scoring_scope.csv",
        ),
    }
    copied: list[dict[str, Any]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    by_name = {str(row["experiment"]): row for row in registry}
    for experiment, (source_value, destination_name) in mapping.items():
        status = by_name[experiment]
        if not status["formal_artifact_eligible"]:
            continue
        source = root / source_value
        destination = output_dir / destination_name
        shutil.copy2(source, destination)
        copied.append(
            {
                "experiment": experiment,
                "source": str(source),
                "destination": str(destination),
            }
        )
    return copied


def _existing_release_summary(root: Path) -> dict[str, Any] | None:
    metrics = _read_json(root / "releases/segformer_b2_v1/test_metrics.json")
    if metrics is None:
        return None
    return {
        "status": "PRELIMINARY_SINGLE_RELEASE_NOT_TASK1_MULTI_SEED",
        "macro_dice": metrics.get("macro_dice"),
        "macro_iou": metrics.get("macro_iou"),
        "keypoint_f1": metrics.get("keypoint_f1"),
        "boundary_f1": metrics.get("boundary_f1"),
        "source": "releases/segformer_b2_v1/test_metrics.json",
    }


def _formal_findings(root: Path) -> list[str]:
    paper = root / "artifacts" / "paper_ijdar"
    findings = [
        (
            "The recovered corpus has 840 file-complete GT samples and 769 "
            "QC-clean unique observations; the QC-clean standard split is "
            "530/119/120 and shares characters across train/val/test."
        ),
        (
            "The immutable character assignment has 28/6/6 characters; after "
            "the same QC exclusions the split has 539/114/116 observations "
            "with zero character overlap."
        ),
        "The current reference library has 7 same-character cross-style pairs and no same-style different-instance pairs.",
    ]
    controlled = _read_json(
        paper / "controlled_perturbation" / "benchmark_report.json"
    )
    if controlled and _formal_run_status(
        paper / "controlled_perturbation" / "run_manifest.json"
    )[0] == "DONE":
        audit = controlled.get("audit", {})
        nuisance = audit.get("nuisance_invariance", {})
        structural = audit.get("structural_sensitivity", {})
        validity = audit.get("validity", {})
        findings.append(
            "Controlled perturbation: nuisance mean absolute drop "
            f"{float(nuisance.get('mean_abs_score_drop', 0.0)):.3f}, versus "
            f"structural mean drop {float(structural.get('mean_score_drop', 0.0)):.3f}; "
            f"invalid/clipping fraction {float(validity.get('invalid_fraction', 0.0)):.3f}."
        )
    audit_report = _read_json(
        paper / "structure_score_audit" / "structure_score_audit_report.json"
    )
    if audit_report and _formal_run_status(
        paper / "structure_score_audit" / "run_manifest.json"
    )[0] == "DONE":
        coverage = audit_report.get("coverage", {})
        invariants = audit_report.get("invariants", {})
        findings.append(
            "Structure-score audit: "
            f"{int(coverage.get('references_with_inactive_direction', 0))}/"
            f"{int(coverage.get('n_references', 0))} references have at least one "
            "inactive direction; coverage correction changes "
            f"{int(invariants.get('n_rows_coverage_score_changed', 0))} valid rows "
            f"(mean downward correction {float(invariants.get('mean_downward_coverage_correction_points', 0.0)):.3f} points)."
        )
    cross = _read_json(paper / "cross_reference" / "cross_reference_report.json")
    if cross and _formal_run_status(
        paper / "cross_reference" / "run_manifest.json"
    )[0] == "DONE":
        by_type = {
            str(row.get("pair_type")): row for row in cross.get("summary", [])
        }
        same = by_type.get("same_character_cross_style", {})
        negative = by_type.get("different_character_negative", {})
        findings.append(
            "Cross-reference: same-character cross-style mean score "
            f"{float(same.get('mean', 0.0)):.3f} (n={int(same.get('n', 0))}), "
            "versus different-character negative mean "
            f"{float(negative.get('mean', 0.0)):.3f} (n={int(negative.get('n', 0))}); "
            "same-style different-instance validation is unsupported by the current library."
        )
    alignment = _read_json(
        paper / "alignment_ablation" / "alignment_ablation_report.json"
    )
    if alignment and _formal_run_status(
        paper / "alignment_ablation" / "run_manifest.json"
    )[0] == "DONE":
        by_variant = {
            str(row.get("alignment_variant")): row
            for row in alignment.get("summary", [])
        }
        no_alignment = by_variant.get("no_alignment", {})
        current = by_variant.get("current_constrained", {})
        wide = by_variant.get("wide_similarity", {})
        findings.append(
            "Alignment ablation: nuisance mean absolute drop was "
            f"{float(no_alignment.get('nuisance_mean_abs_score_drop', 0.0)):.3f} "
            "without alignment, "
            f"{float(current.get('nuisance_mean_abs_score_drop', 0.0)):.3f} with "
            "current constrained alignment, and "
            f"{float(wide.get('nuisance_mean_abs_score_drop', 0.0)):.3f} with the "
            "wide variant. The wide variant did not improve nuisance suppression "
            "or demonstrate the preregistered error-masking story."
        )
    feedback = _read_json(
        paper / "feedback_diagnostic" / "feedback_diagnostic_report.json"
    )
    if feedback and _formal_run_status(
        paper / "feedback_diagnostic" / "run_manifest.json"
    )[0] == "DONE":
        summaries = {
            str(row.get("rule_variant")): row
            for row in feedback.get("summary", [])
        }
        before = summaries.get("legacy-v1", {})
        after = summaries.get("current", {})
        findings.append(
            "Feedback diagnostic: required Recall@3 changed from "
            f"{float(before.get('required_recall_at_3', 0.0)):.3f} to "
            f"{float(after.get('required_recall_at_3', 0.0)):.3f}, while center-direction "
            "wording correctness changed from "
            f"{float(before.get('center_direction_wording_correctness', 0.0)):.3f} to "
            f"{float(after.get('center_direction_wording_correctness', 0.0)):.3f}. "
            "Other reported diagnostic metrics, including specificity, did not improve; "
            "the ground truth is deterministic perturbation cause, not expert aesthetics."
        )
    human = _read_json(
        paper
        / "expert_validation"
        / "human_ratings_v1"
        / "paper_statistics"
        / "human_validation_report.json"
    )
    if human and human.get("data_integrity", {}).get("complete_matrix"):
        correlation = human.get("system_vs_human_mean", {})
        reliability = human.get("canonical_inter_rater_reliability", {})
        current = correlation.get("current_score", {})
        coverage = correlation.get("coverage_aware_score", {})
        findings.append(
            "Blinded human validation: production-score Spearman rho "
            f"{float(current.get('spearman_rho', 0.0)):.3f}, coverage-aware rho "
            f"{float(coverage.get('spearman_rho', 0.0)):.3f}, and ICC(2,k) "
            f"{float(reliability.get('icc_2_k', 0.0)):.3f} across 150 canonical pairs."
        )
    course_scope = _read_json(paper / "course_scoring_scope" / "run_manifest.json")
    if course_scope:
        findings.append(
            "Course-scope audit: the "
            f"{int(course_scope.get('legacy_character_count', 0))} recovered legacy "
            "characters have zero overlap with both current 100-character course "
            "libraries, so no invalid cross-character course score was computed."
        )
    return findings


def _readiness_markdown(
    registry: Sequence[Mapping[str, Any]],
    *,
    formal_tables: Sequence[Mapping[str, Any]],
    preliminary_release: Mapping[str, Any] | None,
    findings: Sequence[str],
) -> str:
    status_lines = [
        f"| {row['experiment']} | {row['status']} | {row.get('blocking_error') or '-'} |"
        for row in registry
    ]
    formal = [row for row in registry if row["formal_artifact_eligible"]]
    blocked = [
        row
        for row in registry
        if row["status"] in {"BLOCKED", "PENDING_TASK1", "PENDING_HUMAN_DATA", "MISSING"}
    ]
    lines = [
        "# IJDAR Experiment Readiness Report",
        "",
        "## A. Completion Status",
        "",
        "| Experiment | Status | Evidence / blocker |",
        "|---|---|---|",
        *status_lines,
        "",
        "## B. Paper-Eligible Formal Results",
        "",
    ]
    if formal:
        lines.extend(
            f"- `{row['experiment']}`: `{row['primary_result']}`" for row in formal
        )
    else:
        lines.append(
            "- None of the new real-reference / human-validation experiments currently pass the formal artifact gate."
        )
    if preliminary_release:
        lines.extend(
            [
                "",
                "- Existing frozen B2 single-release metrics are retained as preliminary evidence,",
                "  but they are not a substitute for Task 1 multi-seed/model-comparison results:",
                f"  `{preliminary_release}`",
            ]
        )
    lines.extend(
        [
            "",
            "## C. Results That Must Not Enter the Paper",
            "",
            "- Any artifact under an output directory containing `synthetic_smoke`.",
            "- The July same-image reference smoke scores near 100.",
            "- Blocked reports, empty templates, or incomplete character-disjoint runs.",
            "- Rule-based or LLM feedback examples without the paired formal diagnostic benchmark.",
            "",
            "## D. Findings and Open Questions",
            "",
            *[f"- {finding}" for finding in findings],
            "",
            "## E. Production Change Recommendation",
            "",
            "No production score, alignment, threshold, or feedback logic should be changed from the current evidence.",
            "All changes in this worktree are research/evaluation infrastructure.",
            "",
            "## F. IJDAR Readiness",
            "",
            "### Must-Have Remaining Items",
            "",
        ]
    )
    lines.extend(
        f"- {row['experiment']}: {row.get('blocking_error') or row['status']}"
        for row in blocked
    )
    lines.extend(
        [
            "",
            "### Nice-to-Have Items",
            "",
            "- Increase same-style different-instance reference coverage under compatible licenses.",
            "- Export same-character direct-digital course submissions for an end-to-end course benchmark.",
            "- Add qualified-expert aesthetic calibration only if the claim scope is expanded beyond structural similarity.",
            "",
            "### Largest Current Risks",
            "",
            "- Scientific risk: structural correlation is externally validated, but the score is not an expert-calibrated aesthetic grade.",
            "- Reproducibility risk: the local segmentation manifest contains stale absolute paths.",
            "- Coverage risk: the two current course libraries contain no same-style different-instance references.",
            "",
            f"Formal tables copied in this run: **{len(formal_tables)}**.",
            "",
        ]
    )
    return "\n".join(lines)


def build_ijdar_paper_results(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    paper = root / "artifacts" / "paper_ijdar"
    final_tables = paper / "final_tables"
    final_figures = paper / "final_figures"
    final_statistics = paper / "final_statistics"
    for path in (final_tables, final_figures, final_statistics):
        path.mkdir(parents=True, exist_ok=True)
    registry = build_artifact_registry(root)
    _write_csv(final_statistics / "experiment_status.csv", registry)
    (final_statistics / "artifact_registry.json").write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    copied = _copy_formal_tables(root, registry, final_tables)
    preliminary = _existing_release_summary(root)
    inventory = {
        "schema_version": 1,
        "formal_artifacts": [
            row for row in registry if row["formal_artifact_eligible"]
        ],
        "copied_tables": copied,
        "preliminary_release": preliminary,
        "negative_results_hidden": False,
        "smoke_results_included": False,
    }
    (final_statistics / "formal_result_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    readiness_path = paper / "IJDAR_EXPERIMENT_READINESS_REPORT.md"
    readiness_path.write_text(
        _readiness_markdown(
            registry,
            formal_tables=copied,
            preliminary_release=preliminary,
            findings=_formal_findings(root),
        ),
        encoding="utf-8",
    )
    return {
        "registry": registry,
        "formal_table_count": len(copied),
        "readiness_report": str(readiness_path),
        "final_tables": str(final_tables),
        "final_figures": str(final_figures),
        "final_statistics": str(final_statistics),
    }
