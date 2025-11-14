"""Utilidades para manipulação de arquivos e diretórios das NFS-e."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Tuple

from .text_utils import clean_spaces


def organizar_pastas_saida(pasta_origem: Path) -> Tuple[Path, Path, Path]:
    base_saida = pasta_origem / "MAPAS_GERADOS"
    pasta_mapas_pdf = base_saida / "MAPAS_PDF"
    pasta_notas = base_saida / "NOTAS_GERADAS_MAPA"
    pasta_manual = pasta_origem / "Notas_Que_Precisam_Gerar_Mapa_Manual"
    for pasta in (base_saida, pasta_mapas_pdf, pasta_notas, pasta_manual):
        pasta.mkdir(parents=True, exist_ok=True)
    return pasta_mapas_pdf, pasta_notas, pasta_manual


def normalizar_nome_arquivo(path: Path) -> Path:
    novo_nome = clean_spaces(path.stem).replace("/", "-").replace("\\", "-")
    novo_nome = novo_nome[:150]
    novo_path = path.with_name(novo_nome + path.suffix)
    if novo_path == path:
        return path
    if novo_path.exists():
        novo_path = novo_path.with_name(novo_path.stem + "_dup" + novo_path.suffix)
    shutil.move(str(path), str(novo_path))
    return novo_path


def mover_para_manual(path: Path, pasta_manual: Path, motivo: str) -> None:
    destino = pasta_manual / path.name
    shutil.move(str(path), str(destino))
    print(f"[Arquivo] Nota movida para manual ({motivo}): {destino}")


def mover_para_processadas(path: Path, pasta_destino: Path) -> Path:
    destino = pasta_destino / path.name
    shutil.move(str(path), str(destino))
    return destino
