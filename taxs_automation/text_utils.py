"""Funções auxiliares de manipulação de texto e regex."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

import difflib


RE_CNPJ = re.compile(r"(?<!\d)(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)")
RE_CNAE = re.compile(r"(?<!\d)(\d{2}\.\d{2}-\d-\d|\d{7})(?!\d)")
RE_LC116 = re.compile(r"(?<!\d)(\d{1,2}\.\d{2})(?!\d)")
RE_PERCENT = re.compile(r"(\d{1,2}[\.,]\d{1,2})\s?%")


TRANSLATION_TABLE = str.maketrans({
    "\n": " ",
    "\r": " ",
    "\t": " ",
})


def clean_spaces(text: str) -> str:
    text = text.translate(TRANSLATION_TABLE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode()
    return clean_spaces(normalized.lower())


def normalize_digits(text: str) -> str:
    return re.sub(r"\D", "", text or "")


def normalizar_cnpj(text: str) -> Optional[str]:
    match = RE_CNPJ.search(text)
    if not match:
        return None
    cnpj = normalize_digits(match.group(1))
    if len(cnpj) == 14:
        return cnpj
    return None


def formatar_cnpj(cnpj: str) -> str:
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def buscar_todos_cnaes(texto: str) -> List[str]:
    return list({normalize_digits(m) for m in RE_CNAE.findall(texto) if len(normalize_digits(m)) == 7})


def buscar_codigos_lc116(texto: str) -> List[str]:
    return list({m for m in RE_LC116.findall(texto)})


def encontrar_percentuais(texto: str) -> List[float]:
    valores: List[float] = []
    for match in RE_PERCENT.findall(texto.replace(",", ".")):
        try:
            valores.append(float(match))
        except ValueError:
            continue
    return valores


def get_close_match(text: str, candidates: Iterable[str], cutoff: float = 0.6) -> Optional[Tuple[str, float]]:
    normalized = normalize_text(text)
    best_ratio = 0.0
    best_candidate: Optional[str] = None
    for candidate in candidates:
        ratio = difflib.SequenceMatcher(None, normalized, normalize_text(candidate)).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_candidate = candidate
    if best_candidate and best_ratio >= cutoff:
        return best_candidate, best_ratio
    return None


def extrair_numero_chamado(nome_arquivo: str) -> Optional[str]:
    match = re.search(r"(\d{6,})", nome_arquivo)
    if match:
        return match.group(1)
    return None
