"""initial schema"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inn", sa.String(12)),
        sa.Column("ogrn", sa.String(15)),
        sa.Column("name", sa.String(500)),
        sa.Column("legal_form", sa.String(8)),
        sa.Column("okved", sa.String(16)),
        sa.Column("registration_date", sa.Date()),
        sa.Column("director_name", sa.String(255)),
        sa.Column("address", sa.String(500)),
        sa.Column("registry_status", sa.String(32)),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("public_number", sa.String(16), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("product_code", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("monthly_revenue", sa.Numeric(14, 2)),
        sa.Column("monthly_expenses", sa.Numeric(14, 2)),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_applications_public_number", "applications", ["public_number"], unique=True)
    op.create_index("ix_applications_status", "applications", ["status"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("from_status", sa.String(32)),
        sa.Column("to_status", sa.String(32), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid()),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "external_checks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("request_json", postgresql.JSONB(), nullable=False),
        sa.Column("response_json", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "score_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("financial_position", sa.String(16), nullable=False),
        sa.Column("debt_service", sa.String(16), nullable=False),
        sa.Column("quality_category", sa.String(4), nullable=False),
        sa.Column("stop_factors_json", postgresql.JSONB(), nullable=False),
        sa.Column("factors_json", postgresql.JSONB(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("offered_amount", sa.Numeric(14, 2)),
        sa.Column("offered_term_months", sa.Integer()),
        sa.Column("offered_rate", sa.Numeric(6, 2)),
        sa.Column("monthly_payment", sa.Numeric(14, 2)),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("client_explanation", sa.Text(), nullable=False),
        sa.Column("awaits_employee", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "info_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("asked_by", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("terms_json", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for name in (
        "contracts",
        "info_requests",
        "score_results",
        "external_checks",
        "application_events",
        "applications",
        "companies",
        "users",
    ):
        op.drop_table(name)
