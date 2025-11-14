"""Rotinas de extração de texto de PDFs com fallback OCR."""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Iterable

import pytesseract
from PIL import Image
from PyPDF2 import PdfReader
from pdf2image import convert_from_path

from .config import TESSDATA_PREFIX_DEFAULT, TESSERACT_CMD_DEFAULT


pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD", TESSERACT_CMD_DEFAULT
)
os.environ.setdefault("TESSDATA_PREFIX", os.getenv("TESSDATA_PREFIX", TESSDATA_PREFIX_DEFAULT))


def extrair_texto_pdf(pdf_path: Path) -> str:
    """Tenta extrair texto nativo do PDF com PyPDF2."""
    try:
        reader = PdfReader(str(pdf_path))
        texto = "\n".join(page.extract_text() or "" for page in reader.pages)
        return texto.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[OCR] Falha na extração nativa do PDF {pdf_path.name}: {exc}")
        return ""


def _ocr_paginas(images: Iterable[Image.Image]) -> str:
    texto_final: list[str] = []
    for idx, imagem in enumerate(images, start=1):
        try:
            buffer = io.BytesIO()
            imagem.save(buffer, format="PNG")
            buffer.seek(0)
            texto = pytesseract.image_to_string(Image.open(buffer), lang="por")
            texto_final.append(texto)
        except Exception as exc:  # noqa: BLE001
            print(f"[OCR] Falha no OCR da página {idx}: {exc}")
    return "\n".join(texto_final)


def extrair_texto_inteligente(pdf_path: Path) -> str:
    """Extrai texto usando método nativo e fallback OCR."""
    texto = extrair_texto_pdf(pdf_path)
    if len(texto) > 500:
        return texto

    try:
        imagens = convert_from_path(str(pdf_path), dpi=300)
        texto_ocr = _ocr_paginas(imagens)
        if len(texto_ocr) > len(texto):
            return texto_ocr
        return texto
    except Exception as exc:  # noqa: BLE001
        print(f"[OCR] Falha ao converter PDF para imagens ({pdf_path.name}): {exc}")
        return texto
