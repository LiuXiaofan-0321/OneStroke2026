from __future__ import annotations

import argparse
from pathlib import Path

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


def _evaluate(model, loader, device, threshold: float = 0.5) -> dict[str, object]:
    torch = _require_torch()
    from onestroke_model.losses.multilabel import multilabel_stroke_loss
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
            loss = multilabel_stroke_loss(logits, masks)
            probs = torch.sigmoid(logits).detach().cpu().numpy()
            targets = masks.detach().cpu().numpy()
            meter.update(probs > threshold, targets > 0.5)
            total_loss += float(loss.item())
            batches += 1
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
    from onestroke_model.losses.multilabel import multilabel_stroke_loss
    from onestroke_model.models import build_model

    seed_everything(int(cfg.get("seed", 20260709)))

    device = _device(str(cfg.get("device", "auto")), torch)
    data_cfg = cfg["data"]
    model = build_model(cfg["model"]).to(device)
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

    optim_cfg = cfg.get("optim", {})
    lr = float(optim_cfg.get("lr", optim_cfg.get("decoder_lr", 3e-4)))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=float(optim_cfg.get("weight_decay", 0.01)),
    )
    scaler = torch.cuda.amp.GradScaler(enabled=bool(optim_cfg.get("amp", True)) and device.type == "cuda")
    epochs = int(optim_cfg.get("epochs", 80))
    patience = int(optim_cfg.get("early_stop_patience", 12))
    output_dir = ensure_dir(cfg.get("output_dir", "artifacts/runs/default"))
    ckpt_dir = ensure_dir(Path(output_dir) / "checkpoints")

    best_macro_dice = -1.0
    bad_epochs = 0
    history: list[dict[str, object]] = []
    print(f"experiment={cfg.get('experiment_name')} device={device} train_batches={len(train_loader)}")

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for batch in train_loader:
            images = batch["image"].to(device=device, dtype=torch.float32)
            masks = batch["mask"].to(device=device, dtype=torch.float32)
            optimizer.zero_grad(set_to_none=True)
            with torch.cuda.amp.autocast(enabled=scaler.is_enabled()):
                logits = model(images)
                loss = multilabel_stroke_loss(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.item())

        val_metrics = _evaluate(model, val_loader, device)
        train_loss = total_loss / max(1, len(train_loader))
        row = {"epoch": epoch, "train_loss": train_loss, **val_metrics}
        history.append(row)
        write_json(Path(output_dir) / "metrics_history.json", history)
        print(
            f"epoch={epoch:03d} train_loss={train_loss:.4f} "
            f"val_macro_dice={val_metrics['macro_dice']:.4f} "
            f"val_keypoint_f1={val_metrics['keypoint_f1']:.4f}"
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
                    "model_state": model.state_dict(),
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

    write_json(Path(output_dir) / "final_metrics.json", history[-1] if history else {})


if __name__ == "__main__":
    main()
