# Материалы для сдачи (Альфа Хак 2026)

## Репозиторий

- URL: https://github.com/SachEnka/Kxakaton
- Ветка: `main`
- Видимость: **public** — жюри открывает репозиторий по ссылке без приглашения
- Аккаунт жюри из ТЗ: `alfa-hack-2026` — для публичного репо отдельный invite не обязателен; если репозиторий сделают private, добавьте collaborator с правом `pull` в настройках GitHub

## Идентификатор версии

Актуальный tip ветки `main` (однозначный идентификатор на момент проверки):

https://github.com/SachEnka/Kxakaton/commits/main

Локально:

```text
git rev-parse origin/main
```

**Commit hash пакета сдачи (архитектура + README + этот файл):** `aeb6a68c33229df355838687248e11857eb4f4b3`  
Последующие коммиты на `main` только уточняют hash/кодировку; для дедлайна указывайте **последний commit на `main`**.

## Как жюри запускает

1. Клонировать репозиторий.
2. Установить Docker Desktop.
3. В корне: `docker compose up --build` или двойной клик `start.bat` (Windows).
4. Открыть http://localhost:8080  
   Swagger: http://localhost:8000/docs

Отдельные Python/Node на машине не нужны.

## Облачная демонстрация

Кейс требует локальный Docker; публикация в облаке — **дополнительно**.

Проверяемая версия полностью автономна локально. Для удалённого показа — любой VPS/VM с Docker:

```text
git clone https://github.com/SachEnka/Kxakaton.git
cd Kxakaton
docker compose up --build -d
```

Порты `8080` и `8000` пробросить наружу. Платные API и закрытые LLM не используются.

**Cloud URL:** не развёрнуто; основной способ проверки — локальный Docker (как в ТЗ).

## Чеклист артефактов кейса

| Артефакт | Где |
|---|---|
| Архитектурная схема | [architecture.md](architecture.md) |
| Диаграмма состояний | [state-machine.md](state-machine.md) |
| Модель данных | [data-model.md](data-model.md) |
| OpenAPI | http://localhost:8000/openapi.json · [openapi.json](openapi.json) |
| Коллекция запросов | [api.http](api.http) |
| Тестовые сценарии | [test-scenarios.md](test-scenarios.md) |
| THIRD_PARTY_NOTICES | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |
| README / запуск | [../README.md](../README.md) |
