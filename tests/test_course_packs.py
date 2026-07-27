from __future__ import annotations

import pytest

from onestroke_model.course_packs import (
    CoursePackError,
    build_course_catalog,
    get_course,
    load_course_packs,
)


def test_checked_in_course_packs_expose_two_hundred_approved_characters() -> None:
    courses = load_course_packs("configs/course_packs.yaml")

    assert set(courses) == {"ouyang_xun_regular_100_beta", "wang_xizhi_running_100_beta"}
    assert len(courses["ouyang_xun_regular_100_beta"].references) == 100
    assert len(courses["wang_xizhi_running_100_beta"].references) == 100

    catalog = build_course_catalog(courses)
    assert catalog["schema_version"] == 1
    assert [item["supported_character_count"] for item in catalog["courses"]] == [100, 100]
    assert catalog["courses"][0]["scoring_label"] == "参考结构匹配度"


def test_course_only_resolves_supported_same_character_reference() -> None:
    course = get_course(
        load_course_packs("configs/course_packs.yaml"), "ouyang_xun_regular_100_beta"
    )

    reference = course.reference_for("亮")

    assert reference.target_char == "亮"
    assert reference.style_id == "ouyang_xun_regular_calli_tongji_beta"
    with pytest.raises(CoursePackError, match="unsupported_character"):
        course.reference_for("永")
    with pytest.raises(CoursePackError, match="target_char"):
        course.reference_for("两个")
