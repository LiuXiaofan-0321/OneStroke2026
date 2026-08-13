from __future__ import annotations

import numpy as np

from onestroke_model.controlled_perturbations import (
    PerturbationDefinition,
    PreparedReferenceScorer,
    apply_perturbation,
)
from onestroke_model.feedback_diagnostic_benchmark import (
    run_feedback_diagnostic,
    summarize_feedback_diagnostic,
)
from onestroke_model.feedback_diagnostic_rules import diagnostic_findings
from onestroke_model.perturbation_benchmark import synthetic_references


def test_current_center_direction_does_not_invent_diagonal() -> None:
    _, references = synthetic_references(128)
    masks = references[0]["masks"]
    outcome = apply_perturbation(masks, references[0]["reference_id"], "global_translation", 8)
    evidence, aligned = PreparedReferenceScorer(masks).score(outcome.masks)
    current = diagnostic_findings("current", evidence, outcome.masks, aligned)
    center = next(item for item in current if item["finding_id"] == "layout_center_offset")
    assert center["center_direction"] in {"left", "right", "up", "down"}


def test_current_local_finding_uses_one_consistent_channel() -> None:
    _, references = synthetic_references(128)
    masks = references[0]["masks"]
    outcome = apply_perturbation(
        masks,
        references[0]["reference_id"],
        "direction_terminal_deletion",
        0.30,
    )
    evidence, aligned = PreparedReferenceScorer(masks).score(outcome.masks)
    findings = diagnostic_findings("current", evidence, outcome.masks, aligned)
    local = next(item for item in findings if item["finding_id"] == "local_direction_structure")
    assert local["channel"] in {"vec1", "vec2", "vec3", "vec4", "vec5"}
    assert local["region"] is not None


def test_small_paired_benchmark_writes_comparable_metrics() -> None:
    _, references = synthetic_references(112)
    definitions = (
        PerturbationDefinition(
            name="global_translation",
            family="nuisance",
            severities=(8.0,),
            unit="pixels",
            expected_behavior="invariant",
            description="test",
        ),
        PerturbationDefinition(
            name="direction_terminal_deletion",
            family="structural",
            severities=(0.30,),
            unit="fraction",
            expected_behavior="decreasing",
            description="test",
        ),
    )
    rows = run_feedback_diagnostic(references[:1], definitions)
    summaries, paired = summarize_feedback_diagnostic(rows)
    assert {row["rule_variant"] for row in summaries} == {"legacy-v1", "current"}
    assert "required_recall_at_3" in paired["metrics"]
    assert all(np.isfinite(float(row["score"])) for row in rows if row["status"] == "valid")
