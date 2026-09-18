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

## Migrations

O schema agora e controlado por Alembic.

Banco novo:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db alembic upgrade head
alembic current
```

Banco legado criado por `create_all()` antes das migrations:

1. compare o schema existente com os models/migration;
2. corrija divergencias manualmente se houver;
3. somente depois execute `alembic stamp head`.

Nao execute `stamp` automaticamente em producao. `create_all()` permanece apenas para desenvolvimento local.

## API Docs

- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
