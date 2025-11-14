"""Ponto de entrada do sistema de automação do MAPA."""
from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from . import config
from .cnae import CNAELC116Cache, CNAEInfo, CNAERepository, cache_path as cache_cnae_path, reconciliar_lc116_cnae
from .config import asset_path
from .extracao import DadosNota, ExtratorDadosNota
from .filesystem import mover_para_manual, mover_para_processadas, normalizar_nome_arquivo, organizar_pastas_saida
from .lc116 import LC116Mapa, LC116Resolver
from .ocr import extrair_texto_inteligente
from .openai_client import OpenAIHelper
from .pdf_report import gerar_mapa_pdf
from .portal import detectar_portal
from .reinf import ReinfRepository, ReinfResolver
from .simples import SimplesCache, obter_status_simples, cache_path as cache_simples_path
from .text_utils import buscar_todos_cnaes, extrair_numero_chamado, formatar_cnpj, normalizar_cnpj
from .tributos import decidir_retencoes, validar_nao_optante
from .ui import ConfiguracaoUnidade, confirmar_cnpj_tomador, perguntar_configuracoes_unidade, selecionar_pasta_notas


@dataclass
class LinhaRelatorio:
    arquivo: str
    cnpj: Optional[str]
    fornecedor: Optional[str]
    data_emissao: Optional[str]
    descricao_servico: Optional[str]
    cnae: Optional[str]
    cnae_desc: Optional[str]
    anexo: Optional[str]
    retencao_inss: Optional[str]
    art_219: Optional[str]
    lc116: Optional[str]
    lc116_desc: Optional[str]
    reinf: Optional[str]
    reinf_desc: Optional[str]
    municipio_prestador: Optional[str]
    municipio_tomador: Optional[str]
    municipio_prestacao: Optional[str]
    valor_servico: Optional[float]
    aliquota_iss_pct: Optional[float]
    ret_iss: float
    ret_inss: float
    valor_liquido: float


class ProcessadorNotas:
    def __init__(self, pasta: Path, config_unidade: ConfiguracaoUnidade) -> None:
        self.pasta = pasta
        self.config_unidade = config_unidade
        self.helper = OpenAIHelper()
        self.extrator = ExtratorDadosNota(self.helper)
        mapa_lc116_path = asset_path("servicos_lei_complementar.txt", writable=True)
        self.mapa_lc116 = LC116Mapa.from_file(mapa_lc116_path)
        self.servicos_txt = mapa_lc116_path.read_text(encoding="utf-8")
        self.lc116_resolver = LC116Resolver(self.mapa_lc116, self.servicos_txt, self.helper)
        cnae_path = asset_path("cnae.xlsx", writable=True)
        reinf_path = asset_path("reinf.xlsx", writable=True)
        self.cnae_repo = CNAERepository.from_excel(cnae_path)
        self.reinf_repo = ReinfRepository.from_excel(reinf_path)
        self.reinf_resolver = ReinfResolver(self.reinf_repo, self.helper)
        self.cache_cnae = CNAELC116Cache(cache_cnae_path())
        self.cache_simples = SimplesCache(cache_simples_path())
        self.linhas_relatorio: List[LinhaRelatorio] = []
        self.pasta_mapas_pdf, self.pasta_notas, self.pasta_manual = organizar_pastas_saida(self.pasta)

    def processar(self) -> None:
        pdfs = sorted(self.pasta.glob("*.pdf"))
        if not pdfs:
            print("Nenhum PDF encontrado na pasta selecionada.")
            return
        primeiro_pdf = pdfs[0]
        texto_primeiro = extrair_texto_inteligente(primeiro_pdf)
        candidatos_cnpj = self.extrator.sugerir_cnpj_tomador(texto_primeiro)
        cnpj_tomador = confirmar_cnpj_tomador(candidatos_cnpj) or normalizar_cnpj(texto_primeiro)
        if not cnpj_tomador:
            print("CNPJ do tomador não confirmado. Encerrando.")
            return
        print(f"CNPJ do tomador confirmado: {formatar_cnpj(cnpj_tomador)}")

        for pdf_path in pdfs:
            try:
                self._processar_nota(pdf_path, cnpj_tomador)
            except Exception as exc:  # noqa: BLE001
                mover_para_manual(pdf_path, self.pasta_manual, f"Erro inesperado: {exc}")

        if self.linhas_relatorio:
            print("Resumo do processamento:")
            for linha in self.linhas_relatorio:
                print(asdict(linha))

    def _processar_nota(self, pdf_path: Path, cnpj_tomador: str) -> None:
        print(f"Processando {pdf_path.name}...")
        pdf_path = normalizar_nome_arquivo(pdf_path)
        texto = extrair_texto_inteligente(pdf_path)
        if len(texto) < 200:
            mover_para_manual(pdf_path, self.pasta_manual, "Texto insuficiente após OCR")
            return

        portal = detectar_portal(texto) or "desconhecido"
        print(f"Portal identificado: {portal}")

        dados = self.extrator.extrair_dados(texto)
        if not dados.nome_fornecedor:
            mover_para_manual(pdf_path, self.pasta_manual, "Não foi possível extrair dados da nota")
            return

        lc116_result = None
        if dados.subitem_lc116_raw and self.mapa_lc116.contains(dados.subitem_lc116_raw):
            lc116_result = self.mapa_lc116.descricao(dados.subitem_lc116_raw)
        else:
            resolver_res = self.lc116_resolver.escolher_com_consenso(texto, dados.descricao_servico or "")
            if resolver_res:
                dados.subitem_lc116_raw = resolver_res.codigo
                lc116_result = resolver_res.descricao

        cnae_info = self._resolver_cnae(dados, texto)
        lc116_codigo, lc116_desc, cnae_codigo, cnae_desc, resumo_reconc = reconciliar_lc116_cnae(
            dados.subitem_lc116_raw, lc116_result, cnae_info
        )
        if resumo_reconc:
            print(resumo_reconc)

        reinf = self.reinf_resolver.escolher(dados.descricao_servico or "", cnae_desc)

        simples_status = obter_status_simples(
            self.helper,
            dados.cnpj_prestador or "",
            dados.data_emissao or "",
            cache=self.cache_simples,
            usar_automacao=False,
        )
        municipio_prestacao = self.extrator.identificar_local_prestacao(texto)

        if simples_status.optante is False and not validar_nao_optante(lc116_codigo):
            mover_para_manual(pdf_path, self.pasta_manual, "Fornecedor não optante sem exceção")
            return

        tributacao = decidir_retencoes(
            valor_servico=dados.valor_total or 0.0,
            texto_nota=texto,
            substituto_tributario=self.config_unidade.substituto_tributario,
            possui_cebas=self.config_unidade.possui_cebas,
            codigo_lc116=lc116_codigo,
            municipio_prestador=dados.municipio_prestador or "",
            municipio_tomador=dados.municipio_tomador or "",
            municipio_prestacao=municipio_prestacao,
            optante_simples=simple_status_bool(simples_status.optante),
            status_simei=simples_status.simei,
            cnae_anexo=cnae_info.anexo if cnae_info else None,
            cnae_retencao_inss=cnae_info.retencao_inss if cnae_info else None,
        )

        valor_total_retencoes = (
            tributacao.iss.valor + tributacao.inss.valor + tributacao.irrf.valor + tributacao.csrf.valor
        )
        valor_liquido = max((dados.valor_total or 0.0) - valor_total_retencoes, 0.0)

        numero_chamado = ""
        if self.config_unidade.preencher_chamado:
            numero_chamado = extrair_numero_chamado(pdf_path.stem) or ""

        dados_mapa = {
            "unidade": self.config_unidade.nome_unidade,
            "fornecedor": dados.nome_fornecedor or "",
            "titulo_mapa": f"{self.config_unidade.nome_unidade} - {dados.nome_fornecedor or ''}".upper(),
            "cod_servico_lc116": lc116_codigo or "",
            "desc_lc116": lc116_desc or "",
            "cnae_codigo": cnae_codigo or "",
            "cnae_descricao": cnae_desc or "",
            "cnae_atividade_especifica": cnae_desc or "",
            "cnae_anexo": cnae_info.anexo if cnae_info else "",
            "cnae_retencao_inss": cnae_info.retencao_inss if cnae_info else "",
            "cnae_art_219": cnae_info.art_219 if cnae_info else "",
            "optante_simples_str": "SIM" if simples_status.optante else "NÃO" if simples_status.optante is False else "NÃO IDENTIFICADO",
            "simei_status": simples_status.simei or "",
            "codigo_reinf": reinf.codigo if reinf else "",
            "descricao_reinf": reinf.descricao if reinf else "",
            "tipo_manutencao": "Serv.",
            "numero_chamado": numero_chamado,
            "numero_nfse": dados.numero_nf or "",
            "data_emissao": dados.data_emissao or "",
            "valor_total_servico": dados.valor_total or 0.0,
            "valor_total_retencoes": valor_total_retencoes,
            "valor_liquido": valor_liquido,
            "aliquota_iss": tributacao.iss.aliquota,
            "valor_iss_retido": tributacao.iss.valor,
            "aliquota_inss": tributacao.inss.aliquota,
            "valor_inss_retido": tributacao.inss.valor,
            "aliquota_irrf": tributacao.irrf.aliquota,
            "valor_irrf_retido": tributacao.irrf.valor,
            "aliquota_csrf": tributacao.csrf.aliquota,
            "valor_csrf_retido": tributacao.csrf.valor,
            "observacoes_legais": tributacao.observacoes,
            "municipio_prestador": dados.municipio_prestador,
            "municipio_tomador": dados.municipio_tomador,
            "municipio_prestacao": municipio_prestacao,
            "trecho_contrato_cessao": "",
        }

        pdf_saida = self.pasta_mapas_pdf / f"{pdf_path.stem}_MAPA.pdf"
        gerar_mapa_pdf(dados_mapa, str(pdf_saida))
        mover_para_processadas(pdf_path, self.pasta_notas)

        self.linhas_relatorio.append(
            LinhaRelatorio(
                arquivo=pdf_path.name,
                cnpj=dados.cnpj_prestador,
                fornecedor=dados.nome_fornecedor,
                data_emissao=dados.data_emissao,
                descricao_servico=dados.descricao_servico,
                cnae=cnae_codigo,
                cnae_desc=cnae_desc,
                anexo=cnae_info.anexo if cnae_info else None,
                retencao_inss=cnae_info.retencao_inss if cnae_info else None,
                art_219=cnae_info.art_219 if cnae_info else None,
                lc116=lc116_codigo,
                lc116_desc=lc116_desc,
                reinf=reinf.codigo if reinf else None,
                reinf_desc=reinf.descricao if reinf else None,
                municipio_prestador=dados.municipio_prestador,
                municipio_tomador=dados.municipio_tomador,
                municipio_prestacao=municipio_prestacao,
                valor_servico=dados.valor_total,
                aliquota_iss_pct=tributacao.iss.aliquota,
                ret_iss=tributacao.iss.valor,
                ret_inss=tributacao.inss.valor,
                valor_liquido=valor_liquido,
            )
        )

    def _resolver_cnae(self, dados: DadosNota, texto: str) -> Optional[CNAEInfo]:
        cnpj = dados.cnpj_prestador or ""
        lc116 = dados.subitem_lc116_raw or ""
        cached = self.cache_cnae.obter(cnpj, lc116)
        if cached:
            info = self.cnae_repo.buscar(cached)
            if info:
                return info

        cnaes_encontrados = buscar_todos_cnaes(texto)
        for codigo in cnaes_encontrados:
            info = self.cnae_repo.buscar(codigo)
            if info:
                self.cache_cnae.registrar(cnpj, lc116, info.codigo)
                return info

        if dados.descricao_servico:
            info = self.cnae_repo.buscar_por_descricao(dados.descricao_servico)
            if info:
                self.cache_cnae.registrar(cnpj, lc116, info.codigo)
                return info
        return None


def simple_status_bool(optante: Optional[bool]) -> Optional[bool]:
    if optante is None:
        return None
    return bool(optante)


def main() -> None:
    try:
        config.verificar_rede()
    except config.FatalConfigurationError:
        sys.exit(1)

    pasta = selecionar_pasta_notas()
    if not pasta:
        sys.exit(0)

    config_unidade = perguntar_configuracoes_unidade()
    if not config_unidade:
        print("Configuração não confirmada. Encerrando.")
        sys.exit(0)

    processador = ProcessadorNotas(pasta, config_unidade)
    processador.processar()
    from tkinter import messagebox, Tk

    root = Tk()
    root.withdraw()
    messagebox.showinfo("Concluído", "Concluído – Todos os arquivos foram processados com sucesso.")
    root.destroy()


if __name__ == "__main__":
    main()
