#!/usr/bin/env python3
"""Rebuild Fig. 6 from frozen assets and all 150 source-data observations.

Contract: explain the frozen ASDS components, then show the closely matched
observed human associations of annotated-mask-union and thresholded-ink scores.
Archetype: schematic-led composite, mechanism above a three-plot validation row.
Structural adaptation preserves all source observations and the deterministic
example selection. No raw mask is reconstructed. Native frozen PDF image tiles
and vector projection paths supply only the unavailable illustrative example.

Run from any directory: python paper/figures/revision/build_figure6.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import fitz
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, FancyArrowPatch
import numpy as np
from PIL import Image
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORIGINAL = ROOT / "paper/figures/figure6_asds_direct_ink.pdf"
REDRAWN = ROOT / "paper/figures/redrawn/figure6_asds_direct_ink.pdf"
PAIRS = ROOT / "artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_pairs.csv"
REPORT = ROOT / "artifacts/paper_ijdar/direct_ink_asds/direct_ink_asds_report.json"
FEATURES = ROOT / "artifacts/paper_ijdar/spatial_score_development/development_features_and_predictions.csv"
STEM = HERE / "figure6_asds_direct_ink"
INK, MUTED, RULE = "#24282D", "#616A74", "#D7DDE3"
RED, BLUE, OVERLAP = "#D62728", "#0072B2", "#4B5057"
W, H = 6.30, 3.08

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Liberation Sans", "Arial", "DejaVu Sans"],
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.linewidth": .55,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": RULE,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "savefig.dpi": 600,
    "mathtext.fontset": "dejavusans",
})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def tile(doc: fitz.Document, xref: int) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(doc.extract_image(xref)["image"])).convert("RGB"))


def glyph_crop(im: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Crop only blank margins, preserving every foreground pixel and 8 px pad."""
    yy, xx = np.where(np.min(im, axis=2) < 230)
    box = [max(0, int(xx.min())-8), max(0, int(yy.min())-8),
           min(im.shape[1], int(xx.max())+9), min(im.shape[0], int(yy.max())+9)]
    return im[box[1]:box[3], box[0]:box[2]], box


def cell_colors(im: np.ndarray, rows: int, cols: int) -> np.ndarray:
    """Recover frozen *display colors*, never infer underlying occupancy values."""
    yy = ((np.arange(rows)+.5)*im.shape[0]/rows).astype(int)
    xx = ((np.arange(cols)+.5)*im.shape[1]/cols).astype(int)
    return im[yy[:, None], xx[None, :], :]/255.


def main() -> None:
    rows = csv_rows(PAIRS)
    report = json.loads(REPORT.read_text())
    assert len(rows) == report["pair_count"] == 150
    assert len({r["source_pair_id"] for r in rows}) == 150
    assert len({r["char_id"] for r in rows}) == report["character_count"] == 40
    x = np.array([float(r["parsed_asds_score"]) for r in rows])
    z = np.array([float(r["direct_ink_asds_score"]) for r in rows])
    y = np.array([float(r["human_mean"]) for r in rows])
    assert np.isfinite(np.column_stack((x, y, z))).all()
    assert ((x >= 0) & (x <= 100) & (z >= 0) & (z <= 100)).all()
    assert ((y >= 1) & (y <= 5)).all()
    median = np.median([float(r["direct_minus_parsed"]) for r in rows])
    selected = min(rows, key=lambda r: (abs(float(r["direct_minus_parsed"])-median), r["source_pair_id"]))
    assert selected["source_pair_id"] == "NAT-18-a8c4efc6a5ce"
    j = rows.index(selected)
    feature = next(r for r in csv_rows(FEATURES) if r["source_pair_id"] == selected["source_pair_id"])
    statistics = [float(spearmanr(x, y).statistic), float(spearmanr(z, y).statistic), float(spearmanr(x, z).statistic)]
    expected = [report["correlation_with_human_mean"]["parsed_asds"]["rho"], report["correlation_with_human_mean"]["direct_ink_asds"]["rho"], report["parsed_direct_score_association"]["rho"]]
    assert np.allclose(statistics, expected, atol=1e-14, rtol=0)
    original, redrawn = fitz.open(ORIGINAL), fitz.open(REDRAWN)
    pair = tile(original, 13)
    assert pair.shape == (287, 583, 3)
    reference, ref_crop = glyph_crop(pair[:, :287])
    candidate, cand_crop = glyph_crop(pair[:, 296:])
    overlay = tile(redrawn, 15)  # Existing semantically recolored overlay; no pixel changes.
    polar = cell_colors(tile(original, 15), 4, 8)
    grid = cell_colors(tile(original, 16), 3, 3)
    drawings = original[0].get_drawings()
    profile_paths = [d for d in drawings if len(d["items"]) > 100 and d["color"] is not None]
    assert len(profile_paths) == 4

    fig = plt.figure(figsize=(6.30, 3.08), facecolor="white")

    def text(a, b, s, **kwargs):
        defaults = dict(fontsize=7, ha="left", va="baseline")
        defaults.update(kwargs)
        return fig.text(a/W, b/H, s, **defaults)

    def ax(a, b, w, h):
        return fig.add_axes([a/W, b/H, w/W, h/H])

    def image_ax(a, b, w, h, im):
        axis = ax(a, b, w, h)
        axis.imshow(im, interpolation="none")
        axis.set_axis_off()
        return axis

    def header(a, label, title):
        text(a, 2.94, label, fontsize=8, fontweight="bold")
        text(a+.13, 2.94, title, fontsize=7.4, fontweight="bold")

    for a, label, title in [(.04,"a","Pair"),(.68,"b","Aligned"),(1.52,"c","Polar"),(2.50,"d","Grid"),(3.30,"e","Projections"),(4.58,"f","Frozen ASDS")]:
        header(a,label,title)

    image_ax(.095, 2.49, .40, .34, candidate)
    image_ax(.095, 2.00, .40, .35, reference)
    text(.295, 2.39, "candidate", ha="center", fontsize=6.5, color=RED)
    text(.295, 1.90, "reference", ha="center", fontsize=6.5, color=BLUE)
    image_ax(.67, 2.02, .66, .81, overlay)
    text(1.00, 1.90, "silhouettes", ha="center", fontsize=6.5, color=MUTED)
    fig.add_artist(FancyArrowPatch((.51/W,2.43/H),(.67/W,2.43/H), transform=fig.transFigure, arrowstyle="-|>", mutation_scale=6, color=RULE, linewidth=.7))

    def heatmap(a, b, w, h, colors):
        axis = ax(a, b, w, h)
        nr, nc = colors.shape[:2]
        for r in range(nr):
            for c in range(nc):
                axis.add_patch(Rectangle((c, r), 1, 1, facecolor=colors[r,c], edgecolor="white", linewidth=.35))
        axis.set(xlim=(0,nc), ylim=(nr,0))
        axis.set_axis_off()

    heatmap(1.52, 2.29, .79, .43, polar)
    heatmap(2.59, 2.21, .51, .51, grid)
    # The source's vmin=0 and per-panel automatic vmax make this normalized
    # display key exact. Absolute occupancy maxima are unavailable in the repo.
    for a, w, name in [(1.52,.79,"Blues"),(2.59,.51,"Oranges")]:
        ca = ax(a, 2.11, w, .037)
        cb = mpl.colorbar.ColorbarBase(ca, cmap=mpl.colormaps[name], norm=mpl.colors.Normalize(0,1), orientation="horizontal", ticks=[0,1])
        cb.outline.set_visible(False)
        cb.solids.set_rasterized(False)
        cb.ax.tick_params(length=0, pad=1.0, labelsize=6.5)
    text(1.915, 2.77, rf"$s_p={float(feature['polar_js_similarity']):.3f}$", ha="center", fontsize=7)
    text(2.845, 2.77, rf"$s_g={float(feature['grid_js_similarity']):.3f}$", ha="center", fontsize=7)
    text(1.915, 2.19, "4 radial × 8 angular bins", ha="center", fontsize=6.5, color=MUTED)
    text(2.30, 1.89, "Relative difference within each map", ha="center", fontsize=6.5, color=MUTED)

    projection = ax(3.32, 2.18, 1.00, .54)
    # Preserve the native vector geometry, remapped only into a new rectangle.
    bounds = [634.6244506835938,36.720001220703125,765.7403564453125,176.6255645751953]
    for d, color, style in zip(profile_paths, [RED,BLUE,RED,BLUE], ["-","-","--","--"]):
        pts = [d["items"][0][1]]+[it[2] for it in d["items"]]
        xx = [(p.x-bounds[0])/(bounds[2]-bounds[0]) for p in pts]
        yy = [(bounds[3]-p.y)/(bounds[3]-bounds[1]) for p in pts]
        projection.plot(xx,yy,color=color,linestyle=style,linewidth=.65 if style=="-" else .55,alpha=1 if style=="-" else .85)
    projection.set(xlim=(0,1),ylim=(0,1),xticks=[0,.5,1],yticks=[])
    projection.set_xticklabels(["0","0.5","1"])
    projection.spines["left"].set_visible(False)
    projection.tick_params(axis="x", length=2, pad=1)
    text(3.82, 2.77, rf"$s_{{\rm proj}}={float(feature['projection_js_similarity']):.3f}$", ha="center", fontsize=7)
    text(3.82, 1.99, "Normalised position", ha="center", fontsize=6.5, color=MUTED)
    text(3.82, 1.88, "rows —   columns - -", ha="center", fontsize=6.5, color=MUTED)

    # Compact formula block retains the exact frozen weights and score.
    fig.add_artist(Line2D([4.48/W,4.48/W],[1.90/H,2.87/H],transform=fig.transFigure,color=RULE,linewidth=.65))
    text(4.63, 2.68, r"$S_{\rm ASDS}=100\,(0.70s_p$", fontsize=7.5)
    text(4.87, 2.52, r"$+\,0.15s_g+0.15s_{\rm proj})$", fontsize=7.5)
    text(4.63, 2.22, f"{x[j]:.1f}", fontsize=12, fontweight="bold")
    text(5.10, 2.24, "/ 100", fontsize=7, color=MUTED)
    text(4.63, 2.07, "Annotated-mask-union score", fontsize=6.5, color=MUTED)
    text(4.63, 1.91, f"Human mean: {y[j]:.2f} / 5", fontsize=7)

    # Small shared overlay key has the same colors as all candidate/reference marks.
    for a, col, label in [(.10,RED,"candidate"),(.77,BLUE,"reference"),(1.43,OVERLAP,"overlap")]:
        fig.add_artist(Rectangle((a/W,1.73/H),.055/W,.055/H,transform=fig.transFigure,facecolor=col,edgecolor="none"))
        text(a+.078,1.73,label,fontsize=6.5)
    text(4.63, 1.73, "● filled point: the pair in a–f", fontsize=6.5, color=MUTED)
    fig.add_artist(Line2D([.04/W,6.26/W],[1.64/H,1.64/H],transform=fig.transFigure,color=RULE,linewidth=.7))
    text(.04, 1.48, "g", fontsize=8, fontweight="bold")
    text(.19, 1.48, "Direct-ink control", fontsize=7.6, fontweight="bold")
    text(1.43, 1.48, "150 pairs · 40 characters", fontsize=6.8, color=MUTED)
    text(6.22, 1.48, r"$\Delta\rho=0.00040$  [95% CI −0.01011, 0.01030]", ha="right", fontsize=6.5)

    lower = [ax(.37,.31,1.67,.91), ax(2.40,.31,1.67,.91), ax(4.62,.31,1.60,.91)]
    ci = report["character_cluster_bootstrap"]
    lower_specs = [
        (x,y,"Annotated-mask union",ci["parsed_asds_rho_ci95"]),
        (z,y,"Direct ink",ci["direct_ink_asds_rho_ci95"]),
        (x,z,"Score ordering",None),
    ]
    for k,(axis,(xx,yy,title,interval)) in enumerate(zip(lower,lower_specs)):
        axis.set_axisbelow(True)
        axis.grid(axis="y" if k<2 else "both", color=RULE, linewidth=.45, alpha=.8)
        axis.scatter(xx,yy,s=8.3,facecolors="none",edgecolors=MUTED,linewidths=.48,alpha=.77,zorder=3)
        axis.scatter([xx[j]],[yy[j]],s=21,facecolor=INK,edgecolor="white",linewidth=.55,zorder=5)
        axis.set_xlim(30,100)
        axis.set_xticks([40,60,80,100])
        axis.tick_params(length=2.4,width=.55,pad=2)
        axis.set_title(title,fontsize=7.1,fontweight="bold",pad=4.5,loc="left",color=INK)
        if k<2:
            axis.set_ylim(.75,5.28)
            axis.set_yticks([1,2,3,4,5])
            axis.text(.035,.93,rf"$\rho={statistics[k]:.3f}$"+f"  [{interval[0]:.3f}, {interval[1]:.3f}]",transform=axis.transAxes,va="top",fontsize=6.5,bbox=dict(facecolor="white",alpha=.9,edgecolor="none",pad=.5))
            axis.set_xlabel("Annotated-mask-union ASDS" if k==0 else "Direct-ink ASDS",labelpad=3)
            if k==0:
                axis.set_ylabel("Mean human rating", labelpad=3)
            else:
                axis.set_yticklabels([])
        else:
            axis.plot([30,100],[30,100],color="#98A2AD",linewidth=.8,linestyle=(0,(3,2)),zorder=1)
            axis.set_ylim(30,100)
            axis.set_yticks([40,60,80,100])
            axis.text(.04,.93,rf"$\rho={statistics[k]:.4f}$",transform=axis.transAxes,va="top",fontsize=6.5,bbox=dict(facecolor="white",alpha=.9,edgecolor="none",pad=.5))
            axis.set_xlabel("Annotated-mask-union ASDS",labelpad=3)
            axis.set_ylabel("Direct-ink ASDS",labelpad=3)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    out_of_canvas=[]
    for artist in fig.findobj(mpl.text.Text):
        if artist.get_visible() and artist.get_text():
            bb=artist.get_window_extent(renderer)
            if bb.x0 < -1 or bb.y0 < -1 or bb.x1 > fig.bbox.width+1 or bb.y1 > fig.bbox.height+1:
                out_of_canvas.append(artist.get_text())
    assert not out_of_canvas, out_of_canvas
    fig.savefig(STEM.with_suffix(".pdf"), facecolor="white")
    fig.savefig(STEM.with_suffix(".svg"), facecolor="white")
    fig.savefig(STEM.with_suffix(".png"), dpi=600, facecolor="white")
    fig.savefig(STEM.with_suffix(".tiff"), dpi=600, facecolor="white", pil_kwargs={"compression":"tiff_lzw"})
    plt.close(fig)
    provenance = {
        "figure_contract": {"conclusion":"On this retrospective clean direct-digital cohort, annotated-mask-union and direct-ink ASDS have closely matched observed human associations and score ordering.","archetype":"schematic-led composite","backend":"Python/matplotlib","dimensions_inches":[W,H]},
        "sources": {str(p.relative_to(ROOT)):sha(p) for p in (ORIGINAL,REDRAWN,PAIRS,REPORT,FEATURES,Path(__file__))},
        "source_field_mapping":{"parsed_asds_score":"annotated-mask-union ASDS, score/100; legacy column name does not mean model prediction","direct_ink_asds_score":"thresholded-ink ASDS, score/100","human_mean":"mean of three human ratings, 1–5","source_pair_id":"observation identifier","char_id":"bootstrap cluster"},
        "observations":{"before":150,"after":150,"excluded":0,"characters":40,"jitter":False,"downsampling":False},
        "example":{"source_pair_id":selected["source_pair_id"],"selection_rule":"smallest absolute distance of direct-minus-parsed score to cohort median, tie by source_pair_id","annotated_mask_union_asds":float(x[j]),"direct_ink_asds":float(z[j]),"human_mean":float(y[j]),"components":{k:float(feature[k]) for k in ("polar_js_similarity","grid_js_similarity","projection_js_similarity")}},
        "frozen_image_adaptation":{"natural_pair":{"pdf":"original","xref":13,"reference_split_x":[0,287],"candidate_split_x":[296,583],"reference_crop":ref_crop,"candidate_crop":cand_crop,"adjustments":"blank-margin crop only; no color/contrast changes"},"overlay":{"pdf":"redrawn","xref":15,"adjustments":"none; reuse existing red/blue/gray display"},"heatmaps":{"pdf":"original","xrefs":[15,16],"adjustments":"exact central RGB of each uniform cell redrawn as vector rectangles; white cell separators added","colorbars":"normalized display key 0–1; each map is divided by its own maximum by the original vmin=0/autovmax rendering; absolute occupancy maxima unavailable","underlying_values_reconstructed":False},"projection_profiles":{"pdf":"original","native_path_count":4,"source_item_counts":[len(d['items']) for d in profile_paths],"source_rectangle_pt":bounds,"adjustments":"native path coordinates affine-remapped into a new rectangle; all four profiles vertically rescaled together for display, preserving relative amplitudes; line widths restyled; no raw probability magnitudes inferred"}},
        "statistics":{"recomputed_spearman":statistics,"agrees_with_frozen_report":True,"ci_source":"unchanged frozen character-cluster bootstrap report, 10000 iterations","paired_difference_ci":ci["parsed_minus_direct_rho_ci95"],"interpretation":"observed closeness, not a formal equivalence test; development-set results"},
        "qa":{"no_text_outside_canvas":True,"native_text":"editable PDF TrueType / SVG text","min_label_font_pt":6.5,"score_callout_font_pt":12,"raster_export_dpi":600,"raw_masks_reconstructed":False,"all_150_points_rendered_per_scatter":True},
        "exports":{ext:sha(STEM.with_suffix('.'+ext)) for ext in ('pdf','svg','png','tiff')},
    }
    STEM.with_suffix(".json").write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+"\n")
    original.close();redrawn.close()
    print(json.dumps({"created":[str(STEM.with_suffix('.'+e)) for e in ('pdf','svg','png','tiff','json')],"n":len(rows),"spearman":statistics}))


if __name__ == "__main__":
    main()
