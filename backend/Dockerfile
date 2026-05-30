# Mini-WFM backend — imagem de produção.
# Build com uv (deps congeladas pelo uv.lock), runtime com gunicorn.
# Roda a partir do código-fonte (não instala o projeto como pacote): o
# working dir /app fica no sys.path, então `app:create_app` e as migrations
# (`app.*`) importam direto.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# Binário do uv direto da imagem oficial (sem pip install).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Camada de dependências (cacheável): instala SÓ as deps de runtime,
# sem o projeto e sem o grupo dev.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Código da aplicação (app/, migrations/, alembic.ini).
COPY . .

EXPOSE 8080

# 2 workers sync bastam pra carga da demo; timeout folgado pro FOR UPDATE.
# Factory pattern do Flask: gunicorn chama create_app().
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "app:create_app()"]
