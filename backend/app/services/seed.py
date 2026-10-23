from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password

DEMO_USERS = [
    ("client.good@demo.local", "Анна Белова", "+7 900 000-00-01", "CLIENT"),
    ("client.offer@demo.local", "Павел Орлов", "+7 900 000-00-02", "CLIENT"),
    ("client.reject@demo.local", "Мария Котова", "+7 900 000-00-03", "CLIENT"),
    ("client.info@demo.local", "Игорь Новиков", "+7 900 000-00-04", "CLIENT"),
    ("underwriter@demo.local", "Елена Крылова", "+7 900 000-00-05", "UNDERWRITER"),
]


def seed(db: Session) -> None:
    existing = set(db.scalars(select(User.email)).all())
    for email, name, phone, role in DEMO_USERS:
        if email in existing:
            continue
        db.add(
            User(
                email=email,
                password_hash=hash_password(settings.demo_password),
                full_name=name,
                phone=phone,
                role=role,
            )
        )
    db.flush()
