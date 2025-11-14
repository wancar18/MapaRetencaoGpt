"""Configurações globais e constantes do sistema de automação do MAPA.

Dependências externas necessárias:
    pip install reportlab PyPDF2 pdf2image pytesseract pillow pandas xlwings openai
    pip install pyautogui mouse pyperclip python-dotenv
    pip install tk (quando aplicável em distribuições Linux)

O projeto destina-se ao Windows 10+ e Python 3.8+. Antes de empacotar com
PyInstaller, verifique as dependências do Tesseract e do Microsoft Visual C++.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from tkinter import filedialog, messagebox, Tk

CAMINHO_REDE = r"\\\\192.168.200.2\\update"
MAPA_TEMPLATE_NAME = "mapa - Copia.xlsx"

TESSERACT_CMD_DEFAULT = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
TESSDATA_PREFIX_DEFAULT = r"C:\\Program Files\\Tesseract-OCR\\tessdata"

OPENAI_MODEL_DEFAULT = "gpt-4.1-mini"


class FatalConfigurationError(RuntimeError):
    """Erro fatal na configuração inicial."""


def _create_root() -> Tk:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return root


def verificar_rede() -> None:
    """Valida a disponibilidade da rede interna.

    Exibe mensagem e encerra o programa caso o caminho não esteja acessível.
    """
    if not Path(CAMINHO_REDE).exists():
        root = _create_root()
        messagebox.showerror(
            "Rede interna não encontrada",
            (
                "Não foi possível localizar a rede interna da Taxs.\n"
                "Verifique a conexão e tente novamente.\n"
                f"Caminho inacessível: {CAMINHO_REDE}"
            ),
        )
        root.destroy()
        raise FatalConfigurationError("Rede interna indisponível")


def app_dir() -> Path:
    """Retorna a pasta base da aplicação, considerando execução com PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def user_dir() -> Path:
    """Retorna o diretório de dados do usuário (LOCALAPPDATA\\Taxs\\Automacao)."""
    base = Path(os.getenv("LOCALAPPDATA", Path.home()))
    target = base / "Taxs" / "Automacao"
    target.mkdir(parents=True, exist_ok=True)
    return target


def asset_path(name: str, writable: bool = False, optional: bool = False) -> Path:
    """Obtém o caminho para um asset estático ou editável.

    Quando writable=True, o arquivo é copiado para o diretório do usuário caso
    ainda não exista. Caso não seja encontrado e optional=False, solicita ao
    usuário a seleção manual do arquivo.
    """
    source_candidates = [app_dir() / name]
    if name.lower() == MAPA_TEMPLATE_NAME.lower():
        source_candidates.extend(
            app_dir() / alt
            for alt in (
                "mapa.xlsx",
                "MAPA.xlsx",
                "Mapa.xlsx",
                "mapa - Copia.xlsm",
                "mapa.xlsm",
            )
        )

    for candidate in source_candidates:
        if candidate.exists():
            if not writable:
                return candidate
            target = user_dir() / name
            if not target.exists():
                target.write_bytes(candidate.read_bytes())
            return target

    if optional:
        raise FileNotFoundError(name)

    root = _create_root()
    messagebox.showwarning(
        "Arquivo não localizado",
        (
            f"Não foi possível localizar o arquivo '{name}'.\n"
            "Selecione manualmente o arquivo correspondente."
        ),
    )
    selected = filedialog.askopenfilename(
        title=f"Selecione o arquivo para {name}",
        initialdir=str(app_dir()),
    )
    root.destroy()

    if not selected:
        raise FatalConfigurationError(f"Arquivo obrigatório ausente: {name}")

    target = user_dir() / name
    target.write_bytes(Path(selected).read_bytes())
    return target


def carregar_json(path: Path, default: Optional[dict] = None) -> dict:
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + ".bak")
        backup.write_bytes(path.read_bytes())
        return default or {}


def salvar_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
