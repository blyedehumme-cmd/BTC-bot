# Lesly Backend

FastAPI API for the Lesly paper-trading dashboard. Signal logic lives in `../btc_bot.py`.

## Quick start

```bash
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Tests

```bash
pip install -r requirements.txt
pytest
```

## Deployment

See [../DEPLOYMENT.md](../DEPLOYMENT.md).
