from app.core.config import get_settings
from app.services.email_notifications import ensure_payment_template


def main() -> None:
    settings = get_settings()
    result = ensure_payment_template(settings)
    region = settings.ses_region or settings.aws_region
    print(f"Plantilla SES {settings.ses_template_name!r} {result} en {region}.")


if __name__ == "__main__":
    main()
