"""Frozen rule variants for the paired feedback-diagnostic benchmark.

The module deliberately returns normalized evidence labels instead of Chinese
surface text.  This keeps the benchmark independent of LLM phrasing and avoids
claiming that deterministic perturbation labels are expert aesthetic judgments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS
from onestroke_model.feedback import extract_findings

RULE_VARIANTS = ("legacy-v1", "current")


@dataclass(frozen=True)
class DiagnosticFinding:
    finding_id: str
    channel: str | None = None
    difference_type: str | None = None
    region: str | None = None
    center_direction: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "finding_id": self.finding_id,
            "channel": self.channel,
            "difference_type": self.difference_type,
            "region": self.region,
            "center_direction": self.center_direction,
        }


def _grid_region(row: int, column: int) -> str:
    return f"r{row}c{column}"


def _dominant_difference(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
    *,
    channel: str | None = None,
    grid: int = 3,
) -> dict[str, Any] | None:
    user = np.asarray(user_masks, dtype=bool)[..., :5]
    reference = np.asarray(reference_masks, dtype=bool)[..., :5]
    if user.shape != reference.shape or user.ndim != 3:
        raise ValueError("direction masks must share [H,W,5] shape")
    channel_indexes = (
        [CHANNELS.index(channel)]
        if channel in CHANNELS[:5]
        else list(range(5))
    )
    height, width, _ = user.shape
    best: dict[str, Any] | None = None
    for channel_index in channel_indexes:
        missing = np.logical_and(
            reference[..., channel_index], ~user[..., channel_index]
        )
        extra = np.logical_and(user[..., channel_index], ~reference[..., channel_index])
        for row in range(grid):
            y0, y1 = row * height // grid, (row + 1) * height // grid
            for column in range(grid):
                x0, x1 = column * width // grid, (column + 1) * width // grid
                missing_count = int(missing[y0:y1, x0:x1].sum())
                extra_count = int(extra[y0:y1, x0:x1].sum())
                count = max(missing_count, extra_count)
                if count == 0:
                    continue
                candidate = {
                    "channel": CHANNELS[channel_index],
                    "difference_type": (
                        "missing_reference_structure"
                        if missing_count >= extra_count
                        else "extra_user_structure"
                    ),
                    "region": _grid_region(row, column),
                    "pixels": count,
                }
                if best is None or int(candidate["pixels"]) > int(best["pixels"]):
                    best = candidate
    return best


def _center_offset(evidence: Mapping[str, object]) -> tuple[float, float]:
    pre = evidence.get("pre_alignment", {})
    if not isinstance(pre, Mapping):
        return 0.0, 0.0
    offset = pre.get("center_offset_normalized", {})
    if not isinstance(offset, Mapping):
        return 0.0, 0.0
    return float(offset.get("x", 0.0)), float(offset.get("y", 0.0))


def _legacy_center_direction(evidence: Mapping[str, object]) -> str:
    offset_x, offset_y = _center_offset(evidence)
    horizontal = "right" if offset_x > 0 else "left"
    vertical = "down" if offset_y > 0 else "up"
    return (
        f"{vertical}_{horizontal}"
        if abs(offset_x) >= abs(offset_y) * 0.45
        else vertical
    )


def _current_center_direction(evidence: Mapping[str, object]) -> str:
    """Use a dominant-axis label unless both components are material.

    The 0.45 ratio is preregistered as a wording rule, not fit to benchmark
    outcomes.  It prevents a near-zero minor component from creating a diagonal
    instruction.
    """

    offset_x, offset_y = _center_offset(evidence)
    abs_x, abs_y = abs(offset_x), abs(offset_y)
    if max(abs_x, abs_y) <= 1e-12:
        return "none"
    if min(abs_x, abs_y) < 0.45 * max(abs_x, abs_y):
        if abs_x > abs_y:
            return "right" if offset_x > 0 else "left"
        return "down" if offset_y > 0 else "up"
    vertical = "down" if offset_y > 0 else "up"
    horizontal = "right" if offset_x > 0 else "left"
    return f"{vertical}_{horizontal}"


def _normalized_findings(
    evidence: Mapping[str, object],
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
    *,
    variant: str,
    max_findings: int,
) -> list[DiagnosticFinding]:
    raw = extract_findings(
        evidence,
        user_masks,
        aligned_reference_masks,
        max_findings=max_findings,
    )
    normalized: list[DiagnosticFinding] = []
    for finding in raw:
        details = finding.evidence
        if finding.finding_id == "layout_center_offset":
            normalized.append(
                DiagnosticFinding(
                    finding_id=finding.finding_id,
                    center_direction=(
                        _legacy_center_direction(evidence)
                        if variant == "legacy-v1"
                        else _current_center_direction(evidence)
                    ),
                )
            )
            continue
        if finding.finding_id != "local_direction_structure":
            normalized.append(DiagnosticFinding(finding_id=finding.finding_id))
            continue

        worst_channel = str(details.get("worst_direction_channel", ""))
        local = details.get("local_difference")
        if variant == "current":
            # The local maximum defines one canonical channel. This prevents
            # pairing a global worst-Dice channel with a different local region.
            local = _dominant_difference(user_masks, aligned_reference_masks)
        elif isinstance(local, Mapping):
            grid = local.get("grid", {})
            if isinstance(grid, Mapping):
                local = {
                    **dict(local),
                    "region": _grid_region(
                        int(grid.get("row", 0)), int(grid.get("column", 0))
                    ),
                }

        local_map = dict(local) if isinstance(local, Mapping) else {}
        normalized.append(
            DiagnosticFinding(
                finding_id=finding.finding_id,
                channel=(
                    str(local_map.get("channel", worst_channel))
                ),
                difference_type=(
                    str(local_map.get("difference_type"))
                    if local_map.get("difference_type")
                    else None
                ),
                region=(
                    str(local_map.get("region")) if local_map.get("region") else None
                ),
            )
        )
    return normalized


def diagnostic_findings(
    variant: str,
    evidence: Mapping[str, object],
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
    *,
    max_findings: int = 3,
) -> list[dict[str, str | None]]:
    if variant not in RULE_VARIANTS:
        raise ValueError(f"unknown feedback diagnostic rule variant: {variant!r}")
    if max_findings < 1:
        raise ValueError("max_findings must be positive")
    return [
        item.as_dict()
        for item in _normalized_findings(
            evidence,
            user_masks,
            aligned_reference_masks,
            variant=variant,
            max_findings=max_findings,
        )
    ]


def finding_ids(findings: Sequence[Mapping[str, object]]) -> list[str]:
    return [str(item.get("finding_id", "")) for item in findings]
