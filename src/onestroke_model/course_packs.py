"""Validated course-pack catalogues for reference-conditioned practice."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from onestroke_model.config import load_yaml
from onestroke_model.utils.io import read_csv_rows


class CoursePackError(ValueError):
    """Raised when a course request cannot be satisfied by an approved reference."""


@dataclass(frozen=True)
class CourseReference:
    reference_id: str
    course_id: str
    style_id: str
    target_char: str
    image_path: str
    source_work_id: str
    source_version: str


@dataclass(frozen=True)
class CoursePack:
    course_id: str
    display_name: str
    style_id: str
    manifest_path: Path
    cache_index_path: Path
    source_dataset: str
    source_license: str
    status: str
    enabled: bool
    scoring_label: str
    references: tuple[CourseReference, ...]

    def reference_for(self, target_char: str) -> CourseReference:
        if len(target_char) != 1:
            raise CoursePackError("target_char must contain exactly one Unicode character")
        matches = [item for item in self.references if item.target_char == target_char]
        if not matches:
            raise CoursePackError(
                f"unsupported_character: course_id={self.course_id!r}, target_char={target_char!r}"
            )
        if len(matches) != 1:
            raise CoursePackError(
                f"ambiguous_reference: course_id={self.course_id!r}, target_char={target_char!r}"
            )
        return matches[0]

    def catalog_entry(self, cache_available: bool | None = None) -> dict[str, object]:
        return {
            "course_id": self.course_id,
            "display_name": self.display_name,
            "style_id": self.style_id,
            "source_dataset": self.source_dataset,
            "source_license": self.source_license,
            "status": self.status,
            "enabled": self.enabled,
            "scoring_label": self.scoring_label,
            "supported_character_count": len(self.references),
            "cache_available": cache_available,
            "characters": [
                {
                    "target_char": item.target_char,
                    "reference_id": item.reference_id,
                    "reference_image_path": item.image_path,
                }
                for item in self.references
            ],
        }


def _project_root(config_path: Path) -> Path:
    """Resolve project-root-relative paths for the checked-in config location."""
    return config_path.parent.parent


def _resolve_project_path(value: object, config_path: Path) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else _project_root(config_path) / path


def _load_references(
    course_config: dict[str, object], manifest_path: Path
) -> tuple[CourseReference, ...]:
    course_id = str(course_config["course_id"])
    style_id = str(course_config["style_id"])
    rows = [
        row
        for row in read_csv_rows(manifest_path)
        if row.get("review_status", "").lower() == "approved" and row.get("style_id") == style_id
    ]
    if not rows:
        raise CoursePackError(f"course {course_id!r} has no approved references in {manifest_path}")
    references: list[CourseReference] = []
    seen_characters: set[str] = set()
    for row in rows:
        target_char = row.get("target_char", "")
        reference_id = row.get("reference_id", "")
        if len(target_char) != 1 or not reference_id:
            raise CoursePackError(f"course {course_id!r} has an invalid manifest reference")
        if target_char in seen_characters:
            raise CoursePackError(
                f"course {course_id!r} has multiple approved references for {target_char!r}; "
                "multi-prototype aggregation is not enabled"
            )
        seen_characters.add(target_char)
        references.append(
            CourseReference(
                reference_id=reference_id,
                course_id=course_id,
                style_id=style_id,
                target_char=target_char,
                image_path=row.get("image_path", ""),
                source_work_id=row.get("source_work_id", ""),
                source_version=row.get("source_version", ""),
            )
        )
    return tuple(references)


def load_course_packs(
    config_path: str | Path = "configs/course_packs.yaml",
) -> dict[str, CoursePack]:
    """Load enabled/disabled course definitions and their approved character references."""
    path = Path(config_path)
    data = load_yaml(path)
    if int(data.get("schema_version", 0)) != 1:
        raise CoursePackError("course pack schema_version must be 1")
    raw_courses = data.get("courses")
    if not isinstance(raw_courses, list):
        raise CoursePackError("course pack config field courses must be a list")
    courses: dict[str, CoursePack] = {}
    required = {
        "course_id",
        "display_name",
        "style_id",
        "manifest",
        "cache_index",
        "source_dataset",
        "source_license",
        "status",
        "enabled",
        "scoring_label",
    }
    for item in raw_courses:
        if not isinstance(item, dict):
            raise CoursePackError("each course definition must be a mapping")
        missing = sorted(required - set(item))
        if missing:
            raise CoursePackError(f"course definition missing fields: {missing}")
        course_id = str(item["course_id"])
        if course_id in courses:
            raise CoursePackError(f"duplicate course_id: {course_id}")
        manifest_path = _resolve_project_path(item["manifest"], path)
        cache_index_path = _resolve_project_path(item["cache_index"], path)
        courses[course_id] = CoursePack(
            course_id=course_id,
            display_name=str(item["display_name"]),
            style_id=str(item["style_id"]),
            manifest_path=manifest_path,
            cache_index_path=cache_index_path,
            source_dataset=str(item["source_dataset"]),
            source_license=str(item["source_license"]),
            status=str(item["status"]),
            enabled=bool(item["enabled"]),
            scoring_label=str(item["scoring_label"]),
            references=_load_references(item, manifest_path),
        )
    if not courses:
        raise CoursePackError("course pack config contains no courses")
    return courses


def get_course(courses: dict[str, CoursePack], course_id: str) -> CoursePack:
    try:
        course = courses[course_id]
    except KeyError as exc:
        raise CoursePackError(f"unknown_course: {course_id!r}") from exc
    if not course.enabled:
        raise CoursePackError(f"course_disabled: {course_id!r}")
    return course


def build_course_catalog(
    courses: dict[str, CoursePack], require_cache: bool = False
) -> dict[str, object]:
    """Return the frontend-safe list of supported characters for every course."""
    catalog_courses: list[dict[str, object]] = []
    for course in courses.values():
        cache_available = course.cache_index_path.is_file()
        if require_cache and course.enabled and not cache_available:
            raise CoursePackError(f"missing_course_cache: {course.cache_index_path}")
        catalog_courses.append(course.catalog_entry(cache_available=cache_available))
    return {"schema_version": 1, "courses": catalog_courses}
