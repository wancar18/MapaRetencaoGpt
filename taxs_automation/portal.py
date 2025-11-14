"""Heurísticas para detectar o portal de emissão da NFS-e."""
from __future__ import annotations

from typing import Optional

from .text_utils import normalize_text


PORTAL_PATTERNS = {
    "ginfes": ("ginfes", "GINFES"),
    "betha": ("betha",),
    "issnet": ("issnet", "iss net"),
    "abaco": ("abaco",),
    "govbr": ("gov.br", "govbr", "portal nacional"),
    "nota_curitiba": ("ipm sistemas", "curitiba"),
}


def detectar_portal(texto: str) -> Optional[str]:
    normalized = normalize_text(texto)
    for portal, patterns in PORTAL_PATTERNS.items():
        if any(pat in normalized for pat in patterns):
            return portal
    return None
