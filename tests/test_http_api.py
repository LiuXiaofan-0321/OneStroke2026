from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import ClassVar

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient

from onestroke_model.course_packs import CoursePackError
from onestroke_model.http_api import ServiceSettings, create_app


def _png_bytes() -> bytes:
    image = Image.new("RGB", (32, 24), color="white")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


class _FakeAnalyzer:
    model_version: ClassVar[str] = "segformer-b2-v1"
    courses: ClassVar[dict[str, object]] = {"ouyang_xun_regular_100_beta": object()}

    @classmethod
    def from_paths(cls, **_: object) -> _FakeAnalyzer:
        return cls()

    def analyze(
        self,
        image_path: Path,
        course_id: str,
        target_char: str,
        output_dir: Path,
    ) -> dict[str, object]:
        if course_id != "ouyang_xun_regular_100_beta":
            raise CoursePackError("unknown_course: bad")
        if target_char != "永":
            raise CoursePackError("unsupported_character: bad")
        Image.new("RGB", (4, 4), color="red").save(output_dir / "overlay.png")
        Image.new("RGB", (4, 4), color="green").save(output_dir / "alignment_overlay.png")
        Image.new("L", (4, 4), color=255).save(output_dir / "mask_vec1.png")
        return {
            "schema_version": 1,
            "model_version": self.model_version,
            "course": {"course_id": course_id, "display_name": "Test course"},
            "reference": {"reference_id": "ref_001", "target_char": target_char},
            "scores": {"prototype_structure_score": 82.5},
            "feedback": [{"severity": "medium", "message": "Adjust the center."}],
            "capabilities": {"segmentation": True, "stroke_order_analysis": False},
            "channels": ["vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"],
            "thresholds": {"vec1": 0.5},
            "latency_ms": 12.0,
            "keypoints": [],
            "stroke_regions": [],
            "mask_assets": {"vec1": "mask_vec1.png"},
            "overlay_asset": "overlay.png",
            "alignment_overlay_asset": "alignment_overlay.png",
            "score_interpretation": "B2 mask-structure agreement.",
        }


def _client(tmp_path: Path) -> TestClient:
    app = create_app(
        ServiceSettings(
            model_config_path=tmp_path / "config.yaml",
            checkpoint_path=tmp_path / "best.pt",
            course_config_path=tmp_path / "courses.yaml",
            artifact_root=tmp_path / "artifacts",
            api_key="test-secret",
            public_base_url="https://model.example",
        ),
        analyzer_factory=_FakeAnalyzer.from_paths,
    )
    return TestClient(app)


def test_http_api_returns_the_developer_contract_and_protected_assets(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post(
            "/analyze-course-practice",
            headers={"Authorization": "Bearer test-secret"},
            data={
                "practice_id": "practice_001",
                "course_id": "ouyang_xun_regular_100_beta",
                "target_char": "永",
            },
            files={"image": ("practice.png", _png_bytes(), "image/png")},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "succeeded"
        assert payload["practice_id"] == "practice_001"
        assert payload["scores"] == {"prototype_structure_score": 82.5}
        assert payload["feedback"][0]["type"] == "structure"
        assert payload["overlay_url"].startswith("https://model.example/artifacts/eval_")
        asset_path = payload["overlay_url"].removeprefix("https://model.example")
        asset = client.get(asset_path, headers={"X-API-Key": "test-secret"})
        assert asset.status_code == 200
        assert asset.headers["content-type"] == "image/png"


def test_http_api_rejects_missing_auth_and_unknown_course(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        denied = client.post("/analyze-course-practice")
        assert denied.status_code == 401
        assert denied.json()["error_code"] == "40101"

        response = client.post(
            "/analyze-course-practice",
            headers={"X-API-Key": "test-secret"},
            data={
                "practice_id": "practice_001",
                "course_id": "unknown_course",
                "target_char": "永",
            },
            files={"image": ("practice.png", _png_bytes(), "image/png")},
        )
        assert response.status_code == 400
        assert response.json()["error_code"] == "40002"
