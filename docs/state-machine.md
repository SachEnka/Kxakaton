# Состояния заявки

Менять статус может только модуль `backend/app/domain/state_machine.py`. Каждый переход пишет строку в `application_events`.

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SUBMITTED: клиент отправил
    SUBMITTED --> VALIDATING: система приняла
    VALIDATING --> NEED_INFO: анкета неполная
    VALIDATING --> ENRICHING: данных достаточно
    NEED_INFO --> VALIDATING: клиент ответил
    ENRICHING --> SCORING: моки ответили
    SCORING --> DECISION_READY: оценка посчитана
    DECISION_READY --> APPROVED: категории I–II
    DECISION_READY --> APPROVED_WITH_CHANGES: категория III
    DECISION_READY --> NEED_INFO: категории IV не хватает данных
    DECISION_READY --> REJECTED: категория V или стоп-фактор
    APPROVED --> CONTRACTING: клиент открыл оформление
    APPROVED_WITH_CHANGES --> CONTRACTING: клиент принял условия
    APPROVED_WITH_CHANGES --> CANCELLED: клиент отказался
    CONTRACTING --> ISSUED: клиент подписал
    REJECTED --> [*]
    ISSUED --> [*]
    CANCELLED --> [*]
```

Категория IV с уже собранными данными остаётся в `DECISION_READY`, пока сотрудник не подтвердит или не изменит решение.

Сотрудник из любого незавершённого статуса может перевести заявку в `NEED_INFO`, `APPROVED`, `APPROVED_WITH_CHANGES` или `REJECTED`. Комментарий обязателен, если решение меняется вручную.

`REJECTED`, `ISSUED` и `CANCELLED` — конечные статусы. Переход вроде `ISSUED → DRAFT` отклоняется.
