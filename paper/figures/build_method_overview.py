from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import (
    Circle,
    FancyArrowPatch,
    FancyBboxPatch,
    Rectangle,
    Wedge,
)

ROOT = Path(__file__).resolve().parent


def rounded_box(ax, xy, width, height, title, lines, color):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.2,
        edgecolor=color,
        facecolor=f"{color}18",
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height - 0.055,
        title,
        ha="center",
        va="top",
        fontsize=10,
        fontweight="bold",
        color=color,
    )
    ax.text(
        x + width / 2,
        y + height / 2 - 0.015,
        "\n".join(lines),
        ha="center",
        va="center",
        fontsize=8.2,
        color="#263238",
        linespacing=1.25,
    )
    return patch


def arrow(ax, start, end):
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color="#546E7A",
            shrinkA=3,
            shrinkB=3,
        )
    )


def mask_icon(ax, x, y, width, height):
    colors = ["#1976D2", "#00897B", "#F9A825", "#E64A19", "#7B1FA2"]
    for index, color in enumerate(colors):
        x0 = x + 0.012 + index * (width - 0.024) / 5
        bar_width = (width - 0.04) / 5
        ax.add_patch(
            Rectangle(
                (x0, y + 0.02),
                bar_width,
                height - 0.04,
                facecolor=f"{color}38",
                edgecolor=color,
                linewidth=0.8,
            )
        )
    ax.add_patch(
        Circle(
            (x + width - 0.035, y + height - 0.035),
            0.012,
            facecolor="#D32F2F",
            edgecolor="white",
            linewidth=0.6,
        )
    )


def polar_icon(ax, center, radius):
    x, y = center
    colors = ["#E3F2FD", "#BBDEFB", "#90CAF9", "#64B5F6"]
    for ring in range(4, 0, -1):
        ax.add_patch(
            Circle(
                (x, y),
                radius * ring / 4,
                facecolor=colors[ring - 1],
                edgecolor="#1976D2",
                linewidth=0.4,
            )
        )
    for angle in range(0, 360, 45):
        ax.add_patch(
            Wedge(
                (x, y),
                radius,
                angle,
                angle + 0.4,
                facecolor="#1976D2",
                edgecolor="none",
            )
        )


def grid_icon(ax, x, y, size):
    for row in range(3):
        for col in range(3):
            shade = 0.12 + 0.10 * ((row + 2 * col) % 4)
            ax.add_patch(
                Rectangle(
                    (x + col * size / 3, y + row * size / 3),
                    size / 3,
                    size / 3,
                    facecolor=(0.49, 0.31, 0.70, shade),
                    edgecolor="#6A1B9A",
                    linewidth=0.5,
                )
            )


def projection_icon(ax, x, y, width, height):
    values = [0.18, 0.34, 0.62, 0.82, 0.55, 0.38, 0.20]
    step = width / len(values)
    for index, value in enumerate(values):
        ax.add_patch(
            Rectangle(
                (x + index * step, y),
                step * 0.72,
                height * value,
                facecolor="#00897B",
                edgecolor="none",
            )
        )


def main():
    fig, ax = plt.subplots(figsize=(14, 5.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    boxes = [
        ((0.02, 0.46), 0.15, 0.42, "Same-character pair", ["learner image", "approved reference"], "#37474F"),
        ((0.21, 0.46), 0.15, 0.42, "Overlapping parser", ["vec1--vec5", "+ endpoint"], "#1565C0"),
        ((0.40, 0.46), 0.15, 0.42, "Constrained alignment", ["translation", "isotropic scale", "rotation within 3 deg"], "#2E7D32"),
        ((0.59, 0.46), 0.18, 0.42, "Structural comparison", ["production score", "ASDS spatial score", "component evidence"], "#6A1B9A"),
        ((0.81, 0.46), 0.17, 0.42, "Auditable output", ["six masks", "score + uncertainty", "localized findings", "optional text"], "#C62828"),
    ]
    patches = [rounded_box(ax, *item) for item in boxes]
    for first, second in pairwise(patches):
        arrow(
            ax,
            (first.get_x() + first.get_width(), first.get_y() + first.get_height() / 2),
            (second.get_x(), second.get_y() + second.get_height() / 2),
        )

    mask_icon(ax, 0.235, 0.49, 0.10, 0.10)
    polar_icon(ax, (0.625, 0.545), 0.035)
    grid_icon(ax, 0.675, 0.51, 0.072)
    projection_icon(ax, 0.602, 0.49, 0.145, 0.04)

    ax.text(
        0.5,
        0.37,
        "Validation is separated by claim",
        ha="center",
        va="center",
        fontsize=10,
        fontweight="bold",
        color="#263238",
    )
    validation = [
        ((0.05, 0.08), 0.20, 0.20, "Parsing", ["QC-clean standard", "character-disjoint", "3 models x 3 seeds"], "#1565C0"),
        ((0.29, 0.08), 0.20, 0.20, "Alignment", ["controlled perturbations", "paired ablations", "reference bootstrap"], "#2E7D32"),
        ((0.53, 0.08), 0.20, 0.20, "Human association", ["150 blinded pairs", "ICC + Spearman", "cluster bootstrap"], "#6A1B9A"),
        ((0.77, 0.08), 0.18, 0.20, "Internal validation", ["character-grouped OOF", "component ablation", "retrospective status"], "#C62828"),
    ]
    for item in validation:
        rounded_box(ax, *item)

    fig.tight_layout(pad=0.3)
    fig.savefig(ROOT / "method_overview.pdf", bbox_inches="tight")
    fig.savefig(ROOT / "method_overview.png", dpi=220, bbox_inches="tight")


if __name__ == "__main__":
    main()
