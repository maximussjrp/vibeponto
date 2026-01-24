# VibePonto Backend

API backend do sistema VibePonto desenvolvida com FastAPI.

## Tecnologias

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async)
- PostgreSQL + PostGIS
- Redis
- Celery

## Instalação

```bash
pip install -e .
```

## Executar

```bash
uvicorn app.main:app --reload
```

## API Docs

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
