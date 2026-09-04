# AI Surveillance

## Before starting

```
cd backend
.\venv\Scripts\activate
```

## Frontend Startup

```
cd frontend
npm run dev
```

## Backend Startup

```
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Model Training

From `backend` (with venv activated):

```
cd backend\fine-tune

# Split long normal videos into fixed-length clips (~5 s @ 30 fps, 224x224)
# Default: reads ../dataset/train/normal -> writes ../dataset_cropped/train_full_frame/normal
# Edit SOURCE_DIR / OUTPUT_DIR in the script if your paths differ.
python preprocess_normal_videos.py

# Recompute optical flow with train/serve-aligned sampling (recommended after preprocess changes)
python precompute_flow.py

# Train with per-epoch metrics; save loss/F1 plots under fine-tune/training_plots/
python anomaly_detection_model.py --plot

# Optional: compute flow on the fly every sample (matches serve exactly; slower)
python anomaly_detection_model.py --online-flow --plot

# Early stopping (default): stop if val_loss does not improve for 7 epochs
python anomaly_detection_model.py --patience 7 --min-delta 1e-4 --plot

# Disable early stopping
python anomaly_detection_model.py --patience 0

# Stronger regularization defaults are on (weight decay, dropout, label smoothing, class weights)
# Override if needed:
python anomaly_detection_model.py --plot --weight-decay 1e-2 --dropout 0.7 --label-smoothing 0.1
```

Other useful flags:

- `--no-plot` — disable plots even if `PLOT_METRICS=1`
- `--epochs N` — override default epoch count (default 40)
- `--fusion add|concat` — two-stream fusion mode
- `--patience N` — early-stop after N epochs without val_loss improvement (default 7; `0` disables)
- `--min-delta X` — minimum val_loss drop to count as improvement (default `1e-4`)
- `--weight-decay X` — AdamW L2 (default `5e-3`)
- `--dropout X` — classifier dropout (default `0.65`)
- `--label-smoothing X` — CE label smoothing (default `0.1`)
- `--backbone-lr` / `--head-lr` — differential LRs (defaults `1e-5` / `1e-4`)
- `--no-class-weights` — disable inverse-frequency FocalLoss alpha

### Train / val split

Use a **stratified** split **per class** so every action has the same train:val ratio (including `normal`):

- **Recommended:** about **80% train / 20% val**
- **With a held-out test set:** about **70% train / 15% val / 15% test** (test is never used for training or early stopping)

Val clips should match train clip length and construction (short action clips, not long full videos as single samples). Avoid inverted splits (e.g. more val than train for rare classes). Details: `backend/ML_PIPELINE_IMPROVEMENTS.md`.

### Checkpoints & early stopping

- **Best val macro-F1** → `backend/suspicious_actions_best.pth` (updated whenever F1 improves)
- **Last completed epoch** → `backend/suspicious_actions.pth` (written when training finishes or stops early)
- **Early stopping** monitors **validation loss**. If it does not decrease by at least `--min-delta` for `--patience` consecutive epochs, training stops. The best-F1 checkpoint is kept separately from the last-epoch weights.

Per-epoch logs include train/val loss, accuracy, macro-F1, per-class precision/recall/F1, and a confusion matrix. More pipeline notes: `backend/ML_PIPELINE_IMPROVEMENTS.md`.

## Database Initialization

```
cd backend
python -m core.init_db
```

## Test Accounts:

ADMIN:
login: admin
pass: 1234

OPERATOR:
login: operator
pass: 1234
