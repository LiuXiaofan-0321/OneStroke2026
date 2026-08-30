"""Shared visual language for the submission figures.

The palette is semantic rather than decorative.  Direction colours, endpoint
markers, and missing/extra overlays must remain stable across every figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties, findfont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

INK = "#202124"
MUTED = "#5F6368"
LIGHT_TEXT = "#7A8087"
GRID = "#D7DCE1"
PANEL_BG = "#F7F8FA"
BLUE = "#0072B2"
RED = "#D62728"
PURPLE = "#7851A9"
CYAN = "#00A6D6"

CHANNEL_NAMES = ("vec1", "vec2", "vec3", "vec4", "vec5", "keypoint")
CHANNEL_LABELS = (
    "vertical",
    "rising diagonal",
    "horizontal",
    "falling diagonal",
    "compound / curved / other",
    "stroke endpoints",
)
CHANNEL_COLORS_HEX = (
    "#D62728",
    "#009E73",
    "#0072B2",
    "#E69F00",
    "#7B4AB5",
    CYAN,
)
CHANNEL_COLORS = np.asarray(
    [
        (214, 39, 40),
        (0, 158, 115),
        (0, 114, 178),
        (230, 159, 0),
        (123, 74, 181),
        (0, 166, 214),
    ],
    dtype=np.uint8,
)


def _available_font(preferred: tuple[str, ...]) -> str:
    for family in preferred:
        path = findfont(family, fallback_to_default=False)
        if Path(path).is_file():
            return family
    return "DejaVu Sans"


LATIN_FONT = _available_font(("Arial", "Liberation Sans", "DejaVu Sans"))
CHINESE_FONT = _available_font(
    ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei", "Arial Unicode MS")
)
CHINESE_FONT_PROPERTIES = FontProperties(family=CHINESE_FONT)


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": LATIN_FONT,
            "font.size": 8.2,
            "axes.titlesize": 8.7,
            "axes.labelsize": 8.2,
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 7.2,
            "figure.dpi": 120,
            "savefig.dpi": 320,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.edgecolor": GRID,
            "axes.linewidth": 0.65,
            "axes.titleweight": "semibold",
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )


def panel_label(ax: plt.Axes, label: str, *, x: float = -0.03, y: float = 1.03) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9.2,
        fontweight="bold",
        color=INK,
        clip_on=False,
    )


def clean_image_axis(ax: plt.Axes) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.55)
        spine.set_color(GRID)


def save_figure(
    figure: plt.Figure,
    stem: str,
    *,
    dpi: int = 360,
    close: bool = True,
) -> tuple[Path, Path]:
    pdf = HERE / f"{stem}.pdf"
    png = HERE / f"{stem}.png"
    figure.savefig(
        pdf,
        bbox_inches="tight",
        pad_inches=0.035,
        facecolor="white",
    )
    figure.savefig(
        png,
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.035,
        facecolor="white",
    )
    if close:
        plt.close(figure)
    return pdf, png


def foreground_bounds(
    foreground: np.ndarray,
    *,
    padding: int = 18,
) -> tuple[int, int, int, int]:
    mask = np.asarray(foreground, dtype=bool)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return 0, mask.shape[0], 0, mask.shape[1]
    y0 = max(0, int(ys.min()) - padding)
    y1 = min(mask.shape[0], int(ys.max()) + padding + 1)
    x0 = max(0, int(xs.min()) - padding)
    x1 = min(mask.shape[1], int(xs.max()) + padding + 1)
    return y0, y1, x0, x1


def crop(array: np.ndarray, bounds: tuple[int, int, int, int]) -> np.ndarray:
    y0, y1, x0, x1 = bounds
    return np.asarray(array)[y0:y1, x0:x1]


def mask_union(masks: np.ndarray) -> np.ndarray:
    value = np.asarray(masks, dtype=bool)
    if value.ndim == 3 and value.shape[-1] == 6:
        return np.any(value[..., :5], axis=-1)
    if value.ndim == 3 and value.shape[0] == 6:
        return np.any(value[:5], axis=0)
    raise ValueError(f"expected [H,W,6] or [6,H,W], got {value.shape}")


def dilate_binary(mask: np.ndarray, radius: int = 2) -> np.ndarray:
    value = np.asarray(mask, dtype=bool)
    if radius <= 0:
        return value.copy()
    pad = radius
    padded = np.pad(value, pad)
    output = np.zeros_like(value)
    size = 2 * radius + 1
    for dy in range(size):
        for dx in range(size):
            output |= padded[dy : dy + value.shape[0], dx : dx + value.shape[1]]
    return output


def erode_binary(mask: np.ndarray, radius: int = 1) -> np.ndarray:
    value = np.asarray(mask, dtype=bool)
    if radius <= 0:
        return value.copy()
    pad = radius
    padded = np.pad(value, pad, constant_values=True)
    output = np.ones_like(value)
    size = 2 * radius + 1
    for dy in range(size):
        for dx in range(size):
            output &= padded[dy : dy + value.shape[0], dx : dx + value.shape[1]]
    return output


def direction_composite(
    masks: np.ndarray,
    *,
    endpoint_outline: bool = True,
    background: int = 255,
) -> np.ndarray:
    value = np.asarray(masks, dtype=bool)
    if value.ndim != 3:
        raise ValueError(f"expected three-dimensional masks, got {value.shape}")
    if value.shape[0] == 6 and value.shape[-1] != 6:
        value = np.moveaxis(value, 0, -1)
    if value.shape[-1] != 6:
        raise ValueError(f"expected six channels, got {value.shape}")

    canvas = np.full((*value.shape[:2], 3), background, dtype=np.uint8)
    direction = value[..., :5]
    active = direction.sum(axis=-1)
    for index, color in enumerate(CHANNEL_COLORS[:5]):
        canvas[np.logical_and(direction[..., index], active == 1)] = color
    canvas[active > 1] = np.asarray((18, 18, 18), dtype=np.uint8)

    keypoint = value[..., 5]
    if np.any(keypoint):
        if endpoint_outline:
            outer = dilate_binary(keypoint, 3)
            inner = dilate_binary(keypoint, 1)
            canvas[np.logical_and(outer, ~inner)] = CHANNEL_COLORS[5]
            canvas[inner] = np.asarray((255, 255, 255), dtype=np.uint8)
        else:
            canvas[dilate_binary(keypoint, 2)] = CHANNEL_COLORS[5]
    return canvas


def difference_overlay(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
) -> np.ndarray:
    user = mask_union(user_masks)
    reference = mask_union(reference_masks)
    canvas = np.full((*user.shape, 3), 255, dtype=np.uint8)
    overlap = np.logical_and(user, reference)
    missing = np.logical_and(reference, ~user)
    extra = np.logical_and(user, ~reference)
    canvas[overlap] = np.asarray((120, 81, 169), dtype=np.uint8)
    canvas[missing] = np.asarray((0, 114, 178), dtype=np.uint8)
    canvas[extra] = np.asarray((214, 39, 40), dtype=np.uint8)
    return canvas


def add_difference_legend(ax: plt.Axes, *, y: float = -0.08) -> None:
    items = (
        ("overlap", PURPLE),
        ("missing reference", BLUE),
        ("extra candidate", RED),
    )
    x = 0.02
    for label, colour in items:
        ax.add_patch(
            plt.Rectangle(
                (x, y),
                0.035,
                0.035,
                transform=ax.transAxes,
                facecolor=colour,
                edgecolor="none",
                clip_on=False,
            )
        )
        ax.text(
            x + 0.043,
            y + 0.017,
            label,
            transform=ax.transAxes,
            ha="left",
            va="center",
            fontsize=6.4,
            color=MUTED,
            clip_on=False,
        )
        x += 0.30

