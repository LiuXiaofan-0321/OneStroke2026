from __future__ import annotations

import csv
import json
from pathlib import Path

from onestroke_model.paper_figures import build_formal_figures


def _manifest(path: Path, formal: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "COMPLETE",
                "additional": {"formal_paper_run": formal},
            }
        ),
        encoding="utf-8",
    )


def test_figure_builder_uses_only_formal_artifacts(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    controlled = paper / "controlled_perturbation"
    _manifest(controlled / "run_manifest.json")
    fields = [
        "perturbation",
        "family",
        "severity_normalized",
        "score_drop_from_identity_mean",
        "score_drop_from_identity_mean_ci95_low",
        "score_drop_from_identity_mean_ci95_high",
    ]
    with (controlled / "perturbation_summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            [
                {
                    "perturbation": "translation",
                    "family": "nuisance",
                    "severity_normalized": 1,
                    "score_drop_from_identity_mean": 0,
                    "score_drop_from_identity_mean_ci95_low": 0,
                    "score_drop_from_identity_mean_ci95_high": 0,
                },
                {
                    "perturbation": "deletion",
                    "family": "structural",
                    "severity_normalized": 1,
                    "score_drop_from_identity_mean": 20,
                    "score_drop_from_identity_mean_ci95_low": 18,
                    "score_drop_from_identity_mean_ci95_high": 22,
                },
            ]
        )
    blocked = paper / "cross_reference"
    _manifest(blocked / "run_manifest.json", formal=False)
    (blocked / "cross_reference_scores.csv").write_text(
        "pair_type,prototype_structure_score\ndifferent_character_negative,999\n",
        encoding="utf-8",
    )

    report = build_formal_figures(paper, paper / "final_figures")

    assert report["created_figure_pairs"] == 2
    assert (paper / "final_figures" / "controlled_nuisance_curves.pdf").is_file()
    assert not (paper / "final_figures" / "cross_reference_distributions.pdf").exists()


def test_alignment_figure_uses_formal_summary_schema(tmp_path: Path) -> None:
    paper = tmp_path / "paper"
    alignment = paper / "alignment_ablation"
    _manifest(alignment / "run_manifest.json")
    (alignment / "alignment_ablation_summary.csv").write_text(
        "alignment_variant,nuisance_mean_abs_score_drop,structural_mean_score_drop\n"
        "no_alignment,38.5,3.7\n"
        "current_constrained,8.5,14.9\n"
        "wide_similarity,11.4,15.1\n",
        encoding="utf-8",
    )

    report = build_formal_figures(paper, paper / "final_figures")

    assert report["created_figure_pairs"] == 1
    assert (paper / "final_figures" / "alignment_tradeoff.pdf").is_file()
