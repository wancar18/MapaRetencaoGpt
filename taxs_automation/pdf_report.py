"""Geração do relatório MAPA em PDF usando ReportLab."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _draw_round_rect(c: canvas.Canvas, x: float, y: float, w: float, h: float, radius: float = 6.0) -> None:
    c.roundRect(x, y, w, h, radius, stroke=1, fill=0)


def _draw_label_value(
    c: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    value: str,
    align: str = "left",
    fontsize: int = 9,
    bold_label: bool = True,
) -> None:
    _draw_round_rect(c, x, y, w, h)
    c.setFont("Helvetica-Bold" if bold_label else "Helvetica", 7)
    c.drawString(x + 4, y + h - 10, label)
    c.setFont("Helvetica", fontsize)
    if align == "left":
        c.drawString(x + 4, y + h / 2 - 4, value)
    elif align == "center":
        c.drawCentredString(x + w / 2, y + h / 2 - 4, value)
    elif align == "right":
        c.drawRightString(x + w - 4, y + h / 2 - 4, value)


def format_currency(valor: Optional[float]) -> str:
    if valor is None:
        return ""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_percent(percent: Optional[float]) -> str:
    if percent is None:
        return ""
    return f"{percent*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class BoxConfig:
    label: str
    value: str
    x: float
    y: float
    w: float
    h: float


class PDFMapaGenerator:
    def __init__(self, dados: Dict[str, Any]) -> None:
        self.dados = dados
        self.width, self.height = A4

    def gerar(self, caminho_saida: str) -> None:
        c = canvas.Canvas(caminho_saida, pagesize=A4)
        self._desenhar_cabecalho(c)
        self._desenhar_identificacao(c)
        self._desenhar_questionarios_e_valores(c)
        self._desenhar_impostos(c)
        self._desenhar_legislacao(c)
        self._desenhar_rodape(c)
        c.showPage()
        c.save()

    def _desenhar_cabecalho(self, c: canvas.Canvas) -> None:
        c.setFillColor(colors.HexColor("#F7931E"))
        c.rect(0, self.height - 30, self.width, 30, fill=1, stroke=0)
        c.rect(0, self.height - 60, self.width, 20, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 16)
        titulo = self.dados.get("titulo_mapa", "MAPA - TAXS")
        c.drawCentredString(self.width / 2, self.height - 45, titulo)
        c.setFillColor(colors.HexColor("#F7931E"))

    def _desenhar_identificacao(self, c: canvas.Canvas) -> None:
        margem = 20 * mm
        y_base = self.height - 110
        largura = self.width - 2 * margem
        _draw_label_value(
            c,
            margem,
            y_base,
            largura,
            30,
            "Fornecedor",
            f"{self.dados.get('unidade', '').upper()} - {self.dados.get('fornecedor', '').upper()}",
        )
        y_base -= 40
        bloco_w = largura / 3
        _draw_label_value(c, margem, y_base, bloco_w, 30, "Unidade", self.dados.get("unidade", ""))
        _draw_label_value(
            c,
            margem + bloco_w + 5,
            y_base,
            bloco_w - 5,
            30,
            "Cód. Serviço",
            self.dados.get("cod_servico_lc116", ""),
            align="center",
        )
        _draw_label_value(
            c,
            margem + 2 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Tipo de atividade",
            self.dados.get("cnae_descricao", ""),
        )
        y_base -= 40
        _draw_label_value(
            c,
            margem,
            y_base,
            bloco_w,
            30,
            "Op. Simples Nacional",
            self.dados.get("optante_simples_str", ""),
            align="center",
        )
        _draw_label_value(
            c,
            margem + bloco_w,
            y_base,
            bloco_w / 2,
            30,
            "Anexo",
            self.dados.get("cnae_anexo", ""),
            align="center",
        )
        _draw_label_value(
            c,
            margem + 1.5 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Código REINF",
            self.dados.get("codigo_reinf", ""),
            align="center",
        )
        _draw_label_value(
            c,
            margem + 2.5 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Descrição REINF",
            self.dados.get("descricao_reinf", ""),
        )

    def _desenhar_questionarios_e_valores(self, c: canvas.Canvas) -> None:
        margem = 20 * mm
        y_base = self.height - 220
        bloco_w = (self.width - 2 * margem) / 4
        _draw_label_value(
            c,
            margem,
            y_base,
            bloco_w,
            30,
            "N° do chamado",
            self.dados.get("numero_chamado", ""),
        )
        _draw_label_value(
            c,
            margem + bloco_w,
            y_base,
            bloco_w,
            30,
            "Total do serviço",
            format_currency(self.dados.get("valor_total_servico")),
        )
        _draw_label_value(
            c,
            margem + 2 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Total das retenções",
            format_currency(self.dados.get("valor_total_retencoes")),
        )
        _draw_label_value(
            c,
            margem + 3 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Total Líquido",
            format_currency(self.dados.get("valor_liquido")),
        )
        y_base -= 40
        _draw_label_value(
            c,
            margem,
            y_base,
            bloco_w,
            30,
            "N° NFS-e",
            self.dados.get("numero_nfse", ""),
        )
        _draw_label_value(
            c,
            margem + bloco_w,
            y_base,
            bloco_w,
            30,
            "Data de emissão",
            self.dados.get("data_emissao", ""),
        )
        _draw_label_value(
            c,
            margem + 2 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Total ret. federais",
            format_currency(
                (self.dados.get("valor_irrf_retido", 0.0) or 0.0)
                + (self.dados.get("valor_csrf_retido", 0.0) or 0.0)
            ),
        )
        _draw_label_value(
            c,
            margem + 3 * bloco_w,
            y_base,
            bloco_w,
            30,
            "Mat. Serv.",
            self.dados.get("tipo_manutencao", ""),
        )

    def _desenhar_impostos(self, c: canvas.Canvas) -> None:
        margem = 20 * mm
        y_base = self.height - 320
        bloco_w = (self.width - 2 * margem) / 4
        impostos = [
            ("ISS", "aliquota_iss", "valor_iss_retido"),
            ("INSS", "aliquota_inss", "valor_inss_retido"),
            ("IRRF", "aliquota_irrf", "valor_irrf_retido"),
            ("CSRF", "aliquota_csrf", "valor_csrf_retido"),
        ]
        for idx, (nome, aliq_key, val_key) in enumerate(impostos):
            x = margem + idx * bloco_w
            _draw_round_rect(c, x, y_base, bloco_w - 5, 60)
            c.setFont("Helvetica-Bold", 10)
            aliq = format_percent(self.dados.get(aliq_key)) or "0,00%"
            c.drawCentredString(x + (bloco_w - 5) / 2, y_base + 45, f"{nome} - {aliq}")
            c.setFont("Helvetica", 10)
            c.drawCentredString(
                x + (bloco_w - 5) / 2,
                y_base + 25,
                format_currency(self.dados.get(val_key, 0.0)),
            )

    def _desenhar_legislacao(self, c: canvas.Canvas) -> None:
        margem = 20 * mm
        y_base = 120
        largura = self.width - 2 * margem
        altura = 120
        _draw_label_value(
            c,
            margem,
            y_base + altura,
            largura / 2 - 5,
            altura,
            "Tipo de atividade",
            self.dados.get("cnae_descricao", ""),
        )
        _draw_label_value(
            c,
            margem + largura / 2,
            y_base + altura,
            largura / 2 - 5,
            altura,
            "Atividade específica",
            self.dados.get("cnae_atividade_especifica", ""),
        )
        _draw_label_value(
            c,
            margem,
            y_base,
            largura / 2 - 5,
            altura,
            "Art. 219",
            self.dados.get("cnae_art_219", ""),
        )
        _draw_label_value(
            c,
            margem + largura / 2,
            y_base,
            largura / 2 - 5,
            altura,
            "Trecho do Contrato que caracteriza Cessão de mão de obra",
            self.dados.get("trecho_contrato_cessao", ""),
            fontsize=8,
        )

        obs = self.dados.get("observacoes_legais", [])
        texto = "\n".join(f"• {item}" for item in obs)
        _draw_label_value(
            c,
            margem,
            y_base + altura + 140,
            largura,
            80,
            "Legislação",
            texto,
            fontsize=8,
        )

    def _desenhar_rodape(self, c: canvas.Canvas) -> None:
        c.setFillColor(colors.HexColor("#F7931E"))
        c.rect(0, 0, self.width, 25, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(self.width / 2, 10, "www.taxs.com.br")
        c.setFillColor(colors.black)


def gerar_mapa_pdf(dados_mapa: Dict[str, Any], caminho_pdf_saida: str) -> None:
    gerador = PDFMapaGenerator(dados_mapa)
    gerador.gerar(caminho_pdf_saida)
