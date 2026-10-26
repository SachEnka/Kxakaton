# Архитектурная схема

Модульный монолит: один backend (FastAPI), один frontend (React за nginx), PostgreSQL. Очереди сообщений и фонового воркера нет: после `submit` конвейер выполняется синхронно внутри запроса к API.

Внешние источники двух видов:

- **демо-ИНН** `7700000001`–`7700000005` и `7700000099` обслуживаются локальными фикстурами (`backend/app/mocks/fixtures.py`), сеть не нужна;
- **любой другой ИНН** запрашивается в открытых сервисах ФНС: поиск ЕГРЮЛ (egrul.nalog.ru) и «Прозрачный бизнес» (pb.nalog.ru). Для этого контейнеру `api` нужен выход в интернет. Кредитное бюро по ИНН не запрашивается.

LLM и платных API нет.

## Компоненты

```mermaid
flowchart TB
  subgraph Client["Клиентский кабинет"]
    W[Визард: цель → продукт → анкета]
    A[Страница заявки и решение]
  end

  subgraph Staff["Кабинет сотрудника"]
    Q[Очередь заявок]
    C[Дело: проверки, факторы, решение]
  end

  subgraph Web["web :8080"]
    FE[React SPA + nginx]
  end

  subgraph API["api :8000"]
    Auth[JWT, роли CLIENT / UNDERWRITER]
    Routes[Маршруты api/<br/>applications, registry, underwriter]
    Cabinet[services/cabinet.py<br/>действия клиента и сотрудника]
    Pipeline[services/pipeline.py<br/>проверка, источники, оценка, решение]
    Integr[integrations/ и mocks/<br/>ЕГРЮЛ, Прозрачный бизнес, фикстуры]
    Score[domain/scoring.py<br/>правила по мотивам 590-П]
    SM[domain/state_machine.py<br/>переходы и журнал]
  end

  Ext[(egrul.nalog.ru<br/>pb.nalog.ru)]
  DB[(PostgreSQL)]

  W --> FE
  A --> FE
  Q --> FE
  C --> FE
  FE -->|/api| Auth
  Auth --> Routes
  Routes --> Cabinet
  Cabinet --> Pipeline
  Pipeline --> Integr
  Integr -.->|только настоящие ИНН| Ext
  Pipeline --> Score
  Cabinet --> SM
  Pipeline --> SM
  Cabinet --> DB
  Pipeline --> DB
  SM --> DB
```

Пунктирная стрелка: обращение к внешним сервисам идёт только для ИНН вне списка демо-ИНН.

## Кредитный конвейер

Конвейер запускается при отправке заявки и при ответе клиента на уточнение.

```mermaid
flowchart TD
  Start[Клиент отправляет заявку] --> Val[Проверка полноты анкеты<br/>SUBMITTED → VALIDATING]
  Val -->|не хватает данных| Ni1[NEED_INFO<br/>вопрос клиенту]
  Val -->|анкета полная| Enr[Запрос источников<br/>ENRICHING]
  Enr -->|ошибка источника| Stuck[Остаётся в ENRICHING<br/>запись FAILED, сотруднику метка]
  Enr -->|ответ получен| Sc[Оценка<br/>SCORING → DECISION_READY]
  Sc -->|I–II| Ok[APPROVED]
  Sc -->|III| Ch[APPROVED_WITH_CHANGES]
  Sc -->|V или стоп-фактор| Rj[REJECTED]
  Sc -->|IV, данных не хватает| Ni2[NEED_INFO]
  Sc -->|IV, данных хватает| Wait[DECISION_READY<br/>ждёт сотрудника]
  Wait --> Desk[Сотрудник: подтвердить, изменить, запросить уточнение]
  Ni1 -->|клиент ответил| Val
  Ni2 -->|клиент ответил| Val
  Ok --> Res[Оформление и подписание в ЛК<br/>смоделировано]
  Ch --> Res
  Desk --> Res
```

Статусы и допустимые переходы — в [state-machine.md](state-machine.md). Категория IV с достаточными данными автоматически не решается: расчёт (встречное предложение или отказ) сохраняется, заявка остаётся в `DECISION_READY` с пометкой «Ждёт сотрудника», а статус меняет сотрудник.

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
| `db` | `postgres:16-alpine` | 5432 | Данные приложения, том `pgdata` |
| `api` | `./backend` (`python:3.12-slim`) | 8000 | Бизнес-логика, OpenAPI, `/health` |
| `web` | `./frontend` (`node:22-alpine` для сборки, `nginx:1.27-alpine` для раздачи) | 8080 | Оба кабинета |

При старте API ждёт базу до 30 секунд, применяет миграцию Alembic и выполняет идемпотентный seed демо-пользователей. `web` стартует после того, как `api` здоров. Переменные API: `DATABASE_URL`, `JWT_SECRET` (значения для показа заданы в `docker-compose.yml`).

## Границы модулей в коде

| Модуль | Путь | Ответственность |
|---|---|---|
| State machine | `backend/app/domain/state_machine.py` | Единственное место, где меняется статус заявки |
| Продукты | `backend/app/domain/products.yaml`, `products.py` | Коридоры сумм и сроков, ставки, подбор |
| Scoring / decision | `backend/app/domain/scoring.py` | Балл, категория, условия; без HTTP и БД |
| Pipeline | `backend/app/services/pipeline.py` | Проверка полноты, источники, оценка, решение |
| Действия кабинетов | `backend/app/services/cabinet.py` | Черновик, отправка, ответы, оформление, решения сотрудника |
| Представления | `backend/app/services/serialize.py` | Данные для клиента и для сотрудника |
| Интеграции | `backend/app/integrations/` | Поиск ЕГРЮЛ, «Прозрачный бизнес», выбор между фикстурой и открытым сервисом |
| Фикстуры | `backend/app/mocks/` | Локальные ответы для демо-ИНН |
| API | `backend/app/api/` | Маршруты клиента, реестра и сотрудника; авторизация в `app/api/__init__.py` и `security.py` |
| UI | `frontend/src/pages/` | Визард, заявка, очередь, дело |

Связанные артефакты: [state-machine.md](state-machine.md), [data-model.md](data-model.md), [openapi.json](openapi.json), [api.http](api.http).

## Известные ограничения архитектуры

- Конвейер синхронный: запрос `submit` держится, пока идёт обращение к внешним сервисам. Для демо-ИНН это мгновенно, для настоящих зависит от ФНС.
- Ошибка источника не переводит заявку в отдельный статус и не повторяется: она остаётся в `ENRICHING` (дефект P1).
- Права сотрудника на смену решения не привязаны к стадии конвейера (дефект P0). Оба описаны в [REQUIREMENTS_CHECKLIST.md](REQUIREMENTS_CHECKLIST.md).
- CORS открыт для всех источников, секреты демонстрационные: конфигурация рассчитана на локальный показ.
