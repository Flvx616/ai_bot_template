# RagChatBot Template

Готовый к продакшену шаблон Telegram-бота на базе LangGraph RAG-агента с **YandexGPT**.
Скопируй, заполни `.env.prod` — и получи рабочего AI-ассистента с семантическим поиском, кешированием и полной наблюдаемостью.

---

## Архитектура

```
Telegram
    │
    ▼
[aiogram 3 bot]
    │  POST /api/v1/chat
    ▼
[FastAPI + middleware]
    │
    ▼
[LangGraph StateGraph]
  ┌──────────────────────────────────────────────────────────┐
  │  validate → decompose_question                           │
  │      └─► answer_parts_async  (параллельный RAG)          │
  │              └─► collect_final_answer                    │
  │                      └─► check_user_answer               │
  │                            ├─ DONE ─► validate_final_answer ─► update_history │
  │                            └─ AGAIN ─► generate_additional_questions ─► loop  │
  └──────────────────────────────────────────────────────────┘
        │
[Redis semantic cache]   [ChromaDB + BM25 rerank]
[Postgres checkpointer]  [Langfuse tracing]
```

**Ключевые возможности:**
- Telegram-бот на aiogram 3 из коробки
- Автоматическая декомпозиция вопроса на подвопросы
- Параллельный асинхронный RAG-поиск по каждому подвопросу
- Цикл самопроверки ответа (до 3 попыток, если ответ неполный)
- Семантический кеш в Redis для каждой ноды графа
- Ограничение частоты запросов по пользователю
- История диалога в Postgres (LangGraph checkpointer)
- Все промпты управляются через Langfuse (нет хардкода в коде)
- Структурированное JSON-логирование + метрики + аудит-трейл

---

## Технологический стек

| Компонент | Технология |
|---|---|
| Telegram-бот | aiogram 3 |
| LLM | YandexGPT (через OpenAI-совместимый API) |
| Граф агента | LangGraph `StateGraph` |
| Управление промптами | Langfuse |
| Векторная БД | ChromaDB |
| Эмбеддинги | Yandex Embeddings API |
| Кеш | Redis Stack (semantic cache через `langchain-redis`) |
| Хранение состояния | PostgreSQL (`AsyncPostgresSaver`) |
| API | FastAPI + Uvicorn |
| Логирование | loguru |

---

## Требования

- **Docker Desktop** (обязательно — все сервисы запускаются в контейнерах)
- Аккаунт **Yandex Cloud** с сервисным аккаунтом и API-ключом
- Аккаунт **Langfuse** (облачный или self-hosted)
- Telegram-бот, созданный через **@BotFather**

---

## Шаг 1 — Настройка Yandex Cloud

Все действия выполняются в [console.yandex.cloud](https://console.yandex.cloud). В AI Studio ничего делать не нужно.

### 1.1 Получить Folder ID
Открой консоль → выбери или создай **Каталог** → скопируй **ID каталога** (формат `b1g...`) из раздела "Обзор" или из URL.

### 1.2 Создать сервисный аккаунт
Каталог → **Сервисные аккаунты** → **Создать** → задай имя → добавь роль `ai.languageModels.user` → Создать.

### 1.3 Создать API-ключ
Открой созданный сервисный аккаунт → вкладка **API-ключи** → **Создать API-ключ**.

При создании ключа нужно выбрать **области действия** (scopes). Выбери обе:
- `yc.ai.languageModels.execute` — для YandexGPT
- `yc.ai.foundationModels.execute` — для Yandex Embeddings API

> **Важно:** Оба scope нужны! `foundationModels.execute` покрывает Embeddings API, без него загрузка документов и семантический поиск не работают.

Скопируй **Секретный ключ** — он показывается только один раз. Это значение `OPENAI_API_KEY`.

> **Важно:** `OPENAI_FOLDER_ID` должен совпадать с каталогом, в котором создан сервисный аккаунт. Если ID не совпадает — получишь ошибку `Specified folder ID does not match with service account folder ID`.

---

## Шаг 2 — Создание Telegram-бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь `/newbot`
3. Задай имя и username бота
4. Скопируй токен вида `1234567890:AAF...` — это значение `TELEGRAM_BOT_TOKEN`

---

## Шаг 3 — Настройка Langfuse

Langfuse хранит все промпты и трейсит вызовы LLM. Без него бот не запустится.

### Вариант А — Langfuse Cloud (проще)
1. Зарегистрируйся на [langfuse.com](https://langfuse.com)
2. Создай проект
3. Перейди в **Settings → API Keys** → скопируй **Secret Key** и **Public Key**
4. `LANGFUSE_HOST=https://cloud.langfuse.com`

### Вариант Б — Self-hosted (Docker)
```bash
git clone https://github.com/langfuse/langfuse.git
cd langfuse
docker compose up -d
```
Открой `http://localhost:3000` → создай проект → скопируй ключи.
`LANGFUSE_HOST=http://localhost:3000`

---

### Создание промптов в Langfuse

Перейди в проект → **Prompts** → **New Prompt**.

**Обязательные правила:**
- Имена промптов должны совпадать **точь-в-точь** (регистр важен)
- Переменные указываются в синтаксисе `{{имя_переменной}}`
- Вкладка должна быть **Text** (не Chat)
- Галочка **"Set the production label"** должна быть **включена** — бот читает только production-версию
- Config оставить пустым `{}`

Создай следующие 7 промптов:

---

#### `policy_validation`
Проверяет входящее сообщение и исходящий ответ на соответствие политике.
Код проверяет наличие слова `"да"` в ответе модели (регистронезависимо).

**Переменные:** `{{text}}`

```
Ты — помощник по модерации контента.
Оцени следующий текст: содержит ли он оскорбления, спам или явно неуместный контент?
Отвечай только "Да" (подходит) или "Нет" (не подходит).

Текст: {{text}}
```

> **Совет:** Если хочешь отключить валидацию — замени текст промпта на `Отвечай только "Да".`
> Не удаляй промпт совсем — это вызовет исключение и бот перестанет отвечать.

---

#### `decompose_question`
Разбивает сложный вопрос на простые подвопросы.

**Переменные:** `{{user_question}}`, `{{user_history}}`

```
Ты — полезный ассистент. Пользователь спросил: "{{user_question}}"

Контекст предыдущего диалога: {{user_history}}

Разбей этот вопрос на простые, независимые подвопросы.
Каждый подвопрос должен быть самодостаточным.

Верни результат строго в формате:
<ЗАДАЧИ>
<PART>Первый подвопрос?
<PART>Второй подвопрос?
<PART>Третий подвопрос?
</ЗАДАЧИ>
```

---

#### `topic_choose_router`
Определяет тему подвопроса для фильтрации в ChromaDB.
Возвращаемое слово должно совпадать с именем подпапки в `docs/`.

**Переменные:** `{{question}}`

```
Ты — классификатор тем. По вопросу ниже верни одно ключевое слово темы,
которое лучше всего описывает предметную область.
Используй только строчные буквы без пробелов.

Доступные темы соответствуют именам подпапок в директории документов ChromaDB
(например: "hr", "legal", "technical", "general").

Вопрос: {{question}}

Верни только ключевое слово темы, ничего больше.
```

---

#### `query_worker`
Отвечает на один подвопрос, используя RAG-контекст из ChromaDB.

**Переменные:** `{{text}}`, `{{rag}}`

```
Ты — полезный ассистент. Ответь на вопрос, используя предоставленный контекст.
Если контекст не содержит достаточной информации, честно скажи об этом.

Вопрос: {{text}}

Контекст из базы знаний:
{{rag}}

Дай чёткий и лаконичный ответ на основе контекста выше.
```

---

#### `summary_response`
Собирает финальный ответ из всех частичных ответов на подвопросы.

**Переменные:** `{{original_question}}`, `{{task_responses}}`, `{{user_history}}`, `{{model_answers}}`, `{{additional_info}}`

```
Ты — полезный ассистент. Объедини частичные ответы ниже в единый,
связный ответ на исходный вопрос пользователя.

Исходный вопрос: {{original_question}}

Частичные ответы:
{{task_responses}}

История диалога:
{{user_history}}

Предыдущие ответы модели:
{{model_answers}}

Дополнительный контекст из предыдущих попыток:
{{additional_info}}

Напиши чёткий, хорошо структурированный финальный ответ.
```

---

#### `check_user_answer`
Проверяет, достаточно ли полно ответ раскрывает вопрос.
Возвращает `DONE` или `AGAIN`.

**Переменные:** `{{question}}`, `{{parts}}`, `{{history_questions}}`, `{{answer}}`

```
Ты — эксперт по оценке качества ответов. Определи, полностью ли ответ раскрывает вопрос.

Вопрос: {{question}}
Подвопросы, которые задавались: {{parts}}
Предыдущие вопросы пользователя: {{history_questions}}

Оцениваемый ответ:
{{answer}}

Ответь только "DONE" если ответ достаточный, или "AGAIN" если нужно улучшение.
```

---

#### `generate_additional_questions`
Генерирует новые подвопросы если текущий ответ неполный.

**Переменные:** `{{question}}`, `{{history_questions}}`, `{{answer}}`, `{{parts}}`

```
Текущий ответ не полностью раскрыл вопрос пользователя.
Сгенерируй новые, отличающиеся подвопросы для поиска недостающей информации.

Исходный вопрос: {{question}}
Ранее заданные подвопросы: {{parts}}
История диалога: {{history_questions}}
Текущий недостаточный ответ: {{answer}}

Верни новые подвопросы строго в формате:
<ЗАДАЧИ>
<PART>Новый подвопрос 1?
<PART>Новый подвопрос 2?
</ЗАДАЧИ>
```

---

## Шаг 4 — Подготовка базы знаний

Документы хранятся в ChromaDB. Загрузчик читает `.docx`-файлы.
**Структура подпапок определяет темы** — имя подпапки первого уровня становится полем `topic` в метаданных и используется промптом `topic_choose_router`.

```
docs/
├── general/
│   └── intro.docx
├── hr/
│   └── onboarding.docx
└── technical/
    └── api_guide.docx
```

> Если документов нет — создай хотя бы один `.docx` файл в `docs/general/` с любым текстом. Без документов ChromaDB будет пустой и бот будет отвечать что информации недостаточно.

---

## Шаг 5 — Настройка окружения

```bash
cp .env.prod.example .env.prod
```

Заполни все значения `CHANGEME` в `.env.prod`:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `OPENAI_FOLDER_ID` | Folder ID каталога Yandex Cloud |
| `OPENAI_API_KEY` | API-ключ сервисного аккаунта |
| `COLLECTION_NAME` | Придумай имя коллекции ChromaDB |
| `PG_USER` | Придумай имя пользователя PostgreSQL |
| `PG_PASSWORD` | Придумай пароль PostgreSQL |
| `POSTGRES_DB` | Придумай имя базы данных |
| `LANGFUSE_SECRET_KEY` | `sk-lf-...` из настроек Langfuse |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-...` из настроек Langfuse |
| `LANGFUSE_HOST` | URL Langfuse |

---

## Шаг 6 — Сборка и запуск

> **На Windows:** `make` может не быть установлен. Используй прямые Docker-команды ниже.

### 6.1 Сборка образа

```powershell
docker build -t rag-chatbot:latest -f mlops/docker/Dockerfile .
```

### 6.2 Запуск всего стека

> **Важно:** Всегда используй флаг `--env-file .env.prod` — без него переменные окружения не подставляются в docker-compose.yml и PostgreSQL не запустится с нужными credentials.

```powershell
docker compose -f mlops/docker/docker-compose.yml --env-file .env.prod up -d
```

Это поднимает 5 контейнеров:
- `rag-chatbot` — FastAPI приложение (порт 32000)
- `rag-telegram-bot` — Telegram-бот на aiogram
- `rag-redis` — Redis Stack (с RediSearch для семантического кеша)
- `rag-chroma` — ChromaDB (векторная БД)
- `rag-postgres` — PostgreSQL (история диалогов)

### 6.3 Проверка

```powershell
curl http://localhost:32000/health
```

Ожидаемый ответ:
```json
{"status":"ok","services":{"postgres":true,"redis":true,"chromadb":true,"langfuse":true}}
```

---

## Шаг 7 — Инициализация базы данных (один раз)

LangGraph требует создания своих таблиц в Postgres. Выполняется **один раз** после первого запуска:

```powershell
docker compose -f mlops/docker/docker-compose.yml --env-file .env.prod exec chatbot python3 scripts/init_db.py
```

Ожидаемый вывод:
```
Connecting to Postgres: postgres:5432/... (user=...)
✓ LangGraph checkpoint tables created (or already exist).
```

---

## Шаг 8 — Загрузка документов

Папка `docs/` не монтируется в контейнер автоматически. Каждый раз после пересоздания контейнера нужно скопировать документы и запустить загрузку:

```powershell
# Скопировать папку docs в контейнер
docker cp docs rag-chatbot:/opt/app-root/docs

# Загрузить документы в ChromaDB
docker compose -f mlops/docker/docker-compose.yml --env-file .env.prod exec chatbot python3 scripts/load_docs.py --dir ./docs
```

Скрипт **идемпотентен** — повторный запуск обновляет только изменённые файлы (по MD5-хешу).

---

## Тестирование через curl (Windows PowerShell)

```powershell
curl -Method POST "http://localhost:32000/api/v1/chat" `
  -Headers @{
    "Content-Type"="application/json"
    "x-trace-id"="test-001"
    "x-request-time"="2026-01-01T00:00:00Z"
    "x-source-name"="test"
    "x-user-id"="user-001"
  } `
  -Body '{"text": "Привет!", "context": ""}'
```

---

## Справочник по API

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/health` | Проверка всех сервисов |
| `GET` | `/info` | Имя и версия сервиса |
| `POST` | `/api/v1/chat` | Основной чат-эндпоинт |
| `POST` | `/api/v1/test_invoke` | Прямой тест LLM |
| `GET` | `/like` | Записать положительную оценку |
| `GET` | `/dislike` | Записать отрицательную оценку |

### Обязательные заголовки

| Заголовок | Описание |
|---|---|
| `x-trace-id` | UUID запроса |
| `x-request-time` | Время запроса (ISO 8601) |
| `x-source-name` | Источник (`telegram`, `web`, `test`) |
| `x-user-id` | ID пользователя |

---

## Как создать нового бота на базе шаблона

1. Скопируй папку шаблона
2. Заполни `.env.prod` (все `CHANGEME`)
3. Создай 7 промптов в Langfuse, адаптируй под предметную область
4. Положи документы `.docx` в `docs/<тема>/`
5. Обнови `PROJECT_NAME` в `.env.prod` и `pyproject.toml`
6. Собери и запусти: `docker build` → `docker compose up -d`
7. Инициализируй БД: `init_db.py` (один раз)
8. Загрузи документы: `docker cp docs` + `load_docs.py`

---

## Известные проблемы и решения

### `make` не работает на Windows
`make` не входит в стандартную поставку Windows. Используй прямые docker-команды как показано в этом README. Или установи через Chocolatey (требует прав администратора):
```powershell
choco install make
```

### `unknown command 'FT._LIST'` при старте
Стандартный образ `redis:7-alpine` не включает модуль RediSearch, который нужен для семантического кеша. В проекте уже используется правильный образ `redis/redis-stack-server:latest` — не меняй его.

### `password authentication failed for user`
PostgreSQL кеширует учётные данные в volume при первом запуске. Если сменил пароль в `.env.prod` — нужно удалить volume и пересоздать:
```powershell
docker compose -f mlops/docker/docker-compose.yml --env-file .env.prod down -v
docker compose -f mlops/docker/docker-compose.yml --env-file .env.prod up -d
```

### `Specified folder ID does not match with service account folder ID`
`OPENAI_FOLDER_ID` в `.env.prod` не совпадает с каталогом где создан сервисный аккаунт. Зайди в Yandex Cloud Console, найди сервисный аккаунт и скопируй ID именно того каталога, в котором он находится.

### Бот отвечает "Your message does not match the expected topic"
Причины:
1. **Промпт `policy_validation` возвращает "нет"** — проверь что в Langfuse у промпта стоит метка `production` и текст промпта корректный
2. **Промпт был удалён** — пересоздай его. Удалённый промпт вызывает исключение, бот уходит в reject
3. **Закешированный отказ в Redis** — очисти кеш и перезапусти chatbot:
   ```powershell
   docker exec rag-redis redis-cli FLUSHALL
   docker restart rag-chatbot
   ```
   > После `FLUSHALL` обязательно перезапусти chatbot — иначе Redis Search индекс будет потерян и все запросы будут падать с ошибкой `No such index llmcache`.

### `Directory not found: ./docs` при load_docs
Папка `docs/` не монтируется автоматически. Нужно скопировать её в контейнер перед загрузкой:
```powershell
docker cp docs rag-chatbot:/opt/app-root/docs
```
Рабочая директория контейнера — `/opt/app-root`, а не `/app`.

### Порт 8000 уже занят
ChromaDB использует порт 8000. Если он занят другим контейнером — останови его перед запуском стека:
```powershell
docker ps   # найди контейнер занимающий 8000
docker stop <имя-контейнера>
```

### После `FLUSHALL` бот не отвечает (`No such index llmcache`)
Redis Search индекс создаётся при старте chatbot-контейнера. `FLUSHALL` удаляет его. Решение:
```powershell
docker restart rag-chatbot
```

---

## Структура проекта

```
.
├── src/
│   ├── service/                    # FastAPI приложение
│   │   ├── api/
│   │   │   ├── os_router.py        # /health, /info
│   │   │   ├── metric_router.py    # /like, /dislike
│   │   │   └── v1/
│   │   │       ├── router.py       # /api/v1/chat, /api/v1/test_invoke
│   │   │       └── schemas.py      # Pydantic-модели
│   │   ├── context.py              # DI-контейнер (APP_CTX)
│   │   └── config.py               # Настройки из env
│   ├── agents/
│   │   └── rag_agent/              # LangGraph агент
│   │       ├── nodes/              # validate / decompose / answer / loop
│   │       ├── workflow/base.py    # Сборка StateGraph
│   │       └── states/             # AgentState + AgentStatus
│   ├── modules/
│   │   ├── chroma_ext/             # ChromaDB + эмбеддинги + BM25
│   │   ├── redis_ext/              # Семантический кеш + rate limiter
│   │   ├── postgres_ext/           # Async пул + LangGraph checkpointer
│   │   └── langfuse_ext/           # Клиент Langfuse + callback
│   └── telegram_bot/
│       └── bot.py                  # Telegram-бот на aiogram 3
├── scripts/
│   ├── init_db.py                  # Создать таблицы LangGraph (1 раз)
│   └── load_docs.py                # Загрузить .docx в ChromaDB
├── docs/                           # Сюда кладёшь свои .docx файлы
│   └── general/
├── tests/
├── mlops/
│   └── docker/
│       ├── Dockerfile              # Образ основного приложения
│       ├── Dockerfile.telegram     # Образ Telegram-бота
│       ├── docker-compose.yml      # Весь стек
│       └── docker-compose.override.yml  # Dev hot-reload
├── .env.prod.example               # Шаблон — скопируй в .env.prod
├── Makefile
└── pyproject.toml
```

---

## Лицензия

MIT
