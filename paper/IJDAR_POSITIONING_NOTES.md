# IJDAR positioning notes

Status date: 2026-08-14

## Special Issue fit

The paper is positioned for the IJDAR Special Issue *Computer Vision Systems
for Document Analysis and Recognition*, whose call includes low-resource and
few-shot document analysis, robustness/generalization, handwritten document
analysis, explainable AI, and practical document applications:

<https://link.springer.com/collections/jaeiejghgj>

The strongest fit is not “a novel SegFormer”. It is:

1. low-resource overlapping structure parsing;
2. character-disjoint generalization;
3. constrained registration with paired robustness experiments;
4. auditable reference-based structural assessment;
5. explicit separation of retrospective score development, grouped internal
   validation, and future external replication.

The official call lists **September 20, 2026** as the submission deadline.
The journal instructions require a 150--250-word abstract, 4--6 keywords, and
a manuscript of no more than 20 pages including references, figures, and
tables. The submission must be marked for the Special Issue in the editorial
system. These are compliance constraints, not merely stylistic preferences.

## Characteristics taken from relevant IJDAR papers

### Baloun et al. (IJDAR 2025)

*On self-supervision in historical handwritten document segmentation* reports
the data regime, segmentation task, pretraining alternatives, and evaluation
conditions explicitly. Its value is not a single headline accuracy but a
controlled comparison under limited annotation.

<https://doi.org/10.1007/s10032-025-00538-6>

Applied here:

- the recovered corpus and QC exclusions are documented;
- standard and character-disjoint settings are separated;
- all declared seeds are retained;
- unavailable writer identity is reported as a limitation.

### Zhang et al., CalliNet (IJDAR 2026)

*CalliNet: a triplet network for Chinese calligraphy style classification*
states a narrowly defined calligraphy task, identifies the limitation of
generic visual features, builds a task-specific comparison, and evaluates
discriminative behaviour rather than claiming general artistic understanding.

<https://doi.org/10.1007/s10032-025-00559-1>

Applied here:

- the construct is structural agreement, not beauty;
- same-character comparison is mandatory;
- style classification/generation is related work, not an inflated claim;
- negative and unsupported reference conditions are stated explicitly.

### Chinese calligraphic style representation (IJDAR 2017)

This paper combines local and global descriptors and makes the representation
itself interpretable.

<https://doi.org/10.1007/s10032-016-0277-z>

Applied here:

- ASDS combines radial/angular organization, coarse spatial balance, and
  projection profiles;
- component ablation reports which descriptor contributes the association.

## Submission narrative

The manuscript should be read as four linked claims:

- **Parsing:** overlapping labels are necessary for intersecting directional
  structure.
- **Generalization:** the best standard-split model is not the best
  unseen-character model.
- **Registration:** limited transform capacity improves nuisance robustness
  without freely repairing local errors.
- **Validity:** human association improves when spatial distribution is
  modelled; post-rating development is reported as retrospective, with
  character-grouped out-of-fold internal validation.

The submission does not claim prospective or external confirmation. The
full-sample ASDS result and the grouped out-of-fold estimate must remain
clearly labelled so the retrospective design is not hidden.
