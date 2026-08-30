"""Build the real-data submission figures that do not require model inference.

Figure 4 is intentionally delegated to ``build_segmentation_qualitative.py``:
that script verifies the SHA-256 of every formal Task-1 checkpoint and refuses
substitution.  This file builds Figures 1--3 and 5--7 from frozen local data,
reference caches, perturbation contracts, and human-rating artifacts.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from onestroke_model.controlled_perturbations import (  # noqa: E402
    PreparedReferenceScorer,
    apply_perturbation,
)
from onestroke_model.feedback_diagnostic_rules import diagnostic_findings  # noqa: E402
from onestroke_model.spatial_structure_score import (  # noqa: E402
    compute_spatial_structure_components,
    grid_occupancy_signature,
    polar_occupancy_signature,
    projection_similarity,
    spatial_structure_score,
)

from figure_style import (  # noqa: E402
    BLUE,
    CHANNEL_COLORS,
    CHANNEL_COLORS_HEX,
    CHANNEL_LABELS,
    CHANNEL_NAMES,
    CHINESE_FONT_PROPERTIES,
    CYAN,
    GRID,
    INK,
    LIGHT_TEXT,
    MUTED,
    PANEL_BG,
    PURPLE,
    RED,
    add_difference_legend,
    clean_image_axis,
    configure_matplotlib,
    crop,
    difference_overlay,
    dilate_binary,
    direction_composite,
    foreground_bounds,
    mask_union,
    panel_label,
    save_figure,
)

configure_matplotlib()

REFERENCE_INDEX = ROOT / "references/cache/segformer_b2_v1/index.json"
REFERENCE_IMAGE_ROOT = ROOT / "references"
QC_AUDIT = ROOT / "artifacts/data_qc/dataset_qc_audit_v1.csv"
LEGACY_DATA_ROOT = ROOT / "data/legacy_gt_v1/output_img"
CHARACTER_MAP = ROOT / "artifacts/paper_ijdar/course_scoring_scope/legacy_character_map.csv"
FROZEN_PAIRS = (
    ROOT
    / "artifacts/paper_ijdar/expert_validation/frozen_study_v1"
    / "frozen_expert_pairs_v1.csv"
)
DIRECT_INK_ROWS = ROOT / "artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_pairs.csv"
ALIGNMENT_ROWS = (
    ROOT / "artifacts/paper_ijdar/alignment_ablation/alignment_ablation_results.csv"
)
FEEDBACK_ROWS = (
    ROOT / "artifacts/paper_ijdar/feedback_diagnostic/feedback_diagnostic_results.csv"
)
CROSS_REFERENCE_PAIRS = (
    ROOT / "artifacts/paper_ijdar/cross_reference/cross_reference_pairs.csv"
)

FIGURE_MANIFEST: dict[str, Any] = {
    "schema_version": 1,
    "selection_principle": (
        "All examples are selected by deterministic rules documented per figure; "
        "no panel is chosen by visual preference."
    ),
    "figures": {},
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def resolve_data_path(value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == "data":
        return ROOT / path
    return ROOT / "data" / path


def load_rgb(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"))


def load_gt_stack(sample_id: str) -> np.ndarray:
    char_id, sample_index = sample_id.split("/")
    return np.load(
        LEGACY_DATA_ROOT / char_id / sample_index / "0.npy",
        allow_pickle=False,
    ).astype(bool)


def load_gt_image(sample_id: str) -> np.ndarray:
    char_id, sample_index = sample_id.split("/")
    return load_rgb(LEGACY_DATA_ROOT / char_id / sample_index / "0.jpg")


def reference_entries() -> dict[str, dict[str, Any]]:
    payload = json.loads(REFERENCE_INDEX.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, Any]] = {}
    for item in payload["references"]:
        entries[str(item["reference_id"])] = dict(item)
    return entries


def load_reference_masks(entry: Mapping[str, Any]) -> np.ndarray:
    cache_path = ROOT / "references/cache/segformer_b2_v1" / str(entry["cache_path"])
    with np.load(cache_path, allow_pickle=False) as payload:
        masks = np.asarray(payload["binary_masks"], dtype=bool)
    if masks.shape != (512, 512, 6):
        raise ValueError(f"unexpected reference cache shape: {cache_path} {masks.shape}")
    return masks


def load_reference_image(entry: Mapping[str, Any]) -> np.ndarray:
    return load_rgb(REFERENCE_IMAGE_ROOT / str(entry["source_image_path"]))


def arrow_between(
    figure: plt.Figure,
    first: plt.Axes,
    second: plt.Axes,
    *,
    color: str = "#7C858E",
) -> None:
    first_box = first.get_position()
    second_box = second.get_position()
    figure.add_artist(
        FancyArrowPatch(
            (first_box.x1 + 0.003, (first_box.y0 + first_box.y1) / 2),
            (second_box.x0 - 0.003, (second_box.y0 + second_box.y1) / 2),
            transform=figure.transFigure,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=0.9,
            color=color,
            clip_on=False,
        )
    )


def stack_pair_images(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    target = max(first.shape[0], second.shape[0])

    def fit(image: np.ndarray) -> np.ndarray:
        canvas = np.full((target, target, 3), 255, dtype=np.uint8)
        height, width = image.shape[:2]
        scale = min(target / height, target / width)
        resized = np.asarray(
            Image.fromarray(image).resize(
                (max(1, round(width * scale)), max(1, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
        )
        y0 = (target - resized.shape[0]) // 2
        x0 = (target - resized.shape[1]) // 2
        canvas[y0 : y0 + resized.shape[0], x0 : x0 + resized.shape[1]] = resized
        return canvas

    gap = np.full((target, max(8, target // 30), 3), 235, dtype=np.uint8)
    return np.concatenate((fit(first), gap, fit(second)), axis=1)


def render_union(mask: np.ndarray) -> np.ndarray:
    foreground = np.asarray(mask, dtype=bool)
    canvas = np.full((*foreground.shape, 3), 255, dtype=np.uint8)
    canvas[foreground] = np.asarray((28, 31, 34), dtype=np.uint8)
    return canvas


def draw_endpoint_outlines(ax: plt.Axes, keypoint_mask: np.ndarray) -> None:
    keypoints = np.asarray(keypoint_mask, dtype=bool)
    ys, xs = np.nonzero(keypoints)
    if len(xs) == 0:
        return
    points = np.column_stack((xs, ys))
    # Stored endpoint targets can occupy a small blob.  Cluster them only for display.
    remaining = set(range(len(points)))
    centres: list[tuple[float, float]] = []
    while remaining:
        seed = remaining.pop()
        cluster = [seed]
        queue = [seed]
        while queue:
            current = queue.pop()
            distances = np.max(np.abs(points[list(remaining)] - points[current]), axis=1)
            neighbours = [
                index
                for index, distance in zip(list(remaining), distances, strict=True)
                if distance <= 4
            ]
            for neighbour in neighbours:
                remaining.remove(neighbour)
                queue.append(neighbour)
                cluster.append(neighbour)
        centre = points[cluster].mean(axis=0)
        centres.append((float(centre[0]), float(centre[1])))
    for x, y in centres:
        ax.add_patch(
            Circle((x, y), radius=7.0, fill=False, edgecolor=CYAN, linewidth=1.25)
        )


def figure1_pipeline() -> tuple[Path, Path]:
    """Introduction figure: real same-character pair through the full pipeline."""

    entries = reference_entries()
    cross_rows = read_csv(CROSS_REFERENCE_PAIRS)
    pair = next(
        row
        for row in cross_rows
        if row["pair_type"] == "same_character_cross_style"
        and row["candidate_char"] == "亮"
    )
    candidate_entry = entries[pair["candidate_reference_id"]]
    reference_entry = entries[pair["reference_reference_id"]]
    candidate_masks = load_reference_masks(candidate_entry)
    reference_masks = load_reference_masks(reference_entry)
    candidate_image = load_reference_image(candidate_entry)
    reference_image = load_reference_image(reference_entry)

    evidence, aligned_reference = PreparedReferenceScorer(reference_masks).score(
        candidate_masks
    )
    overlap_count = candidate_masks[..., :5].sum(axis=-1)
    overlap_bounds = foreground_bounds(overlap_count > 1, padding=28)
    all_bounds = foreground_bounds(
        np.logical_or(mask_union(candidate_masks), mask_union(aligned_reference)),
        padding=25,
    )
    direction_values = evidence["direction_dice"]
    worst_direction = min(direction_values, key=direction_values.get)

    figure = plt.figure(figsize=(13.4, 4.15), constrained_layout=False)
    grid = figure.add_gridspec(
        1,
        5,
        width_ratios=(1.18, 1.05, 1.08, 1.15, 1.16),
        wspace=0.29,
        left=0.025,
        right=0.985,
        top=0.88,
        bottom=0.13,
    )
    axes = [figure.add_subplot(grid[0, index]) for index in range(5)]

    axes[0].imshow(stack_pair_images(reference_image, candidate_image))
    axes[0].set_title("Same character, distinct structure", pad=6)
    axes[0].text(
        0.23,
        -0.065,
        "Ouyang Xun reference",
        transform=axes[0].transAxes,
        ha="center",
        va="top",
        fontsize=6.6,
        color=MUTED,
    )
    axes[0].text(
        0.78,
        -0.065,
        "Wang Xizhi candidate",
        transform=axes[0].transAxes,
        ha="center",
        va="top",
        fontsize=6.6,
        color=MUTED,
    )
    clean_image_axis(axes[0])
    panel_label(axes[0], "(a)")

    candidate_composite = direction_composite(candidate_masks)
    candidate_bounds = foreground_bounds(mask_union(candidate_masks), padding=24)
    axes[1].imshow(crop(candidate_composite, candidate_bounds))
    axes[1].set_title("Overlapping stroke parsing", pad=6)
    overlap_inset = inset_axes(
        axes[1],
        width="39%",
        height="39%",
        loc="lower right",
        borderpad=0.7,
    )
    overlap_inset.imshow(crop(candidate_composite, overlap_bounds))
    overlap_inset.set_xticks([])
    overlap_inset.set_yticks([])
    for spine in overlap_inset.spines.values():
        spine.set_linewidth(0.65)
        spine.set_color(INK)
    overlap_inset.text(
        0.03,
        0.97,
        "overlap zoom",
        transform=overlap_inset.transAxes,
        ha="left",
        va="top",
        fontsize=5.8,
        color=INK,
        bbox={
            "boxstyle": "round,pad=0.10",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.82,
        },
    )
    axes[1].text(
        0.5,
        -0.065,
        "black pixels activate >1 direction channel",
        transform=axes[1].transAxes,
        ha="center",
        va="top",
        fontsize=6.5,
        color=MUTED,
    )
    clean_image_axis(axes[1])
    panel_label(axes[1], "(b)")

    axes[2].imshow(crop(difference_overlay(candidate_masks, aligned_reference), all_bounds))
    axes[2].set_title("Constrained global alignment", pad=6)
    axes[2].text(
        0.5,
        -0.065,
        (
            f"s={evidence['selected_transform']['scale']:.2f}, "
            f"r={evidence['selected_transform']['rotation_degrees']:.0f} deg"
        ),
        transform=axes[2].transAxes,
        ha="center",
        va="top",
        fontsize=6.6,
        color=MUTED,
    )
    for x, label, colour in (
        (0.03, "overlap", PURPLE),
        (0.36, "missing", BLUE),
        (0.68, "extra", RED),
    ):
        axes[2].text(
            x,
            -0.145,
            f"■ {label}",
            transform=axes[2].transAxes,
            ha="left",
            va="top",
            fontsize=6.1,
            color=colour,
            clip_on=False,
        )
    clean_image_axis(axes[2])
    panel_label(axes[2], "(c)")

    user_ink = mask_union(candidate_masks)
    aligned_ink = mask_union(aligned_reference)
    axes[3].imshow(crop(render_union(user_ink), all_bounds))
    bounds_height = all_bounds[1] - all_bounds[0]
    bounds_width = all_bounds[3] - all_bounds[2]
    for fraction in (1 / 3, 2 / 3):
        axes[3].axhline(bounds_height * fraction, color=BLUE, lw=0.65, alpha=0.8)
        axes[3].axvline(bounds_width * fraction, color=BLUE, lw=0.65, alpha=0.8)
    components = compute_spatial_structure_components(candidate_masks, aligned_reference)
    axes[3].set_title("Spatial + directional evidence", pad=6)
    axes[3].text(
        0.5,
        -0.06,
        (
            f"polar {components.polar_js_similarity:.2f}  |  "
            f"grid {components.grid_js_similarity:.2f}  |  "
            f"projection {components.projection_js_similarity:.2f}"
        ),
        transform=axes[3].transAxes,
        ha="center",
        va="top",
        fontsize=6.3,
        color=MUTED,
    )
    clean_image_axis(axes[3])
    panel_label(axes[3], "(d)")

    axes[4].axis("off")
    axes[4].add_patch(
        FancyBboxPatch(
            (0.02, 0.04),
            0.96,
            0.91,
            boxstyle="round,pad=0.025,rounding_size=0.025",
            facecolor=PANEL_BG,
            edgecolor=GRID,
            linewidth=0.8,
            transform=axes[4].transAxes,
        )
    )
    axes[4].text(
        0.07,
        0.86,
        "Auditable output",
        transform=axes[4].transAxes,
        fontsize=9.2,
        fontweight="bold",
    )
    output_lines = (
        f"Production score: {evidence['prototype_structure_score']:.1f}/100",
        f"Weakest direction: {worst_direction}",
        f"Direction Dice: {direction_values[worst_direction]:.2f}",
        f"Ink IoU: {evidence['ink_iou']:.2f}",
        f"Endpoint F1 (3 px): {evidence['keypoint_tolerant_f1_radius_3']:.2f}",
        "",
        "Return: six masks, transform,",
        "missing/extra regions, and bounded",
        "evidence for text realization.",
    )
    axes[4].text(
        0.07,
        0.75,
        "\n".join(output_lines),
        transform=axes[4].transAxes,
        fontsize=7.3,
        linespacing=1.35,
        va="top",
        color=INK,
    )
    panel_label(axes[4], "(e)", x=-0.01, y=1.01)

    for first, second in zip(axes[:-1], axes[1:], strict=True):
        arrow_between(figure, first, second)

    figure.suptitle(
        "Reference-conditioned structural assessment separates perception, alignment, and diagnosis",
        fontsize=11.2,
        fontweight="bold",
        y=0.975,
    )
    FIGURE_MANIFEST["figures"]["figure1_pipeline"] = {
        "candidate_reference_id": pair["candidate_reference_id"],
        "reference_reference_id": pair["reference_reference_id"],
        "target_char": "亮",
        "selection_rule": "fixed same-character cross-style pair for target character 亮",
        "model_cache": str(REFERENCE_INDEX.relative_to(ROOT)).replace("\\", "/"),
    }
    return save_figure(figure, "figure1_pipeline")


def qc_clean_representatives() -> list[dict[str, str]]:
    rows = read_csv(QC_AUDIT)
    by_character: defaultdict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["decision"] == "KEEP" and int(row["char_id"]) < 40:
            by_character[int(row["char_id"])].append(row)
    selected: list[dict[str, str]] = []
    for char_id in range(40):
        candidates = sorted(
            by_character[char_id],
            key=lambda row: (int(row["sample_index"]), row["sample_id"]),
        )
        if not candidates:
            raise ValueError(f"no QC-clean sample for char_id={char_id}")
        selected.append(candidates[0])
    return selected


def draw_qc_flow(ax: plt.Axes) -> None:
    ax.axis("off")
    values = (
        ("894", "sample directories", "#E8EEF5"),
        ("840", "complete six-channel GT", "#E7F3EF"),
        ("-12", "image/GT mismatches", "#FCE8E6"),
        ("-59", "non-canonical exact duplicates", "#FFF3D6"),
        ("769", "QC-clean observations", "#EDE7F6"),
    )
    positions = np.linspace(0.02, 0.82, len(values))
    for index, ((number, label, fill), x) in enumerate(zip(values, positions, strict=True)):
        ax.add_patch(
            FancyBboxPatch(
                (x, 0.25),
                0.16,
                0.55,
                boxstyle="round,pad=0.01,rounding_size=0.02",
                transform=ax.transAxes,
                facecolor=fill,
                edgecolor=GRID,
                linewidth=0.7,
            )
        )
        ax.text(
            x + 0.08,
            0.62,
            number,
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=13.5,
            fontweight="bold",
            color=INK,
        )
        ax.text(
            x + 0.08,
            0.39,
            label,
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=6.4,
            color=MUTED,
            wrap=True,
        )
        if index < len(values) - 1:
            ax.annotate(
                "",
                xy=(positions[index + 1] - 0.008, 0.525),
                xytext=(x + 0.168, 0.525),
                xycoords=ax.transAxes,
                arrowprops={
                    "arrowstyle": "-|>",
                    "lw": 0.75,
                    "color": LIGHT_TEXT,
                },
            )
    ax.text(
        0.02,
        0.93,
        "Semantic QC and exact-duplicate control",
        transform=ax.transAxes,
        fontsize=8.7,
        fontweight="bold",
        va="top",
    )
    ax.text(
        0.02,
        0.08,
        "No exact duplicate group crosses either frozen split.",
        transform=ax.transAxes,
        fontsize=6.6,
        color=MUTED,
        va="bottom",
    )


def figure2_dataset_overview() -> tuple[Path, Path]:
    """Dataset resources: acquisition, all 40 identities, QC, external references."""

    character_map = {
        int(row["char_id"]): row["target_char"] for row in read_csv(CHARACTER_MAP)
    }
    representatives = qc_clean_representatives()
    acquisition_id = "33/18"
    acquisition_dir = LEGACY_DATA_ROOT / "33" / "18"
    full_image = load_rgb(acquisition_dir / "0.jpg")
    isolated_files = sorted(
        path
        for path in acquisition_dir.glob("*.jpg")
        if path.name != "0.jpg"
    )
    isolated_image = load_rgb(isolated_files[0])
    acquisition_masks = load_gt_stack(acquisition_id)

    entries = reference_entries()
    cross_pairs = [
        row
        for row in read_csv(CROSS_REFERENCE_PAIRS)
        if row["pair_type"] == "same_character_cross_style"
    ]

    figure = plt.figure(figsize=(13.4, 10.5), constrained_layout=False)
    outer = figure.add_gridspec(
        4,
        1,
        height_ratios=(1.55, 4.9, 1.05, 1.45),
        hspace=0.26,
        left=0.035,
        right=0.985,
        top=0.965,
        bottom=0.035,
    )

    acquisition_grid = outer[0].subgridspec(1, 4, wspace=0.14)
    acquisition_panels = (
        (full_image, "Complete character"),
        (isolated_image, "Isolated stroke"),
        (direction_composite(acquisition_masks), "Composed direction masks"),
        (render_union(acquisition_masks[..., 5]), "Endpoint target"),
    )
    for index, (image, title) in enumerate(acquisition_panels):
        ax = figure.add_subplot(acquisition_grid[0, index])
        if index < 2:
            foreground = np.any(image < 245, axis=-1)
        elif index == 2:
            foreground = mask_union(acquisition_masks)
        else:
            foreground = acquisition_masks[..., 5]
        bounds = foreground_bounds(foreground, padding=20)
        ax.imshow(crop(image, bounds))
        ax.set_title(f"({chr(ord('a') + index)}) {title}", pad=4)
        clean_image_axis(ax)
        if index == 2:
            ax.text(
                0.5,
                -0.07,
                "black = overlapping direction labels",
                transform=ax.transAxes,
                ha="center",
                va="top",
                fontsize=6.4,
                color=MUTED,
            )
        if index == 3:
            draw_endpoint_outlines(ax, crop(acquisition_masks[..., 5], bounds))

    atlas = outer[1].subgridspec(5, 8, wspace=0.035, hspace=0.055)
    atlas_ids: list[str] = []
    for position, row in enumerate(representatives):
        char_id = int(row["char_id"])
        atlas_ids.append(row["sample_id"])
        image = load_rgb(
            LEGACY_DATA_ROOT / str(row["image_relative_path"]).replace("\\", "/")
        )
        foreground = np.any(image < 245, axis=-1)
        bounds = foreground_bounds(foreground, padding=14)
        ax = figure.add_subplot(atlas[position // 8, position % 8])
        ax.imshow(crop(image, bounds))
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_linewidth(0.42)
            spine.set_color(GRID)
        ax.text(
            0.5,
            0.015,
            f"{character_map[char_id]}  ID {char_id}",
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=6.0,
            fontproperties=CHINESE_FONT_PROPERTIES,
            color=INK,
            bbox={
                "boxstyle": "round,pad=0.12",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.86,
            },
        )
    atlas_anchor = figure.add_subplot(outer[1], frame_on=False)
    atlas_anchor.set_xticks([])
    atlas_anchor.set_yticks([])
    atlas_anchor.patch.set_alpha(0)
    atlas_anchor.text(
        0.0,
        1.055,
        "(e) One deterministic QC-clean representative from each of 40 character identities",
        transform=atlas_anchor.transAxes,
        fontsize=9.0,
        fontweight="bold",
        va="bottom",
    )

    qc_ax = figure.add_subplot(outer[2])
    draw_qc_flow(qc_ax)
    panel_label(qc_ax, "(f)", x=-0.005, y=1.0)

    library = outer[3].subgridspec(2, 8, width_ratios=(0.65, 1, 1, 1, 1, 1, 1, 1))
    style_labels = (
        ("Ouyang Xun\nregular", "ouyang_xun_regular_calli_tongji_beta"),
        ("Wang Xizhi\nrunning", "wang_xizhi_running_calli_tongji_beta"),
    )
    style_images: dict[tuple[str, str], np.ndarray] = {}
    for pair in cross_pairs:
        for key in ("candidate_reference_id", "reference_reference_id"):
            entry = entries[pair[key]]
            style_images[(str(entry["style_id"]), str(entry["target_char"]))] = (
                load_reference_image(entry)
            )
    for row_index, (label, style_id) in enumerate(style_labels):
        label_ax = figure.add_subplot(library[row_index, 0])
        label_ax.axis("off")
        label_ax.text(
            0.95,
            0.5,
            label,
            ha="right",
            va="center",
            fontsize=7.1,
            fontweight="semibold",
        )
        for column_index, pair in enumerate(cross_pairs, start=1):
            char = pair["candidate_char"]
            ax = figure.add_subplot(library[row_index, column_index])
            image = style_images[(style_id, char)]
            foreground = np.any(image < 245, axis=-1)
            ax.imshow(crop(image, foreground_bounds(foreground, padding=8)))
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_linewidth(0.4)
                spine.set_color(GRID)
            if row_index == 1:
                ax.text(
                    0.5,
                    -0.04,
                    char,
                    transform=ax.transAxes,
                    ha="center",
                    va="top",
                    fontsize=6.6,
                    fontproperties=CHINESE_FONT_PROPERTIES,
                )
    library_anchor = figure.add_subplot(outer[3], frame_on=False)
    library_anchor.set_xticks([])
    library_anchor.set_yticks([])
    library_anchor.patch.set_alpha(0)
    library_anchor.text(
        0.0,
        1.08,
        "(g) External reference library: all seven natural same-character cross-style pairs",
        transform=library_anchor.transAxes,
        fontsize=8.9,
        fontweight="bold",
        va="bottom",
    )
    library_anchor.text(
        1.0,
        -0.10,
        "Calli-Tongji Beta, CC-BY-NC-4.0; external references are not segmentation GT.",
        transform=library_anchor.transAxes,
        fontsize=6.4,
        color=MUTED,
        ha="right",
        va="top",
    )

    FIGURE_MANIFEST["figures"]["figure2_dataset_overview"] = {
        "acquisition_sample_id": acquisition_id,
        "atlas_sample_ids": atlas_ids,
        "atlas_selection_rule": (
            "minimum sample_index among dataset_qc_v1 rows with decision=KEEP "
            "for each char_id 0--39"
        ),
        "external_reference_pairs": [row["pair_id"] for row in cross_pairs],
        "external_selection_rule": "all frozen same_character_cross_style pairs",
    }
    return save_figure(figure, "figure2_dataset_overview", dpi=400)


def direction_guide(ax: plt.Axes) -> None:
    ax.set_xlim(-1.2, 1.2)
    ax.set_ylim(-1.2, 1.2)
    ax.set_aspect("equal")
    ax.axis("off")
    for angle, alpha in ((0, 0.9), (90, 0.9), (45, 0.55), (-45, 0.55)):
        radians = np.deg2rad(angle)
        dx, dy = np.cos(radians), np.sin(radians)
        ax.plot(
            [-dx, dx],
            [-dy, dy],
            "--",
            color=GRID,
            lw=0.65,
            alpha=alpha,
        )
    arrows = (
        ((0, -0.95), (0, 0.95), 0),
        ((-0.80, -0.80), (0.80, 0.80), 1),
        ((-1.0, 0), (1.0, 0), 2),
        ((-0.80, 0.80), (0.80, -0.80), 3),
    )
    for start, end, index in arrows:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "-|>",
                "lw": 2.2,
                "color": CHANNEL_COLORS_HEX[index],
            },
        )
    labels = (
        (0.14, 0.98, "left"),
        (0.98, 0.92, "right"),
        (0.98, 0.14, "right"),
        (0.98, -0.92, "right"),
    )
    for index, (x, y, horizontal_alignment) in enumerate(labels):
        ax.text(
            x,
            y,
            f"vec{index + 1}",
            color=CHANNEL_COLORS_HEX[index],
            fontsize=7.4,
            fontweight="bold",
            ha=horizontal_alignment,
            va="center",
            bbox={
                "boxstyle": "round,pad=0.08",
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.88,
            },
        )
    ax.text(
        0,
        -1.13,
        "vec5 = compound / curved / other",
        color=CHANNEL_COLORS_HEX[4],
        fontsize=6.7,
        fontweight="semibold",
        ha="center",
    )


def figure3_channel_definition() -> tuple[Path, Path]:
    """Exact six-channel protocol with crossing and endpoint zooms."""

    sample_id = "33/18"
    sample_dir = LEGACY_DATA_ROOT / "33" / "18"
    masks = load_gt_stack(sample_id)
    full_image = load_gt_image(sample_id)
    isolated_files = sorted(
        path for path in sample_dir.glob("*.jpg") if path.name != "0.jpg"
    )
    isolated_image = load_rgb(isolated_files[0])
    common_bounds = foreground_bounds(mask_union(masks), padding=20)
    isolated_bounds = foreground_bounds(np.any(isolated_image < 245, axis=-1), padding=18)
    overlap = masks[..., :5].sum(axis=-1) > 1
    overlap_bounds = foreground_bounds(overlap, padding=24)
    endpoint_bounds = foreground_bounds(masks[..., 5], padding=35)

    figure = plt.figure(figsize=(13.4, 5.75), constrained_layout=False)
    grid = figure.add_gridspec(
        2,
        6,
        height_ratios=(1.10, 1.0),
        wspace=0.10,
        hspace=0.34,
        left=0.025,
        right=0.985,
        top=0.91,
        bottom=0.055,
    )

    guide_ax = figure.add_subplot(grid[0, 0])
    direction_guide(guide_ax)
    guide_ax.set_title("(a) Fixed direction families", pad=4)

    isolated_ax = figure.add_subplot(grid[0, 1])
    isolated_ax.imshow(crop(isolated_image, isolated_bounds))
    isolated_ax.set_title("(b) Isolated stroke source", pad=4)
    clean_image_axis(isolated_ax)

    input_ax = figure.add_subplot(grid[0, 2])
    input_ax.imshow(crop(full_image, common_bounds))
    input_ax.set_title("(c) Complete character", pad=4)
    clean_image_axis(input_ax)

    overlay_ax = figure.add_subplot(grid[0, 3])
    overlay_ax.imshow(crop(direction_composite(masks), common_bounds))
    overlay_ax.set_title("(d) Composed annotation", pad=4)
    overlay_ax.text(
        0.5,
        0.015,
        "black = simultaneous direction labels",
        transform=overlay_ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=6.2,
        color=MUTED,
        bbox={
            "boxstyle": "round,pad=0.12",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.82,
        },
    )
    clean_image_axis(overlay_ax)

    crossing_ax = figure.add_subplot(grid[0, 4])
    crossing_ax.imshow(crop(direction_composite(masks), overlap_bounds))
    crossing_ax.set_title("(e) Crossing zoom", pad=4)
    clean_image_axis(crossing_ax)
    crossing_ax.add_patch(
        Rectangle(
            (0.5, 0.5),
            max(1, overlap_bounds[3] - overlap_bounds[2] - 1),
            max(1, overlap_bounds[1] - overlap_bounds[0] - 1),
            fill=False,
            edgecolor=INK,
            linewidth=0.75,
        )
    )

    endpoint_ax = figure.add_subplot(grid[0, 5])
    endpoint_crop = crop(full_image, endpoint_bounds)
    endpoint_ax.imshow(endpoint_crop)
    draw_endpoint_outlines(endpoint_ax, crop(masks[..., 5], endpoint_bounds))
    endpoint_ax.set_title("(f) Endpoint zoom", pad=4)
    endpoint_ax.text(
        0.5,
        0.015,
        "cyan circles are display outlines only",
        transform=endpoint_ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=6.1,
        color=MUTED,
        bbox={
            "boxstyle": "round,pad=0.12",
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.82,
        },
    )
    clean_image_axis(endpoint_ax)

    for index, (name, label) in enumerate(zip(CHANNEL_NAMES, CHANNEL_LABELS, strict=True)):
        ax = figure.add_subplot(grid[1, index])
        mask = masks[..., index]
        canvas = np.full((*mask.shape, 3), 255, dtype=np.uint8)
        if index == 5:
            shown = dilate_binary(mask, 2)
            canvas[shown] = CHANNEL_COLORS[index]
        else:
            canvas[mask] = CHANNEL_COLORS[index]
        ax.imshow(crop(canvas, common_bounds))
        ax.set_title(
            f"({chr(ord('g') + index)}) {name}\n{label}",
            fontsize=7.4,
            color=CHANNEL_COLORS_HEX[index],
            fontweight="semibold",
            pad=3,
        )
        clean_image_axis(ax)

    figure.suptitle(
        "Six-channel overlapping annotation contract (project sample 33/18)",
        fontsize=10.8,
        fontweight="bold",
        y=0.985,
    )
    FIGURE_MANIFEST["figures"]["figure3_channel_definition"] = {
        "sample_id": sample_id,
        "source": "recovered project GT",
        "endpoint_definition": "union of manually marked isolated-stroke endpoints only",
        "display_note": "endpoint dilation/outlines are visualization-only",
    }
    return save_figure(figure, "figure3_channel_definition")


def alignment_variant_score(
    reference_masks: np.ndarray,
    user_masks: np.ndarray,
    variant: str,
) -> tuple[np.ndarray, dict[str, float]]:
    if variant == "no_alignment":
        return reference_masks.copy(), {
            "scale": 1.0,
            "rotation_degrees": 0.0,
            "translation_x": 0.0,
            "translation_y": 0.0,
            "alignment_ink_iou": float(
                np.logical_and(mask_union(user_masks), mask_union(reference_masks)).sum()
                / max(
                    1,
                    np.logical_or(mask_union(user_masks), mask_union(reference_masks)).sum(),
                )
            ),
        }
    if variant == "current_constrained":
        return PreparedReferenceScorer(
            reference_masks,
            min_scale=0.8,
            max_scale=1.2,
            max_rotation_degrees=3.0,
        ).align(user_masks)
    if variant == "wide_similarity":
        return PreparedReferenceScorer(
            reference_masks,
            min_scale=0.6,
            max_scale=1.4,
            max_rotation_degrees=12.0,
        ).align(user_masks)
    raise ValueError(variant)


def select_alignment_reference(
    rows: Iterable[Mapping[str, str]],
    conditions: tuple[tuple[str, str], ...],
) -> str:
    all_rows = list(rows)
    current = [
        row
        for row in all_rows
        if row["alignment_variant"] == "current_constrained"
        and row["valid"] == "True"
        and (row["perturbation"], row["severity"]) in conditions
    ]
    by_reference: defaultdict[str, dict[tuple[str, str], Mapping[str, str]]] = (
        defaultdict(dict)
    )
    for row in current:
        by_reference[row["reference_id"]][
            (row["perturbation"], row["severity"])
        ] = row
    eligible = {
        reference_id: values
        for reference_id, values in by_reference.items()
        if all(condition in values for condition in conditions)
    }
    medians = {
        condition: float(
            np.median(
                [
                    float(values[condition]["score_drop"])
                    for values in eligible.values()
                ]
            )
        )
        for condition in conditions
    }
    wide_lookup = {
        (row["reference_id"], row["perturbation"], row["severity"]): row
        for row in all_rows
        if row["alignment_variant"] == "wide_similarity"
        and row["valid"] == "True"
        and (row["perturbation"], row["severity"]) in conditions
    }
    visibly_distinct = {
        reference_id: values
        for reference_id, values in eligible.items()
        if any(
            abs(
                float(values[condition]["score_drop"])
                - float(
                    wide_lookup[
                        (reference_id, condition[0], condition[1])
                    ]["score_drop"]
                )
            )
            >= 1.0
            for condition in conditions
        )
    }
    pool = visibly_distinct or eligible
    return min(
        pool,
        key=lambda reference_id: (
            sum(
                abs(
                    float(pool[reference_id][condition]["score_drop"])
                    - medians[condition]
                )
                for condition in conditions
            ),
            reference_id,
        ),
    )


def figure5_alignment_ablation() -> tuple[Path, Path]:
    """Visual paired ablation for nuisance compensation versus preserved error."""

    conditions = (
        ("global_translation", "16.0"),
        ("global_scale_down", "0.175"),
        ("direction_terminal_deletion", "0.3"),
    )
    rows = read_csv(ALIGNMENT_ROWS)
    reference_id = select_alignment_reference(rows, conditions)
    entries = reference_entries()
    entry = entries[reference_id]
    reference_masks = load_reference_masks(entry)

    row_lookup = {
        (row["perturbation"], row["severity"], row["alignment_variant"]): row
        for row in rows
        if row["reference_id"] == reference_id
        and (row["perturbation"], row["severity"]) in conditions
    }
    row_labels = (
        "Translation nuisance (16 px)",
        "Scale nuisance (-17.5%)",
        "Terminal deletion (30%)",
    )
    variants = ("no_alignment", "current_constrained", "wide_similarity")
    variant_labels = ("No alignment", "Production constrained", "Wider similarity")

    figure, axes = plt.subplots(
        3,
        5,
        figsize=(13.4, 7.35),
        gridspec_kw={"wspace": 0.10, "hspace": 0.22},
    )
    chosen_rows: list[dict[str, Any]] = []
    for row_index, ((perturbation, severity), row_label) in enumerate(
        zip(conditions, row_labels, strict=True)
    ):
        outcome = apply_perturbation(
            reference_masks,
            reference_id,
            perturbation,
            float(severity),
        )
        if not outcome.valid:
            raise ValueError(f"selected qualitative perturbation is invalid: {outcome}")
        common_bounds = foreground_bounds(
            np.logical_or(mask_union(reference_masks), mask_union(outcome.masks)),
            padding=24,
        )
        axes[row_index, 0].imshow(crop(render_union(mask_union(reference_masks)), common_bounds))
        axes[row_index, 1].imshow(crop(render_union(mask_union(outcome.masks)), common_bounds))
        for column_index, variant in enumerate(variants, start=2):
            aligned, transform = alignment_variant_score(
                reference_masks,
                outcome.masks,
                variant,
            )
            bounds = foreground_bounds(
                np.logical_or(mask_union(outcome.masks), mask_union(aligned)),
                padding=24,
            )
            axes[row_index, column_index].imshow(
                crop(difference_overlay(outcome.masks, aligned), bounds)
            )
            result = row_lookup[(perturbation, severity, variant)]
            axes[row_index, column_index].text(
                0.5,
                -0.055,
                (
                    f"score {float(result['score']):.1f}; "
                    f"drop {float(result['score_drop']):.1f}\n"
                    f"s={transform['scale']:.2f}, "
                    f"r={transform['rotation_degrees']:.0f} deg, "
                    f"t=({transform['translation_x']:.0f},{transform['translation_y']:.0f})"
                ),
                transform=axes[row_index, column_index].transAxes,
                ha="center",
                va="top",
                fontsize=6.1,
                color=MUTED,
                linespacing=1.15,
            )
            chosen_rows.append(
                {
                    "reference_id": reference_id,
                    "perturbation": perturbation,
                    "severity": severity,
                    "alignment_variant": variant,
                    "score": float(result["score"]),
                    "score_drop": float(result["score_drop"]),
                }
            )
        for column_index in range(5):
            clean_image_axis(axes[row_index, column_index])
        axes[row_index, 0].set_ylabel(
            row_label,
            fontsize=7.6,
            fontweight="semibold",
            labelpad=7,
        )

    columns = ("Reference", "Perturbed candidate", *variant_labels)
    for column_index, title in enumerate(columns):
        axes[0, column_index].set_title(title, fontsize=8.5, pad=5)
    for index, label in enumerate(("a", "b", "c")):
        panel_label(axes[index, 0], f"({label})", x=-0.06, y=1.02)
    for x, label, colour in (
        (0.095, "■ overlap", PURPLE),
        (0.175, "■ missing reference", BLUE),
        (0.300, "■ extra candidate", RED),
    ):
        figure.text(
            x,
            0.018,
            label,
            ha="left",
            va="bottom",
            fontsize=6.5,
            color=colour,
        )

    figure.text(
        0.995,
        0.003,
        (
            "Across all 200 references: nuisance penalty reduced by 30.118 points "
            "relative to no alignment; additional structural penalty preserved = "
            "11.189 points. Scale summaries are conditional on clipping-safe cases."
        ),
        ha="right",
        va="bottom",
        fontsize=6.4,
        color=MUTED,
    )
    figure.suptitle(
        "Constrained alignment reduces nuisance sensitivity without deformable error removal",
        fontsize=10.8,
        fontweight="bold",
        y=0.99,
    )
    figure.subplots_adjust(left=0.085, right=0.99, top=0.92, bottom=0.09)
    FIGURE_MANIFEST["figures"]["figure5_alignment_ablation"] = {
        "reference_id": reference_id,
        "target_char": entry["target_char"],
        "selection_rule": (
            "among references valid for the three displayed conditions and with "
            "at least one >=1-point current-versus-wide difference, minimize summed "
            "absolute deviation from each condition's median production score drop; "
            "break ties by reference_id"
        ),
        "displayed_rows": chosen_rows,
    }
    return save_figure(figure, "figure5_alignment_ablation")


def _load_pair_masks(pair: Mapping[str, str]) -> tuple[np.ndarray, np.ndarray]:
    candidate_path = resolve_data_path(pair["candidate_image_path"]).with_suffix(".npy")
    reference_path = resolve_data_path(pair["reference_image_path"]).with_suffix(".npy")
    return (
        np.load(candidate_path, allow_pickle=False).astype(bool),
        np.load(reference_path, allow_pickle=False).astype(bool),
    )


def _load_direct_ink(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L")) < 240


def figure6_asds_direct_ink() -> tuple[Path, Path]:
    """ASDS mechanism with its paired direct-ink ablation."""

    frozen = {row["pair_id"]: row for row in read_csv(FROZEN_PAIRS)}
    direct_rows = read_csv(DIRECT_INK_ROWS)
    median_delta = float(
        np.median([float(row["direct_minus_parsed"]) for row in direct_rows])
    )
    selected = min(
        direct_rows,
        key=lambda row: (
            abs(float(row["direct_minus_parsed"]) - median_delta),
            row["source_pair_id"],
        ),
    )
    pair = frozen[selected["source_pair_id"]]
    candidate_masks, reference_masks = _load_pair_masks(pair)
    candidate_image_path = resolve_data_path(pair["candidate_image_path"])
    reference_image_path = resolve_data_path(pair["reference_image_path"])
    candidate_image = load_rgb(candidate_image_path)
    reference_image = load_rgb(reference_image_path)
    _, aligned_reference = PreparedReferenceScorer(reference_masks).score(candidate_masks)
    candidate_ink = mask_union(candidate_masks)
    reference_ink = mask_union(aligned_reference)
    components = compute_spatial_structure_components(candidate_masks, aligned_reference)
    score = spatial_structure_score(components)

    polar_candidate = polar_occupancy_signature(candidate_ink).reshape(4, 8)
    polar_reference = polar_occupancy_signature(reference_ink).reshape(4, 8)
    grid_candidate = grid_occupancy_signature(candidate_ink).reshape(3, 3)
    grid_reference = grid_occupancy_signature(reference_ink).reshape(3, 3)
    row_candidate = candidate_ink.sum(axis=1).astype(float)
    row_reference = reference_ink.sum(axis=1).astype(float)
    col_candidate = candidate_ink.sum(axis=0).astype(float)
    col_reference = reference_ink.sum(axis=0).astype(float)
    row_candidate /= max(1.0, row_candidate.sum())
    row_reference /= max(1.0, row_reference.sum())
    col_candidate /= max(1.0, col_candidate.sum())
    col_reference /= max(1.0, col_reference.sum())

    bounds = foreground_bounds(
        np.logical_or(candidate_ink, reference_ink),
        padding=24,
    )
    figure = plt.figure(figsize=(13.4, 5.0), constrained_layout=False)
    grid = figure.add_gridspec(
        2,
        6,
        height_ratios=(1.0, 0.76),
        width_ratios=(1.15, 1.0, 1.05, 0.85, 1.15, 1.18),
        wspace=0.32,
        hspace=0.31,
        left=0.03,
        right=0.985,
        top=0.89,
        bottom=0.10,
    )

    pair_ax = figure.add_subplot(grid[0, 0])
    pair_ax.imshow(stack_pair_images(reference_image, candidate_image))
    pair_ax.set_title("Natural same-character pair")
    clean_image_axis(pair_ax)
    panel_label(pair_ax, "(a)")

    overlay_ax = figure.add_subplot(grid[0, 1])
    overlay_ax.imshow(crop(difference_overlay(candidate_masks, aligned_reference), bounds))
    overlay_ax.set_title("Aligned silhouettes")
    clean_image_axis(overlay_ax)
    panel_label(overlay_ax, "(b)")

    polar_ax = figure.add_subplot(grid[0, 2])
    polar_difference = np.abs(polar_candidate - polar_reference)
    polar_ax.imshow(polar_difference, cmap="Blues", aspect="auto", vmin=0)
    polar_ax.set_title(f"Polar occupancy\nJSS={components.polar_js_similarity:.3f}")
    polar_ax.set_xlabel("8 angular bins")
    polar_ax.set_ylabel("4 radial bins")
    polar_ax.set_xticks([])
    polar_ax.set_yticks([])
    panel_label(polar_ax, "(c)")

    grid_ax = figure.add_subplot(grid[0, 3])
    grid_difference = np.abs(grid_candidate - grid_reference)
    grid_ax.imshow(grid_difference, cmap="Oranges", vmin=0)
    for boundary in (0.5, 1.5):
        grid_ax.axhline(boundary, color="white", lw=0.9)
        grid_ax.axvline(boundary, color="white", lw=0.9)
    grid_ax.set_title(f"3 x 3 occupancy\nJSS={components.grid_js_similarity:.3f}")
    grid_ax.set_xticks([])
    grid_ax.set_yticks([])
    panel_label(grid_ax, "(d)")

    projection_ax = figure.add_subplot(grid[0, 4])
    x = np.linspace(0, 1, len(row_candidate))
    projection_ax.plot(x, row_candidate, color=RED, lw=1.2, label="candidate rows")
    projection_ax.plot(x, row_reference, color=BLUE, lw=1.2, label="reference rows")
    projection_ax.plot(
        x,
        col_candidate,
        color=RED,
        lw=0.9,
        ls="--",
        alpha=0.78,
        label="candidate columns",
    )
    projection_ax.plot(
        x,
        col_reference,
        color=BLUE,
        lw=0.9,
        ls="--",
        alpha=0.78,
        label="reference columns",
    )
    projection_ax.set_title(
        f"Projection profiles\nJSS={components.projection_js_similarity:.3f}"
    )
    projection_ax.set_xlim(0, 1)
    projection_ax.set_xticks((0, 0.5, 1))
    projection_ax.set_yticks([])
    projection_ax.grid(alpha=0.22, lw=0.4)
    projection_ax.legend(frameon=False, fontsize=5.8, loc="upper right")
    panel_label(projection_ax, "(e)")

    score_ax = figure.add_subplot(grid[0, 5])
    score_ax.axis("off")
    score_ax.add_patch(
        FancyBboxPatch(
            (0.02, 0.06),
            0.96,
            0.88,
            boxstyle="round,pad=0.025,rounding_size=0.025",
            transform=score_ax.transAxes,
            facecolor=PANEL_BG,
            edgecolor=GRID,
            linewidth=0.8,
        )
    )
    score_ax.text(
        0.50,
        0.79,
        r"$S_{\mathrm{ASDS}} = 100(0.70s_p + 0.15s_g + 0.15s_{\mathrm{proj}})$",
        transform=score_ax.transAxes,
        ha="center",
        va="center",
        fontsize=8.0,
    )
    score_ax.text(
        0.50,
        0.57,
        f"Example ASDS = {score:.1f}",
        transform=score_ax.transAxes,
        ha="center",
        va="center",
        fontsize=13.0,
        fontweight="bold",
        color=PURPLE,
    )
    score_ax.text(
        0.50,
        0.34,
        (
            f"Human mean = {float(selected['human_mean']):.2f}/5\n"
            f"parsed - direct = {-float(selected['direct_minus_parsed']):+.3f}"
        ),
        transform=score_ax.transAxes,
        ha="center",
        va="center",
        fontsize=7.2,
        color=MUTED,
        linespacing=1.35,
    )
    panel_label(score_ax, "(f)", x=-0.01, y=1.0)

    ablation_ax = figure.add_subplot(grid[1, :])
    ablation_ax.axis("off")
    ablation_ax.add_patch(
        FancyBboxPatch(
            (0.015, 0.06),
            0.97,
            0.84,
            boxstyle="round,pad=0.012,rounding_size=0.018",
            transform=ablation_ax.transAxes,
            facecolor="#FAFAFB",
            edgecolor=GRID,
            linewidth=0.75,
        )
    )
    ablation_ax.text(
        0.04,
        0.73,
        "(g) Paired direct-ink ablation on the same 150 rated pairs",
        transform=ablation_ax.transAxes,
        fontsize=8.8,
        fontweight="bold",
    )
    metrics = (
        ("Parsed-union ASDS", "rho = 0.55623", "B2 five-direction union"),
        ("Direct-ink ASDS", "rho = 0.55583", "thresholded source raster"),
        ("Paired difference", "delta rho = 0.00040", "95% CI [-0.01011, 0.01030]"),
        ("Score association", "rho = 0.9973", "parsed versus direct score vectors"),
    )
    x_positions = (0.05, 0.29, 0.53, 0.77)
    for x0, (title, value, note) in zip(x_positions, metrics, strict=True):
        ablation_ax.text(
            x0,
            0.48,
            title,
            transform=ablation_ax.transAxes,
            fontsize=7.0,
            fontweight="semibold",
            color=MUTED,
        )
        ablation_ax.text(
            x0,
            0.31,
            value,
            transform=ablation_ax.transAxes,
            fontsize=9.4,
            fontweight="bold",
            color=INK,
        )
        ablation_ax.text(
            x0,
            0.16,
            note,
            transform=ablation_ax.transAxes,
            fontsize=6.3,
            color=LIGHT_TEXT,
        )
    ablation_ax.text(
        0.985,
        0.075,
        "Result: the scalar descriptor is silhouette-based; parsing is retained for direction, overlap, and endpoint evidence.",
        transform=ablation_ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=6.5,
        color=MUTED,
    )

    figure.suptitle(
        "Aligned spatial-distribution similarity and the direct-ink control",
        fontsize=10.8,
        fontweight="bold",
        y=0.985,
    )
    FIGURE_MANIFEST["figures"]["figure6_asds_direct_ink"] = {
        "source_pair_id": selected["source_pair_id"],
        "target_char": selected["target_char"],
        "selection_rule": (
            "pair whose direct-minus-parsed ASDS is closest to the cohort median; "
            "break ties by source_pair_id"
        ),
        "displayed_asds": score,
        "parsed_asds_rho": 0.5562290124897076,
        "direct_ink_asds_rho": 0.5558310017217053,
    }
    return save_figure(figure, "figure6_asds_direct_ink")


LOCAL_PERTURBATIONS = {
    "direction_terminal_deletion",
    "extra_direction_fragment",
    "local_fragment_shift",
    "direction_width_dilate",
    "direction_width_erode",
}


def bool_field(row: Mapping[str, str], name: str) -> bool:
    return row.get(name, "").strip().lower() == "true"


def select_diagnostic_rows(
    rows: Iterable[Mapping[str, str]],
) -> tuple[Mapping[str, str], Mapping[str, str]]:
    current = [
        row
        for row in rows
        if row["rule_variant"] == "current"
        and row["status"] == "valid"
        and row["perturbation"] in LOCAL_PERTURBATIONS
    ]
    successes = [
        row
        for row in current
        if bool_field(row, "strict_primary_top1")
        and bool_field(row, "canonical_local_channel_accuracy")
        and (
            not row["missing_extra_accuracy"]
            or bool_field(row, "missing_extra_accuracy")
        )
        and bool_field(row, "exact_region_localization")
    ]
    failures = []
    for row in current:
        truth = json.loads(row["truth_json"])
        if (
            len(truth.get("affected_regions", [])) > 1
            and bool_field(row, "canonical_local_channel_accuracy")
            and (
                not row["missing_extra_accuracy"]
                or bool_field(row, "missing_extra_accuracy")
            )
            and bool_field(row, "overlap_region_localization")
            and not bool_field(row, "exact_region_localization")
        ):
            failures.append(row)
    if not successes or not failures:
        raise ValueError("could not select deterministic diagnostic cases")
    success = min(
        successes,
        key=lambda row: (
            -float(row["severity"]),
            row["reference_id"],
            row["perturbation"],
        ),
    )
    failure = min(
        failures,
        key=lambda row: (
            -len(json.loads(row["truth_json"])["affected_regions"]),
            -float(row["severity"]),
            row["reference_id"],
            row["perturbation"],
        ),
    )
    return success, failure


def finding_lines(findings: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for rank, finding in enumerate(findings, start=1):
        parts = [str(finding.get("finding_id", ""))]
        for field in ("channel", "difference_type", "region", "center_direction"):
            value = finding.get(field)
            if value:
                parts.append(str(value))
        lines.append(f"{rank}. " + " | ".join(parts))
    return lines or ["No finding returned"]


def diagnostic_case_artifacts(
    row: Mapping[str, str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any], list[dict[str, Any]]]:
    entries = reference_entries()
    entry = entries[row["reference_id"]]
    reference_masks = load_reference_masks(entry)
    outcome = apply_perturbation(
        reference_masks,
        row["reference_id"],
        row["perturbation"],
        float(row["severity"]),
    )
    if not outcome.valid:
        raise ValueError("frozen selected diagnostic row reconstructed as invalid")
    evidence, aligned = PreparedReferenceScorer(reference_masks).score(outcome.masks)
    findings = diagnostic_findings(
        "current",
        evidence,
        outcome.masks,
        aligned,
        max_findings=3,
    )
    stored_findings = json.loads(row["findings_json"])
    if findings != stored_findings:
        raise ValueError("reconstructed diagnostic findings differ from frozen CSV")
    return reference_masks, outcome.masks, aligned, json.loads(row["truth_json"]), findings


def draw_grid_evidence(
    ax: plt.Axes,
    user: np.ndarray,
    reference: np.ndarray,
    truth: Mapping[str, Any],
    findings: list[Mapping[str, Any]],
) -> None:
    image = difference_overlay(user, reference)
    bounds = foreground_bounds(
        np.logical_or(mask_union(user), mask_union(reference)),
        padding=20,
    )
    ax.imshow(crop(image, bounds))
    height = bounds[1] - bounds[0]
    width = bounds[3] - bounds[2]
    for fraction in (1 / 3, 2 / 3):
        ax.axhline(height * fraction, color="white", lw=0.8)
        ax.axvline(width * fraction, color="white", lw=0.8)
    truth_regions = set(truth.get("affected_regions", []))
    local = next(
        (
            finding
            for finding in findings
            if finding.get("finding_id") == "local_direction_structure"
        ),
        {},
    )
    predicted = local.get("region")
    for region in truth_regions:
        row = int(region[1])
        column = int(region[3])
        ax.add_patch(
            Rectangle(
                (column * width / 3, row * height / 3),
                width / 3,
                height / 3,
                fill=False,
                edgecolor="#00BFA5",
                linewidth=1.6,
            )
        )
    if predicted:
        row = int(str(predicted)[1])
        column = int(str(predicted)[3])
        ax.add_patch(
            Rectangle(
                (column * width / 3 + 2, row * height / 3 + 2),
                width / 3 - 4,
                height / 3 - 4,
                fill=False,
                edgecolor="#FFEA00",
                linewidth=1.3,
                linestyle="--",
            )
        )


def figure7_diagnostic_cases() -> tuple[Path, Path]:
    """Frozen success/failure cases for local diagnostic evidence."""

    success, failure = select_diagnostic_rows(read_csv(FEEDBACK_ROWS))
    selected_rows = (success, failure)
    row_titles = (
        "Successful exact localization",
        "Representative metric failure: multi-cell truth",
    )
    figure, axes = plt.subplots(
        2,
        5,
        figsize=(13.4, 6.25),
        gridspec_kw={"wspace": 0.12, "hspace": 0.25},
    )
    manifest_rows: list[dict[str, Any]] = []
    for row_index, (row, title) in enumerate(zip(selected_rows, row_titles, strict=True)):
        reference, user, aligned, truth, findings = diagnostic_case_artifacts(row)
        bounds = foreground_bounds(
            np.logical_or(mask_union(reference), mask_union(user)),
            padding=22,
        )
        axes[row_index, 0].imshow(crop(render_union(mask_union(reference)), bounds))
        axes[row_index, 1].imshow(crop(render_union(mask_union(user)), bounds))
        align_bounds = foreground_bounds(
            np.logical_or(mask_union(user), mask_union(aligned)),
            padding=22,
        )
        axes[row_index, 2].imshow(
            crop(difference_overlay(user, aligned), align_bounds)
        )
        draw_grid_evidence(axes[row_index, 3], user, aligned, truth, findings)

        output_ax = axes[row_index, 4]
        output_ax.axis("off")
        output_ax.add_patch(
            FancyBboxPatch(
                (0.02, 0.04),
                0.96,
                0.91,
                boxstyle="round,pad=0.02,rounding_size=0.025",
                transform=output_ax.transAxes,
                facecolor=PANEL_BG,
                edgecolor=GRID,
                linewidth=0.75,
            )
        )
        output_ax.text(
            0.06,
            0.88,
            "Frozen diagnostic output",
            transform=output_ax.transAxes,
            fontsize=7.9,
            fontweight="bold",
            va="top",
        )
        output_ax.text(
            0.06,
            0.78,
            "\n".join(finding_lines(findings)),
            transform=output_ax.transAxes,
            fontsize=6.2,
            va="top",
            linespacing=1.35,
            color=INK,
        )
        truth_text = (
            f"Truth channel: {truth.get('target_channel')}\n"
            f"Truth type: {truth.get('difference_type')}\n"
            f"Truth cells: {', '.join(truth.get('affected_regions', []))}"
        )
        output_ax.text(
            0.06,
            0.34,
            truth_text,
            transform=output_ax.transAxes,
            fontsize=6.2,
            va="top",
            color=MUTED,
            linespacing=1.3,
        )
        result_label = (
            "Exact region: correct"
            if bool_field(row, "exact_region_localization")
            else "Exact-one-cell metric: failed"
        )
        output_ax.text(
            0.06,
            0.10,
            result_label,
            transform=output_ax.transAxes,
            fontsize=7.0,
            fontweight="bold",
            color=("#198754" if bool_field(row, "exact_region_localization") else RED),
        )

        for column in range(4):
            clean_image_axis(axes[row_index, column])
        axes[row_index, 0].set_ylabel(
            (
                f"{title}\n{row['perturbation']} | severity {row['severity']}"
            ),
            fontsize=7.2,
            fontweight="semibold",
            labelpad=7,
        )
        manifest_rows.append(
            {
                "reference_id": row["reference_id"],
                "target_char": row["target_char"],
                "perturbation": row["perturbation"],
                "severity": float(row["severity"]),
                "truth": truth,
                "findings": findings,
                "exact_region_localization": bool_field(
                    row, "exact_region_localization"
                ),
            }
        )

    column_titles = (
        "Reference",
        "Perturbed candidate",
        "Alignment overlay",
        "Localized evidence",
        "Returned structured evidence",
    )
    for column, title in enumerate(column_titles):
        axes[0, column].set_title(title, fontsize=8.3, pad=5)
    panel_label(axes[0, 0], "(a)", x=-0.06, y=1.02)
    panel_label(axes[1, 0], "(b)", x=-0.06, y=1.02)
    for x, label, colour in (
        (0.405, "■ overlap", PURPLE),
        (0.485, "■ missing reference", BLUE),
        (0.615, "■ extra candidate", RED),
    ):
        figure.text(
            x,
            0.030,
            label,
            ha="left",
            va="bottom",
            fontsize=6.3,
            color=colour,
        )
    axes[1, 3].text(
        0.02,
        -0.12,
        "green solid = truth cells; yellow dashed = predicted cell",
        transform=axes[1, 3].transAxes,
        fontsize=6.1,
        color=MUTED,
        ha="left",
        va="top",
    )
    figure.text(
        0.99,
        0.004,
        (
            "The second case is not concealed: the returned cell overlaps the "
            "multi-cell change, but the frozen exact-one-cell metric records failure."
        ),
        ha="right",
        va="bottom",
        fontsize=6.5,
        color=MUTED,
    )
    figure.suptitle(
        "Localized diagnostic evidence: one success and one audited failure",
        fontsize=10.8,
        fontweight="bold",
        y=0.99,
    )
    figure.subplots_adjust(left=0.10, right=0.99, top=0.91, bottom=0.105)
    FIGURE_MANIFEST["figures"]["figure7_diagnostic_cases"] = {
        "cases": manifest_rows,
        "success_selection_rule": (
            "current rule; local structural perturbation; correct top-1 cause, "
            "channel, applicable missing/extra type, and exact region; then maximum "
            "severity and lexicographic reference_id"
        ),
        "failure_selection_rule": (
            "current rule; multi-cell truth; correct channel/type; predicted cell "
            "overlaps truth but fails exact-one-cell metric; then maximum truth-cell "
            "count, severity, and lexicographic reference_id"
        ),
    }
    return save_figure(figure, "figure7_diagnostic_cases")


def write_manifest() -> Path:
    output = HERE / "figure_provenance_manifest.json"
    output.write_text(
        json.dumps(FIGURE_MANIFEST, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def main() -> None:
    builders = (
        figure1_pipeline,
        figure2_dataset_overview,
        figure3_channel_definition,
        figure5_alignment_ablation,
        figure6_asds_direct_ink,
        figure7_diagnostic_cases,
    )
    for builder in builders:
        pdf, png = builder()
        print(f"created={pdf.relative_to(ROOT)}")
        print(f"created={png.relative_to(ROOT)}")
    print(f"created={write_manifest().relative_to(ROOT)}")
    print(
        "Figure 4 is built separately with build_segmentation_qualitative.py "
        "because formal checkpoint hashes are mandatory."
    )


if __name__ == "__main__":
    main()
