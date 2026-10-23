# Архитектурная схема

Модульный монолит: один backend (FastAPI), один frontend (React), PostgreSQL. Внешние источники — локальные моки плюс опциональные открытые запросы к ФНС для не-демо ИНН. Очередь сообщений в MVP нет: конвейер после `submit` выполняется синхронно в API.

## Компоненты

```mermaid
flowchart TB
  subgraph Client["Клиентский кабинет"]
    W[Визард: цель → продукт → анкета]
    A[Карточка заявки и решение]
  end

  subgraph Staff["Кабинет сотрудника"]
    Q[Очередь заявок]
    C[Досье, проверки, override]
  end

  subgraph Web["web :8080"]
    FE[React SPA + nginx]
  end

  subgraph API["api :8000"]
    Auth[JWT auth / роли]
    AppSvc[Application Service<br/>черновик, валидация, статусы]
    Enrich[Enrichment Engine<br/>ЕГРЮЛ · БКИ · ФНС]
    Score[Scoring + Decision Engine<br/>правила по мотивам 590-П]
    SM[State machine + журнал событий]
  end

  DB[(PostgreSQL)]

  W --> FE
  A --> FE
  Q --> FE
  C --> FE
  FE -->|/api| Auth
  Auth --> AppSvc
  AppSvc --> Enrich
  Enrich --> Score
  AppSvc --> SM
  Score --> SM
  AppSvc --> DB
  Enrich --> DB
  Score --> DB
  SM --> DB
```

## Внутренний кредитный конвейер

```mermaid
flowchart TD
  Start[Клиент: выбор продукта → заполнение → отправка] --> App[Application Service<br/>сохранение, валидация, статусы]
  App --> Enrich[Enrichment Engine<br/>моки / открытые ФНС]
  Enrich --> Score[Scoring + Decision Engine<br/>риск, факторы, правила продукта]
  Score -->|I–II, III авто| Auto[Автоматическое решение<br/>одобрение / отказ / встречное предложение]
  Score -->|IV или ручной контроль| Desk[Кабинет сотрудника<br/>уточнение, confirm, override]
  Auto --> Result[Результат в ЛК<br/>история → принятие условий → демо-выдача]
  Desk --> Result
```

## Развёртывание

```mermaid
flowchart LR
  PC[Обычный ПК жюри] --> DC[docker compose up --build]
  DC --> DB2[db :5432]
  DC --> API2[api :8000<br/>миграции, seed, /docs]
  DC --> WEB2[web :8080]
  WEB2 -->|proxy /api| API2
  API2 --> DB2
```

| Сервис | Образ / сборка | Порт | Назначение |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | Заявки, события, проверки, скоринг |
| `api` | `./backend` | 8000 | Бизнес-логика, OpenAPI |
| `web` | `./frontend` → nginx | 8080 | Оба кабинета |

Переменные API: `DATABASE_URL`, `JWT_SECRET` (см. `docker-compose.yml`).

## Границы модулей в коде

| Модуль | Путь | Ответственность |
|---|---|---|
| State machine | `backend/app/domain/state_machine.py` | Единственное место смены статуса |
| Products | `backend/app/domain/products.yaml` | Коридоры сумм, сроков, ставки |
| Scoring / decision | `backend/app/domain/scoring.py` | Балл, категория, оффер; без HTTP и БД |
| Pipeline | `backend/app/services/pipeline.py` | validate → enrich → score → decide |
| Mocks / registry | `backend/app/mocks`, `integrations/` | ЕГРЮЛ, БКИ, «Прозрачный бизнес» |
| Cabinets API | `backend/app/api/` | Клиент и underwriter |
| UI | `frontend/src/pages/` | Визард, заявка, очередь, дело |

Связанные артефакты: [state-machine.md](state-machine.md), [data-model.md](data-model.md), [openapi.json](openapi.json), [api.http](api.http).
