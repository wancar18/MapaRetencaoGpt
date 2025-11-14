"""Extração de dados estruturados das NFS-e usando OpenAI."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional

from .openai_client import OpenAIHelper


@dataclass
class DadosNota:
    cnpj_prestador: Optional[str]
    data_emissao: Optional[str]
    nome_fornecedor: Optional[str]
    descricao_servico: Optional[str]
    codigo_servico_municipal: Optional[str]
    subitem_lc116_raw: Optional[str]
    numero_nf: Optional[str]
    valor_total: Optional[float]
    municipio_prestador: Optional[str]
    municipio_tomador: Optional[str]
    campo_servico_bruto: Optional[str]


class ExtratorDadosNota:
    def __init__(self, helper: OpenAIHelper) -> None:
        self.helper = helper

    def extrair_dados(self, texto_nota: str) -> DadosNota:
        prompt = (
            "Extraia os campos solicitados da NFS-e. Responda em JSON com as chaves:\n"
            "cnpj_prestador, data_emissao, nome_fornecedor, descricao_servico,"
            " codigo_servico_municipal, subitem_lc116, numero_nf, valor_total,"
            " municipio_prestador, municipio_tomador, campo_servico_bruto.\n"
            "Use apenas informações explícitas."
        )
        resposta = self.helper.chat_completion("Assistente de extração NFS-e", prompt + "\n\n" + texto_nota[:4000])
        try:
            dados = json.loads(resposta.content)
        except json.JSONDecodeError:
            dados = {}
        valor_total = dados.get("valor_total")
        if isinstance(valor_total, str):
            valor_total = valor_total.replace("R$", "").replace(".", "").replace(",", ".")
            try:
                valor_total = float(valor_total)
            except ValueError:
                valor_total = None
        return DadosNota(
            cnpj_prestador=dados.get("cnpj_prestador"),
            data_emissao=dados.get("data_emissao"),
            nome_fornecedor=dados.get("nome_fornecedor"),
            descricao_servico=dados.get("descricao_servico"),
            codigo_servico_municipal=dados.get("codigo_servico_municipal"),
            subitem_lc116_raw=dados.get("subitem_lc116"),
            numero_nf=dados.get("numero_nf"),
            valor_total=valor_total if isinstance(valor_total, (int, float)) else None,
            municipio_prestador=dados.get("municipio_prestador"),
            municipio_tomador=dados.get("municipio_tomador"),
            campo_servico_bruto=dados.get("campo_servico_bruto"),
        )

    def sugerir_cnpj_tomador(self, texto_nota: str) -> list[str]:
        prompt = (
            "Liste até 3 CNPJs do TOMADOR encontrados na nota."
            " Responda em JSON: {\"cnpjs\": [\"...\"]}."
        )
        resposta = self.helper.chat_completion("Extração CNPJ Tomador", prompt + "\n\n" + texto_nota[:4000])
        try:
            dados = json.loads(resposta.content)
            return [c for c in dados.get("cnpjs", []) if isinstance(c, str)]
        except json.JSONDecodeError:
            return []

    def identificar_local_prestacao(self, texto_nota: str) -> Optional[str]:
        prompt = (
            "Identifique o município onde o serviço foi prestado na nota fiscal."
            " Responda apenas com 'Cidade - UF' ou 'NAO CONSTA'."
        )
        resposta = self.helper.chat_completion("Local Prestação", prompt + "\n\n" + texto_nota[:4000])
        conteudo = resposta.content.strip()
        if conteudo.upper() == "NAO CONSTA":
            return None
        return conteudo
