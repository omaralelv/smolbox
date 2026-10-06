import json
import logging
from uuid import UUID

import pytest
from botocore.exceptions import ClientError
from conftest import create_expense
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_workflow_api import _assign_user_to_store, _auth_headers, _create_user

from app.api.v1.endpoints import reimbursement_requests as reimbursement_endpoints
from app.core.config import Settings
from app.models.reimbursement_request import ReimbursementRequest, ReimbursementRequestStatus
from app.models.store import Store
from app.services import email_notifications
from app.services.email_notifications import (
    ensure_payment_template,
    send_payment_registered_email,
)


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    calls: list[dict] = []

    def fake_send(settings: Settings, **kwargs) -> bool:
        calls.append(kwargs)
        return True

    monkeypatch.setattr(reimbursement_endpoints, "send_payment_registered_email", fake_send)
    return calls


@pytest.fixture
def payable_request(
    client: TestClient,
    base_records: dict[str, str],
    session_factory: sessionmaker[Session],
) -> dict[str, str]:
    create_expense(client, base_records, amount="1500.00")
    manager_id = _create_user(client, "accounting_manager")
    _assign_user_to_store(client, base_records["store_id"], manager_id, "accounting_manager")
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(base_records["request_id"]))
        request.status = ReimbursementRequestStatus.approved_for_payment
        db.commit()
    return {**base_records, "headers": _auth_headers(client, "accounting_manager@example.com")}


def _set_store_email(
    session_factory: sessionmaker[Session],
    store_id: str,
    contact_email: str | None,
) -> None:
    with session_factory() as db:
        db.get(Store, UUID(store_id)).contact_email = contact_email
        db.commit()


def _pay(client: TestClient, payable_request: dict, reference: str = "PAGO-001"):
    return client.post(
        f"/api/v1/reimbursement-requests/{payable_request['request_id']}/payments/me",
        headers=payable_request["headers"],
        json={"reference": reference},
    )


def test_payment_email_is_sent_when_enabled_and_store_has_email(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    sent_emails: list[dict],
) -> None:
    test_settings.ses_enabled = True
    _set_store_email(session_factory, payable_request["store_id"], "tienda@example.com")

    response = _pay(client, payable_request)

    assert response.status_code == 201, response.text
    assert len(sent_emails) == 1
    email = sent_emails[0]
    assert email["to_address"] == "tienda@example.com"
    assert email["store_name"] == "Tienda Centro"
    assert email["amount"] == "1500.00"
    assert email["currency"] == "MXN"
    assert email["reference"] == "PAGO-001"
    assert email["payment_id"] == response.json()["id"]
    assert email["store_id"] == payable_request["store_id"]
    assert email["request_ref"]
    assert email["paid_at"]


def test_payment_email_is_not_sent_when_ses_is_disabled(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_settings.ses_enabled = False
    test_settings.ses_sender_email = "no-reply@example.com"
    _set_store_email(session_factory, payable_request["store_id"], "tienda@example.com")

    def fail_if_client_built(settings: Settings):
        raise AssertionError("SES client must not be created when SES is disabled")

    monkeypatch.setattr(email_notifications, "build_ses_client", fail_if_client_built)

    response = _pay(client, payable_request)

    assert response.status_code == 201, response.text


@pytest.mark.parametrize("contact_email", [None, "", "   "])
def test_payment_email_is_not_sent_without_contact_email(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    contact_email: str | None,
) -> None:
    test_settings.ses_enabled = True
    test_settings.ses_sender_email = "no-reply@example.com"
    _set_store_email(session_factory, payable_request["store_id"], contact_email)

    def fail_if_client_built(settings: Settings):
        raise AssertionError("SES client must not be created without a recipient")

    monkeypatch.setattr(email_notifications, "build_ses_client", fail_if_client_built)

    response = _pay(client, payable_request)

    assert response.status_code == 201, response.text


def test_payment_email_is_not_sent_when_payment_is_rejected(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    sent_emails: list[dict],
) -> None:
    test_settings.ses_enabled = True
    _set_store_email(session_factory, payable_request["store_id"], "tienda@example.com")

    first = _pay(client, payable_request)
    assert first.status_code == 201, first.text
    assert len(sent_emails) == 1

    duplicate = _pay(client, payable_request, reference="PAGO-002")
    assert duplicate.status_code == 409
    assert len(sent_emails) == 1


def test_payment_email_is_not_sent_when_request_is_not_approved_for_payment(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    sent_emails: list[dict],
) -> None:
    test_settings.ses_enabled = True
    _set_store_email(session_factory, payable_request["store_id"], "tienda@example.com")
    with session_factory() as db:
        request = db.get(ReimbursementRequest, UUID(payable_request["request_id"]))
        request.status = ReimbursementRequestStatus.treasury_review
        db.commit()

    response = _pay(client, payable_request)

    assert response.status_code == 409
    assert sent_emails == []


class FakeSesClient:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[dict] = []
        self.templates: list[tuple[str, dict]] = []
        self.existing_template = False

    def send_templated_email(self, **kwargs) -> dict:
        if self.error:
            raise self.error
        self.sent.append(kwargs)
        return {"MessageId": "abc"}

    def create_template(self, Template: dict) -> None:
        if self.existing_template:
            raise ClientError({"Error": {"Code": "AlreadyExists"}}, "CreateTemplate")
        self.templates.append(("create", Template))

    def update_template(self, Template: dict) -> None:
        self.templates.append(("update", Template))


def _email_kwargs(**overrides) -> dict:
    kwargs = {
        "payment_id": "payment-1",
        "store_id": "store-1",
        "to_address": "tienda@example.com",
        "store_name": "Tienda Centro",
        "request_ref": "SOL-001",
        "amount": "1500.00",
        "currency": "MXN",
        "paid_at": "2026-10-06T20:00:00+00:00",
        "reference": None,
    }
    kwargs.update(overrides)
    return kwargs


def _ses_settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "ses_enabled": True,
        "ses_sender_email": "no-reply@example.com",
        "aws_region": "us-east-1",
    }
    values.update(overrides)
    return Settings(**values)


def test_service_sends_templated_email_with_all_template_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeSesClient()
    monkeypatch.setattr(email_notifications, "build_ses_client", lambda settings: fake)

    assert send_payment_registered_email(_ses_settings(), **_email_kwargs()) is True

    sent = fake.sent[0]
    assert sent["Source"] == "no-reply@example.com"
    assert sent["Destination"] == {"ToAddresses": ["tienda@example.com"]}
    assert sent["Template"] == "smolbox-payment-registered"
    assert json.loads(sent["TemplateData"]) == {
        "store_name": "Tienda Centro",
        "request_ref": "SOL-001",
        "amount": "1500.00",
        "currency": "MXN",
        "paid_at": "2026-10-06T20:00:00+00:00",
        "reference": "",
    }
    assert "ConfigurationSetName" not in sent


def test_template_subject_contains_request_ref_and_amount() -> None:
    template = email_notifications.payment_template(_ses_settings())

    assert "{{request_ref}}" in template["SubjectPart"]
    assert "{{amount}}" in template["SubjectPart"]
    assert template["SubjectPart"].startswith("Pago registrado")


@pytest.mark.parametrize(
    ("ses_region", "expected_region"),
    [(None, "us-east-1"), ("us-west-2", "us-west-2")],
)
def test_ses_client_uses_explicit_region_with_fallback(
    monkeypatch: pytest.MonkeyPatch,
    ses_region: str | None,
    expected_region: str,
) -> None:
    import boto3

    captured: dict = {}

    def fake_boto_client(service: str, **kwargs):
        captured["service"] = service
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(boto3, "client", fake_boto_client)

    email_notifications.build_ses_client(_ses_settings(ses_region=ses_region))

    assert captured["service"] == "ses"
    assert captured["region_name"] == expected_region


def test_service_logs_error_and_does_not_raise_when_ses_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    error = ClientError({"Error": {"Code": "MessageRejected"}}, "SendTemplatedEmail")
    monkeypatch.setattr(
        email_notifications,
        "build_ses_client",
        lambda settings: FakeSesClient(error=error),
    )

    with caplog.at_level(logging.ERROR, logger=email_notifications.logger.name):
        assert send_payment_registered_email(_ses_settings(), **_email_kwargs()) is False

    record = caplog.records[0]
    assert record.levelno == logging.ERROR
    assert "payment-1" in record.getMessage()
    assert "store-1" in record.getMessage()
    assert "tienda@example.com" in record.getMessage()
    assert record.exc_info is not None


def test_service_logs_info_on_success(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        email_notifications,
        "build_ses_client",
        lambda settings: FakeSesClient(),
    )

    with caplog.at_level(logging.INFO, logger=email_notifications.logger.name):
        send_payment_registered_email(_ses_settings(), **_email_kwargs())

    assert caplog.records[0].levelno == logging.INFO
    assert "payment-1" in caplog.records[0].getMessage()


def test_payment_is_not_rolled_back_when_ses_fails(
    client: TestClient,
    payable_request: dict,
    session_factory: sessionmaker[Session],
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    test_settings.ses_enabled = True
    test_settings.ses_sender_email = "no-reply@example.com"
    _set_store_email(session_factory, payable_request["store_id"], "tienda@example.com")
    error = ClientError({"Error": {"Code": "MessageRejected"}}, "SendTemplatedEmail")
    monkeypatch.setattr(
        email_notifications,
        "build_ses_client",
        lambda settings: FakeSesClient(error=error),
    )

    response = _pay(client, payable_request)

    assert response.status_code == 201, response.text
    paid = client.get(f"/api/v1/reimbursement-requests/{payable_request['request_id']}")
    assert paid.json()["status"] == "paid"


def test_ensure_template_creates_then_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSesClient()
    monkeypatch.setattr(email_notifications, "build_ses_client", lambda settings: fake)

    assert ensure_payment_template(_ses_settings()) == "created"

    fake.existing_template = True
    assert ensure_payment_template(_ses_settings()) == "updated"
    assert [action for action, _ in fake.templates] == ["create", "update"]
