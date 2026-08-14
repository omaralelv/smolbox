from app.dev_hud.product_page import PRODUCT_VIEW_HTML
from app.main import product_view, root


def test_product_view_html_uses_local_api_and_user_flow() -> None:
    assert "Smolbox Producto Demo" in PRODUCT_VIEW_HTML
    assert "/api/v1" in PRODUCT_VIEW_HTML
    assert "/dev-hud/status" in PRODUCT_VIEW_HTML
    assert "/test-hud" in PRODUCT_VIEW_HTML
    assert "HUD técnico" in PRODUCT_VIEW_HTML
    assert "Vista de producto para demostración de flujo" in PRODUCT_VIEW_HTML
    assert "roleTabs" in PRODUCT_VIEW_HTML
    assert "productApp" in PRODUCT_VIEW_HTML
    assert "requestSelect" in PRODUCT_VIEW_HTML
    assert "Crear demo" in PRODUCT_VIEW_HTML
    assert "Demo masivo" in PRODUCT_VIEW_HTML
    assert "Autorizar producto" in PRODUCT_VIEW_HTML
    assert "Rechazar producto" in PRODUCT_VIEW_HTML
    assert "Quitar gasto" in PRODUCT_VIEW_HTML
    assert "Regresar a contabilidad" in PRODUCT_VIEW_HTML
    assert "Registrar pago" in PRODUCT_VIEW_HTML
    assert "selectedExpenseId" in PRODUCT_VIEW_HTML
    assert "executeProductAction" in PRODUCT_VIEW_HTML
    assert "transition:under_accounting_review" in PRODUCT_VIEW_HTML
    assert "seedBulkDemo" in PRODUCT_VIEW_HTML


def test_product_view_is_not_the_technical_hud() -> None:
    assert "Reglas de negocio" not in PRODUCT_VIEW_HTML
    assert "businessRules" not in PRODUCT_VIEW_HTML
    assert "Crear tienda" not in PRODUCT_VIEW_HTML
    assert "Crear usuario" not in PRODUCT_VIEW_HTML
    assert "Personalizar escenario" not in PRODUCT_VIEW_HTML


def test_root_exposes_product_view_route() -> None:
    assert root()["product_view"] == "/product-view"


def test_product_view_route_returns_standalone_html() -> None:
    response = product_view()
    assert response.status_code == 200
    assert b"Smolbox Producto Demo" in response.body
