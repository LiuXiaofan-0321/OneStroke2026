# segformer-b2-v1 交付包

本目录固定 B2 版本的阈值、指标、schema、消融结果和模型清单。大文件 checkpoint 位于：

```text
checkpoints/segformer_b2_v1/best.pt
```

该 checkpoint 通过 Git LFS 管理。克隆后需要执行：

```bash
git lfs install
git lfs pull
```

一条命令导出开发资源：

```bash
python infer.py \
  --config configs/segformer_b2_v1_delivery.yaml \
  --checkpoint checkpoints/segformer_b2_v1/best.pt \
  --image demo.png \
  --output-dir artifacts/demo_b2
```

详细能力、指标和限制见 `docs/model_card_segformer_b2_v1.md`。
