from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
import pytest

from app.db import engine
from app.main import app


@pytest.fixture(scope="module")
def client():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("PostgreSQL недоступен")
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": "Demo-2026"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _submit(client: TestClient, headers: dict, **fields) -> dict:
    created = client.post(
        "/api/applications",
        headers=headers,
        json={
            "purpose": fields["purpose"],
            "product_code": fields["product"],
            "amount": fields["amount"],
            "term_months": fields["term"],
        },
    )
    assert created.status_code == 200, created.text
    application_id = created.json()["id"]
    patched = client.patch(
        f"/api/applications/{application_id}",
        headers=headers,
        json={
            "inn": fields["inn"],
            "legal_form": fields.get("legal_form", "OOO"),
            "monthly_revenue": fields["revenue"],
            "monthly_expenses": fields.get("expenses", 100000),
        },
    )
    assert patched.status_code == 200, patched.text
    submitted = client.post(f"/api/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    return submitted.json()


def test_approval_sign_and_refresh(client: TestClient):
    headers = _login(client, "client.good@demo.local")
    body = _submit(
        client,
        headers,
        purpose="TURNOVER",
        product="TURNOVER",
        amount=1_500_000,
        term=18,
        inn="7700000001",
        revenue=800_000,
        expenses=450_000,
    )
    assert body["status"] == "APPROVED"
    assert body["decision"]["offered_amount"] == 1_500_000
    assert body["decision"]["offered_term_months"] == 18
    accepted = client.post(f"/api/applications/{body['id']}/accept-offer", headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "CONTRACTING"
    signed = client.post(f"/api/applications/{body['id']}/sign", headers=headers)
    assert signed.status_code == 200
    assert signed.json()["status"] == "ISSUED"
    again = client.get(f"/api/applications/{body['id']}", headers=headers)
    assert again.json()["status"] == "ISSUED"
    assert len(again.json()["events"]) >= 5


def test_counter_offer_can_be_declined(client: TestClient):
    headers = _login(client, "client.offer@demo.local")
    body = _submit(
        client,
        headers,
        purpose="TURNOVER",
        product="TURNOVER",
        amount=5_000_000,
        term=24,
        inn="7700000002",
        revenue=400_000,
        expenses=350_000,
    )
    assert body["status"] == "APPROVED_WITH_CHANGES"
    assert body["decision"]["offered_amount"] < 5_000_000
    assert body["decision"]["changes"]
    declined = client.post(f"/api/applications/{body['id']}/decline-offer", headers=headers)
    assert declined.json()["status"] == "CANCELLED"


def test_bankruptcy_reject_visible_to_underwriter(client: TestClient):
    headers = _login(client, "client.reject@demo.local")
    body = _submit(
        client,
        headers,
        purpose="DEVELOPMENT",
        product="DEVELOPMENT",
        amount=2_000_000,
        term=24,
        inn="7700000003",
        revenue=900_000,
    )
    assert body["status"] == "REJECTED"
    assert "банкрот" in body["decision"]["explanation"].lower()
    staff = _login(client, "underwriter@demo.local")
    card = client.get(f"/api/underwriter/applications/{body['id']}", headers=staff)
    assert card.status_code == 200
    stops = card.json()["decision"]["stop_factors"]
    assert any("банкрот" in item.lower() for item in stops)
    assert card.json()["checks"]


def test_clarification_keeps_previous_score(client: TestClient):
    headers = _login(client, "client.info@demo.local")
    body = _submit(
        client,
        headers,
        purpose="TURNOVER",
        product="TURNOVER",
        amount=1_500_000,
        term=18,
        inn="7700000005",
        revenue=350_000,
    )
    assert body["status"] == "NEED_INFO"
    assert body["pending_question"]
    answered = client.post(
        f"/api/applications/{body['id']}/answers",
        headers=headers,
        json={"answer": "Выручка идёт из первых заказов цеха, около 350 тысяч в месяц.", "monthly_revenue": 350000},
    )
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "DECISION_READY"
    staff = _login(client, "underwriter@demo.local")
    card = client.get(f"/api/underwriter/applications/{body['id']}", headers=staff).json()
    assert len(card["scores"]) >= 2
    overridden = client.post(
        f"/api/underwriter/applications/{body['id']}/override",
        headers=staff,
        json={"decision": "APPROVED", "comment": "Подтверждаю пилотную сумму после пояснения выручки.", "amount": 700000, "term_months": 18, "rate": 23},
    )
    assert overridden.status_code == 200, overridden.text
    assert overridden.json()["status"] == "APPROVED"
    client_view = client.get(f"/api/applications/{body['id']}", headers=headers).json()
    assert client_view["status"] == "APPROVED"
    assert "пояснения" in client_view["decision"]["explanation"].lower()


def test_client_cannot_read_foreign_application(client: TestClient):
    owner = _login(client, "client.good@demo.local")
    body = _submit(
        client,
        owner,
        purpose="TURNOVER",
        product="TURNOVER",
        amount=1_000_000,
        term=12,
        inn="7700000001",
        revenue=800_000,
    )
    stranger = _login(client, "client.offer@demo.local")
    denied = client.get(f"/api/applications/{body['id']}", headers=stranger)
    assert denied.status_code == 404
