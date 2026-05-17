FROM python:3.12-slim AS base

USER root

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    APP_ROOT=/opt/app-root \
    HOME=/opt/app-root \
    PYTHONFAULTHANDLER=1 \
    PYTHONIOENCODING=UTF-8 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    UV_VENV=/opt/app-root/.venv

RUN apt-get update && apt-get install -y \
        curl ca-certificates build-essential libpq-dev \
    && pip install --no-cache-dir uv \
    && rm -rf /var/lib/apt/lists/*


################################################################################
# Builder — устанавливает зависимости и собирает пакет
################################################################################
FROM base AS builder

WORKDIR /opt/app-root

# Сначала копируем только pyproject.toml чтобы кешировать слой зависимостей
COPY pyproject.toml ./

# Создаём venv и генерируем lock-файл прямо в образе (нет uv.lock в репозитории)
RUN uv venv --seed --python 3.12 "$UV_VENV"
ENV PATH="$UV_VENV/bin:$PATH"
RUN uv lock && uv sync --no-python-downloads --no-dev

# Копируем исходники и устанавливаем пакет в режиме wheel
COPY src/ ./src/
RUN uv build && pip install --no-deps dist/*.whl


################################################################################
# Final — минимальный runtime-образ
################################################################################
FROM python:3.12-slim AS final

USER root
WORKDIR /opt/app-root

ENV APP_ROOT=/opt/app-root \
    UV_VENV=/opt/app-root/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Только runtime-библиотека psycopg (без dev-заголовков)
RUN apt-get update && apt-get install -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Переносим venv и исходники из builder
COPY --from=builder /opt/app-root/.venv /opt/app-root/.venv
COPY --from=builder /opt/app-root/src   /opt/app-root/src

# Скрипты обслуживания (init_db.py, load_docs.py)
COPY scripts/ ./scripts/

ENV PATH="/opt/app-root/.venv/bin:$PATH"

# Директория для лог-файлов
RUN mkdir -p /opt/app-root/logs \
    && groupadd -g 1001 appuser \
    && useradd  -u 1001 -g appuser -d /opt/app-root -s /bin/bash appuser \
    && chown -R 1001:1001 /opt/app-root

USER 1001

EXPOSE 32000

ENTRYPOINT ["python3", "src/service/__main__.py"]
