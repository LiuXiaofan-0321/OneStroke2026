# Feedback Diagnostic Rules v2

The benchmark-only `current` rule variant freezes three corrections before the
formal paired run:

1. Center-direction wording uses a single dominant axis unless the minor axis is
   at least 45% of the major axis.
2. A local finding is localized within its declared worst direction channel, so
   one finding cannot name two conflicting channels.
3. An alignment-residual suppression candidate was implemented and checked on a
   score-independent two-reference acceptance smoke. It reduced structural
   Recall@3, so it failed the preregistered no-regression gate and is not present
   in the formal `current` rule variant. Alignment-residual false positives remain
   an openly reported limitation rather than being hidden by post-hoc threshold
   tuning.

These rules are research candidates. The formal controlled diagnostic does not
modify production feedback, score weights, alignment ranges, model thresholds,
or LLM prompts.
