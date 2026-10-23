from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session


def stamp(db: Session) -> datetime:
    """Метки внутри одного запроса идут строго по порядку, даже если часы грубые."""
    now = datetime.now(timezone.utc)
    previous = db.info.get("stamp")
    if previous is not None and now <= previous:
        now = previous + timedelta(microseconds=1)
    db.info["stamp"] = now
    return now
