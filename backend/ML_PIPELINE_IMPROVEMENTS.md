# ML Pipeline Accuracy Improvements

Recommendations for improving action classification accuracy in the AI Surveillance backend.

**Context:** Dataset clips are roughly 3–5 seconds each. Observed failures include:

- Standing / normal behavior classified as `fall_floor`
- Punching classified as `shoot_gun`

**Legend:** ✅ = implemented in codebase · ⬜ = still open

---

## Current pipeline (summary)

| Piece | Current setup |
|--------|----------------|
| Model | Two-stream **X3D-M** (RGB + optical flow), fusion=`add` |
| Checkpoint | `suspicious_actions_6classes.pth` → **6 classes only** |
| Train classes | `normal`, `assault`, `fall_floor`, `run`, `shoot_gun`, `shoplift` |
| Dataset folders | **10** classes (also `hit`, `jump`, `kick`, `punch`) |
| Clips | ~3–5 s, 224×224; shared preprocess in `utils/video_preprocess.py` |
| Inference | Strided buffer (`CLIP_LEN=48`, `SAMPLE_STRIDE=4`) + **online Farneback flow** |
| Training script | `fine-tune/anomaly_detection_model.py` |
| Inference | `services/anomaly_predictor.py`, gates in `services/detection_gates.py` |

---

## Root causes of misclassifications

### 1. Optical flow used in training, zeroed at inference (critical) — ✅ fixed

~~At runtime the flow stream was filled with zeros.~~

**Done:** Inference computes real Farneback optical flow via `utils.video_preprocess.compute_optical_flow_clip` / `prepare_model_inputs` (same params as precompute).

---

### 2. `punch` is not a model class → collapses into `shoot_gun` — ⬜ open

Checkpoint classes:

```text
['normal', 'assault', 'fall_floor', 'run', 'shoot_gun', 'shoplift']
```

Dataset has `punch` / `hit` / `kick` (~120–130 train each), but they are **never trained**. Arm-extension / fighting motion is closest to `shoot_gun` or `assault` in feature space → punch becomes “shooting”.

**Mitigation in place:** ✅ weapon/pose gate can veto some false `shoot_gun` (extended-arm / YOLO knife|scissors proxies). Taxonomy merge/retrain still needed.

**Fix options (pick one taxonomy):**

- **A (recommended):** merge confusable fight classes, e.g. `violence = {assault, punch, hit, kick}`; keep `shoot_gun` only if guns are clearly distinct.
- **B:** retrain on **all 10** classes with enough balanced data and hard-negative mining between punch vs shoot_gun.
- **C:** two-stage: coarse (normal / fall / run / violence / theft / weapon), then fine classifier only when coarse says violence/weapon.

Do not keep 10 folders if the model only has 6 labels.

---

### 3. Severe train/val imbalance (and inverted val) — ⬜ open

Approximate counts:

| Class | Train | Val |
|--------|------:|----:|
| normal | 522 | **50** |
| fall_floor | 103 | 136 |
| run | 173 | 232 |
| shoot_gun | 93 | 103 |
| assault | 60 | 50 |
| shoplift | 54 | 58 |
| punch/hit/kick/jump | present | present (unused by 6-class model) |

**Fix:** stratified ~80/20 (or 70/15/15 train/val/test) **per class**, same ratio for normal; target **≥150–300** clips per rare class if possible; keep a held-out test set never used for training.

---

### 4. Train vs inference clip construction mismatch — ✅ fixed

Shared module `utils/video_preprocess.py`:

| Setting | Value |
|---------|------:|
| `CLIP_LEN` / `FRAME_WINDOW` | 48 |
| `SAMPLE_STRIDE` / `STRIDE` | 4 |
| `FRAME_SIZE` | 224×224 |
| RGB mean/std | 0.45 / 0.225 |
| Flow | Farneback (`FLOW_PARAMS`) |

Training RGB uses `read_video_strided_rgb`; serve buffers every `SAMPLE_STRIDE`-th frame and builds the same clip length. Re-run `fine-tune/precompute_flow.py` so `*_flow.npy` matches the new sampling (or train with `--online-flow`).

---

### 5. Person crop train/infer mismatch (when YOLO is on) — ⬜ open

With `useObjectDetection=True`, inference runs on **person crops**. Training mostly uses **full frames**.

**Fix:** train on person-centric crops (YOLO/tracker crop + margin). Extend `dataset_cropped/` beyond `normal` only.

---

### 6. Training loop does not select a good model — partially ✅

| Item | Status |
|------|--------|
| Validation metrics / confusion matrix | ✅ |
| Best checkpoint by val macro-F1 | ✅ (`suspicious_actions_best.pth`) |
| Early stopping on val loss plateau | ✅ patience=7, `--patience` / `--min-delta` |
| Gradient clipping (`max_grad_norm`) | ✅ |
| FocalLoss class weights (`alpha`) | ⬜ |
| Differential LRs | ⬜ |
| Stronger augmentation | ✅ |
| Matplotlib loss/F1 plots (flag) | ✅ `--plot` / `PLOT_METRICS=1` |

---

### Why specific errors happen

**Standing → fall_floor**

- ~~Flow stream broken at inference~~ ✅ fixed
- Few normal samples in val → still open
- ✅ Stricter display/alert thresholds for `fall_floor`
- ✅ MediaPipe pose gate vetoes upright torso for `fall_floor`

**Punch → shoot_gun**

- Punch not in label set → still open
- ✅ Weapon threat gate (pose arm extension + YOLO knife/scissors proxies) can veto weak `shoot_gun`

---

## Improvement plan (priority order)

### P0 — Fix pipeline correctness (biggest accuracy jump)

1. ✅ **Compute real optical flow at inference** (match `precompute_flow.py`), or retrain **RGB-only** and remove the flow branch.
2. ✅ **Align clip_len / sampling / normalize** between train and serve (`FRAME_WINDOW` must equal training `clip_len` under the same striding policy).
3. ⬜ **Decide the label taxonomy** and retrain so every real action you care about is a trained class (or merged).
4. ⬜ **Re-split dataset** stratified; rebuild train/val/test; stop using the inverted val set.

### P1 — Data quality (next biggest win for 3–5 s clips)

5. ⬜ **Clean labels:** manually audit `fall_floor` vs standing/sitting, `shoot_gun` vs punch/pointing, `assault` vs hit/punch. Remove multi-action clips or re-cut so the **labeled action occupies most of the clip**.
6. ⬜ **Balance:** oversample rare classes, undersample normal, or use **class-balanced sampling** + FocalLoss with `alpha` from inverse class frequency.
7. ⬜ **Hard negatives for normal:** standing, walking slowly, sitting down, bending, raising hand, phone use, pointing — labeled **normal** (these kill false falls/shoots).
8. ⬜ **Person crops for all classes** if YOLO is used in production.
9. ⬜ **Temporal crops:** for each 3–5 s video, sample random subwindows during training (start offset) so the model doesn’t memorize “action always starts at frame 0”.
10. ✅ Stronger aug: color jitter, scale/crop, temporal speed jitter, noise (in `apply_video_augmentations`).

### P2 — Training procedure

11. ✅ Log every epoch: val accuracy, **macro-F1**, **per-class recall/precision**, full **confusion matrix**.
12. ✅ Save **best val macro-F1** (or worst-class recall), not last epoch. → `suspicious_actions_best.pth`
12b. ✅ **Early stopping** when val_loss plateaus (`--patience`, default 7).
13. ⬜ Differential LRs: higher for classifier + flow stem, lower for pretrained RGB.
14. ✅ Apply gradient clipping; ⬜ consider label smoothing (0.05–0.1).
15. ⬜ Optional: freeze RGB for first N epochs, then unfreeze.

### P3 — Inference / product-level accuracy

16. ⬜ **Confidence + temporal consensus:** require class C for K of last N windows (e.g. 3/5) before alerting.
17. ✅ Raise thresholds for high-cost classes (`shoot_gun`, `fall_floor`); keep separate **alert threshold** vs **display threshold** (`sensitivity` / `alert_sensitivity`).
18. ⬜ If YOLO is on: **per-track** buffer (one buffer per person ID), not one global buffer shared across people.
19. ✅ Pose gate for fall: MediaPipe “torso near horizontal” veto for upright people (`services/detection_gates.py` → `FallPoseGate`). Flag: `ENABLE_FALL_POSE_GATE`.
20. ✅ For gun: second check when model says `shoot_gun` — YOLO weapon proxies (knife/scissors) + extended-arm pose (`WeaponThreatGate`). Flag: `ENABLE_WEAPON_THREAT_GATE`. (COCO has no firearm class; a dedicated weapon model can replace proxies later.)

### P4 — Model upgrades (only after P0–P2)

21. ⬜ Try **RGB-only X3D-M / X3D-S** first (simpler, often better if flow is poorly aligned).
22. ⬜ Or **VideoMAE / TimeSformer / UniFormer** fine-tune if more data becomes available.
23. ⬜ Skeleton-based action (pose sequence + ST-GCN / PoseC3D) is strong for fall vs stand and punch vs shoot when appearance is noisy.

---

## Suggested target taxonomy (pragmatic for surveillance)

```text
normal
fall
run
violence          # assault + punch + hit + kick
weapon_threat     # shoot_gun (only clear gun pose / weapon visible)
theft             # shoplift
```

Drop or disable `jump` unless it is a real alert class. Fewer, cleaner classes beat 10 noisy ones on a few hundred clips each.

---

## Minimum retrain checklist

```text
1. Fix labels + stratified split (train/val/test)                    ⬜
2. Either:
   a) online flow at inference matching training, OR                 ✅
   b) remove flow, retrain RGB-only
3. Same preprocess for train & serve (T, size, mean/std, stride)     ✅
4. Person-crop training if YOLO crops at infer                       ⬜
5. Class weights + balanced sampler + focal loss alpha               ⬜
6. Val confusion matrix; fix top confusions with hard negatives      ✅ (logging); ⬜ (data fixes)
7. Temporal voting + higher thresholds for fall/shoot                ⬜ voting; ✅ thresholds
8. Ship best-F1 checkpoint                                           ✅
```

---

## Quick wins (without full redesign)

| Change | Effect | Status |
|--------|--------|--------|
| Don’t zero flow at inference | Stops large train/serve gap | ✅ |
| Disable/merge `shoot_gun` until punch is labeled or merged | Stops punch→gun | ⬜ (+ partial gate) |
| Add many “standing still” normals; retrain | Cuts normal→fall | ⬜ |
| Raise `fall_floor` / `shoot_gun` sensitivity (higher threshold) | Fewer false positives now | ✅ |
| Per-person buffers + 3-frame majority vote | Stabilizes live stream | ⬜ |
| Confusion matrix on a real test set of your camera footage | Shows true weak pairs | ✅ (val each epoch) |

---

## How to use new training features

```bash
cd backend/fine-tune

# Recompute flow with aligned sampling (recommended after CLIP_LEN change)
python precompute_flow.py

# Train with epoch metrics; enable plots
python anomaly_detection_model.py --plot

# Or: env flag
set PLOT_METRICS=1
python anomaly_detection_model.py

# Match serve exactly (slower): compute flow online every sample
python anomaly_detection_model.py --online-flow --plot

# Early stopping (default): stop if val_loss does not improve for 7 epochs
python anomaly_detection_model.py --patience 7 --min-delta 1e-4

# Disable early stopping
python anomaly_detection_model.py --patience 0
```

Plots are written under `fine-tune/training_plots/` (`train_loss.png`, `train_f1.png`, …).

Disable plots: omit `--plot`, or pass `--no-plot`.

**Early stopping:** monitors **val_loss**. If it does not drop by at least `--min-delta` for `--patience` consecutive epochs, training stops. Best macro-F1 checkpoint (`suspicious_actions_best.pth`) is still kept separately.

---

## Thresholds (display vs alert)

- **Display** (`sensitivity`): on-screen label when confidence ≥ display threshold.
- **Alert** (`alert_sensitivity`): events/SMS when confidence ≥ alert threshold (always ≥ display).
- Mapping: `threshold = max(0.1, 0.9 - sensitivity * 0.7)` — **lower sensitivity ⇒ higher confidence bar**.

High-cost defaults (stricter than before):

| Action | sensitivity (display) | alert_sensitivity |
|--------|----------------------:|------------------:|
| fall_floor | 0.35 | 0.20 |
| shoot_gun | 0.30 | 0.15 |

Labels below alert but above display are shown in **orange**; alerts in **red**.

---

## Bottom line

Accuracy is limited less by “X3D isn’t good enough” and more by:

1. ~~**Training on flow, inferring with zeros**~~ ✅ fixed
2. **Predicting classes the model never learned** (`punch` → `shoot_gun`) ⬜
3. **Broken split / weak normal coverage** → standing → fall ⬜
4. ~~**Inconsistent temporal preprocessing**~~ ✅ fixed · **global buffer** when multi-person ⬜

Next highest ROI: taxonomy merge + stratified split + retrain with best-F1 checkpoint.

---

## Related files

| Path | Role |
|------|------|
| `utils/video_preprocess.py` | Shared CLIP_LEN, stride, normalize, Farneback flow |
| `utils/metrics.py` | Confusion matrix, precision/recall/F1 |
| `utils/plot_utils.py` | Training loss/F1/accuracy plots |
| `fine-tune/anomaly_detection_model.py` | Training + val metrics + aug + plots |
| `fine-tune/precompute_flow.py` | Offline optical flow (`*_flow.npy`) |
| `models/anomaly_model.py` | Loaded checkpoint + `predict()` |
| `services/anomaly_predictor.py` | Live/upload inference, dual thresholds |
| `services/detection_gates.py` | Fall pose gate + weapon threat gate |
| `core/config.py` | Classes, thresholds, gate flags, `FRAME_WINDOW`, `STRIDE` |
| `schemas/settings.py` | `alert_sensitivity` field |
| `action_recognizer.py` | Simple MediaPipe pose rules (stub) |
| `dataset/train/`, `dataset/val/` | Labeled video + flow pairs |
