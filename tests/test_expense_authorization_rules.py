import pytest

from app.services.expense_authorization_rules import (
    category_requires_manual_authorization_area,
    expense_requires_authorization,
)


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


@pytest.mark.parametrize(
    "category",
    ["Pasajes y Taxis", "Taxi", "Taxis", "No Deducibles", "No Deducible", " no deducible "],
)
def test_manual_area_category_always_requires_authorization(category: str) -> None:
    assert category_requires_manual_authorization_area(category)
    assert expense_requires_authorization(category=category)


@pytest.mark.parametrize("category", [None, "", "Papelería", "Agua", "Insumos"])
def test_other_categories_do_not_require_manual_area(category: str | None) -> None:
    assert not category_requires_manual_authorization_area(category)


def test_non_deductible_description_does_not_change_category_rule() -> None:
    assert not expense_requires_authorization(
        category="Agua", description="No Deducibles", merchant="No Deducible",
    )
