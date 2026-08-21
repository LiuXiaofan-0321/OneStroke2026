from __future__ import annotations

import numpy as np

from onestroke_model.direct_ink_asds import (
    _ink_stack,
    analyze_direct_ink_rows,
)


def test_ink_stack_preserves_foreground_in_union() -> None:
    ink = np.zeros((8, 8), dtype=bool)
    ink[2:6, 3:5] = True
    stack = _ink_stack(ink)
    assert stack.shape == (8, 8, 6)
    assert np.array_equal(np.any(stack[..., :5], axis=-1), ink)
    assert not np.any(stack[..., 1:])


def test_direct_ink_report_uses_paired_character_clusters() -> None:
    rows = []
    for char_id in range(5):
        for pair_index in range(3):
            human = float(pair_index + 1)
            rows.append(
                {
                    "char_id": str(char_id),
                    "human_mean": human,
                    "parsed_asds_score": human,
                    "direct_ink_asds_score": 4.0 - human,
                }
            )
    report = analyze_direct_ink_rows(
        rows, bootstrap_iterations=100, bootstrap_seed=7
    )
    assert report["pair_count"] == 15
    assert report["character_count"] == 5
    assert report["correlation_with_human_mean"]["parsed_asds"]["rho"] == 1.0
    assert report["correlation_with_human_mean"]["direct_ink_asds"]["rho"] == -1.0
    assert report["character_cluster_bootstrap"]["cluster_unit"] == "char_id"
