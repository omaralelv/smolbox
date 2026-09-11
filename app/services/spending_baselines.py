from decimal import Decimal, InvalidOperation

#convertir_decimal_excel
def convertir_decimal(valor):
    try:
        texto = str(valor).strip()

        if not texto or texto.lower() == "nan":
            return Decimal("0.00")

        texto = texto.replace("\u00A0", "")
        texto = texto.replace("$", "")
        texto = texto.replace(",", "")

        if texto.startswith("(") and texto.endswith(")"):
            texto = f"-{texto[1:-1]}"

        return Decimal(texto).quantize(
            Decimal("0.01")
        )

    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Saldo no numérico encontrado: {valor!r}"
        ) from exc