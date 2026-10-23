from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)
    phone: str = ""


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    phone: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RecommendIn(BaseModel):
    purpose: Literal["TURNOVER", "DEVELOPMENT", "CASH_GAP", "UNKNOWN"]
    amount: Decimal = Field(gt=0)
    term_months: int = Field(ge=1, le=120)


class DraftIn(BaseModel):
    purpose: Literal["TURNOVER", "DEVELOPMENT", "CASH_GAP", "UNKNOWN"]
    product_code: str
    amount: Decimal = Field(gt=0)
    term_months: int = Field(ge=1, le=120)


class DraftPatch(BaseModel):
    inn: str | None = None
    legal_form: Literal["OOO", "IP"] | None = None
    company_name: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, ge=1, le=120)
    purpose: Literal["TURNOVER", "DEVELOPMENT", "CASH_GAP", "UNKNOWN"] | None = None
    product_code: str | None = None
    monthly_revenue: Decimal | None = Field(default=None, ge=0)
    monthly_expenses: Decimal | None = Field(default=None, ge=0)
    comment: str | None = None


class AnswerIn(BaseModel):
    answer: str = Field(min_length=2)
    monthly_revenue: Decimal | None = Field(default=None, ge=0)


class OverrideIn(BaseModel):
    decision: Literal["APPROVED", "APPROVED_WITH_CHANGES", "REJECTED"]
    comment: str = Field(min_length=3)
    amount: Decimal | None = Field(default=None, gt=0)
    term_months: int | None = Field(default=None, ge=1, le=120)
    rate: Decimal | None = Field(default=None, gt=0, le=100)


class QuestionIn(BaseModel):
    question: str = Field(min_length=3)
