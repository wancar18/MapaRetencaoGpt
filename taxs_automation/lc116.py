"""Manipulação dos subitens da LC 116/2003."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .openai_client import OpenAIHelper
from .text_utils import get_close_match, buscar_codigos_lc116, normalize_text


@dataclass
class LC116Resultado:
    codigo: Optional[str]
    descricao: Optional[str]
    origem: str


class LC116Mapa:
    def __init__(self, mapa: Dict[str, str]) -> None:
        self._mapa = mapa

    @classmethod
    def from_file(cls, path: Path) -> "LC116Mapa":
        mapa: Dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                codigo, descricao = line.split("-", 1)
                mapa[codigo.strip()] = descricao.strip()
            except ValueError:
                continue
        return cls(mapa)

    def descricao(self, codigo: str) -> Optional[str]:
        return self._mapa.get(codigo.strip())

    def buscar_por_descricao(self, descricao: str, cutoff: float = 0.6) -> Optional[Tuple[str, str, float]]:
        match = get_close_match(descricao, self._mapa.values(), cutoff=cutoff)
        if not match:
            return None
        descricao_encontrada, score = match
        for codigo, desc in self._mapa.items():
            if normalize_text(desc) == normalize_text(descricao_encontrada):
                return codigo, desc, score
        return None

    def contains(self, codigo: str) -> bool:
        return codigo in self._mapa


class LC116Resolver:
    def __init__(self, mapa: LC116Mapa, servicos_txt: str, helper: OpenAIHelper) -> None:
        self._mapa = mapa
        self._servicos_txt = servicos_txt
        self._helper = helper

    def lc116_from_nota(self, texto: str) -> Optional[LC116Resultado]:
        candidatos = buscar_codigos_lc116(texto)
        for codigo in candidatos:
            if self._mapa.contains(codigo):
                return LC116Resultado(codigo=codigo, descricao=self._mapa.descricao(codigo), origem="nota")
        return None

    def lc116_from_descricao(self, descricao_servico: str) -> Optional[LC116Resultado]:
        if not descricao_servico:
            return None
        match = self._mapa.buscar_por_descricao(descricao_servico)
        if match:
            codigo, desc, score = match
            origem = f"match_descricao({score:.2f})"
            return LC116Resultado(codigo, desc, origem)
        return None

    def lc116_from_api(self, contexto: str) -> Optional[LC116Resultado]:
        system_prompt = (
            "Você é um assistente especialista em legislação tributária brasileira."
            " Retorne SOMENTE o código do subitem da LC 116/2003 no formato X.XX,"
            " se conseguir identificá-lo com base na descrição do serviço e na lista a seguir."
        )
        user_prompt = (
            "Lista oficial de subitens da LC 116/2003:\n"
            f"{self._servicos_txt}\n\n"
            "Descrição/Contexto:\n"
            f"{contexto}\n\n"
            "Se não tiver certeza absoluta, responda apenas 'NAO IDENTIFICADO'."
        )
        resposta = self._helper.chat_completion(system_prompt, user_prompt)
        codigo = resposta.content.strip().replace(" ", "")
        if codigo.upper() == "NAOIDENTIFICADO":
            return None
        if self._mapa.contains(codigo):
            return LC116Resultado(codigo, self._mapa.descricao(codigo), origem="api")
        return None

    def escolher_com_consenso(
        self,
        texto_nota: str,
        descricao_servico: str,
        max_rodadas: int = 3,
    ) -> Optional[LC116Resultado]:
        ultima_api: Optional[LC116Resultado] = None
        for rodada in range(1, max_rodadas + 1):
            resultados: List[LC116Resultado] = []
            api_res = self.lc116_from_api(
                f"Rodada {rodada}. Descrição: {descricao_servico}. Texto complementar: {texto_nota[:2000]}"
            )
            if api_res:
                resultados.append(api_res)
                ultima_api = api_res

            nota_res = self.lc116_from_nota(texto_nota)
            if nota_res:
                resultados.append(nota_res)

            desc_res = self.lc116_from_descricao(descricao_servico)
            if desc_res:
                resultados.append(desc_res)

            if not resultados:
                continue

            contagem: Dict[str, List[LC116Resultado]] = {}
            for res in resultados:
                contagem.setdefault(res.codigo or "", []).append(res)

            for codigo, ocorrencias in contagem.items():
                if codigo and len(ocorrencias) >= 2 and self._mapa.contains(codigo):
                    return LC116Resultado(codigo, self._mapa.descricao(codigo), origem="consenso")
        return ultima_api


__all__ = ["LC116Mapa", "LC116Resolver", "LC116Resultado"]
