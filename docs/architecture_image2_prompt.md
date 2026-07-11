# Image 2 原理结构图生成提示词

将下面完整提示词连同“不要修改文字拼写”的要求一并发送给 Image 2。建议生成 `16:9` 横版图，用于汇报 PPT；图中的文字优先使用简短英文，避免生成模型把中文标签绘制错误。PPT 中可再叠加中文说明。

```text
Create a polished academic system architecture diagram for a research presentation, 16:9 landscape, white background, clean vector infographic style, blue-teal-purple color palette, high resolution, no 3D, no photorealism, no logos, no decorative clutter. Use thin arrows, rounded rectangles, clear grouping, and concise English labels only. All text must be exactly legible and spelled correctly.

Title at top center:
"OneStroke: Multi-label Chinese Character Structure Analysis"

Build the diagram from left to right with four clearly separated layers.

Layer 1 on the far left, titled "Data & Annotation":
- A handwritten Chinese character RGB image icon, label "RGB Character Image"
- A stacked six-channel mask icon, label "6-channel Labels"
- Under the mask, show exactly six small colored chips: "vec1", "vec2", "vec3", "vec4", "vec5", "keypoint"
- A small database card, label "Manifest + Group Split"
- A small highlighted sample grid, label "Hard-case Test Set"
- Use arrows from image and labels toward the training layer.

Layer 2 in the center-left, titled "Offline Training":
- A small gray baseline block labeled "U-Net Baseline"
- A large primary blue block labeled "SegFormer-B2 Teacher"
- Inside or directly below the large block show: "Multi-label Sigmoid Output" and six overlapping colored probability maps, clearly indicating that channels can overlap at stroke intersections; do NOT show softmax.
- Under the teacher, show four compact training components connected into it: "Weighted BCE + Dice", "Focal + Dice (Keypoint)", "Boundary Loss", "AdamW + Cosine Schedule"
- Add a small ablation table icon with label "Dice / IoU / Keypoint F1 / Boundary F1"

Above the SegFormer-B2 block, add a purple dashed auxiliary branch titled "SAM2 Boundary Assistant (Controlled Experiment)":
- Inputs: "Auto Stroke Prompts" with tiny point, box, and mask icons
- Middle: "SAM2 Instance Masks"
- Output arrow back to SegFormer-B2 labeled "Boundary / Pseudo-label Aid"
- Add a small red stop-rule tag: "Stop if no stable gain"
- Clearly make this a dashed auxiliary path, not the primary online model.

Layer 3 in the center-right, titled "Cloud Inference & Feedback":
- Input "New Character Image"
- Arrow to "SegFormer-B2"
- Arrow to "6 Probability Maps [H,W,6]"
- Arrow to "Independent Thresholds"
- Arrow to "Stroke Masks + Keypoints"
- Then a feedback dashboard with three simple cards: "Stroke Structure", "Writing Quality", "Explainable Feedback"
- Add a small dashed future card connected to the dashboard: "Style Condition: target_style_id + Reference Character" with examples "Zhao Mengfu", "Ouyang Xun", "Yan Zhenqing". Mark this clearly as "Future Extension".

Layer 4 on the far right, titled "Deployment Roadmap":
- Upper solid cloud block labeled "Cloud Teacher: SegFormer-B2 + SAM2 Aid"
- Lower dashed green block labeled "Edge Student (Future): SegFormer-B0 / MobileNetV3"
- A dashed arrow from cloud teacher to edge student labeled "Knowledge Distillation"
- Under edge student: "ONNX / INT8 / Low Latency"

At the bottom, add a narrow evaluation strip spanning the diagram:
"Fixed Split | U-Net vs SegFormer | Hard Cases | 3 Seeds | Reproducible Training"

Visual rules:
- The SegFormer-B2 teacher must be visually dominant.
- SAM2 must be visually secondary and dashed, showing it is an assistant rather than the final standalone model.
- The font/style and edge deployment parts must be dashed or tagged "Future Extension" so the figure truthfully distinguishes current work from planned work.
- Use arrows that make the full flow obvious: data -> offline training -> cloud inference -> feedback -> future edge deployment.
- Avoid small illegible paragraphs, random Chinese text, equations, fake data values, and unnecessary icons.
```

## 备选简短中文说明（用于 PPT 图注）

> 系统以 SegFormer-B2 为云端六通道多标签结构分割主干，SAM2 仅作为笔画实例边界辅助分支；模型输出五类方向笔画与关键点概率图，为结构化书写反馈提供依据，并预留目标书体条件化评价和端侧蒸馏部署路径。
