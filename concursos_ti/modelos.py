"""Estruturas de dados compartilhadas."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class ItemLista:
    """Uma linha da listagem de concursos (dados resumidos)."""

    url: str
    orgao: str
    titulo: str = ""
    uf: str = ""
    vagas: str = ""
    salario_max: float | None = None
    nivel: str = ""
    inscricao_inicio: str = ""  # ISO (AAAA-MM-DD) ou vazio
    inscricao_fim: str = ""
    aberto: bool = True


@dataclass
class Detalhe:
    """Conteúdo bruto extraído da página de um concurso."""

    titulo: str = ""
    cargos: list[str] = field(default_factory=list)
    paragrafos: list[str] = field(default_factory=list)
    # (texto do link, parágrafo onde ele aparece)
    links: list[tuple[str, str]] = field(default_factory=list)
    editais: list[str] = field(default_factory=list)


@dataclass
class Concurso:
    """Concurso com vagas de TI, já analisado e pronto para envio."""

    url: str
    orgao: str
    uf: str = ""
    titulo: str = ""
    vagas: str = ""
    salario_max: float | None = None
    nivel: str = ""
    inscricao_inicio: str = ""
    inscricao_fim: str = ""
    cargos_ti: list[str] = field(default_factory=list)
    perfis: list[str] = field(default_factory=list)
    taxa: str = ""
    prova: str = ""
    banca: str = ""
    site_inscricao: str = ""
    editais: list[str] = field(default_factory=list)
    visto_em: str = ""

    @property
    def chave(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]

    def para_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict) -> "Concurso":
        nomes = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in nomes})
