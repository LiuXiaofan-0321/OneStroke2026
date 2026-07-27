"""Reusable model-side service for one course-pack writing analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.course_packs import CoursePack, CoursePackError, get_course, load_course_packs
from onestroke_model.feedback import build_feedback_contract
from onestroke_model.inference import (
    now_ms,
    package_prediction,
    prepare_image,
    restore_letterbox_probabilities,
    save_prediction_assets,
)
from onestroke_model.scripts.cache_reference_masks import _load_model
from onestroke_model.style_scoring import save_score_assets, score_masks
from onestroke_model.utils.io import ensure_dir, write_json


def _load_cached_reference(
    cache_index_path: Path, reference_id: str
) -> tuple[dict[str, object], np.ndarray]:
    if not cache_index_path.is_file():
        raise CoursePackError(f"missing_course_cache: {cache_index_path}")
    index = json.loads(cache_index_path.read_text(encoding="utf-8"))
    if list(index.get("channels", [])) != list(CHANNELS):
        raise CoursePackError(
            "course cache channel schema does not match the fixed six-channel schema"
        )
    matches = [
        item for item in index.get("references", []) if item.get("reference_id") == reference_id
    ]
    if len(matches) != 1:
        raise CoursePackError(f"reference_cache_not_unique: {reference_id!r}")
    entry = dict(matches[0])
    cache_path = cache_index_path.parent / str(entry["cache_path"])
    if not cache_path.is_file():
        raise CoursePackError(f"reference_mask_file_missing: {cache_path}")
    with np.load(cache_path) as cache:
        channels = [str(value) for value in cache["channels"].tolist()]
        if channels != list(CHANNELS):
            raise CoursePackError(
                "reference mask channel order does not match the fixed six-channel schema"
            )
        masks = np.asarray(cache["binary_masks"], dtype=np.uint8).astype(bool)
    return entry, masks


@dataclass
class CoursePracticeAnalyzer:
    """A long-lived analyzer that keeps the B2 model in memory between requests."""

    torch: Any
    model: Any
    device: Any
    model_config: dict[str, object]
    thresholds: dict[str, float]
    courses: dict[str, CoursePack]
    model_version: str = "segformer-b2-v1"

    @classmethod
    def from_paths(
        cls,
        model_config_path: str | Path,
        checkpoint_path: str | Path,
        course_config_path: str | Path = "configs/course_packs.yaml",
        model_version: str = "segformer-b2-v1",
    ) -> "CoursePracticeAnalyzer":
        torch, model, device, model_config, thresholds = _load_model(
            model_config_path, checkpoint_path
        )
        return cls(
            torch=torch,
            model=model,
            device=device,
            model_config=model_config,
            thresholds=thresholds,
            courses=load_course_packs(course_config_path),
            model_version=model_version,
        )

    def _predict_canonical(
        self, image_path: str | Path
    ) -> tuple[np.ndarray, np.ndarray, tuple[int, int], float]:
        image_size = int(self.model_config.get("data", {}).get("image_size", 512))
        normalization = str(self.model_config.get("data", {}).get("normalization", "none"))
        array, original_size = prepare_image(image_path, image_size, normalization=normalization)
        started = now_ms()
        with self.torch.no_grad():
            tensor = self.torch.from_numpy(array).to(device=self.device, dtype=self.torch.float32)
            probabilities = self.torch.sigmoid(self.model(tensor)).cpu().numpy()[0]
        latency_ms = now_ms() - started
        probabilities_hwc = np.transpose(probabilities, (1, 2, 0))
        thresholds = np.asarray(
            [self.thresholds[channel] for channel in CHANNELS], dtype=np.float32
        )
        masks = probabilities_hwc >= thresholds.reshape(1, 1, -1)
        return probabilities_hwc, masks, original_size, latency_ms

    def analyze(
        self,
        image_path: str | Path,
        course_id: str,
        target_char: str,
        output_dir: str | Path,
        max_findings: int = 3,
    ) -> dict[str, object]:
        """Analyze one image against the selected same-character course reference."""
        course = get_course(self.courses, course_id)
        reference = course.reference_for(target_char)
        cache_entry, reference_masks = _load_cached_reference(
            course.cache_index_path, reference.reference_id
        )
        probabilities_hwc, user_masks, original_size, latency_ms = self._predict_canonical(
            image_path
        )
        evidence, aligned_reference = score_masks(user_masks, reference_masks)
        evidence.update(
            {
                "model_version": self.model_version,
                "course_id": course.course_id,
                "course_display_name": course.display_name,
                "style_id": course.style_id,
                "target_char": target_char,
                "reference_id": reference.reference_id,
                "cache_index": str(course.cache_index_path.resolve()),
                "score_label": course.scoring_label,
            }
        )
        feedback = build_feedback_contract(
            evidence=evidence,
            user_masks=user_masks,
            aligned_reference_masks=aligned_reference,
            course_id=course.course_id,
            course_name=course.display_name,
            target_char=target_char,
            max_findings=max_findings,
        )
        output = ensure_dir(output_dir)
        restored_probabilities = restore_letterbox_probabilities(probabilities_hwc, original_size)
        packaged = package_prediction(
            restored_probabilities, thresholds=self.thresholds, latency_ms=latency_ms
        )
        result = save_prediction_assets(
            image_path, packaged, output, model_version=self.model_version
        )
        save_score_assets(output, evidence, user_masks, aligned_reference)
        write_json(output / "feedback_contract.json", feedback)
        result["capabilities"] = {
            "segmentation": True,
            "keypoint_localization": True,
            "stroke_region_extraction": True,
            "style_conditioning": True,
            "style_scoring": True,
            "natural_language_feedback": True,
            "stroke_order_analysis": False,
        }
        result["course"] = {
            "course_id": course.course_id,
            "display_name": course.display_name,
            "style_id": course.style_id,
            "status": course.status,
        }
        result["reference"] = {
            "reference_id": reference.reference_id,
            "target_char": target_char,
            "source_work_id": reference.source_work_id,
            "source_version": reference.source_version,
            "cache_reference_id": cache_entry["reference_id"],
        }
        result["scores"] = evidence
        result["feedback"] = feedback["deterministic_feedback"]
        result["feedback_contract_asset"] = "feedback_contract.json"
        result["alignment_overlay_asset"] = "alignment_overlay.png"
        result["score_interpretation"] = evidence["score_interpretation"]
        result["schema_version"] = SCHEMA_VERSION
        write_json(output / "result.json", result)
        return result
