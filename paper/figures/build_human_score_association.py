"""Build the development-stage score-versus-human association figure."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
INPUT = (
    ROOT
    / "artifacts"
    / "paper_ijdar"
    / "spatial_score_development"
    / "development_features_and_predictions.csv"
)
OUTPUT = Path(__file__).with_name("human_score_association.pdf")


def _read_rows() -> list[dict[str, str]]:
    with INPUT.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _binned_medians(
    scores: np.ndarray,
    ratings: np.ndarray,
    *,
    bin_count: int = 6,
) -> tuple[np.ndarray, np.ndarray]:
    order = np.argsort(scores, kind="stable")
    groups = np.array_split(order, bin_count)
    x = np.asarray([np.median(scores[group]) for group in groups])
    y = np.asarray([np.median(ratings[group]) for group in groups])
    return x, y


def main() -> None:
    rows = _read_rows()
    ratings = np.asarray([float(row["human_mean"]) for row in rows])
    panels = (
        ("production_score", "Production", "#386cb0"),
        ("coverage_aware_score", "Coverage-aware", "#f28e2b"),
        ("spatial_structure_score", "ASDS", "#2ca02c"),
    )

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.labelsize": 9,
            "axes.titlesize": 9.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
        }
    )
    figure, axes = plt.subplots(1, 3, figsize=(7.15, 2.35), sharey=True)
    for axis, (field, title, color) in zip(axes, panels, strict=True):
        scores = np.asarray([float(row[field]) for row in rows])
        rho = float(spearmanr(scores, ratings).statistic)
        axis.scatter(
            scores,
            ratings,
            s=11,
            facecolor=color,
            edgecolor="none",
            alpha=0.42,
            rasterized=True,
        )
        median_x, median_y = _binned_medians(scores, ratings)
        axis.plot(
            median_x,
            median_y,
            color="#202020",
            marker="o",
            markersize=3.0,
            linewidth=1.1,
            zorder=4,
        )
        axis.set_title(f"{title}  ($\\rho$={rho:.3f})")
        axis.set_xlabel("Structural score")
        axis.set_xlim(-2, 102)
        axis.set_ylim(0.8, 5.2)
        axis.set_yticks([1, 2, 3, 4, 5])
        axis.grid(color="#d9d9d9", linewidth=0.55, alpha=0.65)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
    axes[0].set_ylabel("Mean blinded human rating")
    figure.tight_layout(w_pad=1.0)
    figure.savefig(OUTPUT, bbox_inches="tight")
    print(OUTPUT)


if __name__ == "__main__":
    main()
