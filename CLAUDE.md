# RagChatBot — контекст для Claude Code

## Стек

Python 3.12 · FastAPI · LangGraph · YandexGPT · ChromaDB · Redis · PostgreSQL · Langfuse · uv · Docker

## Структура

```
src/
  service/
    api/
      os_router.py       # GET /health, /info
      metric_router.py   # GET /like, /dislike
      v1/router.py       # POST /api/v1/chat, /api/v1/test_invoke
      v1/schemas.py      # Pydantic-модели запросов/ответов
    config.py            # Все настройки через pydantic-settings (из env)
    context.py           # AppContext Singleton — DI-контейнер, APP_CTX
  agents/
    rag_agent/
      nodes/core.py      # RagAgent — decompose/answer/collect ноды
      nodes/base.py      # validate, reject, update_history
      nodes/loop.py      # ThinkTwiceNodes — check_answer, gen_questions
      workflow/base.py   # build_builder() — собирает StateGraph
      states/base.py     # AgentState TypedDict
      states/status.py   # AgentStatus enum (ACTIVE/AGAIN/DONE)
  modules/
    chroma_ext/          # ChromaAdapter (semantic search + BM25 rerank)
    redis_ext/           # RedisAdapter (semantic cache) + UserRateLimiter
    postgres_ext/        # PostgresClient (async pool + LangGraph checkpointer)
    langfuse_ext/        # LangfuseClient (prompts + tracing)
scripts/
  init_db.py             # Инициализация таблиц LangGraph в Postgres
  load_docs.py           # Загрузка .docx в ChromaDB
tests/
  conftest.py            # Фикстуры (моки APP_CTX startup)
  test_api.py            # Тесты эндпоинтов
mlops/docker/
  Dockerfile             # Multi-stage: builder (uv) + final (slim)
  docker-compose.yml     # Локальная разработка
  docker-compose-prod.yml# Продакшн (nginx + Docker Secrets)
  docker-compose.override.yml  # Dev hot-reload (make up-dev)
mlops/nginx/             # nginx конфиги (HTTPS + proxy)
```

## Конвенции

- Все настройки — через env vars, определены в `src/service/config.py` (`pydantic-settings`)
- Все промпты хранятся в **Langfuse** (не в коде), имена промптов — в нодах агента
- Логирование через `loguru` — JSON-формат, через `APP_CTX.logger`
- Зависимости — через `uv` (`pyproject.toml`), без `requirements.txt`
- Форматтер — `ruff` (`make lint`)

## Как создать нового бота на базе шаблона

1. Переименовать в `pyproject.toml`: `name`, `description`
2. Обновить `COLLECTION_NAME` в `.env`
3. Загрузить документы: `make load-docs DOCS_DIR=./docs`
4. Создать промпты в Langfuse (7 промптов, см. README)
5. Адаптировать промпты под предметную область
6. Обновить `distribution("RagChatBot")` в `os_router.py` на новое имя

## Ключевые файлы при добавлении фич

| Задача | Файлы |
|---|---|
| Новый API-эндпоинт | `src/service/api/v1/router.py`, `schemas.py` |
| Изменить логику агента | `src/agents/rag_agent/nodes/core.py` |
| Новая нода в граф | `nodes/`, `workflow/base.py` |
| Новый env var | `src/service/config.py` + `.env.example` + `.env.prod.example` |
| Новый промпт | Langfuse UI + соответствующая нода |

## Запуск

```bash
make up        # поднять Docker-стек
make init-db   # создать таблицы (первый запуск)
make logs-app  # смотреть логи
make test      # запустить тесты
make up-dev    # dev-режим с hot-reload (mount src/)
```
