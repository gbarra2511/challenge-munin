# backend/

Backend Flask 3 + SQLAlchemy 2 + Postgres 15. Gerenciado com `uv`.

## Rodar local

```bash
# 1. Subir Postgres
docker compose up -d  # da raiz do repo

# 2. Configurar env
cp .env.example .env

# 3. Instalar deps
uv sync

# 4. Rodar migrações
uv run alembic upgrade head

# 5. Subir app (quando houver rota)
uv run flask --app app.api:create_app run --debug
```

## Comandos úteis

```bash
uv run pytest -v                          # testes
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run alembic revision --autogenerate -m "msg"   # nova migração
uv run alembic upgrade head               # aplicar migrações
uv run alembic downgrade -1               # reverter última
```

## Camadas (ver `../PLANO.md` §3)

```
app/
├── api/            # blueprints Flask (parsing/serialização)
├── services/       # casos de uso
├── domain/         # entidades, value objects, state machines puras
├── repositories/   # acesso a dados (SQLAlchemy)
├── infra/          # JWT, hashing, email, clock, settings
└── models.py       # tabelas SQLAlchemy
```
