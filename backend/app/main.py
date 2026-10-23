import time
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.api import router as auth_router
from app.api.applications import router as applications_router
from app.api.registry import router as registry_router
from app.api.underwriter import router as underwriter_router
from app.db import SessionLocal, engine
from app.services.seed import seed


def _upgrade() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    last_error: Exception | None = None
    for _ in range(30):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            last_error = None
            break
        except OperationalError as exc:
            last_error = exc
            time.sleep(1)
    if last_error is not None:
        raise last_error
    _upgrade()
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="Умный кредитный кабинет",
    version="1.0.0",
    summary="Прототип кредитного конвейера для малого и микробизнеса",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(registry_router, prefix="/api")
app.include_router(underwriter_router, prefix="/api")


@app.get("/health", tags=["service"])
def health() -> dict:
    return {"status": "ok"}
