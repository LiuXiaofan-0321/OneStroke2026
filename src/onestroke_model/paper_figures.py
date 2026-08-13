"""Generate paper figures strictly from completed formal experiment artifacts."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _is_formal_complete(directory: Path) -> bool:
    manifest_path = directory / "run_manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        manifest.get("status") == "COMPLETE"
        and bool(manifest.get("additional", {}).get("formal_paper_run"))
    )


def _save_figure(figure: Any, output: Path, stem: str) -> list[str]:
    output.mkdir(parents=True, exist_ok=True)
    paths = [output / f"{stem}.png", output / f"{stem}.pdf"]
    figure.tight_layout()
    figure.savefig(paths[0], dpi=240, bbox_inches="tight")
    figure.savefig(paths[1], bbox_inches="tight")
    return [str(path) for path in paths]


def _plot_controlled(root: Path, output: Path, plt: Any) -> list[str]:
    directory = root / "controlled_perturbation"
    source = directory / "perturbation_summary.csv"
    if not _is_formal_complete(directory) or not source.is_file():
        return []
    rows = _read_csv(source)
    created: list[str] = []
    for family, title, stem in (
        ("nuisance", "Nuisance perturbation response", "controlled_nuisance_curves"),
        ("structural", "Structural perturbation response", "controlled_structural_curves"),
    ):
        figure, axis = plt.subplots(figsize=(7.2, 4.8))
        grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row["family"] == family:
                grouped[row["perturbation"]].append(row)
        for name, values in sorted(grouped.items()):
            values.sort(key=lambda row: float(row["severity_normalized"]))
            x = [float(row["severity_normalized"]) for row in values]
            y = [float(row["score_drop_from_identity_mean"]) for row in values]
            low = [float(row["score_drop_from_identity_mean_ci95_low"]) for row in values]
            high = [float(row["score_drop_from_identity_mean_ci95_high"]) for row in values]
            axis.plot(x, y, marker="o", linewidth=1.8, label=name)
            axis.fill_between(x, low, high, alpha=0.12)
        axis.set_title(title)
        axis.set_xlabel("Normalized severity")
        axis.set_ylabel("Mean score drop from identity")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=7, ncol=2)
        created.extend(_save_figure(figure, output, stem))
        plt.close(figure)
    return created


def _plot_cross_reference(root: Path, output: Path, plt: Any) -> list[str]:
    directory = root / "cross_reference"
    source = directory / "cross_reference_scores.csv"
    if not _is_formal_complete(directory) or not source.is_file():
        return []
    rows = _read_csv(source)
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[row["pair_type"]].append(float(row["prototype_structure_score"]))
    labels = [
        key
        for key in (
            "same_character_same_style_different_instance",
            "same_character_cross_style",
            "different_character_negative",
        )
        if grouped.get(key)
    ]
    if not labels:
        return []
    values = [grouped[label] for label in labels]
    display = {
        "same_character_same_style_different_instance": "Same char/style",
        "same_character_cross_style": "Same char/cross style",
        "different_character_negative": "Different char",
    }
    figure, axis = plt.subplots(figsize=(6.6, 4.6))
    axis.boxplot(values, labels=[display[label] for label in labels], showmeans=True)
    for index, samples in enumerate(values, start=1):
        rng = np.random.default_rng(20260811 + index)
        jitter = rng.normal(index, 0.035, size=len(samples))
        axis.scatter(jitter, samples, alpha=0.65, s=20)
    axis.set_title("Cross-reference structural score distributions")
    axis.set_ylabel("Prototype structure score")
    axis.grid(axis="y", alpha=0.25)
    created = _save_figure(figure, output, "cross_reference_distributions")
    plt.close(figure)
    return created


def _plot_alignment(root: Path, output: Path, plt: Any) -> list[str]:
    directory = root / "alignment_ablation"
    source = directory / "alignment_ablation_summary.csv"
    if not _is_formal_complete(directory) or not source.is_file():
        return []
    rows = _read_csv(source)
    if not rows:
        return []
    figure, axis = plt.subplots(figsize=(6.3, 4.8))
    for row in rows:
        axis.scatter(
            float(row["nuisance_mean_abs_score_drop"]),
            float(row["structural_mean_score_drop"]),
            s=70,
            label=row["alignment_variant"],
        )
    axis.set_xlabel("Nuisance penalty (lower is better)")
    axis.set_ylabel("Structural-error penalty (higher preserves error)")
    axis.set_title("Alignment robustness / error-preservation trade-off")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    created = _save_figure(figure, output, "alignment_tradeoff")
    plt.close(figure)
    return created


def _plot_feedback(root: Path, output: Path, plt: Any) -> list[str]:
    directory = root / "feedback_diagnostic"
    source = directory / "feedback_diagnostic_summary.csv"
    if not _is_formal_complete(directory) or not source.is_file():
        return []
    rows = _read_csv(source)
    metrics = (
        "required_recall_at_3",
        "strict_primary_top1",
        "canonical_local_channel_accuracy",
        "missing_extra_accuracy",
        "overlap_region_localization",
        "false_positive_specificity",
        "center_direction_wording_correctness",
    )
    labels = ("Recall@3", "Top-1", "Channel", "Missing/extra", "Region", "Specificity", "Center")
    x = np.arange(len(metrics))
    width = 0.36
    figure, axis = plt.subplots(figsize=(8.4, 4.8))
    for index, row in enumerate(rows):
        values = [
            np.nan if row.get(metric, "") == "" else float(row[metric])
            for metric in metrics
        ]
        axis.bar(
            x + (index - (len(rows) - 1) / 2) * width,
            values,
            width=width,
            label=row["rule_variant"],
        )
    axis.set_xticks(x, labels, rotation=25, ha="right")
    axis.set_ylim(0.0, 1.05)
    axis.set_ylabel("Accuracy / recall / specificity")
    axis.set_title("Paired feedback diagnostic")
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    created = _save_figure(figure, output, "feedback_diagnostic_summary")
    plt.close(figure)
    return created


def build_formal_figures(
    paper_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required; install the paper extra") from exc
    root = Path(paper_root)
    output = Path(output_dir)
    created: list[str] = []
    created.extend(_plot_controlled(root, output, plt))
    created.extend(_plot_cross_reference(root, output, plt))
    created.extend(_plot_alignment(root, output, plt))
    created.extend(_plot_feedback(root, output, plt))
    report = {
        "schema_version": 1,
        "source_policy": "completed formal run manifests only",
        "created_files": created,
        "created_figure_pairs": len(created) // 2,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "figure_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
