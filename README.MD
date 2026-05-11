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

```
cd backend\fine-tune
python anomaly_detection_model.py
```

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
