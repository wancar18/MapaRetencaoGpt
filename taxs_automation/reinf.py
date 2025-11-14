"""Seleção de códigos REINF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from .openai_client import OpenAIHelper
from .text_utils import get_close_match


@dataclass
class ReinfInfo:
    codigo: Optional[str]
    descricao: Optional[str]
    origem: str


class ReinfRepository:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df

    @classmethod
    def from_excel(cls, path: Path) -> "ReinfRepository":
        df = pd.read_excel(path)
        return cls(df)

    def buscar(self, codigo: str) -> Optional[ReinfInfo]:
        linha = self.df[self.df.iloc[:, 0].astype(str) == str(codigo)]
        if linha.empty:
            return None
        row = linha.iloc[0]
        return ReinfInfo(codigo=str(row.iloc[0]), descricao=str(row.iloc[1]), origem="tabela")

    def aproximar(self, descricao: str) -> Optional[ReinfInfo]:
        col_descricao = self.df.iloc[:, 1].astype(str).tolist()
        match = get_close_match(descricao, col_descricao, cutoff=0.6)
        if not match:
            return None
        descricao_encontrada, _ = match
        linha = self.df[self.df.iloc[:, 1].astype(str) == descricao_encontrada]
        if linha.empty:
            return None
        row = linha.iloc[0]
        return ReinfInfo(codigo=str(row.iloc[0]), descricao=descricao_encontrada, origem="match")


class ReinfResolver:
    def __init__(self, repo: ReinfRepository, helper: OpenAIHelper) -> None:
        self.repo = repo
        self.helper = helper

    def escolher(self, descricao_servico: str, descricao_cnae: Optional[str], max_rodadas: int = 3) -> Optional[ReinfInfo]:
        contexto = descricao_servico
        if descricao_cnae:
            contexto += f"\nDescrição CNAE: {descricao_cnae}"
        ultima_api: Optional[ReinfInfo] = None
        for rodada in range(1, max_rodadas + 1):
            prompt = (
                "Você é um especialista em EFD-REINF.\n"
                "Escolha o código REINF mais compatível com a descrição do serviço.\n"
                "Retorne apenas o código, sem texto adicional.\n"
                "Se não souber, responda 'NAO IDENTIFICADO'.\n"
                f"Descrição rodada {rodada}:\n{contexto}"
            )
            resp = self.helper.chat_completion("Assistente REINF", prompt)
            codigo = resp.content.strip()
            if codigo.upper() != "NAO IDENTIFICADO":
                reinf = self.repo.buscar(codigo)
                if reinf:
                    reinf.origem = "api"
                    return reinf
                ultima_api = ReinfInfo(codigo=codigo, descricao=None, origem="api-sem-tabela")

            match = self.repo.aproximar(descricao_servico)
            if match:
                return match
        return ultima_api
