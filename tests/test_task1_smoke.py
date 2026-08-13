from __future__ import annotations

from onestroke_model.scripts.generate_task1_configs import build_config
from onestroke_model.task1_smoke import build_smoke_config


def test_smoke_config_isolated_from_formal_outputs() -> None:
    formal = build_config("main_qc", "deeplabv3plus", 20260811)
    smoke = build_smoke_config(formal, model_key="deeplabv3plus")
    assert smoke["output_dir"].endswith("task1_smoke/deeplabv3plus")
    assert smoke["formal_training"] is False
    assert smoke["debug"] == {
        "max_train_batches": 1,
        "max_val_batches": 1,
    }
    assert smoke["optim"]["epochs"] == 1
    assert smoke["optim"]["warmup_epochs"] == 0
    assert smoke["data"]["batch_size"] == 2
    assert formal["optim"]["epochs"] == 120
    assert formal["output_dir"].endswith(
        "main_qc/runs/deeplabv3plus_seed_20260811"
    )
