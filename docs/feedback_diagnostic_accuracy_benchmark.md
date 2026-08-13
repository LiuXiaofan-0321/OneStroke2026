# Feedback Diagnostic Accuracy Benchmark

This benchmark evaluates deterministic feedback rules against known mask-space
perturbation causes. It does not use LLM output and does not claim expert
calligraphy or aesthetic accuracy.

Both `legacy-v1` and `current` consume the same approved real references, the
same perturbations, the same constrained alignment, and the same structure-score
evidence. The paired metrics are:

- required Recall@3;
- strict primary-cause Top-1;
- policy-conditioned Recall@3;
- canonical local-channel accuracy;
- missing/extra classification accuracy;
- exact and overlapping 3x3-region localization;
- false-positive specificity on rotation/compound nuisance cases;
- center-direction wording correctness.

Deterministic perturbation labels are valid diagnostic ground truth only. Human
expert validation remains a separate experiment.

```bash
python -m onestroke_model.scripts.run_feedback_diagnostic_benchmark \
  --cache-index references/cache/segformer_b2_v1/index.json \
  --output-dir artifacts/paper_ijdar/feedback_diagnostic
```
