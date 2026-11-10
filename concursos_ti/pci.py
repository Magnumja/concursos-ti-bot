"""Coleta de concursos no PCI Concursos (páginas públicas de busca por cargo).

O site lista, por termo de cargo, concursos abertos (classes ``na``/``da``) e
encerrados (``ea``). Só os abertos interessam. Os PDFs de edital ficam atrás de
um captcha, então o bot aponta para a página do concurso em vez de baixá-los.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

from .modelos import Detalhe, ItemLista

log = logging.getLogger(__name__)

BASE = "https://www.pciconcursos.com.br"
USER_AGENT = "concursos-ti-bot/1.0 (+https://github.com/Magnumja/concursos-ti-bot)"

# Termos de busca por cargo; cada um vira BASE/vagas/<termo>.
TERMOS = [
    "tecnologia-da-informacao",
    "informatica",
    "tecnico-de-informatica",
    "analista-de-sistemas",
    "sistemas",
    "programador",
    "desenvolvedor",
    "software",
    "suporte",
    "infraestrutura",
    "banco-de-dados",
    "dados",
    "ciencia-de-dados",
    "seguranca-da-informacao",
    "computacao",
]

_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_SALARIO = re.compile(r"R\$\s*([\d.]+,\d{2})")


class Cliente:
    """HTTP educado: identifica o bot, espera entre requisições e tenta de novo."""

    def __init__(self, pausa: float = 0.6, timeout: float = 30, tentativas: int = 3):
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = USER_AGENT
        self.pausa, self.timeout, self.tentativas = pausa, timeout, tentativas

    def get(self, url: str) -> str:
        erro: Exception | None = None
        for n in range(self.tentativas):
            try:
                r = self.sessao.get(url, timeout=self.timeout)
                r.raise_for_status()
                r.encoding = "utf-8"
                time.sleep(self.pausa)
                return r.text
            except requests.RequestException as e:  # rede instável: tenta de novo
                erro = e
                time.sleep(self.pausa * (n + 2))
        raise RuntimeError(f"falha ao buscar {url}: {erro}")


def _iso(d: tuple[str, str, str]) -> str:
    dia, mes, ano = d
    try:
        return date(int(ano), int(mes), int(dia)).isoformat()
    except ValueError:
        return ""


def _moeda(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse_lista(html: str) -> list[ItemLista]:
    """Extrai os concursos de uma página de busca/listagem."""
    itens = []
    for div in BeautifulSoup(html, "html.parser").select("div[data-url]"):
        a = div.select_one(".ca a")
        if not a:
            continue
        cd = div.select_one(".cd")
        linhas = list(cd.stripped_strings) if cd else []
        resumo = linhas[0] if linhas else ""
        sal = _SALARIO.search(resumo)
        vagas = re.sub(r"\s*até R\$.*", "", resumo).strip()
        if not re.search(r"\d", vagas):
            vagas = ""
        ce = div.select_one(".ce")
        datas = [_iso(d) for d in _DATA.findall(ce.get_text(" ") if ce else "")]
        cc = div.select_one(".cc")
        uf = cc.get_text(strip=True).replace("\xa0", "") if cc else ""
        itens.append(
            ItemLista(
                url=div["data-url"],
                orgao=a.get_text(strip=True),
                titulo=a.get("title", ""),
                uf=uf,
                vagas=vagas,
                salario_max=_moeda(sal.group(1)) if sal else None,
                nivel=linhas[-1] if len(linhas) >= 2 else "",
                inscricao_inicio=datas[0] if len(datas) > 1 else "",
                inscricao_fim=datas[-1] if datas else "",
                aberto="ea" not in (div.get("class") or []),
            )
        )
    return itens


def parse_detalhe(html: str) -> Detalhe:
    """Extrai título, cargos, parágrafos, links e nomes dos editais da notícia."""
    sopa = BeautifulSoup(html, "html.parser")
    art = sopa.find("article") or sopa
    h1 = art.find("h1")

    def limpo(tag) -> str:
        return re.sub(r"\s+", " ", tag.get_text(" ")).strip()

    det = Detalhe(titulo=limpo(h1) if h1 else "")
    det.cargos = [t for t in (limpo(li) for li in art.find_all("li")) if t]
    for p in art.find_all("p"):
        texto = limpo(p)
        if not texto:
            continue
        det.paragrafos.append(texto)
        for a in p.select("a[data-link-noticia]"):
            det.links.append((limpo(a), texto))
    det.editais = [a.get("title") or limpo(a) for a in sopa.select("a.edital-pdf-link")]
    return det


def listar_candidatos(cliente: Cliente, termos: list[str] = TERMOS) -> list[ItemLista]:
    """Junta os concursos abertos de todas as buscas, sem repetir URL."""
    vistos: dict[str, ItemLista] = {}
    falhas = 0
    for termo in termos:
        try:
            html = cliente.get(f"{BASE}/vagas/{termo}")
        except RuntimeError as e:
            falhas += 1
            log.warning("%s", e)
            continue
        for item in parse_lista(html):
            if item.aberto:
                vistos.setdefault(item.url, item)
    if falhas == len(termos):
        raise RuntimeError("nenhuma busca do PCI Concursos respondeu")
    log.info("%d concursos abertos candidatos em %d buscas", len(vistos), len(termos))
    return list(vistos.values())
