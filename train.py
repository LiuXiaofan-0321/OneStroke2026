from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np

from onestroke_model.constants import CHANNELS, SCHEMA_VERSION
from onestroke_model.config import load_yaml
from onestroke_model.utils.io import ensure_dir, write_json
from onestroke_model.utils.seed import seed_everything


def _require_torch():
    try:
        import torch
    except ImportError as exc:
        raise SystemExit("PyTorch is required for training. Run: python -m pip install -e '.[train]'") from exc
    return torch


def _device(name: str, torch_module):
    if name == "auto":
        return torch_module.device("cuda" if torch_module.cuda.is_available() else "cpu")
    return torch_module.device(name)


def _threshold_array(cfg: dict[str, Any]) -> np.ndarray:
    thresholds = cfg.get("thresholds", {})
    return np.asarray([float(thresholds.get(channel, 0.5)) for channel in CHANNELS], dtype=np.float32).reshape(
        1, len(CHANNELS), 1, 1
    )


def _build_loss(cfg: dict[str, Any], output_dir: Path):
    from onestroke_model.data.dataset import estimate_direction_pos_weight
    from onestroke_model.losses.multilabel import MultiLabelStrokeLoss

    loss_cfg = cfg.get("loss", {})
    direction_cfg = loss_cfg.get("direction", {})
    keypoint_cfg = loss_cfg.get("keypoint", {})
    raw_pos_weight = direction_cfg.get("pos_weight", "auto")
    if raw_pos_weight == "auto":
        statistics = estimate_direction_pos_weight(
            cfg["data"]["manifest"],
            cfg["data"]["splits"],
            max_samples=int(direction_cfg.get("pos_weight_max_samples", 200)),
            max_weight=float(direction_cfg.get("pos_weight_max", 100.0)),
        )
        direction_pos_weight = statistics["direction_pos_weight"]
    else:
        if not isinstance(raw_pos_weight, list) or len(raw_pos_weight) != 5:
            raise ValueError("loss.direction.pos_weight must be 'auto' or a five-number list")
        direction_pos_weight = [float(value) for value in raw_pos_weight]
        statistics = {"method": "configured", "direction_pos_weight": direction_pos_weight}

    write_json(output_dir / "data_statistics.json", statistics)
    return MultiLabelStrokeLoss(
        direction_pos_weight=direction_pos_weight,
        direction_bce_weight=float(direction_cfg.get("bce_weight", 1.0)),
        direction_dice_weight=float(direction_cfg.get("dice_weight", 1.0)),
        keypoint_focal_weight=float(keypoint_cfg.get("focal_weight", 1.0)),
        keypoint_dice_weight=float(keypoint_cfg.get("dice_weight", 1.0)),
        focal_gamma=float(keypoint_cfg.get("focal_gamma", 2.0)),
        focal_alpha=float(keypoint_cfg.get("focal_alpha", 0.25)),
        boundary_weight=float(loss_cfg.get("boundary_weight", 0.2)),
    ), statistics


def _build_optimizer(model, cfg: dict[str, Any], torch_module):
    optim_cfg = cfg.get("optim", {})
    weight_decay = float(optim_cfg.get("weight_decay", 0.01))
    model_cfg = cfg.get("model", {})
    if model_cfg.get("name") == "segformer" and hasattr(model, "model") and hasattr(model.model, "segformer"):
        encoder_lr = float(optim_cfg.get("encoder_lr", 3e-5))
        decoder_lr = float(optim_cfg.get("decoder_lr", encoder_lr * float(optim_cfg.get("decoder_lr_scale", 10.0))))
        encoder_params = list(model.model.segformer.parameters())
        encoder_ids = {id(param) for param in encoder_params}
        decoder_params = [param for param in model.parameters() if id(param) not in encoder_ids]
        if not decoder_params:
            raise ValueError("could not identify SegFormer decoder parameters")
        param_groups = [
            {"params": encoder_params, "lr": encoder_lr, "name": "encoder"},
            {"params": decoder_params, "lr": decoder_lr, "name": "decoder"},
        ]
    else:
        lr = float(optim_cfg.get("lr", optim_cfg.get("decoder_lr", 3e-4)))
        param_groups = [{"params": model.parameters(), "lr": lr, "name": "model"}]
    optimizer = torch_module.optim.AdamW(param_groups, weight_decay=weight_decay)
    return optimizer, [{"name": group["name"], "lr": group["lr"]} for group in param_groups]


def _build_scheduler(optimizer, cfg: dict[str, Any], torch_module):
    optim_cfg = cfg.get("optim", {})
    name = str(optim_cfg.get("scheduler", "none")).lower()
    if name in {"none", "off", ""}:
        return None
    if name == "cosine":
        return torch_module.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=int(optim_cfg.get("epochs", 80)),
            eta_min=float(optim_cfg.get("min_lr", 1e-6)),
        )
    raise ValueError(f"unsupported optim.scheduler: {name}")


def _evaluate(model, loader, device, loss_fn, threshold_array: np.ndarray, max_batches: int = 0) -> dict[str, object]:
    torch = _require_torch()
    from onestroke_model.metrics.segmentation import SegmentationMeter

    model.eval()
    meter = SegmentationMeter(num_channels=len(CHANNELS))
    total_loss = 0.0
    batches = 0
    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(device=device, dtype=torch.float32)
            masks = batch["mask"].to(device=device, dtype=torch.float32)
            logits = model(images)
            loss = loss_fn(logits, masks)
            probs = torch.sigmoid(logits).detach().cpu().numpy()
            targets = masks.detach().cpu().numpy()
            meter.update(probs >= threshold_array, targets > 0.5)
            total_loss += float(loss.item())
            batches += 1
            if max_batches > 0 and batches >= max_batches:
                break
    metrics = meter.compute()
    metrics["loss"] = total_loss / max(1, batches)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train U-Net or SegFormer on six-channel stroke masks.")
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    torch = _require_torch()
    from onestroke_model.data.dataset import make_torch_loader
    from onestroke_model.models import build_model

    seed_everything(int(cfg.get("seed", 20260709)))
    device = _device(str(cfg.get("device", "auto")), torch)
    data_cfg = cfg["data"]
    output_dir = ensure_dir(cfg.get("output_dir", "artifacts/runs/default"))
    ckpt_dir = ensure_dir(output_dir / "checkpoints")
    loss_fn, statistics = _build_loss(cfg, output_dir)
    model = build_model(cfg["model"]).to(device)
    loss_fn = loss_fn.to(device)
    train_loader = make_torch_loader(
        data_cfg["manifest"],
        data_cfg["splits"],
        "train",
        int(data_cfg.get("image_size", 512)),
        int(data_cfg.get("batch_size", 4)),
        int(data_cfg.get("num_workers", 0)),
        shuffle=True,
    )
    val_loader = make_torch_loader(
        data_cfg["manifest"],
        data_cfg["splits"],
        "val",
        int(data_cfg.get("image_size", 512)),
        int(data_cfg.get("batch_size", 4)),
        int(data_cfg.get("num_workers", 0)),
        shuffle=False,
    )
    optimizer, parameter_groups = _build_optimizer(model, cfg, torch)
    scheduler = _build_scheduler(optimizer, cfg, torch)
    threshold_array = _threshold_array(cfg)
    thresholds = {channel: float(threshold_array[0, i, 0, 0]) for i, channel in enumerate(CHANNELS)}
    write_json(
        output_dir / "run_metadata.json",
        {
            "schema_version": SCHEMA_VERSION,
            "channels": CHANNELS,
            "config": cfg,
            "device": str(device),
            "parameter_groups": parameter_groups,
            "thresholds": thresholds,
            "class_weight_statistics": statistics,
        },
    )

    optim_cfg = cfg.get("optim", {})
    debug_cfg = cfg.get("debug", {})
    max_train_batches = int(debug_cfg.get("max_train_batches", 0))
    max_val_batches = int(debug_cfg.get("max_val_batches", 0))
    scaler = torch.cuda.amp.GradScaler(enabled=bool(optim_cfg.get("amp", True)) and device.type == "cuda")
    epochs = int(optim_cfg.get("epochs", 80))
    patience = int(optim_cfg.get("early_stop_patience", 12))
    best_macro_dice = -1.0
    bad_epochs = 0
    history: list[dict[str, object]] = []
    print(
        f"experiment={cfg.get('experiment_name')} device={device} "
        f"train_batches={len(train_loader)} val_batches={len(val_loader)}"
    )
    print(f"direction_pos_weight={statistics['direction_pos_weight']}")

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        train_batches = 0
        for batch in train_loader:
            images = batch["image"].to(device=device, dtype=torch.float32)
            masks = batch["mask"].to(device=device, dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=scaler.is_enabled()):
                logits = model(images)
                loss = loss_fn(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.item())
            train_batches += 1
            if max_train_batches > 0 and train_batches >= max_train_batches:
                break

        val_metrics = _evaluate(model, val_loader, device, loss_fn, threshold_array, max_batches=max_val_batches)
        train_loss = total_loss / max(1, train_batches)
        learning_rates = [float(group["lr"]) for group in optimizer.param_groups]
        row = {"epoch": epoch, "train_loss": train_loss, "learning_rates": learning_rates, **val_metrics}
        history.append(row)
        write_json(output_dir / "metrics_history.json", history)
        print(
            f"epoch={epoch:03d} train_loss={train_loss:.4f} "
            f"val_macro_dice={val_metrics['macro_dice']:.4f} "
            f"val_keypoint_f1={val_metrics['keypoint_f1']:.4f} "
            f"val_boundary_f1={val_metrics['boundary_f1']:.4f}"
        )

        macro_dice = float(val_metrics["macro_dice"])
        if macro_dice > best_macro_dice:
            best_macro_dice = macro_dice
            bad_epochs = 0
            torch.save(
                {
                    "schema_version": SCHEMA_VERSION,
                    "channels": CHANNELS,
                    "config": cfg,
                    "thresholds": thresholds,
                    "class_weight_statistics": statistics,
                    "model_state": model.state_dict(),
                    "optimizer_state": optimizer.state_dict(),
                    "scheduler_state": scheduler.state_dict() if scheduler else None,
                    "best_macro_dice": best_macro_dice,
                    "epoch": epoch,
                },
                ckpt_dir / "best.pt",
            )
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                print(f"early_stop epoch={epoch} best_macro_dice={best_macro_dice:.4f}")
                break
        if scheduler:
            scheduler.step()

    write_json(output_dir / "final_metrics.json", history[-1] if history else {})


if __name__ == "__main__":
    main()
