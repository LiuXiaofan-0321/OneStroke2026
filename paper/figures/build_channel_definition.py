"""Build the six-channel annotation-definition figure from recovered GT.

The figure deliberately uses the historical stroke-isolated source and its
deterministically generated masks. It does not use model predictions.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SAMPLE_DIR = ROOT / "data" / "legacy_gt_v1" / "output_img" / "33" / "18"

CHANNEL_NAMES = ["vec1", "vec2", "vec3", "vec4", "vec5", "endpoint"]
CHANNEL_LABELS = [
    "vertical",
    "rising diagonal",
    "horizontal",
    "falling diagonal",
    "compound / other",
    "stroke endpoints",
]
COLORS = np.asarray(
    [
        (222, 45, 38),
        (0, 166, 118),
        (33, 113, 181),
        (238, 174, 33),
        (138, 76, 181),
        (20, 175, 70),
    ],
    dtype=np.uint8,
)


def foreground_bounds(array: np.ndarray, padding: int = 18) -> tuple[int, int, int, int]:
    if array.ndim == 3:
        foreground = np.any(array < 245, axis=-1)
    else:
        foreground = array > 0
    ys, xs = np.where(foreground)
    if len(xs) == 0:
        return 0, array.shape[0], 0, array.shape[1]
    y0 = max(0, int(ys.min()) - padding)
    y1 = min(array.shape[0], int(ys.max()) + padding + 1)
    x0 = max(0, int(xs.min()) - padding)
    x1 = min(array.shape[1], int(xs.max()) + padding + 1)
    return y0, y1, x0, x1


def crop_to_bounds(
    array: np.ndarray,
    bounds: tuple[int, int, int, int],
) -> np.ndarray:
    y0, y1, x0, x1 = bounds
    return array[y0:y1, x0:x1]


def render_mask(mask: np.ndarray, color: np.ndarray) -> np.ndarray:
    canvas = np.full((*mask.shape, 3), 255, dtype=np.uint8)
    canvas[mask] = color
    return canvas


def render_overlap(masks: np.ndarray) -> np.ndarray:
    direction = masks[..., :5].astype(bool)
    canvas = np.full((*direction.shape[:2], 3), 255, dtype=np.uint8)
    active_count = direction.sum(axis=-1)
    single = active_count == 1
    for index, color in enumerate(COLORS[:5]):
        canvas[single & direction[..., index]] = color
    canvas[active_count > 1] = np.asarray((20, 20, 20), dtype=np.uint8)
    return canvas


def draw_direction_legend(ax: plt.Axes) -> None:
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.plot([-1.05, 1.05], [0, 0], "--", color="#b0b0b0", lw=0.8)
    ax.plot([0, 0], [-1.05, 1.05], "--", color="#b0b0b0", lw=0.8)
    ax.plot([-0.82, 0.82], [-0.82, 0.82], "--", color="#d0d0d0", lw=0.7)
    ax.plot([-0.82, 0.82], [0.82, -0.82], "--", color="#d0d0d0", lw=0.7)

    arrows = [
        ((0, -0.92), (0, 0.92), 0),
        ((-0.78, -0.78), (0.78, 0.78), 1),
        ((-0.95, 0), (0.95, 0), 2),
        ((-0.78, 0.78), (0.78, -0.78), 3),
    ]
    for start, end, index in arrows:
        color = COLORS[index] / 255
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={"arrowstyle": "-|>", "lw": 2.4, "color": color},
        )
    positions = [(0.17, 0.92), (0.72, 0.68), (0.93, 0.17), (0.72, -0.75)]
    for index, (x, y) in enumerate(positions):
        ax.text(
            x,
            y,
            f"vec{index + 1}",
            color=COLORS[index] / 255,
            fontsize=8.5,
            fontweight="bold",
            ha="center",
            va="center",
        )
    ax.text(
        0,
        -1.12,
        "vec5: compound / other",
        color=COLORS[4] / 255,
        fontsize=8,
        fontweight="bold",
        ha="center",
    )
    ax.set_title("(a) Fixed direction families", fontsize=9, fontweight="bold")


def main() -> None:
    stacked = np.load(SAMPLE_DIR / "0.npy").astype(bool)
    full_image = np.asarray(Image.open(SAMPLE_DIR / "0.jpg").convert("RGB"))
    isolated = np.asarray(Image.open(SAMPLE_DIR / "4.jpg").convert("RGB"))
    common_bounds = foreground_bounds(np.any(stacked[..., :5], axis=-1), padding=20)
    isolated_bounds = foreground_bounds(isolated, padding=25)

    fig = plt.figure(figsize=(11.3, 5.15), constrained_layout=True)
    grid = fig.add_gridspec(2, 6, height_ratios=[1.15, 1.0])

    legend_ax = fig.add_subplot(grid[0, 0:2])
    draw_direction_legend(legend_ax)

    isolated_ax = fig.add_subplot(grid[0, 2])
    isolated_ax.imshow(crop_to_bounds(isolated, isolated_bounds))
    isolated_ax.set_title("(b) Isolated stroke\nwith endpoint markers", fontsize=8.5)
    isolated_ax.axis("off")

    input_ax = fig.add_subplot(grid[0, 3])
    input_ax.imshow(crop_to_bounds(full_image, common_bounds), cmap="gray")
    input_ax.set_title("(c) Complete input", fontsize=8.5)
    input_ax.axis("off")

    overlap_ax = fig.add_subplot(grid[0, 4:6])
    overlap_ax.imshow(crop_to_bounds(render_overlap(stacked), common_bounds))
    overlap_ax.set_title(
        "(d) Direction overlay\nblack = multi-channel overlap",
        fontsize=8.5,
    )
    overlap_ax.axis("off")

    for index, (name, label) in enumerate(zip(CHANNEL_NAMES, CHANNEL_LABELS)):
        ax = fig.add_subplot(grid[1, index])
        mask = stacked[..., index]
        if index == 5:
            # Dilate only for print visibility; the stored target is unchanged.
            padded = np.pad(mask, 2)
            shown = np.zeros_like(mask)
            for dy in range(5):
                for dx in range(5):
                    shown |= padded[dy : dy + mask.shape[0], dx : dx + mask.shape[1]]
            mask = shown
        ax.imshow(crop_to_bounds(render_mask(mask, COLORS[index]), common_bounds))
        ax.set_title(
            f"({chr(ord('e') + index)}) {name}\n{label}",
            fontsize=8.1,
            color=COLORS[index] / 255,
            fontweight="bold",
        )
        ax.axis("off")

    fig.suptitle(
        "Recovered six-channel annotation protocol (sample 33/18)",
        fontsize=11,
        fontweight="bold",
    )
    fig.savefig(HERE / "channel_definition.pdf", bbox_inches="tight")
    fig.savefig(HERE / "channel_definition.png", dpi=260, bbox_inches="tight")


if __name__ == "__main__":
    main()
