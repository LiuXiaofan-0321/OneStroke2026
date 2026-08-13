"""GPU smoke-test planning and execution for the three formal Task 1 models."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from onestroke_model.config import load_yaml
from onestroke_model.reproducibility import utc_now_iso

REPRESENTATIVE_CONFIGS = (
    Path("configs/paper_ijdar/main_qc_unet_seed_20260811.yaml"),
    Path("configs/paper_ijdar/main_qc_deeplabv3plus_seed_20260811.yaml"),
    Path("configs/paper_ijdar/main_qc_segformer_b2_seed_20260811.yaml"),
)


def build_smoke_config(
    formal_config: dict[str, Any],
    *,
    model_key: str,
) -> dict[str, Any]:
    config = json.loads(json.dumps(formal_config))
    config["experiment_name"] = f"task1_smoke_{model_key}"
    config["formal_training"] = False
    config["data"]["num_workers"] = 0
    config["optim"]["epochs"] = 1
    config["optim"]["early_stop_patience"] = 1
    config["optim"]["warmup_epochs"] = 0
    config["debug"] = {
        "max_train_batches": 1,
        "max_val_batches": 1,
    }
    config["output_dir"] = f"artifacts/paper_ijdar/task1_smoke/{model_key}"
    return config


def _commands(config_path: Path, output_dir: Path) -> list[str]:
    checkpoint = output_dir / "checkpoints/best.pt"
    thresholds = output_dir / "thresholds_smoke.json"
    metrics = output_dir / "test_metrics_smoke.json"
    return [
        f'python train.py --config "{config_path.as_posix()}"',
        (
            "python -m onestroke_model.scripts.calibrate_thresholds "
            f'--config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--output "{thresholds.as_posix()}" --max-batches 1'
        ),
        (
            f'python eval.py --config "{config_path.as_posix()}" '
            f'--checkpoint "{checkpoint.as_posix()}" '
            f'--thresholds-json "{thresholds.as_posix()}" '
            f'--split test --output "{metrics.as_posix()}" --max-batches 1'
        ),
    ]


def build_task1_smoke_plan(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    runs: list[dict[str, Any]] = []
    for formal_path in REPRESENTATIVE_CONFIGS:
        formal = load_yaml(root / formal_path)
        model_name = str(formal["model"]["name"])
        model_key = (
            "segformer_b2" if model_name == "segformer" else model_name
        )
        smoke_config = build_smoke_config(formal, model_key=model_key)
        output_dir = Path(str(smoke_config["output_dir"]))
        smoke_config_path = output_dir / "smoke_config.yaml"
        runs.append(
            {
                "model_key": model_key,
                "formal_config": formal_path.as_posix(),
                "smoke_config": smoke_config_path.as_posix(),
                "output_dir": output_dir.as_posix(),
                "config": smoke_config,
                "commands": _commands(smoke_config_path, output_dir),
            }
        )
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now_iso(),
        "project_root": str(root),
        "run_count": len(runs),
        "formal_results": False,
        "runs": runs,
    }


def _run_command(command: str, *, cwd: Path, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n[{utc_now_iso()}] $ {command}\n")
        log.flush()
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"smoke command failed with exit code {completed.returncode}; "
            f"see {log_path}"
        )


def run_task1_smoke(
    project_root: str | Path,
    *,
    execute: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_task1_smoke_plan(root)
    smoke_root = root / "artifacts/paper_ijdar/task1_smoke"
    smoke_root.mkdir(parents=True, exist_ok=True)
    (smoke_root / "smoke_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not execute:
        return plan

    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Task 1 GPU smoke requires PyTorch") from exc
    if not torch.cuda.is_available():
        raise RuntimeError(
            "Task 1 GPU smoke requires a CUDA GPU; switch the AutoDL instance "
            "out of no-card mode before using --execute"
        )

    results: list[dict[str, Any]] = []
    for run in plan["runs"]:
        output_dir = root / run["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        config_path = root / run["smoke_config"]
        config_path.write_text(
            yaml.safe_dump(
                run["config"],
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        log_path = output_dir / "smoke.log"
        for command in run["commands"]:
            _run_command(command, cwd=root, log_path=log_path)
        thresholds_path = output_dir / "thresholds_smoke.json"
        metrics_path = output_dir / "test_metrics_smoke.json"
        thresholds = json.loads(thresholds_path.read_text(encoding="utf-8"))
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if thresholds.get("formal_calibration") is not False:
            raise ValueError("smoke threshold output was misclassified as formal")
        if metrics.get("formal_evaluation") is not False:
            raise ValueError("smoke test metrics were misclassified as formal")
        results.append(
            {
                "model_key": run["model_key"],
                "status": "PASSED",
                "checkpoint": str(output_dir / "checkpoints/best.pt"),
                "thresholds": str(thresholds_path),
                "metrics": str(metrics_path),
                "log": str(log_path),
            }
        )
    report = {
        "schema_version": 1,
        "generated_at_utc": utc_now_iso(),
        "formal_results": False,
        "passed_count": len(results),
        "results": results,
    }
    (smoke_root / "smoke_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report
