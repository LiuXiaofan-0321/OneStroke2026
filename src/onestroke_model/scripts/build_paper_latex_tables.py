"""Generate LaTeX tables from completed formal and journal-statistics artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _fmt(value: str | float | None, digits: int = 3) -> str:
    if value in (None, ""):
        return "--"
    return f"{float(value):.{digits}f}"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def build_tables(project_root: Path) -> list[Path]:
    root = project_root.resolve()
    artifacts = root / "artifacts/paper_ijdar"
    output = root / "paper/tables"
    created: list[Path] = []

    controlled = _read(
        artifacts
        / "journal_statistics/controlled_perturbation_journal_statistics.csv"
    )
    rows = []
    for row in controlled:
        ci = (
            f"[{_fmt(row['bootstrap_mean_ci95_low'])}, "
            f"{_fmt(row['bootstrap_mean_ci95_high'])}]"
        )
        severity_spearman = _fmt(row["severity_spearman_mean"])
        rows.append(
            "{} & {} & {} & {} & {} & {} & {} & {} & {} & {} \\\\".format(
                row["perturbation"].replace("_", r"\_"),
                row["n_valid"],
                _fmt(row["mean"]),
                _fmt(row["median"]),
                _fmt(row["std_ddof1"]),
                ci,
                f"[{_fmt(row['p05'])}, {_fmt(row['p95'])}]",
                _fmt(row["invalid_fraction"]),
                severity_spearman,
                _fmt(row["adjacent_nonincreasing_rate"]),
            )
        )
    path = output / "controlled_perturbation.tex"
    _write(
        path,
        r"""\begin{table*}[t]
\caption{Per-perturbation score-drop statistics. Nuisance rows use absolute
drop; structural rows use signed drop from the identity score. Confidence
intervals use reference-level bootstrap resampling.}
\label{tab:controlled}
\centering
\scriptsize
\begin{tabular}{lrrrrrrrrr}
\toprule
Perturbation & $N$ & Mean & Median & SD & 95\% CI & P05--P95 &
Invalid & $\rho_s$ & Monotonic \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table*}""",
    )
    created.append(path)

    alignment = [
        row
        for row in _read(
            artifacts / "journal_statistics/alignment_paired_statistics.csv"
        )
        if row["scope_type"] == "family"
    ]
    rows = []
    for row in alignment:
        rows.append(
            "{} & {} & {} & {} & {} & [{}, {}] & {} & {} \\\\".format(
                row["comparison"].replace("current_constrained_vs_", "Ours--").replace(
                    "_", r"\_"
                ),
                row["family"],
                row["n_reference_pairs"],
                _fmt(row["current_mean"]),
                _fmt(row["comparator_mean"]),
                _fmt(row["paired_bootstrap_ci95_low"]),
                _fmt(row["paired_bootstrap_ci95_high"]),
                _fmt(row["wilcoxon_p_two_sided"], 2),
                _fmt(row["rank_biserial_positive_favors_current"]),
            )
        )
    path = output / "alignment_ablation.tex"
    _write(
        path,
        r"""\begin{table*}[t]
\caption{Paired alignment comparison. Positive benefit differences favour the
current constrained alignment. Wilcoxon tests use per-reference mean paired
differences.}
\label{tab:alignment}
\centering
\small
\begin{tabular}{llrrrrrrr}
\toprule
Comparison & Family & Refs & Ours & Comparator & Benefit 95\% CI & $p$ & RBC \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table*}""",
    )
    created.append(path)

    alignment_breakdown = [
        row
        for row in _read(
            artifacts / "journal_statistics/alignment_paired_statistics.csv"
        )
        if row["scope_type"] == "perturbation"
    ]
    rows = []
    for row in alignment_breakdown:
        rows.append(
            "{} & {} & {} & {} & {} & [{}, {}] & {} & {} \\\\".format(
                row["comparison"].replace("current_constrained_vs_", "Ours--").replace(
                    "_", r"\_"
                ),
                row["perturbation"].replace("_", r"\_"),
                row["n_reference_pairs"],
                _fmt(row["current_mean"]),
                _fmt(row["comparator_mean"]),
                _fmt(row["paired_bootstrap_ci95_low"]),
                _fmt(row["paired_bootstrap_ci95_high"]),
                _fmt(row["wilcoxon_p_two_sided"], 2),
                _fmt(row["rank_biserial_positive_favors_current"]),
            )
        )
    path = output / "alignment_ablation_breakdown.tex"
    _write(
        path,
        r"""\begin{table*}[t]
\caption{Paired alignment comparisons by perturbation family. Positive
benefit differences favour the current constrained alignment.}
\label{tab:alignment-breakdown}
\centering
\scriptsize
\begin{tabular}{llrrrrrr}
\toprule
Comparison & Perturbation & Refs & Ours & Comparator & Benefit 95\% CI & $p$ & RBC \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table*}""",
    )
    created.append(path)

    inactive = [
        row
        for row in _read(
            artifacts / "journal_statistics/inactive_channel_distribution.csv"
        )
        if row["style_id"] == "ALL" and int(row["inactive_direction_count"]) <= 2
    ]
    rows = [
        "{} & {} & {} \\\\".format(
            row["inactive_direction_count"],
            row["reference_count"],
            _fmt(row["fraction"]),
        )
        for row in inactive
    ]
    path = output / "structure_score_audit.tex"
    _write(
        path,
        r"""\begin{table}[t]
\caption{Inactive direction channels among 200 references.}
\label{tab:inactive}
\centering
\begin{tabular}{rrr}
\toprule
Inactive channels & References & Fraction \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table}""",
    )
    created.append(path)

    cross = _read(artifacts / "cross_reference/cross_reference_summary.csv")
    rows = []
    for row in cross:
        if int(row["n"]) == 0:
            continue
        rows.append(
            "{} & {} & {} & {} & [{}, {}] \\\\".format(
                row["pair_type"].replace("_", r"\_"),
                row["n"],
                _fmt(row["mean"]),
                _fmt(row["median"]),
                _fmt(row["mean_ci95_low"]),
                _fmt(row["mean_ci95_high"]),
            )
        )
    path = output / "cross_reference.tex"
    _write(
        path,
        r"""\begin{table*}[t]
\caption{Cross-reference structural agreement.}
\label{tab:cross-reference}
\centering
\begin{tabular}{lrrrr}
\toprule
Pair type & $N$ & Mean & Median & Mean 95\% CI \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table*}""",
    )
    created.append(path)

    failures = _read(
        artifacts / "journal_statistics/feedback_failure_taxonomy_summary.csv"
    )
    rows = [
        "{} & {} & {} \\\\".format(
            row["failure_type"].replace("_", r"\_"),
            row["count"],
            _fmt(row["fraction_of_exact_region_failures"]),
        )
        for row in failures
    ]
    path = output / "feedback_failure_taxonomy.tex"
    _write(
        path,
        r"""\begin{table}[t]
\caption{Primary taxonomy of exact-region diagnostic failures.}
\label{tab:feedback-failures}
\centering
\small
\begin{tabular}{lrr}
\toprule
Failure type & Count & Fraction \\
\midrule
"""
        + "\n".join(rows)
        + r"""
\bottomrule
\end{tabular}
\end{table}""",
    )
    created.append(path)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    for path in build_tables(args.project_root):
        print(path)


if __name__ == "__main__":
    main()
