"""Evidence-grounded feedback contracts and optional LLM rendering."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: str
    priority: float
    title: str
    message: str
    action: str
    evidence: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "action": self.action,
            "evidence": self.evidence,
        }


_SEVERITY_WEIGHT = {"high": 3.0, "medium": 2.0, "low": 1.0}


def _severity(value: float, high: float, medium: float, low: float) -> str | None:
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    if value >= low:
        return "low"
    return None


def _region_name(y: int, x: int) -> str:
    vertical = ("上部", "中部", "下部")[y]
    horizontal = ("左侧", "中央", "右侧")[x]
    return f"{vertical}{horizontal}" if horizontal != "中央" else vertical


def _dominant_difference(
    user_masks: np.ndarray,
    reference_masks: np.ndarray,
    grid: int = 3,
) -> dict[str, object] | None:
    """Locate the strongest missing/extra directional-mask evidence region."""
    user = np.asarray(user_masks, dtype=bool)[..., :5]
    reference = np.asarray(reference_masks, dtype=bool)[..., :5]
    if user.shape != reference.shape or user.ndim != 3:
        raise ValueError("direction masks must share [H,W,5] shape")
    height, width, _ = user.shape
    best: dict[str, object] | None = None
    for channel_index, channel in enumerate(CHANNELS[:5]):
        missing = np.logical_and(reference[..., channel_index], ~user[..., channel_index])
        extra = np.logical_and(user[..., channel_index], ~reference[..., channel_index])
        for y in range(grid):
            y0, y1 = y * height // grid, (y + 1) * height // grid
            for x in range(grid):
                x0, x1 = x * width // grid, (x + 1) * width // grid
                missing_count = int(missing[y0:y1, x0:x1].sum())
                extra_count = int(extra[y0:y1, x0:x1].sum())
                count = max(missing_count, extra_count)
                if count == 0:
                    continue
                candidate = {
                    "channel": channel,
                    "region": _region_name(y, x),
                    "difference_type": "missing_reference_structure"
                    if missing_count >= extra_count
                    else "extra_user_structure",
                    "pixels": count,
                    "grid": {"row": y, "column": x, "size": grid},
                }
                if best is None or int(candidate["pixels"]) > int(best["pixels"]):
                    best = candidate
    return best


def _match_band(score: float) -> str:
    if score >= 90:
        return "high_reference_match"
    if score >= 70:
        return "moderate_reference_match"
    return "low_reference_match"


def _direction_value(evidence: Mapping[str, object]) -> tuple[str, float]:
    raw = evidence.get("direction_dice", {})
    if not isinstance(raw, Mapping) or not raw:
        return "vec1", 1.0
    values = [(str(channel), float(value)) for channel, value in raw.items()]
    return min(values, key=lambda item: item[1])


def extract_findings(
    evidence: Mapping[str, object],
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
    max_findings: int = 3,
) -> list[Finding]:
    """Create conservative, explainable issues from scoring evidence only."""
    if max_findings < 1:
        raise ValueError("max_findings must be positive")
    findings: list[Finding] = []
    pre = evidence.get("pre_alignment", {})
    if not isinstance(pre, Mapping):
        pre = {}
    center_offset = pre.get("center_offset_normalized", {})
    if isinstance(center_offset, Mapping):
        offset_x = float(center_offset.get("x", 0.0))
        offset_y = float(center_offset.get("y", 0.0))
        offset = float(np.hypot(offset_x, offset_y))
        severity = _severity(offset, 0.08, 0.04, 0.02)
        if severity:
            horizontal = "右" if offset_x > 0 else "左"
            vertical = "下" if offset_y > 0 else "上"
            dominant = (
                f"{horizontal}{vertical}"
                if abs(offset_x) >= abs(offset_y) * 0.45
                else vertical
            )
            findings.append(
                Finding(
                    finding_id="layout_center_offset",
                    severity=severity,
                    priority=offset * 10,
                    title="整体重心偏移",
                    message=f"与范字相比，整体墨迹重心偏向{dominant}侧。",
                    action="先调整字的整体占位和主部件位置，再处理局部笔画；不要通过拉伸整张字图来补偿。",
                    evidence={
                        "center_offset_normalized": {"x": offset_x, "y": offset_y},
                        "center_distance_normalized": float(
                            pre.get("center_distance_normalized", offset)
                        ),
                    },
                )
            )
    area_ratio = float(pre.get("reference_to_user_ink_area_ratio", 1.0))
    scale_error = abs(float(np.log(max(area_ratio, 1e-6))))
    severity = _severity(scale_error, 0.30, 0.15, 0.08)
    if severity:
        direction = "偏小" if area_ratio > 1.0 else "偏大"
        findings.append(
            Finding(
                finding_id="layout_ink_scale",
                severity=severity,
                priority=scale_error * 8,
                title="整体大小比例",
                message=f"相对范字，当前字的整体墨迹面积{direction}。",
                action="先按参考字的外接范围控制字的整体大小，再微调各部件之间的留白。",
                evidence={"reference_to_user_ink_area_ratio": area_ratio},
            )
        )
    keypoint_f1 = float(evidence.get("keypoint_tolerant_f1_radius_3", 1.0))
    severity = _severity(1.0 - keypoint_f1, 0.45, 0.25, 0.10)
    if severity:
        findings.append(
            Finding(
                finding_id="keypoint_relation",
                severity=severity,
                priority=(1.0 - keypoint_f1) * 8,
                title="起收笔与转折关系",
                message="关键点与范字的对应关系存在明显差异。",
                action="重点观察起笔、收笔、转折和交叉位置，先对齐这些骨架点，再追求笔画粗细。",
                evidence={"keypoint_tolerant_f1_radius_3": keypoint_f1},
            )
        )
    channel, worst_dice = _direction_value(evidence)
    severity = _severity(1.0 - worst_dice, 0.50, 0.25, 0.08)
    if severity:
        local = _dominant_difference(user_masks, aligned_reference_masks)
        region = str(local["region"]) if local else "局部"
        difference_type = str(local["difference_type"]) if local else "difference"
        kind = "缺少" if difference_type == "missing_reference_structure" else "多出"
        findings.append(
            Finding(
                finding_id="local_direction_structure",
                severity=severity,
                priority=(1.0 - worst_dice) * 7,
                title="局部笔画结构",
                message=f"{region}的笔画结构与范字差异较大，当前主要表现为{kind}对应结构。",
                action="打开叠加图，对照该区域的笔画位置、走向和收束范围；一次只调整这一处，不要同时改动整字。",
                evidence={
                    "worst_direction_channel": channel,
                    "worst_direction_dice": worst_dice,
                    "local_difference": local,
                },
            )
        )
    findings.sort(
        key=lambda item: (-_SEVERITY_WEIGHT[item.severity], -item.priority, item.finding_id)
    )
    return findings[:max_findings]


def build_feedback_contract(
    evidence: Mapping[str, object],
    user_masks: np.ndarray,
    aligned_reference_masks: np.ndarray,
    course_id: str,
    course_name: str,
    target_char: str,
    max_findings: int = 3,
) -> dict[str, object]:
    """Build frontend-safe deterministic feedback and a constrained LLM payload."""
    score = float(evidence["prototype_structure_score"])
    findings = extract_findings(
        evidence, user_masks, aligned_reference_masks, max_findings=max_findings
    )
    if findings:
        summary = "已识别出优先练习的结构问题，请按顺序逐项调整。"
    else:
        summary = "当前字与所选范字的结构接近；仍建议查看叠加图进行细节练习。"
    contract = {
        "schema_version": SCHEMA_VERSION,
        "feedback_type": "evidence_grounded_reference_practice",
        "score_label": "参考结构匹配度",
        "score_is_calibrated_calligraphy_grade": False,
        "course": {"course_id": course_id, "display_name": course_name},
        "target_char": target_char,
        "summary": summary,
        "structural_match": {
            "prototype_structure_score": score,
            "band": _match_band(score),
            "interpretation": (
                "B2 mask-structure agreement with the selected same-character reference."
            ),
        },
        "findings": [item.as_dict() for item in findings],
        "deterministic_feedback": [
            {
                "severity": item.severity,
                "title": item.title,
                "message": item.message,
                "action": item.action,
            }
            for item in findings
        ],
        "llm_policy": {
            "may_rephrase_findings": True,
            "must_not_change_score": True,
            "must_not_invent_unobserved_strokes": True,
            "must_not_claim_expert_or_aesthetic_grade": True,
            "max_feedback_items": max_findings,
        },
    }
    contract["llm_messages"] = build_llm_messages(contract)
    return contract


def build_llm_messages(contract: Mapping[str, object]) -> list[dict[str, str]]:
    """Create a provider-neutral Chinese prompt that limits the LLM to evidence."""
    system = (
        "你是一名书法练习助手。只能根据提供的结构化证据生成中文练习建议。"
        "不得修改或重算分数，不得编造未提供的笔画、笔顺、书法史事实或审美等级。"
        "不要自称书法老师或专家。输出三部分：一句肯定、最多三条可执行改进建议、一句练习顺序提醒。"
    )
    payload = dict(contract)
    payload.pop("llm_messages", None)
    user = "请依据以下 JSON 生成面向学生的练习建议：\n" + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_openai_compatible(
    messages: Sequence[Mapping[str, str]],
    api_url: str,
    model: str,
    api_key_env: str = "ONESTROKE_LLM_API_KEY",
    timeout_seconds: float = 20.0,
) -> dict[str, object]:
    """Optional OpenAI-compatible text rendering. No network call occurs by default."""
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"missing LLM API key environment variable: {api_key_env}")
    payload = {
        "model": model,
        "messages": [dict(item) for item in messages],
        "temperature": 0.2,
    }
    request = Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        # The URL is explicitly configured by the deploying backend, never the frontend.
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"LLM HTTP error: {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("LLM connection failed") from exc
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("LLM response does not match OpenAI chat-completions schema") from exc
    return {"provider": "openai_compatible", "model": model, "text": str(content)}
