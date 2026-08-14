from __future__ import annotations

import json
from pathlib import Path

from onestroke_model.paper_results import build_ijdar_paper_results


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_aggregator_rejects_smoke_and_blocked_artifacts(tmp_path: Path) -> None:
    paper = tmp_path / "artifacts" / "paper_ijdar"
    _write_json(
        paper / "controlled_perturbation" / "run_manifest.json",
        {
            "status": "SMOKE",
            "additional": {"formal_paper_run": False},
        },
    )
    (paper / "controlled_perturbation" / "perturbation_summary.csv").write_text(
        "value\n999\n",
        encoding="utf-8",
    )
    _write_json(
        paper / "alignment_ablation" / "run_manifest.json",
        {
            "status": "BLOCKED",
            "additional": {"formal_paper_run": False, "cache_error": "missing"},
        },
    )
    _write_json(
        paper / "preflight" / "preflight_report.json",
        {"task1": {"status": "PENDING_TASK1"}},
    )
    _write_json(
        paper / "expert_validation" / "study_package" / "expert_study_metadata.json",
        {"status": "PENDING_PAIR_SCORES_AND_HUMAN_RATINGS"},
    )
    report = build_ijdar_paper_results(tmp_path)
    assert report["formal_table_count"] == 0
    inventory = json.loads(
        (
            paper / "final_statistics" / "formal_result_inventory.json"
        ).read_text(encoding="utf-8")
    )
    assert inventory["smoke_results_included"] is False
    assert not (paper / "final_tables" / "controlled_perturbation.csv").exists()
    readiness = (paper / "IJDAR_EXPERIMENT_READINESS_REPORT.md").read_text(
        encoding="utf-8"
    )
    assert "smartphone_unseen_writer" not in readiness
    assert "course_scoring_scope_audit" in readiness


def test_aggregator_copies_only_complete_formal_table(tmp_path: Path) -> None:
    paper = tmp_path / "artifacts" / "paper_ijdar"
    _write_json(
        paper / "cross_reference" / "run_manifest.json",
        {
            "status": "COMPLETE",
            "additional": {"formal_paper_run": True},
        },
    )
    source = paper / "cross_reference" / "cross_reference_summary.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("pair_type,mean\ncross,50\n", encoding="utf-8")
    _write_json(
        paper / "preflight" / "preflight_report.json",
        {"task1": {"status": "PENDING_TASK1"}},
    )
    report = build_ijdar_paper_results(tmp_path)
    assert report["formal_table_count"] == 1
    assert (paper / "final_tables" / "cross_reference.csv").read_text(
        encoding="utf-8"
    ) == source.read_text(encoding="utf-8")


def test_aggregator_accepts_only_formal_feedback_summary(tmp_path: Path) -> None:
    paper = tmp_path / "artifacts" / "paper_ijdar"
    _write_json(
        paper / "feedback_diagnostic" / "run_manifest.json",
        {
            "status": "COMPLETE",
            "additional": {"formal_paper_run": True},
        },
    )
    source = paper / "feedback_diagnostic" / "feedback_diagnostic_summary.csv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("rule_variant,required_recall_at_3\ncurrent,0.8\n", encoding="utf-8")
    _write_json(
        paper / "preflight" / "preflight_report.json",
        {"task1": {"status": "PENDING_TASK1"}},
    )

    report = build_ijdar_paper_results(tmp_path)

    assert report["formal_table_count"] == 1
    assert (paper / "final_tables" / "feedback_diagnostic.csv").read_text(
        encoding="utf-8"
    ) == source.read_text(encoding="utf-8")


def test_aggregator_recognizes_completed_task1_human_and_course_scope(
    tmp_path: Path,
) -> None:
    paper = tmp_path / "artifacts" / "paper_ijdar"
    _write_json(
        paper / "task1" / "summary_manifest.json",
        {"completed_run_count": 18, "missing_experiments": []},
    )
    task1_table = paper / "task1" / "results_summary.csv"
    task1_table.write_text("protocol,model,n_seeds\nmain_qc,unet,3\n", encoding="utf-8")

    human_dir = paper / "expert_validation" / "human_ratings_v1" / "paper_statistics"
    _write_json(
        human_dir / "human_validation_report.json",
        {"data_integrity": {"complete_matrix": True}},
    )
    (human_dir / "per_evaluator_summary.csv").write_text(
        "evaluator_id,n\nE01,150\n",
        encoding="utf-8",
    )

    _write_json(
        paper / "course_scoring_scope" / "run_manifest.json",
        {"status": "COMPLETE_NO_ELIGIBLE_PAIRS"},
    )
    (paper / "course_scoring_scope" / "course_overlap_summary.csv").write_text(
        "style_id,overlap_character_count\ncourse_a,0\n",
        encoding="utf-8",
    )

    report = build_ijdar_paper_results(tmp_path)
    by_name = {row["experiment"]: row for row in report["registry"]}

    assert by_name["task1_main_segmentation"]["status"] == "DONE"
    assert by_name["character_disjoint_generalization"]["status"] == "DONE"
    assert by_name["expert_structural_similarity_validation"]["status"] == "DONE"
    assert by_name["course_scoring_scope_audit"]["status"] == "DONE"
    assert report["formal_table_count"] == 3
