from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.clock import stamp

TERMINAL = {"REJECTED", "ISSUED", "CANCELLED"}

SYSTEM_EDGES = {
    ("SUBMITTED", "VALIDATING"),
    ("VALIDATING", "NEED_INFO"),
    ("VALIDATING", "ENRICHING"),
    ("ENRICHING", "SCORING"),
    ("SCORING", "DECISION_READY"),
    ("DECISION_READY", "APPROVED"),
    ("DECISION_READY", "APPROVED_WITH_CHANGES"),
    ("DECISION_READY", "NEED_INFO"),
    ("DECISION_READY", "REJECTED"),
}

CLIENT_EDGES = {
    ("DRAFT", "SUBMITTED"),
    ("NEED_INFO", "VALIDATING"),
    ("APPROVED", "CONTRACTING"),
    ("APPROVED_WITH_CHANGES", "CONTRACTING"),
    ("APPROVED_WITH_CHANGES", "CANCELLED"),
    ("CONTRACTING", "ISSUED"),
}

UNDERWRITER_TARGETS = {"NEED_INFO", "APPROVED", "APPROVED_WITH_CHANGES", "REJECTED"}


class TransitionError(Exception):
    pass


def ensure_transition(current: str, target: str, actor_type: str) -> None:
    if actor_type == "UNDERWRITER":
        if current in TERMINAL:
            raise TransitionError(f"Заявка в статусе {current} уже завершена")
        if target not in UNDERWRITER_TARGETS:
            raise TransitionError(f"Сотрудник не переводит заявку в {target}")
        if current == target:
            raise TransitionError("Статус не меняется")
        return
    edges = SYSTEM_EDGES if actor_type == "SYSTEM" else CLIENT_EDGES
    if (current, target) not in edges:
        raise TransitionError(f"Нельзя перейти из {current} в {target}")


@dataclass
class TransitionResult:
    from_status: str
    to_status: str


def transition(
    db: Session,
    application,
    target: str,
    *,
    actor_type: str,
    actor_user_id: UUID | None,
    message: str,
    payload: dict | None = None,
) -> TransitionResult:
    from app.models import ApplicationEvent

    ensure_transition(application.status, target, actor_type)
    previous = application.status
    moment = stamp(db)
    application.status = target
    application.updated_at = moment
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=previous,
            to_status=target,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            message=message,
            payload_json=payload or {},
            created_at=moment,
        )
    )
    db.flush()
    return TransitionResult(previous, target)


def log_event(
    db: Session,
    application,
    *,
    actor_type: str,
    actor_user_id: UUID | None,
    message: str,
    payload: dict | None = None,
) -> None:
    from app.models import ApplicationEvent

    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=application.status,
            to_status=application.status,
            actor_type=actor_type,
            actor_user_id=actor_user_id,
            message=message,
            payload_json=payload or {},
            created_at=stamp(db),
        )
    )
    db.flush()
