"""Filtro de cargos de TI e análise do concurso (taxa, prova, banca, o que estudar)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from .modelos import Concurso, Detalhe, ItemLista


def norm(s: str) -> str:
    """Minúsculas, sem acento e com espaços simples — base para todos os regex."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


_TI = re.compile(
    r"""
    tecnologia\ d[ae]\ informacao | \bt\.?i\.?c?\b | informatica
  | sistemas?\ de\ informacao | analis(?:ta|e)\ de\ sistemas?
  | desenvolv\w+\ de\ (?:sistemas?|software|aplicac) | \bprogramad | \bdesenvolvedor
  | software | banco\ de\ dados | \bdba\b | processamento\ de\ dados
  | (?:ciencia|cientista|engenh\w+|analis\w+|arquitet\w+)\ de\ dados
  | redes?\ de\ (?:computador|dados|comunicac) | (?:administrador|analista|tecnico)\ de\ redes?
  | seguranca\ (?:da|de|em)\ (?:informacao|ti\b) | ciberne | \bcomputacao\b | computadores
  | \bweb\ ?(?:designer|master|desenvolv) | devops | service\ desk | help\ ?desk
  | suporte\ (?:tecnico|em\ ti|de\ ti|a\ usuario|computacional|de\ informatica)
  | tecnico\ de\ suporte | inteligencia\ artificial
  | infraestrutura\ de\ (?:ti\b|redes|tecnologia)
    """,
    re.X,
)
# "Suporte técnico" que é nome de carreira administrativa, não de TI.
_FALSO_SUPORTE = re.compile(r"profissional de suporte tecnico|suporte administrativ\w*")

# perfil -> (regex no cargo, rótulo, tópicos para estudar)
PERFIS: dict[str, tuple[str, str, list[str]]] = {
    "dev": (
        r"programad|desenvolv|software|analis(?:ta|e) de sistemas|sistemas de informacao|\bweb",
        "Desenvolvimento",
        ["Lógica e algoritmos", "Estruturas de dados", "POO", "Java / Python / JavaScript",
         "SQL e modelagem", "APIs REST", "Git", "Testes", "Engenharia de software (ágil, UML)"],
    ),
    "infra": (
        r"\bredes?\b|infraestrutura|devops|nuvem|cloud|telecom",
        "Infraestrutura e Redes",
        ["TCP/IP e modelo OSI", "Roteamento e switching", "Linux e Windows Server",
         "DNS, DHCP e Active Directory", "Virtualização e contêineres", "Computação em nuvem",
         "Backup e alta disponibilidade", "Monitoramento"],
    ),
    "suporte": (
        r"suporte|help ?desk|service desk|tecnic\w+ (?:em|de) informatica|manutenc",
        "Suporte",
        ["Hardware e manutenção", "Windows e Linux", "Redes (cabeamento, Wi-Fi, TCP/IP)",
         "Pacote Office / LibreOffice", "Segurança básica e backup", "ITIL e atendimento ao usuário"],
    ),
    "dados": (
        r"\bdados\b|\bdba\b|business intelligence|\bbi\b",
        "Dados",
        ["SQL avançado", "Modelagem relacional e dimensional", "ETL e Data Warehouse",
         "BI e visualização", "Python para dados", "Estatística", "Big Data e NoSQL", "LGPD"],
    ),
    "seguranca": (
        r"seguranca|ciberne",
        "Segurança da Informação",
        ["Criptografia e certificação digital", "ISO 27001/27002", "Ataques e malwares",
         "Firewall, IDS/IPS e VPN", "Gestão de identidades", "Gestão de riscos", "LGPD",
         "Resposta a incidentes"],
    ),
    "docencia": (
        r"professor|instrutor|docente",
        "Docência",
        ["Conteúdo específico da disciplina (veja o edital)", "Didática e prova de aula",
         "Plano de aula e títulos", "Legislação educacional (LDB)"],
    ),
    "geral": (
        r"$^",  # nunca casa: é o perfil de quem não caiu em nenhum outro
        "TI — visão geral",
        ["Engenharia de software", "Banco de dados e SQL", "Redes de computadores",
         "Segurança da informação", "Sistemas operacionais", "Governança (ITIL, COBIT)",
         "Gestão de projetos (PMBOK, Scrum)"],
    ),
}
BASE_COMUM = ["Língua Portuguesa", "Raciocínio lógico", "Legislação do órgão", "Inglês técnico"]

# regex (texto normalizado) -> (nome, site, estilo de prova)
BANCAS: list[tuple[str, str, str, str]] = [
    (r"cebraspe|cespe", "Cebraspe", "www.cebraspe.org.br",
     "itens de certo/errado, em que um erro costuma anular um acerto — só marque o que souber"),
    (r"\bfgv\b|getulio vargas", "FGV", "conhecimento.fgv.br/concursos",
     "questões longas e interpretativas, com casos práticos"),
    (r"\bfcc\b|carlos chagas", "FCC", "www.concursosfcc.com.br",
     "cobrança literal de conceitos e de lei seca"),
    (r"vunesp", "Vunesp", "www.vunesp.com.br", "questões diretas, com muito português e interpretação"),
    (r"cesgranrio", "Cesgranrio", "www.cesgranrio.org.br", "questões objetivas com foco em aplicação prática"),
    (r"\bibfc\b", "IBFC", "www.ibfc.org.br", ""),
    (r"idecan", "Idecan", "www.idecan.org.br", ""),
    (r"\baocp\b", "Instituto AOCP", "www.institutoaocp.org.br", ""),
    (r"quadrix", "Quadrix", "www.quadrix.org.br", ""),
    (r"consulplan", "Consulplan", "www.institutoconsulplan.org.br", ""),
    (r"fundatec", "Fundatec", "www.fundatec.org.br", ""),
    (r"\biades\b", "Iades", "www.iades.com.br", ""),
    (r"\bibade\b", "Ibade", "www.ibade.org.br", ""),
    (r"fepese", "Fepese", "www.fepese.org.br", ""),
    (r"selecon", "Selecon", "www.selecon.org.br", ""),
    (r"fumarc", "Fumarc", "www.fumarc.com.br", ""),
]

_SITE = re.compile(r"^(?:https?://)?[\w-]+(?:\.[\w-]+)+(?:/\S*)?$")
_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])")
_VALOR = re.compile(r"R\$\s*([\d.]+,\d{2})")
_DATA_EXTENSO = re.compile(
    r"\d{1,2}º?(?: (?:e|a) \d{1,2}º?)? de (?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto"
    r"|setembro|outubro|novembro|dezembro)(?: de \d{4})?|\d{2}/\d{2}/\d{4}",
    re.I,
)


def eh_cargo_ti(texto: str) -> bool:
    return bool(_TI.search(_FALSO_SUPORTE.sub(" ", norm(texto))))


def perfis_de(cargos: list[str]) -> list[str]:
    """Perfis de estudo dos cargos, na ordem em que aparecem."""
    achados: list[str] = []
    for cargo in cargos:
        n = norm(cargo)
        casou = [p for p, (rx, _, _) in PERFIS.items() if re.search(rx, n)]
        if "docencia" in casou:  # prova de professor segue outra lógica de estudo
            casou = ["docencia"]
        for p in casou or ["geral"]:
            if p not in achados:
                achados.append(p)
    return achados


def _frases(paragrafos: list[str]) -> list[str]:
    return [f for p in paragrafos for f in _FRASE.split(p)]


def extrair_taxa(paragrafos: list[str]) -> str:
    """Menor e maior valor da taxa de inscrição citados no texto."""
    candidatas = []
    for p in paragrafos:
        for f in _FRASE.split(p):
            m = re.search(r"taxas?\b", f, re.I)
            if m:  # só valores citados depois da palavra "taxa"
                candidatas.insert(0, f[m.end():])
            elif "inscri" in norm(p) and re.match(r"\s*os? valor(?:es)?\b", f, re.I):
                candidatas.append(f)
    for trecho in candidatas:
        valores = sorted(
            (n, v) for v in _VALOR.findall(trecho)
            if (n := float(v.replace(".", "").replace(",", "."))) < 1000  # acima disso é salário
        )
        if valores:
            menor, maior = valores[0][1], valores[-1][1]
            return f"R$ {menor}" if menor == maior else f"R$ {menor} a R$ {maior}"
    return ""


def extrair_prova(paragrafos: list[str]) -> str:
    """Data da prova, como escrita na notícia."""
    for f in _frases(paragrafos):
        n = norm(f)
        if "prova" not in n or re.search(r"inscric|isenc|pagamento|validade", n):
            continue
        if not re.search(r"previst|aplicad|realizad|ocorrer|sera|serao|\bdia\b|acontec", n):
            continue
        m = _DATA_EXTENSO.search(f)
        if m:
            return m.group(0)
    return ""


def extrair_banca(det: Detalhe) -> tuple[str, str]:
    """(banca, site de inscrição) a partir do link no parágrafo de inscrições."""
    alvo = next((t for t, p in det.links if "inscri" in norm(p)), "")
    n = norm(alvo or next((p for p in det.paragrafos if "inscri" in norm(p)), ""))
    eh_site = bool(_SITE.match(alvo))
    for rx, nome, site, _ in BANCAS:
        if re.search(rx, n):
            return nome, (alvo if eh_site else site)
    if eh_site:
        return "", alvo
    nome = re.sub(r"^(?:site|portal) d[aeo]s? ", "", alvo, flags=re.I)
    # Texto genérico de link ("sistema online", "área do candidato") não é nome de banca.
    return (nome if nome[:1].isupper() else ""), ""


def estilo_da_banca(banca: str) -> str:
    return next((e for _, nome, _, e in BANCAS if nome == banca), "")


def uf_do_titulo(titulo: str) -> str:
    m = re.search(r" - ([A-Z]{2}(?:(?:/|, | e )[A-Z]{2})*)\b", titulo)
    return m.group(1) if m else ""


def analisar(item: ItemLista, det: Detalhe, hoje: date) -> Concurso | None:
    """Monta o Concurso se houver cargo de TI; devolve None caso contrário."""
    cargos = list(dict.fromkeys(c for c in det.cargos if eh_cargo_ti(c)))
    if not cargos:
        # Sem cargo de TI na lista: aceita só se o texto citar a área claramente.
        texto = norm(" ".join([det.titulo, *det.paragrafos[:4]]))
        if not re.search(r"tecnologia da informacao|informatica|analista de sistemas", texto):
            return None
    banca, site = extrair_banca(det)
    return Concurso(
        url=item.url,
        orgao=item.orgao,
        uf=item.uf or uf_do_titulo(det.titulo or item.titulo) or "Nacional",
        titulo=det.titulo or item.titulo,
        vagas=item.vagas,
        salario_max=item.salario_max,
        nivel=item.nivel,
        inscricao_inicio=item.inscricao_inicio,
        inscricao_fim=item.inscricao_fim,
        cargos_ti=cargos,
        perfis=perfis_de(cargos) if cargos else ["geral"],
        taxa=extrair_taxa(det.paragrafos),
        prova=extrair_prova(det.paragrafos),
        banca=banca,
        site_inscricao=site,
        editais=det.editais,
        visto_em=hoje.isoformat(),
    )
