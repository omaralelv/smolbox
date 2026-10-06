import json
import logging
from typing import Any
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

PAYMENT_TEMPLATE_SUBJECT = "Pago registrado – Solicitud {{request_ref}} – {{amount}} {{currency}}"
PAYMENT_TEMPLATE_TEXT = (
    "Hola {{store_name}},\n\n"
    "Se registró el pago de la solicitud {{request_ref}}.\n"
    "Monto: {{amount}} {{currency}}\n"
    "Fecha de pago: {{paid_at}}\n"
    "Referencia: {{reference}}\n"
)
PAYMENT_TEMPLATE_HTML = (
    "<h1>Pago registrado</h1>"
    "<p>Hola {{store_name}},</p>"
    "<p>Se registró el pago de la solicitud <strong>{{request_ref}}</strong>.</p>"
    "<ul>"
    "<li>Monto: <strong>{{amount}} {{currency}}</strong></li>"
    "<li>Fecha de pago: {{paid_at}}</li>"
    "<li>Referencia: {{reference}}</li>"
    "</ul>"
)


def build_ses_client(settings: Settings) -> Any:
    import boto3

    return boto3.client(
        "ses",
        region_name=settings.ses_region or settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_session_token=settings.aws_session_token,
    )


def payment_template(settings: Settings) -> dict[str, str]:
    return {
        "TemplateName": settings.ses_template_name,
        "SubjectPart": PAYMENT_TEMPLATE_SUBJECT,
        "TextPart": PAYMENT_TEMPLATE_TEXT,
        "HtmlPart": PAYMENT_TEMPLATE_HTML,
    }


def ensure_payment_template(settings: Settings) -> str:
    """Create the SES payment template, or update it if it already exists."""
    client = build_ses_client(settings)
    template = payment_template(settings)
    try:
        client.create_template(Template=template)
        return "created"
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "AlreadyExists":
            raise
    client.update_template(Template=template)
    return "updated"


def send_payment_registered_email(
    settings: Settings,
    *,
    payment_id: UUID | str,
    store_id: UUID | str,
    to_address: str | None,
    store_name: str,
    request_ref: str,
    amount: str,
    currency: str,
    paid_at: str,
    reference: str | None,
) -> bool:
    """Send the payment email. Never raises: failures are logged only."""
    recipient = (to_address or "").strip()
    if not settings.ses_enabled or not recipient or not settings.ses_sender_email:
        return False

    template_data = {
        "store_name": store_name,
        "request_ref": request_ref,
        "amount": amount,
        "currency": currency,
        "paid_at": paid_at,
        "reference": reference or "",
    }
    send_kwargs: dict[str, Any] = {
        "Source": settings.ses_sender_email,
        "Destination": {"ToAddresses": [recipient]},
        "Template": settings.ses_template_name,
        "TemplateData": json.dumps(template_data),
    }
    if settings.ses_configuration_set:
        send_kwargs["ConfigurationSetName"] = settings.ses_configuration_set

    try:
        build_ses_client(settings).send_templated_email(**send_kwargs)
    except (ClientError, BotoCoreError):
        logger.exception(
            "Payment email failed payment_id=%s store_id=%s to_address=%s",
            payment_id,
            store_id,
            recipient,
        )
        return False

    logger.info(
        "Payment email sent payment_id=%s store_id=%s to_address=%s",
        payment_id,
        store_id,
        recipient,
    )
    return True
