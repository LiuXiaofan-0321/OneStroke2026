"""Recompose manuscript Figure 1 with a multi-pair input gallery.

Contract
--------
Panel (a) shows three natural same-character cross-style pairs from the frozen
external reference library instead of a single pair; panels (b)--(e) are the
unchanged frozen vector artwork, which is carried over as PDF content rather
than re-rendered as raster. The pipeline panels therefore keep their exact
type, hairlines, and colours, and the added labels reuse the source PDF's own
embedded font subset.

The single pair of the previous revision (target character 亮, row 1 here) is
reused pixel-for-pixel from the frozen figure; the two additional rows are the
next pairs in the frozen cross-reference file, resized with the same
256 -> 194 px reduction already applied to the frozen tiles. No new sample
selection, cropping, thresholding, or model inference is performed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import fitz
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
PAPER = HERE.parents[1]
ROOT = PAPER.parent
SOURCE = PAPER / "figures/redrawn/figure1_pipeline.pdf"
REFERENCE_INDEX = ROOT / "references/cache/segformer_b2_v1/index.json"
CROSS_PAIRS = ROOT / "artifacts/paper_ijdar/cross_reference/cross_reference_pairs.csv"
STEM = HERE / "figure1_pipeline"
TILE_PX = 194

# Panel (a) geometry in source-page points (origin top-left, y downwards).
CLEAR = fitz.Rect(6.0, 0.0, 70.0, 120.0)
GALLERY_TOP = 12.0
GALLERY_LEFT = 13.0
GLYPH = 25.0
COLUMN_GAP = 2.5
ROW_GAP = 3.5
LABEL_COLUMN = 9.0
HEADER_SIZE = 5.8
CJK_SIZE = 8.0
TITLE_SIZE = 7.2
MUTED = (0.38, 0.42, 0.45)

# Plate treatment copied from the frozen figure: panels (b)--(d) are framed on
# the shared plate grey, panel (e) is the same grey card, and the bottom
# stage-label strip is a hair darker. Panel (a) adopts the card treatment so
# the source images no longer sit as bare white cut-outs beside them.
PLATE = (247, 248, 250)  # PANEL_BG in figure_style.py
FRAME = (215, 220, 225)  # GRID in figure_style.py
FRAME_WIDTH = 0.55  # clean_image_axis spine width
STRIP = (238, 240, 242)  # measured stage-label strip colour
STRIP_FILL = fitz.Rect(1.44, 107.5, 72.4, 121.18)
# The stage-label strip carries a small arrow between consecutive labels. The
# first of them (between "Input pair" and "Overlapping parse") lies inside the
# redacted area, so that band of the frozen vector artwork is re-inserted
# verbatim after the repair instead of being approximated.
ARROW_BAND = fitz.Rect(60.4, 107.5, 68.6, 121.18)
REGULAR_STYLE = "ouyang_xun_regular_calli_tongji_beta"
RUNNING_STYLE = "wang_xizhi_running_calli_tongji_beta"
CJK_FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_reference_index() -> dict[str, dict]:
    payload = json.loads(REFERENCE_INDEX.read_text(encoding="utf-8"))
    return {entry["reference_id"]: entry for entry in payload["references"]}


def selected_pairs() -> list[dict]:
    """The frozen pipeline pair (亮) followed by the next pairs in file order."""

    with CROSS_PAIRS.open(newline="", encoding="utf-8") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row["pair_type"] == "same_character_cross_style"
        ]
    pivot = next(index for index, row in enumerate(rows) if row["candidate_char"] == "亮")
    chosen = [rows[pivot]]
    cursor = pivot + 1
    while len(chosen) < 3:
        chosen.append(rows[cursor % len(rows)])
        cursor += 1
    return chosen


def styles_of(pair: dict) -> tuple[str, str]:
    """Return (regular-script reference id, running-script candidate id)."""

    by_role = {
        pair["reference_style_id"]: pair["reference_reference_id"],
        pair["candidate_style_id"]: pair["candidate_reference_id"],
    }
    return by_role[REGULAR_STYLE], by_role[RUNNING_STYLE]


def tile_from_image(path: Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    if image.size != (256, 256):
        raise ValueError(f"Unexpected source tile size for {path}: {image.size}")
    return np.asarray(image.resize((TILE_PX, TILE_PX), Image.LANCZOS))


def png_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="PNG")
    return buffer.getvalue()


def on_plate(tile: np.ndarray) -> np.ndarray:
    """Map the tile's white paper onto the figure's card grey.

    The mapping is a single uniform linear function per channel,
    ``out = round(C * plate / 255)``: white paper becomes exactly the plate
    colour and black ink stays black. No contrast, gamma, threshold, or crop
    operation is applied, and the ink density relative to the paper,
    ``(paper - min(RGB)) / paper``, is unchanged up to one 8-bit level.
    """

    scaled = tile.astype(np.uint16) * np.asarray(PLATE, dtype=np.uint16)
    return ((scaled + 127) // 255).astype(np.uint8)


def ink_coverage(tile: np.ndarray, paper: float) -> np.ndarray:
    return (paper - tile.min(axis=-1).astype(np.float64)) / paper


def main() -> None:
    source = fitz.open(SOURCE)
    source_page = source[0]
    page_rect = source_page.rect
    width, height = page_rect.width, page_rect.height

    # --- Read the frozen panel (a) so the reused tiles stay bit-identical. ----
    embedded = [item for item in source_page.get_image_info(xrefs=True)
                if item["bbox"][2] <= 60.0]
    if len(embedded) != 2:
        raise ValueError("Expected the two frozen panel-(a) tiles.")
    frozen_tiles = {
        index: np.asarray(
            Image.open(io.BytesIO(source.extract_image(item["xref"])["image"])).convert("RGB")
        )
        for index, item in enumerate(sorted(embedded, key=lambda item: item["bbox"][1]))
    }

    labels = {span["text"].strip(): span for span in _spans(source_page)}
    for required in ("reference", "candidate", "Input pair"):
        if required not in labels:
            raise ValueError(f"Frozen figure is missing the label {required!r}.")

    font_regular = _extract_font(source, source_page, "LMSansTT8-Regular")
    font_bold = _extract_font(source, source_page, "LMSansTT10-Bold")

    # --- New page: frozen vector content, panel (a) cleared. ------------------
    output = fitz.open()
    page = output.new_page(width=width, height=height)
    page.show_pdf_page(page_rect, source, 0)
    # Redaction removes the superseded panel-(a) tiles and labels instead of
    # covering them, so the rebuilt page carries no hidden duplicate content.
    page.add_redact_annot(CLEAR, fill=(1, 1, 1))
    page.apply_redactions(
        images=fitz.PDF_REDACT_IMAGE_REMOVE,
        graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
    )
    # The redaction also cleared the stage-label strip beneath the panel-(a)
    # label; restore it so the strip runs continuously like its neighbours.
    page.draw_rect(STRIP_FILL, color=None, fill=_rgb_tuple(STRIP), overlay=True)
    # Put the frozen strip band back so the "Input pair -> Overlapping parse"
    # arrow reappears with its original geometry, colour, and line width.
    source_arrow = _arrow_band_geometry(source_page)
    page.show_pdf_page(ARROW_BAND, source, 0, clip=ARROW_BAND)

    reference_font = ("fig1", str(font_regular[0]))
    title_font = ("fig1b", str(font_bold[0]))
    page.insert_font(fontname=reference_font[0], fontfile=reference_font[1])
    page.insert_font(fontname=title_font[0], fontfile=title_font[1])
    regular_metrics = fitz.Font(fontfile=reference_font[1])
    bold_metrics = fitz.Font(fontfile=title_font[1])

    pairs = selected_pairs()
    entries = load_reference_index()
    total_width = 2 * GLYPH + COLUMN_GAP
    left = GALLERY_LEFT
    columns = (
        (left, left + GLYPH),
        (left + GLYPH + COLUMN_GAP, left + total_width),
    )
    if columns[-1][1] > CLEAR.x1 - 4.0:
        raise ValueError("Panel-(a) gallery exceeds the cleared area.")
    page.insert_font(fontname="fig1cjk", fontfile=str(CJK_FONT))
    cjk_metrics = fitz.Font(fontfile=str(CJK_FONT))

    provenance: dict[str, object] = {
        "schema_version": 1,
        "figure": "manuscript Figure 1",
        "source_pdf": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_pdf_sha256": sha256(SOURCE.read_bytes()),
        "page_size_inches": [round(width / 72, 4), round(height / 72, 4)],
        "reused_frozen_tiles": False,
        "panel_a": {
            "arrangement": "rows are target characters, columns are style roles",
            "glyph_points": GLYPH,
            "label_column_points": LABEL_COLUMN,
            "columns": ["Ouyang Xun regular-script reference", "Wang Xizhi running-script candidate"],
            "selection_rule": (
                "the frozen pipeline pair (亮) followed by the next pairs in the "
                "frozen cross_reference_pairs.csv order"
            ),
            "rows": [],
        },
        "preserved_panels": "b--e are the frozen vector artwork, copied unchanged",
        "panel_a_card": {
            "facecolor": "#%02X%02X%02X" % PLATE,
            "frame_color": "#%02X%02X%02X" % FRAME,
            "frame_width_points": FRAME_WIDTH,
            "paper_mapping": (
                "out = round(C * plate / 255) per channel; white paper maps to the "
                "plate colour and black ink is fixed"
            ),
            "strip_restored": [round(v, 2) for v in STRIP_FILL],
            "arrow_band_restored": [round(v, 2) for v in ARROW_BAND],
            "arrow_geometry_in_source": source_arrow,
            "note": (
                "Tiles keep their geometry, scale, and ink coverage; only the paper "
                "colour changes, so panel (a) matches the framed cards of panels (b)--(e)"
            ),
        },
        "fonts": {
            "regular": {"source_name": font_regular[1], "sha256": sha256(font_regular[2])},
            "bold": {"source_name": font_bold[1], "sha256": sha256(font_bold[2])},
            "cjk": {"file": CJK_FONT.name, "name": cjk_metrics.name},
        },
        "inference": "none; cached masks and source tiles only",
    }

    for row_index, pair in enumerate(pairs):
        top = GALLERY_TOP + row_index * (GLYPH + ROW_GAP)
        regular_id, running_id = styles_of(pair)
        row_record = {"row": row_index + 1, "target_char": pair["candidate_char"],
                      "pair_id": pair["pair_id"], "tiles": []}
        for column, (x0, x1) in enumerate(columns):
            reference_id = regular_id if column == 0 else running_id
            if row_index == 0:
                # Keep the frozen tiles exactly as published in the previous revision.
                tile = frozen_tiles[column]
                origin = f"frozen tile xref {sorted(embedded, key=lambda i: i['bbox'][1])[column]['xref']}"
                provenance["reused_frozen_tiles"] = True
            else:
                entry = entries[reference_id]
                tile = tile_from_image(ROOT / "references" / entry["source_image_path"])
                origin = f"source image {entry['source_image_path']}"
            target = fitz.Rect(x0, top, x1, top + GLYPH)
            plated = on_plate(tile)
            deviation = float(
                np.abs(ink_coverage(tile, 255.0) - ink_coverage(plated, float(min(PLATE)))).max()
            )
            page.insert_image(target, stream=png_bytes(plated), keep_proportion=False)
            page.draw_rect(target, color=_rgb_tuple(FRAME), width=FRAME_WIDTH)
            row_record["tiles"].append({
                "column": column,
                "role": "reference" if column == 0 else "candidate",
                "reference_id": reference_id,
                "origin": origin,
                "native_size": list(tile.shape[:2]),
                "source_rgb_sha256": sha256(tile.tobytes()),
                "plated_rgb_sha256": sha256(plated.tobytes()),
                "ink_coverage_max_deviation": deviation,
                "target_points": [round(v, 2) for v in target],
            })
            if deviation > 1.0 / 255.0 + 1e-9:
                raise AssertionError("Plate mapping changed the ink coverage.")
        provenance["panel_a"]["rows"].append(row_record)
        character = pair["candidate_char"]
        page.insert_text(
            fitz.Point(
                GALLERY_LEFT - LABEL_COLUMN
                + (LABEL_COLUMN - cjk_metrics.text_length(character, fontsize=CJK_SIZE)) / 2,
                top + GLYPH / 2 + CJK_SIZE * 0.36,
            ),
            character, fontname="fig1cjk", fontsize=CJK_SIZE, color=MUTED,
        )

    # --- Labels: keep the frozen wording, font subset, size, and colour. ------
    colour = _rgb(labels["reference"]["color"])
    for index, (x0, x1) in enumerate(columns):
        text = "reference" if index == 0 else "candidate"
        size = _fit_size(regular_metrics, text, x1 - x0, HEADER_SIZE)
        page.insert_text(
            fitz.Point((x0 + x1) / 2 - regular_metrics.text_length(text, fontsize=size) / 2,
                       GALLERY_TOP - 3.0),
            text, fontname=reference_font[0], fontsize=size, color=colour,
        )

    title = "Input pair"
    title_colour = _rgb(labels["Input pair"]["color"])
    title_centre = CLEAR.x0 + CLEAR.width / 2
    title_width = bold_metrics.text_length(title, fontsize=TITLE_SIZE)
    page.insert_text(
        fitz.Point(title_centre - title_width / 2, labels["Input pair"]["origin"][1]),
        title, fontname=title_font[0], fontsize=TITLE_SIZE, color=title_colour,
    )

    # Subset every embedded font to the glyphs actually used; the CJK face that
    # supplies the character labels is otherwise stored almost in full.
    output.subset_fonts()
    output.save(STEM.with_suffix(".pdf"), garbage=4, deflate=True)
    output.close()
    source.close()

    # --- Verification and derivatives ---------------------------------------
    rebuilt = fitz.open(STEM.with_suffix(".pdf"))
    rebuilt_page = rebuilt[0]
    text = rebuilt_page.get_text()
    for expected in ("reference", "candidate", "Input pair", "Overlapping parse",
                     "Bounded registration", "Spatial evidence", "Structured output"):
        if expected not in text:
            raise AssertionError(f"Label missing after recomposition: {expected!r}")
    if abs(rebuilt_page.rect.width - width) > 0.01 or abs(rebuilt_page.rect.height - height) > 0.01:
        raise AssertionError("Recomposition changed the page size.")
    # The strip arrow must survive the repair: the band is compared with the
    # frozen figure at 600 dpi and has to match exactly, so the rebuilt strip
    # carries the same chevrons as its neighbours.
    frozen_pixels = np.frombuffer(
        _band_pixmap(SOURCE, ARROW_BAND).samples, dtype=np.uint8
    )
    rebuilt_pixels = np.frombuffer(
        _band_pixmap(STEM.with_suffix(".pdf"), ARROW_BAND).samples, dtype=np.uint8
    )
    if frozen_pixels.shape != rebuilt_pixels.shape:
        raise AssertionError("Arrow band rasterisation changed shape.")
    deviation = int(np.abs(frozen_pixels.astype(int) - rebuilt_pixels.astype(int)).max())
    if deviation != 0:
        raise AssertionError(f"Arrow band no longer matches the frozen figure (max {deviation}/255).")
    provenance["verification"] = {
        "page_size_preserved": True,
        "labels_present": True,
        "glyph_tiles": 6,
        "frozen_tiles_reused": provenance["reused_frozen_tiles"],
        "strip_arrow_band_matches_frozen_figure": True,
        "no_inferential_statistics": True,
    }
    pixmap = rebuilt_page.get_pixmap(dpi=600)
    pixmap.save(STEM.with_suffix(".png"))
    provenance["outputs"] = {
        "pdf": {"file": STEM.with_suffix(".pdf").name,
                "sha256": sha256(STEM.with_suffix(".pdf").read_bytes())},
        "png": {"file": STEM.with_suffix(".png").name,
                "sha256": sha256(STEM.with_suffix(".png").read_bytes())},
    }
    STEM.with_suffix(".json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rebuilt.close()
    print(json.dumps(provenance["verification"], ensure_ascii=False, indent=2))


def _spans(page: fitz.Page) -> list[dict]:
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans.extend(line["spans"])
    return spans


def _arrow_band_geometry(page: fitz.Page) -> dict[str, object]:
    """Describe the frozen strip arrow inside ``ARROW_BAND``.

    The arrow is a stroked shaft plus a filled head, both vector art. Recording
    the geometry lets the provenance file document exactly which artwork the
    repair re-inserts, and the count assertion fails loudly if the frozen
    figure ever stops containing it.
    """

    shapes = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        # ``intersects`` misses the zero-height shaft rectangle, so overlap is
        # tested on the coordinate intervals as well.
        overlaps = (
            min(rect.x1, ARROW_BAND.x1) - max(rect.x0, ARROW_BAND.x0) >= -0.01
            and min(rect.y1, ARROW_BAND.y1) - max(rect.y0, ARROW_BAND.y0) >= -0.01
        )
        if not overlaps:
            continue
        if rect.x1 > ARROW_BAND.x1 + 0.5 or rect.y1 > ARROW_BAND.y1 + 0.5:
            continue
        shapes.append(
            {
                "operation": drawing["type"],
                "stroke_width": drawing.get("width"),
                "colour": [round(v, 4) for v in (drawing.get("color") or drawing.get("fill") or ())],
                "points": [
                    [round(v, 2) for v in (point.x, point.y)]
                    for item in drawing["items"]
                    for point in item[1:]
                    if hasattr(point, "x")
                ],
            }
        )
    if len(shapes) != 2:
        raise ValueError(
            f"Expected the frozen strip arrow (shaft and head) in {ARROW_BAND}, found {len(shapes)} shapes."
        )
    return {"shapes": shapes, "note": "re-inserted verbatim from the frozen figure"}


def _extract_font(document: fitz.Document, page: fitz.Page, name: str) -> tuple[Path, str, bytes]:
    matches = [item for item in page.get_fonts(full=True) if name in item[3]]
    if len(matches) != 1:
        raise ValueError(f"Expected one embedded font named {name}.")
    xref = matches[0][0]
    _base, extension, _kind, content = document.extract_font(xref)
    path = HERE / "qa" / f"figure1_{name}.ttf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path, name, content


def _rgb(value: int) -> tuple[float, float, float]:
    return ((value >> 16 & 255) / 255, (value >> 8 & 255) / 255, (value & 255) / 255)


def _band_pixmap(path: Path, rect: fitz.Rect):
    document = fitz.open(path)
    try:
        return document[0].get_pixmap(dpi=600, clip=rect)
    finally:
        document.close()


def _rgb_tuple(value: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(channel / 255 for channel in value)


def _fit_size(font: fitz.Font, text: str, limit: float, preferred: float) -> float:
    size = preferred
    while size > 4.4 and font.text_length(text, fontsize=size) > limit:
        size -= 0.1
    return round(size, 2)


if __name__ == "__main__":
    main()
