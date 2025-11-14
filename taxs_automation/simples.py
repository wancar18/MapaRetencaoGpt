"""Automação e análise de optantes do Simples Nacional e SIMEI."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pyautogui
import pyperclip

from .config import carregar_json, salvar_json, user_dir
from .openai_client import OpenAIHelper


CONSULTA_URL = "https://www8.receita.fazenda.gov.br/SimplesNacional/aplicacoes.aspx?id=21"
CACHE_FILENAME = "consulta_simples_cache.json"


@dataclass
class SimplesResultado:
    texto_consulta: str
    optante: Optional[bool]
    simei: Optional[str]


class SimplesCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = carregar_json(path, default={})

    def obter(self, cnpj: str) -> Optional[dict]:
        return self.data.get(cnpj)

    def registrar(self, cnpj: str, resultado: dict) -> None:
        self.data[cnpj] = resultado
        salvar_json(self.path, self.data)


def abrir_chrome_e_site() -> None:
    print("[Simples] Abrindo navegador para consulta...")
    pyautogui.hotkey("win", "r")
    time.sleep(1)
    pyautogui.typewrite("chrome\n")
    time.sleep(2)
    pyautogui.typewrite(CONSULTA_URL + "\n")
    time.sleep(5)


def consultar_simples_via_automacao(cnpj: str) -> str:
    print(f"[Simples] Consultando CNPJ {cnpj}...")
    pyautogui.hotkey("ctrl", "l")
    pyautogui.typewrite(CONSULTA_URL + "\n")
    time.sleep(5)
    pyautogui.press("tab", presses=5, interval=0.3)
    pyautogui.typewrite(cnpj)
    pyautogui.press("enter")
    time.sleep(5)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.5)
    return pyperclip.paste()


def analisar_optante_openai(helper: OpenAIHelper, texto: str, data_emissao: str) -> Optional[bool]:
    prompt = (
        "Determine se a empresa era optante do Simples Nacional na data informada.\n"
        f"Data de emissão: {data_emissao}\n"
        f"Texto completo da consulta:\n{texto}\n\n"
        "Responda apenas com: optante / nao optante / nao identificado."
    )
    resp = helper.chat_completion("Análise Simples Nacional", prompt)
    conteudo = resp.content.lower().strip()
    if "optante" == conteudo or conteudo == "optante":
        return True
    if conteudo in {"nao optante", "não optante"}:
        return False
    return None


def analisar_simei_openai(helper: OpenAIHelper, texto: str, data_emissao: str) -> Optional[str]:
    prompt = (
        "Determine se a empresa era enquadrada como SIMEI na data informada.\n"
        f"Data de emissão: {data_emissao}\n"
        f"Texto completo:\n{texto}\n\n"
        "Responda com: simei / nao_simei / nao_identificado."
    )
    resp = helper.chat_completion("Análise SIMEI", prompt)
    conteudo = resp.content.lower().strip()
    if conteudo in {"simei", "não simei", "nao simei", "nao_simei"}:
        return conteudo.replace(" ", "_")
    if conteudo == "nao_identificado":
        return None
    return conteudo


def obter_status_simples(
    helper: OpenAIHelper,
    cnpj: str,
    data_emissao: str,
    cache: Optional[SimplesCache] = None,
    usar_automacao: bool = False,
) -> SimplesResultado:
    if cache:
        cached = cache.obter(cnpj)
        if cached:
            return SimplesResultado(
                texto_consulta=cached.get("texto", ""),
                optante=cached.get("optante"),
                simei=cached.get("simei"),
            )

    texto_consulta = ""
    if usar_automacao:
        abrir_chrome_e_site()
        texto_consulta = consultar_simples_via_automacao(cnpj)

    if not texto_consulta:
        texto_consulta = "Consulta não automatizada realizada manualmente."

    optante = analisar_optante_openai(helper, texto_consulta, data_emissao)
    simei = analisar_simei_openai(helper, texto_consulta, data_emissao)

    resultado = SimplesResultado(texto_consulta, optante, simei)
    if cache:
        cache.registrar(
            cnpj,
            {
                "texto": texto_consulta,
                "optante": optante,
                "simei": simei,
            },
        )
    return resultado


def cache_path() -> Path:
    return user_dir() / CACHE_FILENAME
