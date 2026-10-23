# Материалы для сдачи (Альфа Хак 2026)

## Репозиторий

- URL: https://github.com/SachEnka/Kxakaton
- Ветка: `main`
- Видимость: **public** — жюри открывает репозиторий по ссылке без приглашения
- Аккаунт жюри из ТЗ: `alfa-hack-2026` — для публичного репо отдельный invite не обязателен; если репозиторий сделают private, добавьте collaborator с правом `pull`

## Идентификатор версии

После каждого пуша на `main` актуальный commit:

```text
git rev-parse HEAD
```

или последний коммит: https://github.com/SachEnka/Kxakaton/commits/main

**Commit hash:** `1bc03c07c5d178f2ec8b012298cf9e3bf13c3ca6`  
(пакет сдачи: схема + README + этот файл; следующий коммит может только уточнять hash)

## Как жюри запускает

1. Клонировать репозиторий.
2. Установить Docker Desktop.
3. В корне: `docker compose up --build` или двойной клик `start.bat` (Windows).
4. Открыть http://localhost:8080  
   Swagger: http://localhost:8000/docs

Отдельные Python/Node на машине не нужны.

## Облачная демонстрация

Кейс требует локальный Docker; публикация в облаке — **дополнительно**.

Проверяемая версия полностью автономна локально. Для удалённого показа допустим любой VPS/VM с Docker:

```text
git clone https://github.com/SachEnka/Kxakaton.git
cd Kxakaton
docker compose up --build -d
```

Порты `8080` и `8000` пробросить наружу и открыть в файрволе. Платные API и закрытые LLM не используются.

**Cloud URL:** не развёрнуто; основной способ проверки — локальный Docker.

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
