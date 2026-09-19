from app.services.expense_authorization_rules import expense_requires_authorization


def test_taxi_category_requires_authorization() -> None:
    assert expense_requires_authorization(category="Pasajes y Taxis")


def test_taxi_text_requires_authorization() -> None:
    assert expense_requires_authorization(
        description="Taxi para realizar pago del servicio de agua",
    )
    assert expense_requires_authorization(merchant="Taxi Local Norte")


def test_regular_expense_does_not_require_authorization() -> None:
    assert not expense_requires_authorization(
        category="Papeleria",
        description="Compra de hojas",
        merchant="Proveedor Demo",
    )


def test_explicit_authorization_is_preserved() -> None:
    assert expense_requires_authorization(explicit=True, category="Papeleria")
