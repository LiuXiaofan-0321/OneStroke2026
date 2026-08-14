"""Select a score-independent confirmatory human-rating pair set.

The selection excludes every development pair and every glyph instance seen in
the 150-pair development study.  It stops at an internal-review package and
does not freeze or expose pairs to raters.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

CONFIRMATORY_STATUS = "CANDIDATE_ONLY_DO_NOT_RATE"
CONFIRMATORY_FREEZE_STATUS = "NOT_FROZEN"
CONFIRMATORY_STUDY_VERSION = "spatial_score_confirmatory_v1"
CONFIRMATORY_SELECTION_SEED = 20260814


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(fieldnames or ())
    if not fields:
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"])
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(*values: str) -> str:
    payload = ":".join([str(CONFIRMATORY_SELECTION_SEED), *values])
    return hashlib.sha256(payload.encode()).hexdigest()


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def select_confirmatory_pairs(
    candidate_pool: Sequence[Mapping[str, Any]],
    development_pairs: Sequence[Mapping[str, Any]],
    *,
    target_pair_count: int = 100,
    base_pairs_per_character: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    development_pair_ids = {str(row["pair_id"]) for row in development_pairs}
    development_instances = {
        str(row[field])
        for row in development_pairs
        for field in ("candidate_instance_id", "reference_instance_id")
    }
    eligible: list[dict[str, Any]] = []
    for source in candidate_pool:
        row = dict(source)
        if str(row["pair_id"]) in development_pair_ids:
            continue
        if str(row["candidate_instance_id"]) in development_instances:
            continue
        if str(row["reference_instance_id"]) in development_instances:
            continue
        if any(
            _boolish(row.get(field))
            for field in (
                "same_instance_detected",
                "same_image_detected",
                "same_mask_detected",
                "near_duplicate_suspected",
            )
        ):
            continue
        eligible.append(row)

    by_character: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_character[str(row["char_id"])].append(row)
    character_ids = sorted(by_character, key=int)
    if not character_ids:
        raise ValueError("no confirmatory candidate characters remain")
    base_total = len(character_ids) * base_pairs_per_character
    extra_count = target_pair_count - base_total
    if not 0 <= extra_count <= len(character_ids):
        raise ValueError(
            "target count must allow either base or base+1 pairs per character"
        )
    for char_id in character_ids:
        by_character[char_id].sort(
            key=lambda row: _stable_hash(
                "pair-order",
                char_id,
                str(row["pair_id"]),
            )
        )
        if len(by_character[char_id]) < base_pairs_per_character:
            raise ValueError(
                f"character {char_id} has only {len(by_character[char_id])} "
                "instance-independent candidates"
            )

    extra_eligible = [
        char_id
        for char_id in character_ids
        if len(by_character[char_id]) >= base_pairs_per_character + 1
    ]
    if len(extra_eligible) < extra_count:
        raise ValueError("insufficient characters for balanced extra pairs")
    extra_characters = set(
        sorted(
            extra_eligible,
            key=lambda char_id: _stable_hash("extra-character", char_id),
        )[:extra_count]
    )

    selected: list[dict[str, Any]] = []
    reserves: list[dict[str, Any]] = []
    for char_id in character_ids:
        count = base_pairs_per_character + int(char_id in extra_characters)
        for row in by_character[char_id][:count]:
            selected.append(
                {
                    **row,
                    "confirmatory_study_version": CONFIRMATORY_STUDY_VERSION,
                    "study_status": CONFIRMATORY_STATUS,
                    "freeze_status": CONFIRMATORY_FREEZE_STATUS,
                    "selection_policy": (
                        "score-independent stable hash; excludes all development "
                        "pairs and development glyph instances"
                    ),
                }
            )
        reserves.extend(
            {
                **row,
                "confirmatory_study_version": CONFIRMATORY_STUDY_VERSION,
                "study_status": "RESERVE_ONLY_DO_NOT_RATE",
                "freeze_status": CONFIRMATORY_FREEZE_STATUS,
                "selection_policy": "score-independent stable-hash reserve order",
            }
            for row in by_character[char_id][count:]
        )

    selected.sort(
        key=lambda row: (
            int(row["char_id"]),
            _stable_hash("selected-final-order", str(row["pair_id"])),
        )
    )
    for index, row in enumerate(selected, start=1):
        row["confirmatory_selection_rank"] = index
    reserves.sort(
        key=lambda row: (
            int(row["char_id"]),
            _stable_hash("reserve-final-order", str(row["pair_id"])),
        )
    )
    for index, row in enumerate(reserves, start=1):
        row["confirmatory_reserve_rank"] = index

    if len(selected) != target_pair_count:
        raise RuntimeError(
            f"selected {len(selected)} pairs instead of {target_pair_count}"
        )
    pair_ids = {str(row["pair_id"]) for row in selected}
    selected_instances = {
        str(row[field])
        for row in selected
        for field in ("candidate_instance_id", "reference_instance_id")
    }
    metadata = {
        "schema_version": 1,
        "study_version": CONFIRMATORY_STUDY_VERSION,
        "status": CONFIRMATORY_STATUS,
        "freeze_status": CONFIRMATORY_FREEZE_STATUS,
        "selection_seed": CONFIRMATORY_SELECTION_SEED,
        "candidate_pool_count": len(candidate_pool),
        "development_pair_count": len(development_pair_ids),
        "development_instance_count": len(development_instances),
        "eligible_instance_independent_pair_count": len(eligible),
        "selected_pair_count": len(selected),
        "reserve_pair_count": len(reserves),
        "character_count": len(character_ids),
        "pairs_per_character": {
            char_id: sum(str(row["char_id"]) == char_id for row in selected)
            for char_id in character_ids
        },
        "pair_overlap_with_development": len(pair_ids & development_pair_ids),
        "instance_overlap_with_development": len(
            selected_instances & development_instances
        ),
        "selection_uses_production_score": False,
        "selection_uses_coverage_score": False,
        "selection_uses_spatial_score": False,
        "selection_uses_human_rating": False,
        "next_gate": (
            "Project team reviews images for corruption or accidental duplication. "
            "Any replacement must use the preordered reserve list without consulting "
            "any model score. Freeze the final list before collecting ratings."
        ),
    }
    return selected, reserves, metadata


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_confirmatory_review_sheets(
    selected: list[dict[str, Any]],
    *,
    data_root: Path,
    output_dir: Path,
    pairs_per_sheet: int = 20,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cell_width, cell_height = 470, 250
    columns, rows_per_page = 4, 5
    if pairs_per_sheet != columns * rows_per_page:
        raise ValueError("review sheet layout requires 20 pairs per page")
    paths: list[Path] = []
    for page, start in enumerate(range(0, len(selected), pairs_per_sheet), start=1):
        canvas = Image.new(
            "RGB",
            (columns * cell_width, 52 + rows_per_page * cell_height),
            "white",
        )
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (18, 12),
            f"Confirmatory internal review only | sheet {page:02d}",
            fill=(150, 0, 0),
            font=_font(22),
        )
        for slot, row in enumerate(selected[start : start + pairs_per_sheet], start=1):
            local = slot - 1
            left = (local % columns) * cell_width
            top = 52 + (local // columns) * cell_height
            draw.rectangle(
                (left, top, left + cell_width - 1, top + cell_height - 1),
                outline=(180, 180, 180),
            )
            images: list[Image.Image] = []
            for field in ("candidate_image_path", "reference_image_path"):
                relative = Path(str(row[field]).replace("\\", "/"))
                image = Image.open(data_root / relative).convert("RGB")
                image.thumbnail((165, 165), Image.Resampling.LANCZOS)
                images.append(image)
            canvas.paste(images[0], (left + 18, top + 45))
            canvas.paste(images[1], (left + 212, top + 45))
            draw.text(
                (left + 10, top + 8),
                (
                    f"{start + slot:03d} char_id={row['char_id']} "
                    f"({row['target_char']})"
                ),
                fill="black",
                font=_font(17),
            )
            draw.text(
                (left + 18, top + 215),
                f"C {row['candidate_instance_id']}",
                fill=(0, 70, 150),
                font=_font(14),
            )
            draw.text(
                (left + 212, top + 215),
                f"R {row['reference_instance_id']}",
                fill=(100, 60, 0),
                font=_font(14),
            )
            draw.text(
                (left + 18, top + 232),
                "Selection did not use any model score",
                fill=(30, 30, 30),
                font=_font(14),
            )
            row["review_sheet"] = f"confirmatory_review_{page:02d}.png"
            row["review_sheet_slot"] = slot
        path = output_dir / f"confirmatory_review_{page:02d}.png"
        canvas.save(path)
        paths.append(path)
    return paths


def build_confirmatory_candidate_review(
    *,
    candidate_pool_path: str | Path,
    development_pairs_path: str | Path,
    data_root: str | Path,
    output_dir: str | Path,
    target_pair_count: int = 100,
) -> dict[str, Any]:
    pool_path = Path(candidate_pool_path)
    development_path = Path(development_pairs_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    selected, reserves, metadata = select_confirmatory_pairs(
        _read_csv(pool_path),
        _read_csv(development_path),
        target_pair_count=target_pair_count,
    )
    sheets = render_confirmatory_review_sheets(
        selected,
        data_root=Path(data_root),
        output_dir=output,
    )
    _write_csv(output / "confirmatory_candidate_pairs_100.csv", selected)
    _write_csv(output / "confirmatory_reserve_pairs.csv", reserves)
    review_rows = [
        {
            "study_status": CONFIRMATORY_STATUS,
            "freeze_status": CONFIRMATORY_FREEZE_STATUS,
            "selection_rank": row["confirmatory_selection_rank"],
            "pair_id": row["pair_id"],
            "char_id": row["char_id"],
            "target_char": row["target_char"],
            "candidate_instance_id": row["candidate_instance_id"],
            "reference_instance_id": row["reference_instance_id"],
            "review_sheet": row["review_sheet"],
            "review_sheet_slot": row["review_sheet_slot"],
            "same_instance_suspected": "",
            "bad_image_suspected": "",
            "accidental_duplicate_suspected": "",
            "keep_for_freeze": "",
            "review_notes": "",
        }
        for row in selected
    ]
    _write_csv(output / "confirmatory_review_form.csv", review_rows)
    metadata.update(
        {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "inputs": {
                "candidate_pool": {
                    "path": pool_path.as_posix(),
                    "sha256": _sha256(pool_path),
                },
                "development_pairs": {
                    "path": development_path.as_posix(),
                    "sha256": _sha256(development_path),
                },
                "data_root": Path(data_root).as_posix(),
            },
            "review_sheets": [path.name for path in sheets],
        }
    )
    (output / "confirmatory_candidate_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "\n".join(
            [
                "# Confirmatory human-rating candidates",
                "",
                f"Status: **{CONFIRMATORY_STATUS} / {CONFIRMATORY_FREEZE_STATUS}**.",
                "",
                "Do not send these pairs to raters yet.",
                "",
                (
                    "Review `confirmatory_review_form.csv` with the five numbered "
                    "contact sheets. Check only corruption, accidental duplication, "
                    "or mismatched characters. Do not inspect production, "
                    "coverage-aware, spatial, or human scores when deciding exclusions."
                ),
                "",
                (
                    "All 100 pairs are distinct from the development pairs and use no "
                    "glyph instance that appeared in the 150-pair development study. "
                    "Replacements must come from `confirmatory_reserve_pairs.csv` in "
                    "its recorded order."
                ),
                "",
                (
                    "After review, create a new immutable frozen study package before "
                    "any human rating starts."
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return metadata
