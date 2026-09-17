#!/usr/bin/env python3
"""Recompose the frozen dataset overview without changing any sample pixels.

Figure contract
---------------
Claim: a documented audit yields 769 unique labelled samples covering 40
identities; seven natural cross-style pairs illustrate the separate reference
library, whose masks are parser-derived and are not segmentation ground truth.
Archetype: image plate with an audit flow. Panel a: audit counts; b: all 40
previously selected project representatives; c: all seven previously selected
reference pairs. The repeated acquisition examples are omitted here because
the preceding channel-definition figure explains the annotation contract.

Python/matplotlib only; final size 6.30 x 4.35 in. Exact RGB image arrays are
decoded from the previous vector PDF and embedded again with interpolation
disabled. No recropping, thresholding, resampling of the source arrays,
contrast changes, new sample selection, modelling, or statistical analysis.
Native raster dimensions, PDF object IDs, and hashes are exported to JSON.
Latin and Chinese text remain editable in PDF/SVG; the SVG embeds the original
PDF's subset Chinese font so the character identity labels are portable.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path

import fitz
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, findfont, fontManager
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / "figures/redrawn/figure2_dataset_overview.pdf"
MANIFEST = ROOT / "figures/figure_provenance_manifest.json"
CHAR_MAP = ROOT.parent / "artifacts/paper_ijdar/course_scoring_scope/legacy_character_map.csv"
WIDTH, HEIGHT = 6.30, 4.35
INK, MUTED, RULE = "#24282D", "#616A74", "#D7DDE3"
ACCENT = "#176B7D"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def select_latin_font() -> str:
    for family in ("Liberation Sans", "Arial", "DejaVu Sans"):
        try:
            findfont(family, fallback_to_default=False)
            return family
        except ValueError:
            continue
    raise RuntimeError("No supported sans-serif font is available.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    qa = OUT / "qa"
    qa.mkdir(exist_ok=True)
    document = fitz.open(SOURCE)
    page = document[0]
    embedded = page.get_image_info(xrefs=True)
    assert len(embedded) == 58, "Unexpected source PDF image structure."
    assert [x["xref"] for x in embedded[4:44]] == list(range(17, 57))
    assert [x["xref"] for x in embedded[44:58]] == list(range(57, 71))

    old_manifest = json.loads(MANIFEST.read_text())["figures"]["figure2_dataset_overview"]
    with CHAR_MAP.open(newline="") as stream:
        identities = {int(r["char_id"]): r["target_char"] for r in csv.DictReader(stream)}
    assert sorted(identities) == list(range(40))
    source_text = page.get_text()
    for identity, character in identities.items():
        assert f"{character}{identity}" in source_text.replace(" ", "")
    pair_section = source_text.split("Wang Xizhi\nrunning script\n", 1)[1]
    pair_chars = pair_section.split("Calli-Tongji", 1)[0].strip().splitlines()
    assert len(pair_chars) == 7

    # Reuse the embedded font, avoiding guesses about unfamiliar identity names.
    chinese_font_info = [f for f in page.get_fonts(full=True) if "WenQuanYi" in f[3]]
    assert len(chinese_font_info) == 1
    font_xref = chinese_font_info[0][0]
    font_bytes = document.extract_font(font_xref)[3]
    font_path = qa / "figure3_wenquanyi_subset.ttf"
    font_path.write_bytes(font_bytes)
    chinese_name = FontProperties(fname=str(font_path)).get_name()
    latin_font = select_latin_font()
    fontManager.addfont(font_path)
    chinese = FontProperties(family=[chinese_name, latin_font])
    plt.rcParams.update({
        "font.family": latin_font,
        "font.size": 7,
        "text.color": INK,
        "axes.labelcolor": INK,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "image.interpolation": "none",
        "image.resample": False,
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })
    fig = plt.figure(figsize=(6.30, 4.35), dpi=600)
    meta: dict[str, object] = {
        "schema_version": 1,
        "figure": "manuscript Figure 3",
        "source_pdf": str(SOURCE.relative_to(ROOT.parent)),
        "source_pdf_sha256": sha256(SOURCE.read_bytes()),
        "source_manifest_sha256": sha256(MANIFEST.read_bytes()),
        "character_map_sha256": sha256(CHAR_MAP.read_bytes()),
        "size_inches": [WIDTH, HEIGHT],
        "latin_font": latin_font,
        "chinese_font": {
            "source_pdf_xref": font_xref,
            "sha256": sha256(font_bytes),
            "family": chinese_name,
            "note": "Existing PDF's Chinese subset; also embedded into SVG.",
        },
        "image_integrity": {
            "source": "Decoded image XObjects from the existing frozen figure PDF.",
            "crop": "Unchanged; no additional crop or padding in source arrays.",
            "intensity_adjustment": "None",
            "pixel_resampling": "None in embedded source arrays; nearest/no interpolation for display.",
            "selection": "All original 40 representatives and all original seven reference pairs.",
            "omitted_panels": "Only four repeated acquisition illustrations; explained in Figure 2.",
        },
        "qc": {
            "recovered": 894, "missing_mapping": 54, "complete": 840,
            "mismatches": 12, "duplicate_noncanonical": 59, "clean": 769,
            "identity_count": 40,
            "source": "Data Resources subsection, frozen counts; no recomputation.",
            "check": "894 - 54 = 840; 840 - 12 - 59 = 769",
        },
        "images": [],
    }
    assert 894 - 54 == 840 and 840 - 12 - 59 == 769

    def txt(x: float, y: float, value: str, **kwargs):
        return fig.text(x / WIDTH, y / HEIGHT, value, transform=fig.transFigure,
                        ha=kwargs.pop("ha", "left"), va=kwargs.pop("va", "center"),
                        fontsize=kwargs.pop("fontsize", 7), **kwargs)

    def line(x0: float, y: float, x1: float, color: str = RULE):
        fig.add_artist(Line2D([x0 / WIDTH, x1 / WIDTH], [y / HEIGHT, y / HEIGHT],
                              transform=fig.transFigure, color=color, linewidth=0.6))

    def arrow(x0: float, y: float, x1: float):
        fig.add_artist(FancyArrowPatch((x0 / WIDTH, y / HEIGHT),
                                      (x1 / WIDTH, y / HEIGHT),
                                      transform=fig.transFigure, arrowstyle="-|>",
                                      mutation_scale=7, linewidth=0.85, color=MUTED))

    def heading(letter: str, title: str, y: float, note: str | None = None):
        txt(0.06, y, letter, fontsize=9, fontweight="bold")
        txt(0.25, y, title, fontsize=8.2, fontweight="bold")
        if note:
            txt(6.20, y, note, fontsize=6.5, color=MUTED, ha="right")

    def image_tile(xref: int, center_x: float, center_y: float,
                   max_w: float, max_h: float, identity_metadata: dict):
        record = document.extract_image(xref)
        data = record["image"]
        arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))
        h, w = arr.shape[:2]
        scale = min(max_w / w, max_h / h)
        draw_w, draw_h = w * scale, h * scale
        ax = fig.add_axes([(center_x - draw_w / 2) / WIDTH,
                           (center_y - draw_h / 2) / HEIGHT,
                           draw_w / WIDTH, draw_h / HEIGHT])
        ax.imshow(arr, interpolation="none", resample=False, aspect="equal")
        ax.set_axis_off()
        image_record = {
            "xref": xref,
            "native_width": w,
            "native_height": h,
            "decoded_rgb_sha256": sha256(arr.tobytes()),
            "extracted_image_sha256": sha256(data),
            "display_inches": [draw_w, draw_h],
            "effective_resolution_ppi": round(1 / scale, 2),
            **identity_metadata,
        }
        meta["images"].append(image_record)

    # Panel a: exact counts are a discrete audit flow, not proportional bars.
    heading("a", "Quality control", 4.18,
            "Semantic audit; exclusions frozen before any evaluation")
    for x, n, label, accent in (
        (0.51, "894", "Recovered", False),
        (2.78, "840", "Complete GT", False),
        (5.61, "769", "QC-clean", True),
    ):
        txt(x, 3.94, n, ha="center", fontsize=20, fontweight="bold",
            color=ACCENT if accent else INK)
        txt(x, 3.70, label, ha="center", fontsize=7.2,
            color=ACCENT if accent else MUTED)
    arrow(1.04, 3.93, 2.22)
    txt(1.62, 4.045, "−54", fontsize=8.0, ha="center", fontweight="bold")
    txt(1.62, 3.73, "No direction map", fontsize=6.5, color=MUTED, ha="center")
    arrow(3.39, 3.93, 5.03)
    txt(4.20, 4.045, "−12 image/GT mismatches", fontsize=6.6, ha="center")
    txt(4.20, 3.73, "−59 non-canonical exact duplicates", fontsize=6.5,
        color=MUTED, ha="center")
    txt(0.06, 3.48, "40 identities retained", fontsize=7.0, fontweight="bold")
    txt(6.20, 3.48, "No exact-duplicate group crosses either frozen split.",
        fontsize=6.5, color=MUTED, ha="right")
    line(0.06, 3.36, 6.20)

    # Panel b: retain the original row-major identity order and every source tile.
    heading("b", "Project corpus", 3.23,
            "One frozen QC-clean representative per identity; "
            "the training and evaluation corpus")
    for identity in range(40):
        row, col = divmod(identity, 10)
        cx = 0.365 + col * 0.610
        cy = 2.955 - row * 0.438
        image_tile(17 + identity, cx, cy, 0.535, 0.320, {
            "panel": "b", "identity": identity, "target_char": identities[identity],
            "sample_id": old_manifest["atlas_sample_ids"][identity],
        })
        # CJK and Latin labels are separate editable text objects, using fonts
        # that are actually available and preserving the original identity map.
        txt(cx - 0.055, cy - 0.217, identities[identity], ha="right", fontsize=6.8,
            color=MUTED, fontproperties=chinese)
        txt(cx - 0.027, cy - 0.217, str(identity), fontsize=6.3, color=MUTED)
    line(0.06, 1.29, 6.20)

    # Panel c: exact pairs in their original order; these are parser-cache masks.
    heading("c", "External references", 1.165,
            "All 7 natural same-character cross-style pairs; "
            "separate external library")
    for row, (name, style) in enumerate((("Ouyang Xun", "regular script"),
                                       ("Wang Xizhi", "running script"))):
        cy = 0.875 - 0.377 * row
        txt(0.06, cy + 0.038, name, fontsize=6.6, fontweight="bold")
        txt(0.06, cy - 0.088, style, fontsize=6.3, color=MUTED)
        for col in range(7):
            cx = 1.40 + col * 0.755
            image_tile(57 + row * 7 + col, cx, cy, 0.560, 0.305, {
                "panel": "c", "style": style, "calligrapher": name,
                "target_char": pair_chars[col],
                "pair_id": old_manifest["external_reference_pairs"][col],
            })
            if row == 1:
                txt(cx, 0.274, pair_chars[col], fontsize=6.8, color=MUTED,
                    ha="center", fontproperties=chinese)
    txt(0.06, 0.083, "Cached v1 parser masks, not segmentation GT", fontsize=6.3, color=MUTED)
    txt(6.20, 0.083, "Calli-Tongji open subset · CC BY-NC 4.0", fontsize=6.3,
        color=MUTED, ha="right")

    assert len(meta["images"]) == 54
    prefix = OUT / "figure3_dataset_overview"
    fig.savefig(prefix.with_suffix(".pdf"), dpi=600)
    fig.savefig(prefix.with_suffix(".svg"), dpi=600)
    fig.savefig(prefix.with_suffix(".png"), dpi=600)
    # Portable editable CJK text: include the font already embedded in source.
    svg_path = prefix.with_suffix(".svg")
    svg = svg_path.read_text()
    face = ("<style type=\"text/css\">@font-face { font-family: '" + chinese_name +
            "'; src: url(data:font/ttf;base64," + base64.b64encode(font_bytes).decode() +
            ") format('truetype'); font-weight: normal; font-style: normal; }</style>")
    svg = svg.replace("<defs>", "<defs>" + face, 1)
    svg_path.write_text(svg)
    # Explicit dimensions ensure the delivered figure keeps the requested size.
    pdf = fitz.open(prefix.with_suffix(".pdf"))
    assert abs(pdf[0].rect.width / 72 - WIDTH) < 0.001
    assert abs(pdf[0].rect.height / 72 - HEIGHT) < 0.001
    output_image_hashes = []
    storage_flips_corrected = 0
    for info in pdf[0].get_image_info(xrefs=True):
        rgb = np.asarray(Image.open(io.BytesIO(pdf.extract_image(info["xref"])["image"])).convert("RGB"))
        transform = info["transform"]
        assert transform[1] == 0 and transform[2] == 0
        if transform[3] < 0:
            rgb = np.flipud(rgb)
            storage_flips_corrected += 1
        if transform[0] < 0:
            rgb = np.fliplr(rgb)
        output_image_hashes.append(sha256(rgb.tobytes()))
    expected_hashes = [im["decoded_rgb_sha256"] for im in meta["images"]]
    assert sorted(output_image_hashes) == sorted(expected_hashes), "Export changed native pixels."
    output_text = pdf[0].get_text()
    missing_char_labels = [c for c in [*identities.values(), *pair_chars] if c not in output_text]
    assert not missing_char_labels, f"Missing editable CJK labels: {missing_char_labels}"
    meta["verification"] = {
        "native_rgb_hash_multiset_matches_source": True,
        "pdf_storage_row_reversals_corrected_by_page_transform": storage_flips_corrected,
        "embedded_images": len(output_image_hashes),
        "all_identity_labels_selectable_in_pdf": True,
        "final_pdf_inches": [pdf[0].rect.width / 72, pdf[0].rect.height / 72],
        "svg_contains_editable_text": "<text" in svg,
        "svg_embeds_cjk_font": "data:font/ttf;base64," in svg,
        "png_dpi": 600,
        "counts_reconcile": True,
        "no_inferential_statistics": True,
    }
    meta["outputs"] = {
        ext: {"file": prefix.with_suffix("." + ext).name,
              "sha256": sha256(prefix.with_suffix("." + ext).read_bytes())}
        for ext in ("pdf", "svg", "png")
    }
    prefix.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    plt.close(fig)
    print(json.dumps(meta["verification"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
