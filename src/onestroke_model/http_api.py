"""Authenticated HTTP wrapper for the course-practice B2 analysis pipeline.

The service is intentionally synchronous at the HTTP boundary: one request returns
one complete B2 segmentation, reference-structure score, and evidence-grounded
feedback result.  The long-lived analyzer is loaded once at startup and inference
is serialized to avoid competing GPU requests on a small deployment instance.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from starlette.datastructures import UploadFile

from onestroke_model.constants import CHANNELS
from onestroke_model.course_packs import CoursePackError, build_course_catalog
from onestroke_model.course_practice import CoursePracticeAnalyzer
from onestroke_model.feedback import call_openai_compatible
from onestroke_model.utils.io import write_json

LOGGER = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/healthz"})
_ASSET_FILENAMES = frozenset(
    {"overlay.png", "alignment_overlay.png"}
    | {f"mask_{channel}.png" for channel in CHANNELS}
)
_MAX_IMAGE_DIMENSION = 8192


class ApiError(Exception):
    """A controlled API error that maps to the shared model-service contract."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class ServiceSettings:
    """Runtime-only service settings. Secrets are never written to result assets."""

    model_config_path: Path
    checkpoint_path: Path
    course_config_path: Path
    artifact_root: Path
    model_version: str = "segformer-b2-v1"
    public_base_url: str | None = None
    api_key: str | None = None
    allowed_ips: frozenset[str] = frozenset()
    max_upload_bytes: int = 10 * 1024 * 1024
    llm_url: str | None = None
    llm_model: str | None = None
    llm_api_key_env: str = "ONESTROKE_LLM_API_KEY"

    @classmethod
    def from_environment(cls, require_api_key: bool = True) -> ServiceSettings:
        """Read deployment configuration without exposing any secret in logs."""
        api_key = os.environ.get("ONESTROKE_API_KEY")
        if require_api_key and not api_key:
            raise RuntimeError("ONESTROKE_API_KEY must be set before starting the HTTP service")
        llm_url = os.environ.get("ONESTROKE_LLM_URL")
        llm_model = os.environ.get("ONESTROKE_LLM_MODEL")
        if bool(llm_url) != bool(llm_model):
            raise RuntimeError("ONESTROKE_LLM_URL and ONESTROKE_LLM_MODEL must be set together")
        raw_ips = os.environ.get("ONESTROKE_ALLOWED_IPS", "")
        allowed_ips = frozenset(item.strip() for item in raw_ips.split(",") if item.strip())
        max_upload_mb = int(os.environ.get("ONESTROKE_MAX_UPLOAD_MB", "10"))
        if max_upload_mb < 1:
            raise RuntimeError("ONESTROKE_MAX_UPLOAD_MB must be at least 1")
        return cls(
            model_config_path=Path(
                os.environ.get("ONESTROKE_MODEL_CONFIG", "configs/segformer_b2_v1_delivery.yaml")
            ),
            checkpoint_path=Path(os.environ.get("ONESTROKE_CHECKPOINT", "checkpoints/segformer_b2_v1/best.pt")),
            course_config_path=Path(
                os.environ.get("ONESTROKE_COURSE_CONFIG", "configs/course_packs.yaml")
            ),
            artifact_root=Path(
                os.environ.get("ONESTROKE_ARTIFACT_ROOT", "artifacts/http_api/practice")
            ),
            model_version=os.environ.get("ONESTROKE_MODEL_VERSION", "segformer-b2-v1"),
            public_base_url=os.environ.get("ONESTROKE_PUBLIC_BASE_URL") or None,
            api_key=api_key,
            allowed_ips=allowed_ips,
            max_upload_bytes=max_upload_mb * 1024 * 1024,
            llm_url=llm_url or None,
            llm_model=llm_model or None,
            llm_api_key_env=os.environ.get("ONESTROKE_LLM_API_KEY_ENV", "ONESTROKE_LLM_API_KEY"),
        )


def _failure_response(error: ApiError) -> Any:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "status": "failed",
            "error_code": error.error_code,
            "error_message": error.message,
        },
    )


def _course_error_to_api_error(error: CoursePackError) -> ApiError:
    message = str(error)
    if message.startswith(("unknown_course:", "course_disabled:")):
        return ApiError(400, "40002", "Unknown or disabled course_id.")
    if message.startswith(("unsupported_character:", "ambiguous_reference:")):
        return ApiError(409, "40901", "This course does not include the requested target_char.")
    if message.startswith(("missing_course_cache:", "reference_mask_file_missing:")):
        return ApiError(503, "50301", "The approved reference-mask cache is unavailable.")
    return ApiError(500, "50001", "Course reference configuration is invalid.")


def _new_task_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"eval_{timestamp}_{secrets.token_hex(5)}"


def _request_api_key(request: Any) -> str | None:
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return request.headers.get("x-api-key")


def _validate_request_access(request: Any, settings: ServiceSettings) -> None:
    client_host = request.client.host if request.client else None
    if settings.allowed_ips and client_host not in settings.allowed_ips:
        raise ApiError(403, "40301", "The caller IP is not on the model-service allowlist.")
    if settings.api_key:
        supplied_key = _request_api_key(request)
        if not supplied_key or not secrets.compare_digest(supplied_key, settings.api_key):
            raise ApiError(401, "40101", "Missing or invalid model-service API key.")


def _required_text(form: Any, field: str, error_code: str = "40002") -> str:
    value = form.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, error_code, f"Missing required multipart field: {field}.")
    value = value.strip()
    if len(value) > 128:
        raise ApiError(400, error_code, f"Multipart field is too long: {field}.")
    return value


def _validate_image(payload: bytes, max_upload_bytes: int) -> tuple[bytes, str]:
    if not payload:
        raise ApiError(400, "40001", "The uploaded image is empty.")
    if len(payload) > max_upload_bytes:
        raise ApiError(413, "41301", "The uploaded image exceeds the configured size limit.")
    try:
        with Image.open(BytesIO(payload)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ApiError(400, "40001", "The image is damaged or not a PNG/JPEG file.") from exc
    if image_format not in {"PNG", "JPEG"}:
        raise ApiError(400, "40001", "Only PNG and JPEG images are supported.")
    if width < 1 or height < 1 or width > _MAX_IMAGE_DIMENSION or height > _MAX_IMAGE_DIMENSION:
        raise ApiError(400, "40001", "The image dimensions are outside the supported range.")
    return payload, ".png" if image_format == "PNG" else ".jpg"


def _public_url(request: Any, settings: ServiceSettings, task_id: str, filename: str) -> str:
    base = (settings.public_base_url or str(request.base_url)).rstrip("/")
    return f"{base}/artifacts/{quote(task_id)}/{quote(filename)}"


def _response_payload(
    request: Any,
    settings: ServiceSettings,
    task_id: str,
    practice_id: str,
    result: dict[str, object],
    llm_feedback: dict[str, object] | None,
) -> dict[str, object]:
    mask_assets = result.get("mask_assets", {})
    if not isinstance(mask_assets, dict):
        mask_assets = {}
    mask_urls = {
        str(channel): _public_url(request, settings, task_id, str(filename))
        for channel, filename in mask_assets.items()
        if str(filename) in _ASSET_FILENAMES
    }
    overlay_filename = str(result.get("overlay_asset", "overlay.png"))
    alignment_filename = str(result.get("alignment_overlay_asset", "alignment_overlay.png"))
    score_evidence = result.get("scores", {})
    if not isinstance(score_evidence, dict):
        score_evidence = {}
    score_value = score_evidence.get("prototype_structure_score")
    feedback = result.get("feedback", [])
    if not isinstance(feedback, list):
        feedback = []
    normalized_feedback = [
        {"type": "structure", **item} if isinstance(item, dict) else item for item in feedback
    ]
    payload: dict[str, object] = {
        "task_id": task_id,
        "practice_id": practice_id,
        "status": "succeeded",
        "schema_version": result.get("schema_version", 1),
        "model_version": result.get("model_version", settings.model_version),
        "course": result.get("course", {}),
        "reference": result.get("reference", {}),
        "scores": {"prototype_structure_score": score_value},
        "feedback": normalized_feedback,
        "capabilities": result.get("capabilities", {}),
        "segmentation": {
            "channels": result.get("channels", list(CHANNELS)),
            "thresholds": result.get("thresholds", {}),
            "latency_ms": result.get("latency_ms"),
            "keypoints": result.get("keypoints", []),
            "stroke_regions": result.get("stroke_regions", []),
            "mask_urls": mask_urls,
        },
        "overlay_url": _public_url(request, settings, task_id, overlay_filename),
        "alignment_overlay_url": _public_url(request, settings, task_id, alignment_filename),
        "score_interpretation": result.get("score_interpretation"),
    }
    if llm_feedback:
        payload["ai_feedback"] = {"source": "llm", **llm_feedback}
    else:
        payload["ai_feedback"] = {"source": "deterministic", "items": normalized_feedback}
    return payload


def create_app(
    settings: ServiceSettings,
    analyzer_factory: Callable[..., CoursePracticeAnalyzer] = CoursePracticeAnalyzer.from_paths,
) -> Any:
    """Build the FastAPI app without loading B2 until the server lifespan begins."""
    @asynccontextmanager
    async def lifespan(app: Any) -> Any:
        settings.artifact_root.mkdir(parents=True, exist_ok=True)
        LOGGER.info("Loading %s for HTTP inference", settings.model_version)
        app.state.analyzer = analyzer_factory(
            model_config_path=settings.model_config_path,
            checkpoint_path=settings.checkpoint_path,
            course_config_path=settings.course_config_path,
            model_version=settings.model_version,
        )
        app.state.analysis_lock = asyncio.Lock()
        LOGGER.info("Model HTTP service is ready with %d enabled courses", len(app.state.analyzer.courses))
        yield

    app = FastAPI(
        title="OneStroke Model Service",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
        return _failure_response(error)

    @app.middleware("http")
    async def protect_private_routes(request: Request, call_next: Any) -> Any:
        if request.url.path not in _PUBLIC_PATHS:
            try:
                _validate_request_access(request, settings)
            except ApiError as error:
                return _failure_response(error)
        return await call_next(request)

    @app.get("/healthz")
    async def healthz() -> dict[str, object]:
        analyzer = app.state.analyzer
        return {
            "status": "ok",
            "model_version": analyzer.model_version,
            "enabled_course_count": len(analyzer.courses),
        }

    @app.get("/course-catalog")
    async def course_catalog() -> dict[str, object]:
        catalog = build_course_catalog(app.state.analyzer.courses, require_cache=False)
        for course in catalog["courses"]:
            for character in course["characters"]:
                character.pop("reference_image_path", None)
        return catalog

    @app.post("/analyze-course-practice")
    async def analyze_course_practice(request: Request) -> dict[str, object]:
        content_type = request.headers.get("content-type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ApiError(400, "40001", "Content-Type must be multipart/form-data.")
        try:
            form = await request.form()
        except Exception as exc:
            raise ApiError(400, "40001", "Unable to parse multipart image upload.") from exc
        practice_id = _required_text(form, "practice_id")
        course_id = _required_text(form, "course_id")
        target_char = _required_text(form, "target_char", error_code="40901")
        upload = form.get("image")
        if not isinstance(upload, UploadFile):
            raise ApiError(400, "40001", "Missing multipart image file field: image.")
        payload = await upload.read(settings.max_upload_bytes + 1)
        payload, suffix = _validate_image(payload, settings.max_upload_bytes)

        task_id = _new_task_id()
        output_dir = settings.artifact_root / task_id
        output_dir.mkdir(parents=True, exist_ok=False)
        image_path = output_dir / f"input{suffix}"
        image_path.write_bytes(payload)

        try:
            async with app.state.analysis_lock:
                result = await asyncio.to_thread(
                    app.state.analyzer.analyze,
                    image_path=image_path,
                    course_id=course_id,
                    target_char=target_char,
                    output_dir=output_dir,
                )
        except CoursePackError as error:
            raise _course_error_to_api_error(error) from error
        except ApiError:
            raise
        except Exception as error:
            LOGGER.exception("B2 analysis failed for task_id=%s practice_id=%s", task_id, practice_id)
            raise ApiError(500, "50001", "Model inference failed. Please retry the analysis.") from error

        llm_feedback: dict[str, object] | None = None
        if settings.llm_url and settings.llm_model:
            try:
                contract_path = output_dir / "feedback_contract.json"
                import json

                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                llm_feedback = await asyncio.to_thread(
                    call_openai_compatible,
                    contract["llm_messages"],
                    settings.llm_url,
                    settings.llm_model,
                    settings.llm_api_key_env,
                )
                write_json(output_dir / "llm_feedback.json", llm_feedback)
            except Exception:
                LOGGER.exception("Optional LLM rendering failed for task_id=%s; using rules feedback", task_id)

        response = _response_payload(request, settings, task_id, practice_id, result, llm_feedback)
        write_json(output_dir / "http_response.json", response)
        return response

    @app.get("/artifacts/{task_id}/{filename}")
    async def fetch_artifact(task_id: str, filename: str) -> Any:
        if not task_id.startswith("eval_") or filename not in _ASSET_FILENAMES:
            raise ApiError(404, "40401", "The requested analysis asset does not exist.")
        artifact_path = settings.artifact_root / task_id / filename
        if not artifact_path.is_file():
            raise ApiError(404, "40401", "The requested analysis asset does not exist.")
        return FileResponse(artifact_path, media_type="image/png")

    return app
