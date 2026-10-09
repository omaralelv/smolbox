import re

def limpiar_nombre_archivo(valor: str) -> str:
    """
    Convierte texto en un nombre seguro para archivo.

    Elimina o reemplaza caracteres no permitidos en Windows,
    como: < > : " / \\ | ? * y caracteres de control.
    """
    nombre = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        str(valor or ""),
    ).strip()

    return nombre or "archivo"