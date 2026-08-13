"""Freeze an approved natural-pair set and build offline blinded rating tools."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import shutil
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from onestroke_model.expert_candidate_pairs import (
    CANDIDATE_STATUS,
    WRITER_IDENTITY_STATUS,
)

FROZEN_STATUS = "FROZEN_DO_NOT_CHANGE_AFTER_HUMAN_RATING_STARTS"
STUDY_VERSION = "expert_structural_validation_v1"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields_found: list[str] = []
        for row in rows:
            for field in row:
                if field not in fields_found:
                    fields_found.append(field)
        fields = fields_found or ("status",)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(seed: int, *values: str) -> str:
    return hashlib.sha256(
        ":".join([str(seed), *values]).encode("utf-8")
    ).hexdigest()


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


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


def validate_approved_selection(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected_pairs: int = 150,
) -> list[dict[str, Any]]:
    if len(rows) != expected_pairs:
        raise ValueError(f"expected {expected_pairs} approved pairs, got {len(rows)}")
    required = (
        "pair_id",
        "char_id",
        "target_char",
        "candidate_instance_id",
        "reference_instance_id",
        "current_score",
        "coverage_aware_score",
        "candidate_image_sha256",
        "reference_image_sha256",
        "candidate_mask_sha256",
        "reference_mask_sha256",
        "writer_identity_status",
        "style_id",
    )
    normalized: list[dict[str, Any]] = []
    pair_ids: set[str] = set()
    unordered: set[tuple[str, str]] = set()
    for row in rows:
        missing = [
            field
            for field in required
            if str(row.get(field, "")).strip() == ""
            and field != "writer_identity_status"
        ]
        if missing:
            raise ValueError(f"approved row missing fields {missing}: {row!r}")
        pair_id = str(row["pair_id"])
        if pair_id in pair_ids:
            raise ValueError(f"duplicate pair_id in approved selection: {pair_id}")
        pair_ids.add(pair_id)
        candidate = str(row["candidate_instance_id"])
        reference = str(row["reference_instance_id"])
        if candidate == reference:
            raise ValueError(f"self pair cannot be frozen: {pair_id}")
        key = tuple(sorted((candidate, reference)))
        if key in unordered:
            raise ValueError(f"duplicate unordered pair cannot be frozen: {key}")
        unordered.add(key)
        if _boolish(row.get("same_image_detected")):
            raise ValueError(f"same-image pair cannot be frozen: {pair_id}")
        if _boolish(row.get("same_mask_detected")):
            raise ValueError(f"same-mask pair cannot be frozen: {pair_id}")
        if _boolish(row.get("near_duplicate_suspected")):
            raise ValueError(f"near-duplicate pair requires review: {pair_id}")
        if str(row.get("writer_identity_status", "")) != WRITER_IDENTITY_STATUS:
            raise ValueError(f"writer identity status changed for {pair_id}")
        if _boolish(row.get("different_writer_claim")):
            raise ValueError(f"different-writer claim is unsupported: {pair_id}")
        if _boolish(row.get("cross_style_verified")):
            raise ValueError(f"cross-style verification is unsupported: {pair_id}")
        current = float(row["current_score"])
        coverage = float(row["coverage_aware_score"])
        if not math.isfinite(current) or not math.isfinite(coverage):
            raise ValueError(f"non-finite score in {pair_id}")
        normalized.append(
            {
                **dict(row),
                "current_score": current,
                "coverage_aware_score": coverage,
            }
        )
    return sorted(
        normalized,
        key=lambda row: int(row.get("selection_rank", 0)),
    )


def freeze_selection(
    approved_rows: Sequence[Mapping[str, Any]],
    output_path: str | Path,
    *,
    approval_note: str,
) -> list[dict[str, Any]]:
    output = Path(output_path)
    if output.exists():
        raise FileExistsError(
            f"frozen pair file already exists and must not be overwritten: {output}"
        )
    frozen_rows: list[dict[str, Any]] = []
    for order, row in enumerate(approved_rows, start=1):
        frozen_rows.append(
            {
                **dict(row),
                "study_status": "APPROVED_FOR_HUMAN_RATING",
                "freeze_status": FROZEN_STATUS,
                "frozen_order": order,
                "approval_note": approval_note,
            }
        )
    _write_csv(output, frozen_rows)
    return frozen_rows


def _instance_image_path(dataset_root: Path, instance_id: str) -> Path:
    char_id, sample_index = instance_id.split("/", maxsplit=1)
    return dataset_root / char_id / sample_index / "0.jpg"


def _make_presentations(
    frozen_rows: Sequence[Mapping[str, Any]],
    *,
    duplicate_fraction: float,
    seed: int,
) -> list[dict[str, Any]]:
    if not 0 <= duplicate_fraction < 0.5:
        raise ValueError("duplicate_fraction must be in [0, 0.5)")
    duplicate_count = round(len(frozen_rows) * duplicate_fraction)
    duplicate_source_ids = {
        str(row["pair_id"])
        for row in sorted(
            frozen_rows,
            key=lambda row: _stable_hash(seed, "repeat-source", str(row["pair_id"])),
        )[:duplicate_count]
    }
    presentations: list[dict[str, Any]] = []
    for row in frozen_rows:
        pair_id = str(row["pair_id"])
        presentations.append(
            {
                "source_pair_id": pair_id,
                "is_repeat": False,
                "repeat_index": 0,
                **dict(row),
            }
        )
        if pair_id in duplicate_source_ids:
            presentations.append(
                {
                    "source_pair_id": pair_id,
                    "is_repeat": True,
                    "repeat_index": 1,
                    **dict(row),
                }
            )
    for row in presentations:
        row["blinded_pair_id"] = (
            "EXP-"
            + _stable_hash(
                seed,
                "blind",
                str(row["source_pair_id"]),
                str(row["repeat_index"]),
            )[:12]
        )
    if len({str(row["blinded_pair_id"]) for row in presentations}) != len(
        presentations
    ):
        raise RuntimeError("blinded presentation IDs are not unique")
    return presentations


def _render_pair_asset(
    candidate_path: Path,
    reference_path: Path,
    output_path: Path,
    *,
    target_char: str,
) -> None:
    with Image.open(candidate_path) as image:
        candidate = image.convert("RGB")
    with Image.open(reference_path) as image:
        reference = image.convert("RGB")
    candidate.thumbnail((360, 360), Image.Resampling.LANCZOS)
    reference.thumbnail((360, 360), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (820, 445), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (20, 12),
        f"目标汉字：{target_char}",
        fill=(25, 25, 25),
        font=_font(24),
    )
    draw.text((135, 55), "待评字", fill=(0, 70, 150), font=_font(22))
    draw.text((540, 55), "参照字", fill=(125, 70, 0), font=_font(22))
    canvas.paste(candidate, (30 + (360 - candidate.width) // 2, 83))
    canvas.paste(reference, (430 + (360 - reference.width) // 2, 83))
    draw.line((410, 82, 410, 432), fill=(210, 210, 210), width=2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, optimize=True)


def _evaluator_order(
    presentations: Sequence[Mapping[str, Any]],
    evaluator_id: str,
    *,
    seed: int,
) -> list[dict[str, Any]]:
    ordered = sorted(
        (dict(row) for row in presentations),
        key=lambda row: _stable_hash(
            seed,
            "evaluator-order",
            evaluator_id,
            str(row["blinded_pair_id"]),
        ),
    )
    # Prevent an original and its hidden repeat from becoming adjacent.
    for index in range(1, len(ordered)):
        if ordered[index]["source_pair_id"] != ordered[index - 1]["source_pair_id"]:
            continue
        swap_index = next(
            (
                candidate
                for candidate in range(index + 1, len(ordered))
                if ordered[candidate]["source_pair_id"]
                not in {
                    ordered[index - 1]["source_pair_id"],
                    ordered[index + 1]["source_pair_id"]
                    if index + 1 < len(ordered)
                    else "",
                }
            ),
            None,
        )
        if swap_index is not None:
            ordered[index], ordered[swap_index] = ordered[swap_index], ordered[index]
    return ordered


def _html_payload(
    evaluator_id: str,
    ordered_rows: Sequence[Mapping[str, Any]],
) -> str:
    public_items = [
        {
            "blinded_pair_id": row["blinded_pair_id"],
            "target_char": row["target_char"],
            "asset": f"assets/{row['blinded_pair_id']}.png",
        }
        for row in ordered_rows
    ]
    items_json = json.dumps(public_items, ensure_ascii=False)
    safe_evaluator = html.escape(evaluator_id)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>一笔成章·结构相似度专家盲评 {safe_evaluator}</title>
  <style>
    :root {{ font-family: "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; color: #1f2937; }}
    body {{ margin: 0; background: #f4f6f8; }}
    .page {{ max-width: 1040px; margin: 0 auto; padding: 20px; }}
    .card {{ background: white; border-radius: 14px; padding: 20px; margin-bottom: 16px;
             box-shadow: 0 4px 18px rgba(0,0,0,.07); }}
    h1 {{ margin: 0 0 10px; font-size: 25px; }}
    .muted {{ color: #667085; }}
    .warning {{ background: #fff7e6; border-left: 4px solid #f59e0b; padding: 12px; }}
    label {{ display: block; margin: 9px 0 5px; }}
    input[type=number], select, textarea {{
      width: 100%; box-sizing: border-box; padding: 9px; border: 1px solid #cbd5e1;
      border-radius: 7px; font: inherit;
    }}
    .pair-image {{ display: block; width: 100%; max-width: 820px; margin: 12px auto;
                   border: 1px solid #e5e7eb; border-radius: 8px; }}
    .rating {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 9px; margin: 16px 0; }}
    .rating label {{ border: 1px solid #cbd5e1; border-radius: 9px; padding: 12px 6px;
                     text-align: center; cursor: pointer; background: #fafafa; }}
    .rating label:has(input:checked) {{ border-color: #2563eb; background: #eff6ff; }}
    .buttons {{ display: flex; flex-wrap: wrap; gap: 9px; margin-top: 15px; }}
    button {{ border: 0; border-radius: 8px; padding: 10px 16px; cursor: pointer;
              background: #2563eb; color: white; font: inherit; }}
    button.secondary {{ background: #64748b; }}
    button.danger {{ background: #b91c1c; }}
    button:disabled {{ opacity: .45; cursor: not-allowed; }}
    .progress {{ height: 12px; background: #e2e8f0; border-radius: 10px; overflow: hidden; }}
    .progress > div {{ height: 100%; background: #16a34a; width: 0; }}
    .rubric td, .rubric th {{ border: 1px solid #d9dee6; padding: 7px; }}
    .rubric {{ border-collapse: collapse; width: 100%; }}
    #study {{ display: none; }}
    @media (max-width: 700px) {{
      .rating {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<main class="page">
  <section id="intro" class="card">
    <h1>一笔成章：汉字结构相似度专家盲评</h1>
    <p>评价者编号：<strong>{safe_evaluator}</strong></p>
    <div class="warning">
      本任务只评价“待评字”与“参照字”的结构相似程度，不评价书法美感、
      历史真伪、个人水平或作品好坏。不要与其他评价者讨论题目。
    </div>
    <h2>评分标准</h2>
    <table class="rubric">
      <tr><th>分数</th><th>含义</th></tr>
      <tr><td>1</td><td>完全不相似：主要部件、比例或相对位置明显不同。</td></tr>
      <tr><td>2</td><td>较不相似：能看出是同一个字，但存在多处主要结构差异。</td></tr>
      <tr><td>3</td><td>中等相似：整体结构基本对应，同时有若干明显差异。</td></tr>
      <tr><td>4</td><td>较相似：主要部件和相对位置一致，仅有局部比例或位置差异。</td></tr>
      <tr><td>5</td><td>高度相似：主要部件、比例和相对位置均高度一致。</td></tr>
    </table>
    <p class="muted">粗细或书写风格只有在改变结构关系时才影响评分。题目中可能含有隐藏重复项，用于一致性检验。</p>
    <label>相关背景（不填写姓名、学号、手机号）</label>
    <select id="expertise">
      <option value="">请选择</option>
      <option>书法教师</option>
      <option>书法相关专业学生</option>
      <option>长期书法学习者</option>
      <option>其他相关背景</option>
    </select>
    <label>书法学习/实践年数</label>
    <input id="years" type="number" min="0" max="80" step="0.5">
    <label>其中书法教学年数（没有则填 0）</label>
    <input id="teachingYears" type="number" min="0" max="80" step="0.5" value="0">
    <label><input id="consent" type="checkbox"> 我已阅读研究说明，自愿参加，并知道可以在提交前退出。</label>
    <div class="buttons">
      <button id="startButton" onclick="startStudy()">开始评分</button>
    </div>
  </section>

  <section id="study">
    <div class="card">
      <div id="progressText"></div>
      <div class="progress"><div id="progressBar"></div></div>
    </div>
    <div class="card">
      <h2 id="itemTitle"></h2>
      <img id="pairImage" class="pair-image" alt="待评字与参照字">
      <div class="rating">
        <label><input type="radio" name="rating" value="1"> 1<br>完全不相似</label>
        <label><input type="radio" name="rating" value="2"> 2<br>较不相似</label>
        <label><input type="radio" name="rating" value="3"> 3<br>中等相似</label>
        <label><input type="radio" name="rating" value="4"> 4<br>较相似</label>
        <label><input type="radio" name="rating" value="5"> 5<br>高度相似</label>
      </div>
      <label>可选备注（只写结构观察）</label>
      <textarea id="comment" rows="2"></textarea>
      <div class="buttons">
        <button class="secondary" onclick="go(-1)">上一题</button>
        <button onclick="go(1)">保存并下一题</button>
        <button class="secondary" onclick="jumpFirstMissing()">跳到第一道未评分题</button>
      </div>
    </div>
    <div class="card">
      <strong>请在全部完成后导出 CSV 并交回项目负责人。</strong>
      <div class="buttons">
        <button onclick="downloadCsv()">导出评分 CSV</button>
        <button class="secondary" onclick="downloadJson()">导出进度备份 JSON</button>
        <button class="danger" onclick="clearAll()">清空本机进度</button>
      </div>
    </div>
  </section>
</main>
<script>
const evaluatorId = {json.dumps(evaluator_id, ensure_ascii=False)};
const studyVersion = {json.dumps(STUDY_VERSION)};
const items = {items_json};
const storageKey = studyVersion + ":" + evaluatorId;
let currentIndex = 0;
let state = JSON.parse(localStorage.getItem(storageKey) || "{{}}");
state.answers = state.answers || {{}};
state.metadata = state.metadata || {{}};

function escapeCsv(value) {{
  const text = String(value ?? "");
  return '"' + text.replaceAll('"', '""') + '"';
}}
function saveState() {{
  localStorage.setItem(storageKey, JSON.stringify(state));
}}
function saveCurrent() {{
  const item = items[currentIndex];
  const checked = document.querySelector('input[name=rating]:checked');
  const comment = document.getElementById("comment").value.trim();
  if (checked) {{
    state.answers[item.blinded_pair_id] = {{
      rating: Number(checked.value),
      optional_comment: comment
    }};
  }} else if (comment) {{
    state.answers[item.blinded_pair_id] = {{
      rating: null,
      optional_comment: comment
    }};
  }}
  saveState();
}}
function render() {{
  const item = items[currentIndex];
  document.getElementById("itemTitle").textContent =
    `题目 ${{currentIndex + 1}} / ${{items.length}} · 目标汉字：${{item.target_char}}`;
  document.getElementById("pairImage").src = item.asset;
  const answer = state.answers[item.blinded_pair_id] || {{}};
  document.querySelectorAll('input[name=rating]').forEach(input => {{
    input.checked = Number(input.value) === Number(answer.rating);
  }});
  document.getElementById("comment").value = answer.optional_comment || "";
  const completed = items.filter(item => state.answers[item.blinded_pair_id]?.rating).length;
  document.getElementById("progressText").textContent =
    `已完成 ${{completed}} / ${{items.length}}；进度自动保存在本浏览器。`;
  document.getElementById("progressBar").style.width =
    `${{100 * completed / items.length}}%`;
}}
function startStudy() {{
  const expertise = document.getElementById("expertise").value;
  const years = document.getElementById("years").value;
  const teachingYears = document.getElementById("teachingYears").value;
  const consent = document.getElementById("consent").checked;
  if (!expertise || years === "" || teachingYears === "" || !consent) {{
    alert("请完成背景信息并确认自愿参加。");
    return;
  }}
  state.metadata = {{
    evaluator_id: evaluatorId,
    expertise_category: expertise,
    years_calligraphy_experience: years,
    teaching_experience_years: teachingYears,
    consent_confirmed: true
  }};
  saveState();
  document.getElementById("intro").style.display = "none";
  document.getElementById("study").style.display = "block";
  render();
}}
function go(delta) {{
  saveCurrent();
  currentIndex = Math.max(0, Math.min(items.length - 1, currentIndex + delta));
  render();
  window.scrollTo({{top: 0, behavior: "smooth"}});
}}
function jumpFirstMissing() {{
  saveCurrent();
  const index = items.findIndex(item => !state.answers[item.blinded_pair_id]?.rating);
  if (index < 0) {{
    alert("全部题目已经评分。");
    return;
  }}
  currentIndex = index;
  render();
  window.scrollTo({{top: 0, behavior: "smooth"}});
}}
function downloadBlob(filename, content, type) {{
  const blob = new Blob([content], {{type}});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}}
function downloadCsv() {{
  saveCurrent();
  const missing = items.filter(item => !state.answers[item.blinded_pair_id]?.rating);
  if (missing.length && !confirm(`还有 ${{missing.length}} 道题未评分，仍要导出吗？`)) return;
  const fields = [
    "evaluator_id", "blinded_pair_id", "target_char",
    "structural_similarity_rating_1_to_5", "optional_comment",
    "consent_confirmed", "expertise_category",
    "years_calligraphy_experience", "teaching_experience_years",
    "study_version", "completed_at"
  ];
  const now = new Date().toISOString();
  const lines = [fields.map(escapeCsv).join(",")];
  for (const item of items) {{
    const answer = state.answers[item.blinded_pair_id] || {{}};
    const row = [
      evaluatorId, item.blinded_pair_id, item.target_char,
      answer.rating || "", answer.optional_comment || "",
      state.metadata.consent_confirmed || false,
      state.metadata.expertise_category || "",
      state.metadata.years_calligraphy_experience || "",
      state.metadata.teaching_experience_years || "",
      studyVersion, now
    ];
    lines.push(row.map(escapeCsv).join(","));
  }}
  downloadBlob(`${{evaluatorId}}_expert_ratings.csv`, "\\ufeff" + lines.join("\\r\\n"), "text/csv;charset=utf-8");
}}
function downloadJson() {{
  saveCurrent();
  downloadBlob(
    `${{evaluatorId}}_expert_ratings_backup.json`,
    JSON.stringify({{study_version: studyVersion, evaluator_id: evaluatorId, ...state}}, null, 2),
    "application/json;charset=utf-8"
  );
}}
function clearAll() {{
  if (!confirm("确定清空本评价者在此浏览器中的全部评分进度吗？")) return;
  localStorage.removeItem(storageKey);
  location.reload();
}}
if (state.metadata.consent_confirmed) {{
  document.getElementById("intro").style.display = "none";
  document.getElementById("study").style.display = "block";
  render();
}}
</script>
</body>
</html>
"""


def _write_evaluator_package(
    package_root: Path,
    evaluator_id: str,
    ordered_rows: Sequence[Mapping[str, Any]],
    source_assets: Path,
) -> None:
    evaluator_dir = package_root / evaluator_id
    assets_dir = evaluator_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for row in ordered_rows:
        blinded_id = str(row["blinded_pair_id"])
        shutil.copyfile(
            source_assets / f"{blinded_id}.png",
            assets_dir / f"{blinded_id}.png",
        )
    (evaluator_dir / f"{evaluator_id}_rating_tool.html").write_text(
        _html_payload(evaluator_id, ordered_rows),
        encoding="utf-8",
    )
    public_rows = [
        {
            "evaluator_id": evaluator_id,
            "presentation_order": index,
            "blinded_pair_id": row["blinded_pair_id"],
            "target_char": row["target_char"],
            "structural_similarity_rating_1_to_5": "",
            "optional_comment": "",
        }
        for index, row in enumerate(ordered_rows, start=1)
    ]
    _write_csv(evaluator_dir / f"{evaluator_id}_blank_form.csv", public_rows)
    (evaluator_dir / "使用说明.txt").write_text(
        (
            f"评价者编号：{evaluator_id}\n\n"
            f"请双击 {evaluator_id}_rating_tool.html，在浏览器中独立完成评分。\n"
            "评分会自动保存到当前浏览器。全部完成后点击“导出评分 CSV”，"
            "把导出的 CSV 发给项目负责人。\n\n"
            "不要打开或索要 internal 目录，不要与其他评价者讨论题目，"
            "不要评价艺术美感，只评价结构相似度。\n"
        ),
        encoding="utf-8",
    )


def build_frozen_expert_study(
    *,
    approved_selection_path: str | Path,
    dataset_root: str | Path,
    output_dir: str | Path,
    evaluator_ids: Sequence[str] = ("E01", "E02", "E03"),
    duplicate_fraction: float = 0.10,
    seed: int = 20260812,
    approval_note: str = "Project lead approved all 150 internally reviewed pairs.",
) -> dict[str, Any]:
    selection_path = Path(approved_selection_path)
    root = Path(dataset_root).resolve()
    output = Path(output_dir)
    frozen_path = output / "frozen_expert_pairs_v1.csv"
    if frozen_path.exists():
        raise FileExistsError(
            f"study is already frozen; refusing to rebuild or change it: {frozen_path}"
        )
    rows = validate_approved_selection(_read_csv(selection_path))
    output.mkdir(parents=True, exist_ok=True)
    frozen_rows = freeze_selection(
        rows,
        frozen_path,
        approval_note=approval_note,
    )
    presentations = _make_presentations(
        frozen_rows,
        duplicate_fraction=duplicate_fraction,
        seed=seed,
    )
    internal_dir = output / "internal_DO_NOT_SEND_TO_EVALUATORS"
    source_assets = internal_dir / "blinded_pair_assets"
    internal_rows: list[dict[str, Any]] = []
    for presentation in presentations:
        candidate_path = _instance_image_path(
            root,
            str(presentation["candidate_instance_id"]),
        )
        reference_path = _instance_image_path(
            root,
            str(presentation["reference_instance_id"]),
        )
        if not candidate_path.is_file() or not reference_path.is_file():
            raise FileNotFoundError(
                f"missing source image for frozen pair {presentation['source_pair_id']}"
            )
        blinded_id = str(presentation["blinded_pair_id"])
        _render_pair_asset(
            candidate_path,
            reference_path,
            source_assets / f"{blinded_id}.png",
            target_char=str(presentation["target_char"]),
        )
        internal_rows.append(
            {
                "blinded_pair_id": blinded_id,
                "source_pair_id": presentation["source_pair_id"],
                "duplicate_of_source_pair_id": (
                    presentation["source_pair_id"]
                    if _boolish(presentation["is_repeat"])
                    else ""
                ),
                "is_repeat": _boolish(presentation["is_repeat"]),
                "target_char": presentation["target_char"],
                "char_id": presentation["char_id"],
                "style_id": presentation["style_id"],
                "candidate_instance_id": presentation["candidate_instance_id"],
                "reference_instance_id": presentation["reference_instance_id"],
                "candidate_asset": f"blinded_pair_assets/{blinded_id}.png",
                "reference_asset": f"blinded_pair_assets/{blinded_id}.png",
                "system_score": presentation["current_score"],
                "coverage_aware_score": presentation["coverage_aware_score"],
                "selection_seed": seed,
            }
        )
    _write_csv(internal_dir / "expert_rating_pairs.csv", internal_rows)
    evaluator_root = output / "SEND_ONE_FOLDER_TO_EACH_EVALUATOR"
    evaluator_orders: dict[str, list[str]] = {}
    for evaluator_id in evaluator_ids:
        ordered = _evaluator_order(
            presentations,
            evaluator_id,
            seed=seed,
        )
        evaluator_orders[evaluator_id] = [
            str(row["blinded_pair_id"]) for row in ordered
        ]
        _write_evaluator_package(
            evaluator_root,
            evaluator_id,
            ordered,
            source_assets,
        )
    metadata = {
        "schema_version": 1,
        "study_version": STUDY_VERSION,
        "freeze_status": FROZEN_STATUS,
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "approved_selection_source": str(selection_path.resolve()),
        "approved_selection_sha256": _sha256_file(selection_path),
        "frozen_pair_file": str(frozen_path.resolve()),
        "frozen_pair_file_sha256": _sha256_file(frozen_path),
        "unique_frozen_pairs": len(frozen_rows),
        "hidden_repeat_presentations": sum(
            _boolish(row["is_repeat"]) for row in presentations
        ),
        "total_presentations_per_evaluator": len(presentations),
        "evaluator_ids": list(evaluator_ids),
        "evaluator_order_sha256": {
            evaluator_id: hashlib.sha256(
                "\n".join(order).encode("utf-8")
            ).hexdigest()
            for evaluator_id, order in evaluator_orders.items()
        },
        "model_scores_exposed_to_evaluators": False,
        "source_pair_ids_exposed_to_evaluators": False,
        "repeat_identity_exposed_to_evaluators": False,
        "claim_scope": "structural similarity only, not aesthetic grading",
        "writer_identity_status": WRITER_IDENTITY_STATUS,
        "approval_note": approval_note,
        "change_policy": (
            "Do not modify the frozen CSV, pair assets, blinded IDs, or evaluator "
            "packages after any human rating has started. Any required change creates "
            "a new study version and invalidates partially collected v1 ratings."
        ),
    }
    (output / "freeze_manifest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output / "真人评分总说明.md").write_text(
        f"""# 真人结构相似度评分操作说明

## 已冻结内容

- 正式题目：150 对。
- 每位评价者实际看到：165 道，其中 15 道为隐藏重复题。
- 评价者：建议至少 3 人，当前编号为 `{", ".join(evaluator_ids)}`。
- 任务范围：只判断结构相似度，不评价美感、书法水平或历史真实性。
- 冻结文件 SHA-256：`{metadata["frozen_pair_file_sha256"]}`。

从第一位评价者开始评分起，不得修改 `frozen_expert_pairs_v1.csv`、
图片、盲化编号和题目顺序。若发现必须修改的问题，应停止 v1，创建新的
study version，不能将新旧评分混合。

## 发给评价者

每位评价者只收到自己的文件夹：

- `SEND_ONE_FOLDER_TO_EACH_EVALUATOR/E01`
- `SEND_ONE_FOLDER_TO_EACH_EVALUATOR/E02`
- `SEND_ONE_FOLDER_TO_EACH_EVALUATOR/E03`

严禁把 `internal_DO_NOT_SEND_TO_EVALUATORS` 发给评价者，因为其中包含
模型分数、原始 pair ID 和重复题映射。

评价者双击文件夹中的 `E0X_rating_tool.html`，填写背景信息并独立完成
165 道评分。浏览器会自动保存进度。完成后点击“导出评分 CSV”，将 CSV
交回项目负责人。

## 组织建议

1. 先确认学校是否要求伦理审批、豁免或知情同意备案。
2. 评价者使用匿名编号，不收集姓名、学号、手机号。
3. 每人独立评分，不讨论题目，不查看模型结果。
4. 建议分 2–3 次完成，每约 50–60 道休息一次。
5. 最好在相近尺寸、正常亮度的屏幕上查看，浏览器缩放保持 100%。
6. 回收文件应为 `E01_expert_ratings.csv` 等，每份应有 165 行且无漏评。

## 回收后

将三份 CSV 放入：

`returned_ratings/`

随后运行评分汇总和统计脚本。论文报告至少包括：

- 系统分数与专家平均分的 Spearman 相关及按字符 bootstrap 95% CI；
- ICC(2,1) 和 ICC(2,k)；
- 隐藏重复题的评价者内一致性；
- 缺失评分和排除情况；
- 评价者背景的匿名描述。
""",
        encoding="utf-8",
    )
    return metadata
