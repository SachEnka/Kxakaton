import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32), default="")
    role: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    companies: Mapped[list["Company"]] = relationship(back_populates="owner")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    ogrn: Mapped[str | None] = mapped_column(String(15), nullable=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(8), nullable=True)
    okved: Mapped[str | None] = mapped_column(String(16), nullable=True)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    director_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registry_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    owner: Mapped[User] = relationship(back_populates="companies")
    applications: Mapped[list["Application"]] = relationship(back_populates="company")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    public_number: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id"))
    product_code: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int]
    monthly_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    monthly_expenses: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[Company] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application", order_by="ApplicationEvent.created_at")
    checks: Mapped[list["ExternalCheck"]] = relationship(back_populates="application", order_by="ExternalCheck.created_at")
    scores: Mapped[list["ScoreResult"]] = relationship(back_populates="application", order_by="ScoreResult.created_at")
    info_requests: Mapped[list["InfoRequest"]] = relationship(back_populates="application", order_by="InfoRequest.created_at")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="application")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32))
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="events")


class ExternalCheck(Base):
    __tablename__ = "external_checks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    source: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    request_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    response_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="checks")


class ScoreResult(Base):
    __tablename__ = "score_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    score: Mapped[int]
    financial_position: Mapped[str] = mapped_column(String(16))
    debt_service: Mapped[str] = mapped_column(String(16))
    quality_category: Mapped[str] = mapped_column(String(4))
    stop_factors_json: Mapped[list] = mapped_column(JSONB, default=list)
    factors_json: Mapped[list] = mapped_column(JSONB, default=list)
    decision: Mapped[str] = mapped_column(String(32))
    offered_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    offered_term_months: Mapped[int | None] = mapped_column(nullable=True)
    offered_rate: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    explanation: Mapped[str] = mapped_column(Text, default="")
    client_explanation: Mapped[str] = mapped_column(Text, default="")
    awaits_employee: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    application: Mapped[Application] = relationship(back_populates="scores")


class InfoRequest(Base):
    __tablename__ = "info_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    asked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped[Application] = relationship(back_populates="info_requests")


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    terms_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped[Application] = relationship(back_populates="contracts")
