import pytest

from app.services.ocr_receiver import _edit_distance, assess_invoice_receiver
from app.services.textract_ocr import validate_expected_invoice_receiver

NAME = "COMERCIAL IAC"
RFC = "CIA090819PW4"


def _check(text):
    return assess_invoice_receiver(text, expected_name=NAME, expected_rfc=RFC)


@pytest.mark.parametrize("text", [
    "RECEPTOR\nRazon social: COMERCIAL IAC\nRFC: CIA090819PW4",
    "Receptor: razon social: comerci\u00e1l-iac; R.F.C.: c.i.a-09 08 19 pw4",
    "COMERCIAL IAC\nCIA090819PW4",
    "COMERCIAL IAC CIA090819PW4",
    "RECEPTOR\nCOMERCIAL\nIAC\nRFC: CIA090819PW4",
    "Nombre del receptor: COMERCIAL IAC\nRFC del receptor: CIA090819PW4",
    "Nombre del receptor: COMERCIAL IAC\nR.F.C. del receptor: CIA090819PW4",
    "RFC receptor: CIA090819PW4\nRazon social receptor: COMERCIAL IAC",
    "CLIENTE: COMERCIAL IAC\nRFC: CIA090819PW4",
    "RECEPTOR CLIENTE: COMERCIAL IAC\nRFC: CIA090819PW4",
])
def test_receiver_exact_match_normalizes_without_consuming_tolerance(text):
    result = _check(text)
    assert result["accepted"]
    assert result["match_rule"] == "any"
    assert result["matched_fields"] == ["razon_social", "rfc"]
    assert result["missing_fields"] == []
    for field in result["fields"].values():
        assert field["match_type"] == "exact"
        assert field["edit_distance"] == 0


@pytest.mark.parametrize("field,detected,differences", [
    ("rfc", "CIA090819PWX", 1),
    ("rfc", "CIA090819PXX", 2),
    ("rfc", "CIA090819XXX", 3),
    ("rfc", "CIA090819PW", 1),
    ("rfc", "CIA090819P", 2),
    ("rfc", "CIA090819", 3),
    ("rfc", "CIA0X90819PW4", 1),
    ("rfc", "CIA0XX90819PW4", 2),
    ("rfc", "CIA0XXX90819PW4", 3),
    ("razon_social", "COMERCIAL IAX", 1),
    ("razon_social", "COMERCIAL IXX", 2),
    ("razon_social", "COMERCIAL XXX", 3),
    ("razon_social", "COMERCIAL IA", 1),
    ("razon_social", "COMERCIAL I", 2),
    ("razon_social", "COMERCIAL", 3),
    ("razon_social", "COMERXCIAL IAC", 1),
    ("razon_social", "COMERXXCIAL IAC", 2),
    ("razon_social", "COMERXXXCIAL IAC", 3),
])
def test_receiver_accepts_one_to_three_edits_in_each_field(field, detected, differences):
    name = detected if field == "razon_social" else "OTRA EMPRESA"
    rfc = detected if field == "rfc" else "OTR010101AAA"
    result = _check(f"RECEPTOR\nNombre: {name}\nRFC: {rfc}")
    assert result["accepted"]
    assert result["matched_fields"] == [field]
    match = result["fields"][field]
    assert match["match_type"] == "tolerated"
    assert match["edit_distance"] == differences
    assert match["detected"] == detected
    assert match["expected"] == (NAME if field == "razon_social" else RFC)


def test_limit_is_per_field_not_shared_between_both():
    result = _check("RECEPTOR\nNombre: COMERCIAL XXX\nRFC: CIA090819XXX")
    assert result["accepted"]
    assert [field["edit_distance"] for field in result["fields"].values()] == [3, 3]


@pytest.mark.parametrize("name,differences", [
    ("COMERC1AL IAC", 1), ("C0MERC1AL1AC", 3),
])
def test_unlabeled_name_can_contain_digit_confusions(name, differences):
    result = _check(f"{name}\n{RFC}")
    assert result["accepted"]
    assert result["fields"]["razon_social"]["edit_distance"] == differences


@pytest.mark.parametrize("field,detected", [
    ("rfc", "CIA09081XXXX"),
    ("rfc", "CIA09081"),
    ("rfc", "CIA0XXXX90819PW4"),
    ("razon_social", "COMERCIA XXXX"),
    ("razon_social", "COMERCIA"),
    ("razon_social", "COMERXXXXCIAL IAC"),
])
def test_field_with_four_differences_does_not_match_but_other_field_can_pass(field, detected):
    name = detected if field == "razon_social" else NAME
    rfc = detected if field == "rfc" else RFC
    result = _check(f"RECEPTOR\nNombre: {name}\nRFC: {rfc}")
    assert result["accepted"]
    assert not result["fields"][field]["accepted"]
    assert result["missing_fields"] == [field]
    assert result["fields"][field]["edit_distance"] is None


@pytest.mark.parametrize("text,missing", [
    (None, ["razon_social", "rfc"]),
    ("", ["razon_social", "rfc"]),
    ("RECEPTOR\nNombre: COMERCIAL IAC", ["rfc"]),
    ("RECEPTOR\nRFC: CIA090819PW4", ["razon_social"]),
    ("RECEPTOR\nNombre:\nRFC: CIA090819PW4", ["razon_social"]),
    ("RECEPTOR\nNombre: COMERCIAL IAC\nRFC:\nTotal: 100.00", ["rfc"]),
])
def test_absent_fields_stay_unmatched_without_blocking_the_other_field(text, missing):
    result = _check(text)
    assert result["accepted"] == (len(missing) == 1)
    assert result["missing_fields"] == missing
    for field in missing:
        assert result["fields"][field]["match_type"] == "missing"
    assert validate_expected_invoice_receiver(
        text, expected_name=NAME, expected_rfc=RFC,
    ) == ([] if result["accepted"] else missing)


@pytest.mark.parametrize("text", [
    "EMISOR\nNombre: COMERCIAL IAC\nRFC: CIA090819PW4",
    "EMISOR | RECEPTOR\nNombre: COMERCIAL IAC\nRFC: CIA090819PW4",
    (
        "Nombre: COMERCIAL IAC\nRFC: CIA090819PW4\n"
        "Nombre: OTRA EMPRESA\nRFC: OTR010101AAA"
    ),
    (
        "EMISOR Nombre: COMERCIAL IAC RFC: CIA090819PW4\n"
        "RECEPTOR Nombre: OTRA EMPRESA RFC: OTR010101AAA"
    ),
    (
        "RECEPTOR Nombre: OTRA EMPRESA RFC: OTR010101AAA\n"
        "EMISOR Nombre: COMERCIAL IAC RFC: CIA090819PW4"
    ),
    (
        "Nombre del emisor: COMERCIAL IAC\nRFC del emisor: CIA090819PW4\n"
        "Nombre del receptor: OTRA EMPRESA\nRFC del receptor: OTR010101AAA"
    ),
    "RECEPTOR Nombre: OTRA EMPRESA RFC: OTR010101AAA\nCONCEPTOS\nCOMERCIAL IAC CIA090819PW4",
    (
        "RECEPTOR Nombre: COMERCIAL IAC RFC: OTR010101AAA\n"
        "RECEPTOR Nombre: OTRA EMPRESA RFC: CIA090819PW4"
    ),
])
def test_global_search_accepts_both_values_anywhere_regardless_of_role(text):
    result = _check(text)
    assert result["accepted"]
    assert result["scope"] == "global"
    assert all(field["match_type"] == "exact" for field in result["fields"].values())


@pytest.mark.parametrize("text", [
    "Facturado a: COMERCIAL IAC\nRFC: CIA090819PW4",
    (
        "FOLIO FISCAL: DEMO\nNumero de serie CSD del emisor: 123\n"
        "Facturado a: COMERCIAL IAC\nDireccion: CALLE DEMO 22\nRFC: CIA090819PW4"
    ),
    "CLIENTE\nCOMERCIAL\nIAC\nDOMICILIO: DEMO\nCIA 090 819 PW 4",
    "SUBTOTAL: 100\nNotas: comerci\u00e1l-iac\nR.F.C.: c.i.a-09 08 19 pw4",
    (
        "RECEPTOR: NOMBRE OMITIDO RFC: OMITIDO\n"
        "Notas: COMERCIAL IAX\nSello: CIA090819PWX"
    ),
    "COMERCIAL IAX;\nC.I.A.09 08 19 P.W.X\nAV REFORMA 326",
])
def test_global_search_does_not_depend_on_labels_order_or_invoice_body(text):
    assert _check(text)["accepted"]


@pytest.mark.parametrize("text", [
    "RECEPTOR Nombre: OTRA EMPRESA RFC: CIA090819PW4",
    "EMISOR Nombre: COMERCIAL IAC RFC: OTR010101AAA",
])
def test_global_search_accepts_a_match_for_either_field(text):
    result = _check(text)
    assert result["accepted"]
    assert len(result["matched_fields"]) == 1
    assert len(result["missing_fields"]) == 1


@pytest.mark.parametrize("text", [
    "FOLIO FISCAL: DEMO\nFacturado a: OTRA EMPRESA\nRFC: OTR010101AAA",
    "TOTAL: $100.00\nSin datos fiscales",
    "RECEPTOR Nombre: COMERCIA XXXX RFC: CIA09081XXXX",
    "RECEPTOR Nombre: COMERCIA XXXX RFC:",
    "RECEPTOR Nombre: RFC: CIA09081XXXX",
])
def test_global_search_rejects_when_neither_field_matches(text):
    result = _check(text)
    assert not result["accepted"]
    assert result["matched_fields"] == []
    assert result["missing_fields"] == ["razon_social", "rfc"]
    assert validate_expected_invoice_receiver(
        text, expected_name=NAME, expected_rfc=RFC,
    ) == result["missing_fields"]


def test_global_search_prefers_exact_match_over_an_earlier_tolerated_match():
    result = _check("COMERCIAL XXX\nCIA090819XXX\nCOMERCIAL IAC\nCIA090819PW4")
    assert result["accepted"]
    assert all(field["match_type"] == "exact" for field in result["fields"].values())


def test_global_search_reaches_the_end_of_a_long_document():
    result = _check("CONCEPTOS\nArticulo de prueba $100.00\n" * 1000 + "COMERCIAL IAX CIA090819PWX")
    assert result["accepted"]
    assert all(field["edit_distance"] == 1 for field in result["fields"].values())


@pytest.mark.parametrize("text", [
    "COMERCIAL IACXXXX CIA090819PW4XXXX",
    "COMERCIAL IAC\nXXXX\nCIA090819PW4\nXXXX",
    "AV REFORMA 326 COMERCIAL IAC\nCIA090819PW4",
])
def test_global_exact_search_checks_presence_not_full_field_identity(text):
    result = _check(text)
    assert result["accepted"]
    assert all(field["edit_distance"] == 0 for field in result["fields"].values())


def test_unset_expected_fields_are_not_required():
    result = assess_invoice_receiver(None, expected_name=None, expected_rfc=None)
    assert result["accepted"]
    assert all(field["match_type"] == "not_required" for field in result["fields"].values())
    assert result["matched_fields"] == []


@pytest.mark.parametrize("expected_name,expected_rfc,text,accepted,matched", [
    (None, RFC, RFC, True, ["rfc"]),
    (None, RFC, NAME, False, []),
    (None, RFC, None, False, []),
    (" ", RFC, "OTR010101AAA", False, []),
    (NAME, None, NAME, True, ["razon_social"]),
    (NAME, None, RFC, False, []),
    (NAME, None, None, False, []),
    (NAME, "", "OTRA EMPRESA", False, []),
])
def test_only_configured_fields_can_satisfy_the_or_rule(
    expected_name, expected_rfc, text, accepted, matched,
):
    result = assess_invoice_receiver(
        text, expected_name=expected_name, expected_rfc=expected_rfc,
    )
    assert result["accepted"] == accepted
    assert result["matched_fields"] == matched


def test_repeated_identical_unlabeled_fields_are_not_ambiguous():
    result = _check("Nombre: COMERCIAL IAC\nRFC: CIA090819PW4\n" * 2)
    assert result["accepted"]


def test_name_does_not_include_address_from_reported_receiver_text():
    text = (
        "RECEPTOR FACTURAR A: 77750385 1814\n"
        "ENTREGAR EN:\n"
        "RFC RECEPTOR CIA090819PW\n"
        "NOMBRE RECEPTOR: COMERCIAL IAC\n"
        "AV REFORMA 326 CENTRO PUEBLA DE ZARAGOZA PUEBLA MEXICO C.P.\n"
        "DOMICILIO RECEPTOR: CALLE DE PRUEBA 22 CENTRO\n"
        "72000\nHUIXQUILUCAN\nESTADO DE MEXICO MEXICO C.P. 52760\n"
        "USO DEL CFDI POR EL RECEPTOR G03-Gastos en general\n"
        "DOMICILIO FISCAL RECEPTOR: 52760\nREGIMEN FISCAL RECEPTOR: 601"
    )
    result = _check(text)
    assert result["accepted"]
    assert result["fields"]["razon_social"]["detected"] == NAME
    assert result["fields"]["razon_social"]["match_type"] == "exact"
    assert result["fields"]["rfc"]["detected"] == "CIA090819PW"
    assert result["fields"]["rfc"]["edit_distance"] == 1


@pytest.mark.parametrize("address", [
    "AV REFORMA 326 CENTRO",
    "AV. REFORMA 326 CENTRO",
    "AVENIDA REFORMA 326 CENTRO",
    "CALLE DE PRUEBA 22",
    "CALZADA DE PRUEBA 100",
    "BLVD. DE PRUEBA 428",
    "PROLONGACION REFORMA 6623",
    "CARRETERA DE PRUEBA KM 12",
    "PASEO DE PRUEBA S/N",
])
@pytest.mark.parametrize("separator", ["\n", "  ", "; ", " | ", "\t"])
def test_address_boundary_keeps_complete_multiline_name(address, separator):
    result = _check(
        f"RFC RECEPTOR: {RFC}\nNOMBRE RECEPTOR: COMERCIAL\nIAC{separator}{address}"
    )
    assert result["accepted"]
    assert result["fields"]["razon_social"]["detected"] == NAME
    assert result["fields"]["razon_social"]["edit_distance"] == 0


@pytest.mark.parametrize("address_label", [
    "DOMICILIO RECEPTOR", "DOMICILIO FISCAL DEL RECEPTOR", "DIRECCION DEL RECEPTOR",
    "REGIMEN FISCAL RECEPTOR", "USO DEL CFDI POR EL RECEPTOR",
])
def test_non_identity_receiver_fields_do_not_split_its_rfc_and_name(address_label):
    result = _check(
        f"RFC RECEPTOR: {RFC}\n{address_label}: DATO ADICIONAL\nNOMBRE RECEPTOR: {NAME}"
    )
    assert result["accepted"]
    assert result["fields"]["razon_social"]["edit_distance"] == 0
    assert result["fields"]["rfc"]["edit_distance"] == 0


@pytest.mark.parametrize("name", ["OTRA EMPRESA", "COMERCIA XXXX"])
def test_global_search_accepts_rfc_despite_an_unmatched_name_next_to_an_address(name):
    result = _check(
        f"RFC RECEPTOR: {RFC}\nNOMBRE RECEPTOR: {name}\nCALLE DE PRUEBA 22"
    )
    assert result["accepted"]
    assert result["matched_fields"] == ["rfc"]
    assert result["missing_fields"] == ["razon_social"]


def test_global_search_can_find_the_name_inside_an_address():
    result = _check(f"RFC RECEPTOR: {RFC}\nNOMBRE RECEPTOR:\nAV REFORMA 326 COMERCIAL IAC")
    assert result["accepted"]
    assert result["fields"]["razon_social"]["detected"] == NAME


def test_rfc_address_boundary_does_not_change_the_three_character_limit():
    result = _check(
        "RFC RECEPTOR: CIA09081XXXX\nAV REFORMA 326\nNOMBRE RECEPTOR: COMERCIAL IAC"
    )
    assert result["accepted"]
    assert result["matched_fields"] == ["razon_social"]
    assert result["missing_fields"] == ["rfc"]


@pytest.mark.parametrize("expected,detected,distance", [
    ("ABC", "ABC", 0), ("ABC", "ABX", 1), ("ABC", "AB", 1),
    ("ABC", "XABC", 1), ("ABC", "ACB", 2), ("ABCD", "WXYZ", 4),
])
def test_edit_distance_counts_insertions_deletions_and_substitutions(expected, detected, distance):
    assert _edit_distance(expected, detected, 3) == distance
