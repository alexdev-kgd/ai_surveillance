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

Copy `backend/.env.example` to `backend/.env`. Generate a secret with
`python -c "import secrets; print(secrets.token_urlsafe(48))"` and put it in
`SECRET_KEY`. The backend refuses to start with a missing or short key (minimum
32 bytes). Keep the same secret across workers and restarts; changing it invalidates
existing tokens. Do not commit it.

Set `CORS_ORIGINS` to comma-separated exact frontend origins (scheme, host and
port, without a trailing slash). The example permits the two local Vite origins;
replace them with the deployed frontend origin in production. An empty value
disables cross-origin browser access. Wildcards are rejected.

```
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Email notifications (Gmail SMTP)

Copy `backend/.env.example` to `backend/.env` and set these values:

- `SMTP_HOST` - `smtp.gmail.com`
- `SMTP_PORT` - `465` (SSL)
- `SMTP_USER` - the Gmail address used to sign in
- `SMTP_PASSWORD` - a Google App Password, not the ordinary account password
- `EMAIL_FROM` - same Gmail address as `SMTP_USER` (or an allowed alias)
- `EMAIL_FROM_NAME` - display name in the `From` header, for example `Видеонаблюдение магазина`
- `EMAIL_TO` - notification recipient

Create an App Password at https://myaccount.google.com/apppasswords (2-Step Verification must be enabled). The local `.env` file is ignored by Git. Do not commit the App Password.

To send a real test message from `backend` with the venv active:

```
python send_test_email.py
```

On success the script prints `[MAIL] Notification sent to ... via SMTP` and exits with code 0. On a bad password it prints `[MAIL ERROR] SMTP authentication failed: ...` and exits with code 1. The main detection loop keeps running if mail fails.

### SMS notifications (SMS Aero)

Set these values in `backend/.env`:

- `SMSAERO_EMAIL` - login email from the SMS Aero cabinet
- `SMSAERO_API_KEY` - API key from https://smsaero.ru/cabinet/settings/apikey/
- `SMSAERO_PHONE` - recipient number in international digits, for example `79506781834`
- `SMSAERO_SIGN` - sender name (default `SMS Aero`)

`SMSAERO_TEST_MODE=true` uses the `sms/testsend` endpoint and does not deliver a real message. Do not commit the API key.

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

- `--no-plot` - disable plots even if `PLOT_METRICS=1`
- `--epochs N` - override default epoch count (default 40)
- `--fusion add|concat` - two-stream fusion mode
- `--patience N` - early-stop after N epochs without val_loss improvement (default 7; `0` disables)
- `--min-delta X` - minimum val_loss drop to count as improvement (default `1e-4`)
- `--weight-decay X` - AdamW L2 (default `5e-3`)
- `--dropout X` - classifier dropout (default `0.65`)
- `--label-smoothing X` - CE label smoothing (default `0.1`)
- `--backbone-lr` / `--head-lr` - differential LRs (defaults `1e-5` / `1e-4`)
- `--no-class-weights` - disable inverse-frequency FocalLoss alpha

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
