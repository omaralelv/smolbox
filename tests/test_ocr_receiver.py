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
    ("rfc", "CIA090819PW4X", 1),
    ("rfc", "CIA090819PW4XX", 2),
    ("rfc", "CIA090819PW4XXX", 3),
    ("razon_social", "COMERCIAL IAX", 1),
    ("razon_social", "COMERCIAL IXX", 2),
    ("razon_social", "COMERCIAL XXX", 3),
    ("razon_social", "COMERCIAL IA", 1),
    ("razon_social", "COMERCIAL I", 2),
    ("razon_social", "COMERCIAL", 3),
    ("razon_social", "COMERCIAL IACX", 1),
    ("razon_social", "COMERCIAL IACXX", 2),
    ("razon_social", "COMERCIAL IACXXX", 3),
])
def test_receiver_accepts_one_to_three_edits_in_each_field(field, detected, differences):
    name = detected if field == "razon_social" else NAME
    rfc = detected if field == "rfc" else RFC
    result = _check(f"RECEPTOR\nNombre: {name}\nRFC: {rfc}")
    assert result["accepted"]
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
    ("rfc", "CIA090819PW4XXXX"),
    ("rfc", "CIA090819PW4\nXXXX"),
    ("razon_social", "COMERCIA XXXX"),
    ("razon_social", "COMERCIA"),
    ("razon_social", "COMERCIAL IACXXXX"),
    ("razon_social", "COMERCIAL IAC\nXXXX"),
])
def test_receiver_rejects_four_differences(field, detected):
    name = detected if field == "razon_social" else NAME
    rfc = detected if field == "rfc" else RFC
    result = _check(f"RECEPTOR\nNombre: {name}\nRFC: {rfc}")
    assert not result["accepted"]
    assert result["missing_fields"] == [field]
    assert result["fields"][field]["match_type"] == "mismatch"


@pytest.mark.parametrize("text,missing", [
    (None, ["razon_social", "rfc"]),
    ("", ["razon_social", "rfc"]),
    ("RECEPTOR\nNombre: COMERCIAL IAC", ["rfc"]),
    ("RECEPTOR\nRFC: CIA090819PW4", ["razon_social"]),
    ("RECEPTOR\nNombre:\nRFC: CIA090819PW4", ["razon_social"]),
    ("RECEPTOR\nNombre: COMERCIAL IAC\nRFC:\nTotal: 100.00", ["rfc"]),
])
def test_absent_fields_do_not_pass_via_tolerance(text, missing):
    result = _check(text)
    assert not result["accepted"]
    assert result["missing_fields"] == missing
    for field in missing:
        assert result["fields"][field]["match_type"] == "missing"
    assert validate_expected_invoice_receiver(
        text, expected_name=NAME, expected_rfc=RFC,
    ) == missing


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
def test_expected_values_in_issuer_or_different_receivers_do_not_approve(text):
    assert not _check(text)["accepted"]


def test_unset_expected_fields_are_not_required():
    result = assess_invoice_receiver(None, expected_name=None, expected_rfc=None)
    assert result["accepted"]
    assert all(field["match_type"] == "not_required" for field in result["fields"].values())


def test_repeated_identical_unlabeled_fields_are_not_ambiguous():
    result = _check("Nombre: COMERCIAL IAC\nRFC: CIA090819PW4\n" * 2)
    assert result["accepted"]


@pytest.mark.parametrize("expected,detected,distance", [
    ("ABC", "ABC", 0), ("ABC", "ABX", 1), ("ABC", "AB", 1),
    ("ABC", "XABC", 1), ("ABC", "ACB", 2), ("ABCD", "WXYZ", 4),
])
def test_edit_distance_counts_insertions_deletions_and_substitutions(expected, detected, distance):
    assert _edit_distance(expected, detected, 3) == distance
