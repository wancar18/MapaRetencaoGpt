"""Manipulação da tabela CNAE e reconciliação com LC 116."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

from .config import carregar_json, salvar_json, user_dir
from .text_utils import get_close_match, normalize_digits, normalize_text


@dataclass
class CNAEInfo:
    codigo: str
    descricao: str
    anexo: Optional[str]
    retencao_inss: Optional[str]
    art_219: Optional[str]


class CNAERepository:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    @classmethod
    def from_excel(cls, path: Path) -> "CNAERepository":
        df = pd.read_excel(path)
        df.columns = [normalize_text(str(col)) for col in df.columns]
        return cls(df)

    def normalizar_codigo(self, codigo: str) -> Optional[str]:
        codigo = normalize_digits(codigo)
        if len(codigo) == 7:
            return codigo
        return None

    def buscar(self, codigo: str) -> Optional[CNAEInfo]:
        codigo_norm = self.normalizar_codigo(codigo)
        if not codigo_norm:
            return None
        linha = self.df[self.df["cnae"].astype(str).str.zfill(7) == codigo_norm]
        if linha.empty:
            return None
        row = linha.iloc[0]
        return CNAEInfo(
            codigo=codigo_norm,
            descricao=str(row.get("descricao", "")),
            anexo=str(row.get("anexo", "") or row.get("anexosn", "")),
            retencao_inss=str(row.get("retencao", row.get("retencao inss", ""))),
            art_219=str(row.get("art219", "")),
        )

    def buscar_por_descricao(self, descricao: str) -> Optional[CNAEInfo]:
        match = get_close_match(descricao, self.df.get("descricao", []), cutoff=0.6)
        if not match:
            return None
        descricao_encontrada, _ = match
        linha = self.df[self.df["descricao"].astype(str) == descricao_encontrada]
        if linha.empty:
            return None
        row = linha.iloc[0]
        return self.buscar(str(row.get("cnae")))


class CNAELC116Cache:
    """Cache persistente de decisões CNAE x LC116 por CNPJ."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._cache: Dict[str, Dict[str, str]] = carregar_json(path, default={})

    def chave(self, cnpj: str) -> Dict[str, str]:
        return self._cache.setdefault(cnpj, {})

    def obter(self, cnpj: str, lc116: str) -> Optional[str]:
        return self._cache.get(cnpj, {}).get(lc116)

    def salvar(self) -> None:
        salvar_json(self._path, self._cache)

    def registrar(self, cnpj: str, lc116: str, cnae: str) -> None:
        self.chave(cnpj)[lc116] = cnae
        self.salvar()


def reconciliar_lc116_cnae(
    lc116_codigo: Optional[str],
    lc116_desc: Optional[str],
    cnae_info: Optional[CNAEInfo],
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Realiza conciliação leve entre LC116 e CNAE."""
    if not cnae_info:
        return lc116_codigo, lc116_desc, None, None, None
    resumo = None
    if lc116_desc and cnae_info.descricao and normalize_text(lc116_desc) in normalize_text(cnae_info.descricao):
        resumo = "CNAE compatível com LC116 pela descrição"
    return (
        lc116_codigo,
        lc116_desc,
        cnae_info.codigo,
        cnae_info.descricao,
        resumo or "Reconciliação padrão",
    )


def cache_path() -> Path:
    return user_dir() / "decisoes_cnae_lc116.json"
