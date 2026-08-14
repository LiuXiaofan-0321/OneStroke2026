"""Audit whether QC-clean legacy handwriting can support course-specific scoring."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _character_map(rows: list[dict[str, str]]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for row in rows:
        raw_char_id = row.get("char_id", "").strip()
        target_char = row.get("target_char", "").strip()
        if not raw_char_id or not target_char:
            continue
        char_id = int(raw_char_id)
        previous = mapping.get(char_id)
        if previous is not None and previous != target_char:
            raise ValueError(
                f"inconsistent target_char for char_id={char_id}: {previous!r} vs {target_char!r}"
            )
        mapping[char_id] = target_char
    if not mapping:
        raise ValueError("no legacy character mapping could be recovered")
    return mapping


def audit_course_legacy_overlap(
    *,
    character_map_source: str | Path,
    course_manifest: str | Path,
    qc_manifest: str | Path,
    splits_path: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Write a same-character eligibility audit and return its run manifest."""

    character_map_source = Path(character_map_source)
    course_manifest = Path(course_manifest)
    qc_manifest = Path(qc_manifest)
    splits_path = Path(splits_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    char_map = _character_map(_read_rows(character_map_source))
    qc_rows = {row["sample_id"]: row for row in _read_rows(qc_manifest)}
    split_rows = _read_rows(splits_path)

    approved_by_style: dict[str, set[str]] = defaultdict(set)
    for row in _read_rows(course_manifest):
        if row.get("review_status", "").strip().lower() != "approved":
            continue
        approved_by_style[row["style_id"].strip()].add(row["target_char"].strip())

    test_sample_ids_by_char: dict[int, list[str]] = defaultdict(list)
    for split_row in split_rows:
        if split_row.get("split") != "test":
            continue
        sample_id = split_row["sample_id"]
        if sample_id not in qc_rows:
            raise ValueError(f"split sample missing from QC manifest: {sample_id}")
        test_sample_ids_by_char[int(split_row["char_id"])].append(sample_id)

    character_rows = [
        {"char_id": char_id, "target_char": target_char}
        for char_id, target_char in sorted(char_map.items())
    ]
    _write_csv(
        output_dir / "legacy_character_map.csv",
        ["char_id", "target_char"],
        character_rows,
    )

    summary_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    for style_id, course_chars in sorted(approved_by_style.items()):
        overlapping = sorted(
            (char_id, target_char)
            for char_id, target_char in char_map.items()
            if target_char in course_chars
        )
        eligible_test_samples = sum(
            len(test_sample_ids_by_char[char_id]) for char_id, _ in overlapping
        )
        summary_rows.append(
            {
                "style_id": style_id,
                "legacy_character_count": len(char_map),
                "course_character_count": len(course_chars),
                "overlap_character_count": len(overlapping),
                "overlap_characters": "".join(target_char for _, target_char in overlapping),
                "eligible_qc_test_sample_count": eligible_test_samples,
            }
        )
        for char_id, target_char in overlapping:
            for sample_id in sorted(test_sample_ids_by_char[char_id]):
                candidate_rows.append(
                    {
                        "style_id": style_id,
                        "char_id": char_id,
                        "target_char": target_char,
                        "sample_id": sample_id,
                        "image_path": qc_rows[sample_id]["image_path"],
                        "split": "test",
                    }
                )

    _write_csv(
        output_dir / "course_overlap_summary.csv",
        [
            "style_id",
            "legacy_character_count",
            "course_character_count",
            "overlap_character_count",
            "overlap_characters",
            "eligible_qc_test_sample_count",
        ],
        summary_rows,
    )
    _write_csv(
        output_dir / "eligible_course_scoring_pairs.csv",
        ["style_id", "char_id", "target_char", "sample_id", "image_path", "split"],
        candidate_rows,
    )

    total_overlap = sum(int(row["overlap_character_count"]) for row in summary_rows)
    total_candidates = len(candidate_rows)
    manifest = {
        "schema_version": 1,
        "experiment_name": "legacy_to_course_character_overlap_audit_v1",
        "status": (
            "COMPLETE_NO_ELIGIBLE_PAIRS" if total_candidates == 0 else "COMPLETE"
        ),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "inputs": {
            "character_map_source": {
                "path": character_map_source.as_posix(),
                "sha256": _sha256(character_map_source),
            },
            "course_manifest": {
                "path": course_manifest.as_posix(),
                "sha256": _sha256(course_manifest),
            },
            "qc_manifest": {
                "path": qc_manifest.as_posix(),
                "sha256": _sha256(qc_manifest),
            },
            "splits": {
                "path": splits_path.as_posix(),
                "sha256": _sha256(splits_path),
            },
        },
        "legacy_character_count": len(char_map),
        "course_count": len(summary_rows),
        "total_style_specific_overlap_count": total_overlap,
        "eligible_qc_test_sample_count": total_candidates,
        "same_character_required": True,
        "cross_character_scoring_prohibited": True,
        "interpretation": (
            "The QC-clean legacy corpus cannot be used for the current two course packs "
            "because it shares no target character with either approved reference set. "
            "No cross-character score was computed."
            if total_candidates == 0
            else "Eligible same-character QC test samples are listed for course scoring."
        ),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--character-map-source",
        default=(
            "artifacts/paper_ijdar/expert_validation/"
            "candidate_review_v1/candidate_review_form.csv"
        ),
    )
    parser.add_argument(
        "--course-manifest",
        default="references/calli_tongji_beta_manifest.csv",
    )
    parser.add_argument(
        "--qc-manifest",
        default="artifacts/data_qc/manifest_qc_v1.csv",
    )
    parser.add_argument(
        "--splits",
        default="artifacts/data_qc/standard_splits_qc_v1.csv",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/paper_ijdar/course_scoring_scope",
    )
    args = parser.parse_args()

    manifest = audit_course_legacy_overlap(
        character_map_source=args.character_map_source,
        course_manifest=args.course_manifest,
        qc_manifest=args.qc_manifest,
        splits_path=args.splits,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
