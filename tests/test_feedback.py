from __future__ import annotations

import numpy as np

from onestroke_model.feedback import build_feedback_contract
from onestroke_model.style_scoring import score_masks


def _masks(x0: int, y0: int, direction_count: int = 5) -> np.ndarray:
    masks = np.zeros((64, 64, 6), dtype=np.uint8)
    masks[y0 : y0 + 16, x0 : x0 + 8, :direction_count] = 1
    masks[y0 + 7 : y0 + 9, x0 + 3 : x0 + 5, 5] = 1
    return masks


def test_feedback_contract_uses_structural_evidence_without_aesthetic_claims() -> None:
    evidence, aligned = score_masks(
        _masks(46, 40, direction_count=3), _masks(6, 8, direction_count=5)
    )

    contract = build_feedback_contract(
        evidence=evidence,
        user_masks=_masks(46, 40, direction_count=3),
        aligned_reference_masks=aligned,
        course_id="ouyang_xun_regular_100_beta",
        course_name="欧阳询楷书·100字练习包（Beta）",
        target_char="亮",
    )

    assert contract["score_label"] == "参考结构匹配度"
    assert contract["score_is_calibrated_calligraphy_grade"] is False
    assert contract["llm_policy"]["must_not_change_score"] is True
    assert len(contract["findings"]) <= 3
    assert contract["findings"]
    prompt = contract["llm_messages"][0]["content"]
    assert "不得修改或重算分数" in prompt
    assert "不得编造" in prompt


def test_feedback_contract_reports_no_findings_for_exact_match() -> None:
    masks = _masks(16, 16)
    evidence, aligned = score_masks(masks, masks)

    contract = build_feedback_contract(
        evidence=evidence,
        user_masks=masks,
        aligned_reference_masks=aligned,
        course_id="ouyang_xun_regular_100_beta",
        course_name="欧阳询楷书·100字练习包（Beta）",
        target_char="亮",
    )

    assert contract["findings"] == []
    assert "结构接近" in contract["summary"]
