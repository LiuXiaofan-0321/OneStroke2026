"""Recompose manuscript Figure 2 from the frozen PDF's embedded images.

Contract: independently acquired strokes give five overlapping direction
channels and one endpoint channel. A crossing retains both direction labels.
Archetype: schematic-led composite, with overlap as the visual focus.
All raster tiles are extracted without recolouring, segmentation, or inference.
The frozen tile resolution is retained. Text and callouts are vector objects.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import fitz
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, ConnectionPatch, Rectangle
from PIL import Image

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "figure3_channel_definition.pdf"
STEM = HERE / "figure2_channel_definition"
W, H = 6.30, 3.12
INK, MUTED, RULE = "#24282D", "#616A74", "#D7DDE3"
COLORS = ["#D62728", "#009E73", "#0072B2", "#E69F00", "#7B4AB5", "#00A6D6"]
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Liberation Sans", "Arial", "DejaVu Sans"],
    "font.size": 7, "text.color": INK,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "axes.linewidth": 0.5,
})


def main():
    doc = fitz.open(SOURCE)
    info = doc[0].get_image_info(xrefs=True)
    if len(info) != 11:
        raise ValueError("Frozen Figure 2 must contain exactly 11 source image tiles.")
    tiles, provenance = [], []
    for i, item in enumerate(info):
        raw = doc.extract_image(item["xref"])["image"]
        tile = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"))
        tiles.append(tile)
        provenance.append({"tile_index": i, "xref": item["xref"],
                           "shape": list(tile.shape),
                           "decoded_rgb_sha256": hashlib.sha256(tile.tobytes()).hexdigest()})
    fig = plt.figure(figsize=(6.30, 3.12))

    def text(x, y, value, size=7, weight="normal", color=INK, **kwargs):
        return fig.text(x/W, y/H, value, fontsize=size, fontweight=weight,
                        color=color, va="baseline", **kwargs)

    def label(x, y, letter, title):
        text(x, y, letter, 8, "bold")
        text(x+.16, y+.005, title, 7, "bold")

    def image_at(x, y, w, h, array):
        ax = fig.add_axes([x/W, y/H, w/W, h/H])
        ax.imshow(array, interpolation="none")
        ax.set_axis_off()
        return ax

    def rule(x1, y1, x2, y2, color=RULE, lw=.5):
        fig.add_artist(Line2D([x1/W,x2/W],[y1/H,y2/H], transform=fig.transFigure,
                              color=color, linewidth=lw))

    label(.04, 2.995, "a", "Acquired annotation sources")
    label(2.24, 2.995, "b", "Overlapping direction labels")
    text(.07, 2.78, "Complete character", 6.6)
    text(1.19, 2.78, "One isolated stroke", 6.6)
    image_at(.06, 1.56, 1.03, 1.16, tiles[1])
    stroke_ax = image_at(1.21, 1.57, .69, 1.14, tiles[0])
    # Circles surround the two visible original endpoint markers, for display only.
    # They are not new annotation and do not modify the stored raster.
    stroke_ax.add_patch(Circle((94,577), 22, fill=False, edgecolor=COLORS[5], linewidth=.9))
    stroke_ax.add_patch(Circle((331,103), 22, fill=False, edgecolor=COLORS[5], linewidth=.9))
    text(.08, 1.42, "Project sample 33/18", 6.4, color=MUTED)
    text(1.16, 1.42, "Two marked termini", 6.4, color=MUTED)
    rule(2.08, 1.42, 2.08, 2.82)

    text(2.28, 2.78, "Composed annotation", 6.6)
    overlay_ax = image_at(2.26, 1.43, 1.15, 1.30, tiles[2])
    # Exact rectangular crop of the displayed red/blue crossing. No resampling
    # or target reconstruction is used; original mask edges remain visible.
    x0, y0, x1, y1 = 350, 340, 465, 445
    crossing = tiles[2][y0:y1, x0:x1]
    zoom_ax = image_at(3.84, 1.82, 1.13, 1.00, crossing)
    zoom_ax.set_axis_on()
    zoom_ax.set_xticks([]); zoom_ax.set_yticks([])
    for spine in zoom_ax.spines.values():
        spine.set_edgecolor(RULE); spine.set_linewidth(.6)
    overlay_ax.add_patch(Rectangle((x0-.5,y0-.5),x1-x0,y1-y0,
                                  fill=False,edgecolor=INK,linewidth=.7))
    for ya, yb in [(y0-.5,-.5),(y1-.5,y1-y0-.5)]:
        fig.add_artist(ConnectionPatch(xyA=(x1-.5,ya),coordsA=overlay_ax.transData,
                                      xyB=(-.5,yb),coordsB=zoom_ax.transData,
                                      linewidth=.6,color="#9AA4AF"))
    text(3.82, 2.86, "Crossing enlarged", 6.6)
    text(5.14, 2.57, "vec1", 6.8, "bold")
    text(5.14, 2.34, "+", 7)
    text(5.14, 2.11, "vec3", 6.8, "bold")
    rule(5.00,2.60,5.07,2.60,COLORS[0],2.1)
    rule(5.00,2.14,5.07,2.14,COLORS[2],2.1)
    text(3.83, 1.63, "One pixel can retain both labels.", 6.7, "bold")
    text(3.83, 1.43, "Black = simultaneous direction labels", 6.4, color=MUTED)
    rule(.04, 1.27, 6.26, 1.27)

    label(.04, 1.08, "c", "Six stored channels")
    text(6.23, 1.09, "Five direction masks + one endpoint mask", 6.5,
         color=MUTED, ha="right")
    names = ["vec1", "vec2", "vec3", "vec4", "vec5", "endpoint"]
    desc = ["Vertical", "Rising diagonal", "Horizontal", "Falling diagonal",
            "Compound / other", "Stroke termini"]
    for i in range(6):
        x=.055+i*1.048
        rule(x, .957, x+.067, .957, COLORS[i], 2.1)
        text(x+.115, .932, names[i], 6.8, "bold")
        text(x+.005, .778, desc[i], 6.15, color=MUTED)
        image_at(x+.07, .02, .81, .70, tiles[5+i])
    fig.savefig(STEM.with_suffix(".pdf"))
    fig.savefig(STEM.with_suffix(".svg"))
    fig.savefig(STEM.with_suffix(".png"), dpi=600)
    fig.savefig(STEM.with_suffix(".tiff"), dpi=600,
                pil_kwargs={"compression": "tiff_lzw"})
    (HERE/"qa").mkdir(exist_ok=True)
    fig.savefig(HERE/"qa"/"figure2_print_size.png", dpi=300)
    plt.close(fig)
    report = {
        "manuscript_figure": 2,
        "core_claim": "Five independently composed direction masks preserve overlapping labels; the sixth mask marks stroke termini.",
        "archetype": "schematic-led composite",
        "source": str(SOURCE.relative_to(HERE.parents[1])),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "backend": "python", "size_inches": [W,H],
        "sample": "33/18", "tiles": provenance,
        "layout_mapping": {"a":[1,0],"b":[2],"c":[5,6,7,8,9,10]},
        "omitted_redundant_source_tiles": {
            "3":"The old broad crossing crop is replaced by an exact local crop of tile 2.",
            "4":"The duplicate full-character endpoint context is omitted; both isolated termini and the entire endpoint channel remain shown."},
        "crop_xyxy_on_composed_tile": [x0,y0,x1,y1],
        "image_integrity": "Decoded source pixels unchanged. No brightness, contrast, recolouring, smoothing, model inference, or new masks. Existing endpoint dilation is inherited from frozen display tiles; added endpoint circles and ROI rectangle are vector display marks only.",
        "limitations": "The repository lacks the source masks. This is a faithful re-layout of frozen figure tiles, not a reconstruction or revalidation of ground truth. Enlarged raster crossing intentionally retains visible pixels.",
    }
    STEM.with_suffix(".json").write_text(json.dumps(report,indent=2)+"\n")
    print(STEM.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
