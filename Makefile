COMPOSE_FILE := mlops/docker/docker-compose.yml
COMPOSE_DEV  := mlops/docker/docker-compose.override.yml
IMAGE        := rag-chatbot:latest
DOCS_DIR     ?= ./docs

.PHONY: build up up-dev down logs logs-app shell init-db load-docs test lint clean help

build:      ## Собрать Docker-образ
	docker build -t $(IMAGE) -f mlops/docker/Dockerfile .

up:         ## Запустить стек (dev, читает .env.prod из корня)
	docker compose -f $(COMPOSE_FILE) up -d

up-dev:     ## Запустить с монтированием src/ и hot-reload
	docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV) up -d

down:       ## Остановить стек
	docker compose -f $(COMPOSE_FILE) down

logs:       ## Логи всех сервисов (Ctrl+C для выхода)
	docker compose -f $(COMPOSE_FILE) logs -f

logs-app:   ## Логи только chatbot
	docker compose -f $(COMPOSE_FILE) logs -f chatbot

shell:      ## Открыть bash внутри контейнера chatbot
	docker compose -f $(COMPOSE_FILE) exec chatbot bash

init-db:    ## Создать таблицы LangGraph в Postgres (запускается внутри контейнера)
	docker compose -f $(COMPOSE_FILE) exec chatbot python3 scripts/init_db.py

load-docs:  ## Загрузить документы в ChromaDB (make load-docs DOCS_DIR=./docs)
	docker compose -f $(COMPOSE_FILE) exec chatbot python3 scripts/load_docs.py --dir $(DOCS_DIR)

test:       ## Запустить тесты (uv sync обязателен)
	uv run pytest tests/ -v

lint:       ## Проверить код через ruff
	uv run ruff check src/ scripts/ tests/

clean:      ## Удалить __pycache__, .ruff_cache, .pytest_cache
	find . -type d \( -name __pycache__ -o -name .ruff_cache -o -name .pytest_cache \) \
		-exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

help:       ## Показать эту справку
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
