from __future__ import annotations

import csv
import io
import zipfile

from PIL import Image

from onestroke_model.scripts.import_calli_tongji import import_calli_tongji
from onestroke_model.scripts.validate_reference_manifest import validate_reference_manifest


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (256, 256), "white").save(output, format="PNG")
    return output.getvalue()


def test_import_calli_tongji_extracts_selected_styles(tmp_path) -> None:
    archive = tmp_path / "calli.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for category, target_char in (("欧阳询-楷", "欧"), ("王羲之-行", "王"), ("颜真卿-楷", "颜")):
            handle.writestr(f"Calli-Tongji/{category}/{target_char}.png", _png_bytes())

    manifest = tmp_path / "references" / "manifest.csv"
    report = import_calli_tongji(archive, tmp_path / "references" / "images", manifest)

    assert report["num_references"] == 2
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["style_id"] for row in rows} == {
        "ouyang_xun_regular_calli_tongji_beta",
        "wang_xizhi_running_calli_tongji_beta",
    }
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "styles:\n"
        "  - style_id: ouyang_xun_regular_calli_tongji_beta\n"
        "    enabled: true\n"
        "    author_id: ouyang_xun\n"
        "    script_style: kaishu\n"
        "  - style_id: wang_xizhi_running_calli_tongji_beta\n"
        "    enabled: true\n"
        "    author_id: wang_xizhi\n"
        "    script_style: xingshu\n",
        encoding="utf-8",
    )
    validation = validate_reference_manifest(manifest, registry, check_files=True, require_approved=True)
    assert validation["valid"] is True
