"""Regras de ISS, INSS e demais retenções."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .text_utils import encontrar_percentuais, normalize_text


CODIGOS_EXCECAO_NAO_OPTANTE = {
    "7.02",
    "7.05",
    "7.09",
    "10.04",
    "10.05",
    "10.09",
}


@dataclass
class RetencaoResultado:
    aliquota: float
    valor: float
    mensagem: str


@dataclass
class TributacaoNota:
    iss: RetencaoResultado
    inss: RetencaoResultado
    irrf: RetencaoResultado
    csrf: RetencaoResultado
    observacoes: List[str]


def clamp_percentual(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, valor))


def calcular_valor(percentual: float, base: float) -> float:
    return round(base * percentual, 2)


def buscar_aliquota_iss(texto: str, valor_servico: float) -> Optional[float]:
    percentuais = encontrar_percentuais(texto)
    for perc in percentuais:
        perc_normalizado = perc / 100.0
        if 0.015 <= perc_normalizado <= 0.055:
            return round(perc_normalizado, 4)
    if valor_servico:
        return 0.05
    return None


def derivar_por_razao(valor_iss: float, base: float) -> Optional[float]:
    if not base:
        return None
    retorno = valor_iss / base
    if 0.015 <= retorno <= 0.06:
        return round(retorno, 4)
    return None


def decidir_retencoes(
    *,
    valor_servico: float,
    texto_nota: str,
    substituto_tributario: bool,
    possui_cebas: bool,
    codigo_lc116: Optional[str],
    municipio_prestador: str,
    municipio_tomador: str,
    municipio_prestacao: Optional[str],
    optante_simples: Optional[bool],
    status_simei: Optional[str],
    cnae_anexo: Optional[str],
    cnae_retencao_inss: Optional[str],
) -> TributacaoNota:
    observacoes: List[str] = []

    aliquota_iss = buscar_aliquota_iss(texto_nota, valor_servico) or 0.0
    valor_iss_retido = 0.0
    mensagem_iss = "ISS não retido."

    municipio_prestacao = municipio_prestacao or municipio_prestador

    if status_simei and status_simei.lower().startswith("simei"):
        mensagem_iss = "ISS não retido (fornecedor SIMEI)."
        observacoes.append(mensagem_iss)
    elif codigo_lc116 == "3.01":
        mensagem_iss = "ISS não retido (LC 116 3.01)."
        observacoes.append(mensagem_iss)
    else:
        if substituto_tributario and municipio_tomador and municipio_prestador:
            if normalize_text(municipio_tomador) == normalize_text(municipio_prestador):
                valor_iss_retido = calcular_valor(aliquota_iss, valor_servico)
                mensagem_iss = "ISS retido (municípios iguais; substituto tributário)."
            elif municipio_prestacao and normalize_text(municipio_prestacao) == normalize_text(municipio_tomador):
                valor_iss_retido = calcular_valor(aliquota_iss, valor_servico)
                mensagem_iss = "ISS retido no tomador (local da prestação coincide)."
            else:
                mensagem_iss = "Local de prestação não coincide; verificação manual."
        elif municipio_prestacao and normalize_text(municipio_prestacao) == normalize_text(municipio_prestador):
            mensagem_iss = "ISS devido ao município do prestador (sem retenção)."
        else:
            mensagem_iss = "Local de prestação indefinido; analisar manualmente."
        observacoes.append(mensagem_iss)

    aliquota_inss = 0.0
    valor_inss = 0.0
    mensagem_inss = "Sem retenção de INSS."

    if status_simei and status_simei.lower().startswith("simei"):
        if possui_cebas:
            aliquota_inss = 0.2
            valor_inss = calcular_valor(aliquota_inss, valor_servico)
            mensagem_inss = "INSS 20% (CEBAS)."
            observacoes.append(
                "Aplicar 20% de INSS conforme Inciso II do art. 191, IN 2.110/2022 (CEBAS)."
            )
        else:
            mensagem_inss = "INSS não retido (fornecedor SIMEI)."
            observacoes.append(mensagem_inss)
    else:
        if optante_simples:
            if cnae_anexo and cnae_anexo.strip() == "IV" and str(cnae_retencao_inss).upper() == "SIM":
                aliquota_inss = 0.11
                valor_inss = calcular_valor(aliquota_inss, valor_servico)
                mensagem_inss = "Retenção INSS 11% (Anexo IV)."
                observacoes.append("Retenção INSS conforme art. 191 IN 971/2009.")
            else:
                mensagem_inss = "INSS não retido (optante Simples, anexo não retentor)."
                observacoes.append(mensagem_inss)
        else:
            mensagem_inss = "Fornecedor não optante: avaliar retenção manual."
            observacoes.append(mensagem_inss)

    aliquota_irrf = 0.0
    valor_irrf = 0.0
    mensagem_irrf = "Sem retenção de IRRF."
    if codigo_lc116 == "10.09":
        aliquota_irrf = 0.015
        valor_irrf = calcular_valor(aliquota_irrf, valor_servico)
        mensagem_irrf = "IRRF 1,5% conforme LC 116 10.09."
        observacoes.append("Aplicar IRRF 1,5% conforme art. 714 do RIR/2018.")

    aliquota_csrf = 0.0
    valor_csrf = 0.0
    mensagem_csrf = "Sem retenção de CSRF."

    return TributacaoNota(
        iss=RetencaoResultado(aliquota=aliquota_iss, valor=valor_iss_retido, mensagem=mensagem_iss),
        inss=RetencaoResultado(aliquota=aliquota_inss, valor=valor_inss, mensagem=mensagem_inss),
        irrf=RetencaoResultado(aliquota=aliquota_irrf, valor=valor_irrf, mensagem=mensagem_irrf),
        csrf=RetencaoResultado(aliquota=aliquota_csrf, valor=valor_csrf, mensagem=mensagem_csrf),
        observacoes=observacoes,
    )


def validar_nao_optante(codigo_lc116: Optional[str]) -> bool:
    if not codigo_lc116:
        return False
    return codigo_lc116 in CODIGOS_EXCECAO_NAO_OPTANTE
