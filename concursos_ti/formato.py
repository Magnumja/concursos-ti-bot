"""Mensagens do Telegram (HTML) — cartão completo, lista resumida e botões."""
from __future__ import annotations

import hashlib
from datetime import date
from html import escape
from urllib.parse import quote

from .analise import BASE_COMUM, PERFIS, estilo_da_banca
from .modelos import Concurso

LIMITE = 4000  # o Telegram aceita 4096 caracteres por mensagem
MAX_CARGOS = 8


def id_curto(c: Concurso) -> str:
    """Identificador estável e curto, usado no comando /ver_<id>."""
    return hashlib.md5(c.chave.encode()).hexdigest()[:6]


def data_br(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else ""


def dias_restantes(c: Concurso, hoje: date) -> int | None:
    return (date.fromisoformat(c.inscricao_fim) - hoje).days if c.inscricao_fim else None


def moeda(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _prazo(c: Concurso, hoje: date) -> str:
    d = dias_restantes(c, hoje)
    if d is None:
        return ""
    if c.inscricao_inicio and date.fromisoformat(c.inscricao_inicio) > hoje:
        return f"🕓 Abre em {data_br(c.inscricao_inicio)}"
    if d == 0:
        return "🚨 Último dia"
    if d <= 5:
        return f"⏳ Últimos {d} dias" if d > 1 else "⏳ Encerra amanhã"
    return f"🗓 Faltam {d} dias"


def _link(texto: str, url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return f'<a href="{escape(url, quote=True)}">{escape(texto)}</a>'


def card(c: Concurso, hoje: date, comunidade: str = "", atualizado: bool = False) -> str:
    """Cartão completo de um concurso, pronto para ler e encaminhar."""
    selos = [s for s in (
        "🔁 Prazo atualizado" if atualizado else "",
        "🔥 Salário alto" if (c.salario_max or 0) >= 10000 else "",
        _prazo(c, hoje),
    ) if s]
    L = [f"🖥 <b>{escape(c.orgao)}</b> · {escape(c.uf)}"]
    if selos:
        L.append(" · ".join(selos))

    L.append("")
    if c.cargos_ti:
        L.append("💼 <b>Cargos de TI</b>")
        for cargo in c.cargos_ti[:MAX_CARGOS]:
            L.append("• " + escape(cargo if len(cargo) <= 140 else cargo[:137] + "…"))
        if len(c.cargos_ti) > MAX_CARGOS:
            L.append(f"<i>… e mais {len(c.cargos_ti) - MAX_CARGOS} no edital</i>")
    else:
        L.append("💼 <b>Área de TI citada no edital</b> — confira os cargos na página")

    L.append("")
    if c.salario_max:
        L.append(f"💰 <b>Salário:</b> até {moeda(c.salario_max)}")
    if c.vagas:
        L.append(f"👥 <b>Vagas no concurso:</b> {escape(c.vagas)}")
    if c.nivel:
        L.append(f"🎓 <b>Nível:</b> {escape(c.nivel)}")
    if c.inscricao_fim:
        periodo = f"{data_br(c.inscricao_inicio)} a " if c.inscricao_inicio else "até "
        L.append(f"🗓 <b>Inscrições:</b> {periodo}{data_br(c.inscricao_fim)}")
    L.append(f"💳 <b>Taxa:</b> {escape(c.taxa) if c.taxa else 'ver edital'}")
    if c.prova:
        L.append(f"📝 <b>Prova:</b> {escape(c.prova)}")
    if c.banca or c.site_inscricao:
        site = _link(c.site_inscricao.removeprefix("https://"), c.site_inscricao) if c.site_inscricao else ""
        rotulo = "Banca" if c.banca else "Inscrição"
        L.append(f"🏛 <b>{rotulo}:</b> " + " — ".join(x for x in (escape(c.banca), site) if x))
    edital = escape(c.editais[0].title() if c.editais else "Edital")
    L.append(f'📄 <b>Edital:</b> {edital} — {_link("baixar na página do concurso", c.url)}')

    L.append("")
    L.append("📚 <b>O que estudar</b>")
    for p in c.perfis[:3]:
        _, rotulo, topicos = PERFIS[p]
        L.append(f"<b>{rotulo}:</b> {escape(', '.join(topicos))}")
    L.append(f"<b>Base comum:</b> {', '.join(BASE_COMUM)}")
    estilo = estilo_da_banca(c.banca)
    if estilo:
        L.append(f"🎯 <b>Estilo {escape(c.banca)}:</b> {estilo}")
    L.append("<i>Guia pelo perfil do cargo — o conteúdo oficial é o do edital.</i>")

    if comunidade:
        L.append("")
        L.append(f"👥 <b>Comunidade:</b> {escape(comunidade)}")
    return "\n".join(L)[:LIMITE]


def teclado(c: Concurso, comunidade: str = "") -> dict:
    """Botões: edital, compartilhar e comunidade."""
    texto = f"🖥 Concurso de TI: {c.orgao} ({c.uf})"
    if c.salario_max:
        texto += f" — até {moeda(c.salario_max)}"
    compartilhar = f"https://t.me/share/url?url={quote(c.url, safe='')}&text={quote(texto)}"
    linhas = [[
        {"text": "📄 Edital e inscrição", "url": c.url},
        {"text": "📤 Compartilhar", "url": compartilhar},
    ]]
    if comunidade.startswith("https://"):
        linhas.append([{"text": "👥 Entrar na comunidade", "url": comunidade}])
    return {"inline_keyboard": linhas}


def linha_resumo(c: Concurso, hoje: date) -> str:
    partes = [f"até {moeda(c.salario_max)}" if c.salario_max else "", _prazo(c, hoje)]
    extra = " · ".join(p for p in partes if p)
    return f"<b>{escape(c.orgao)}</b> ({escape(c.uf)})\n{extra}\nDetalhes: /ver_{id_curto(c)}"


def lista(concursos: list[Concurso], hoje: date, titulo: str, comunidade: str = "") -> list[str]:
    """Lista resumida, quebrada em mensagens que cabem no limite do Telegram."""
    if not concursos:
        return [f"<b>{escape(titulo)}</b>\n\nNada encontrado agora. Tente /concursos."]
    rodape = f"\n\n👥 Comunidade: {escape(comunidade)}" if comunidade else ""
    mensagens, atual = [], f"<b>{escape(titulo)}</b> — {len(concursos)}"
    for c in concursos:
        bloco = "\n\n" + linha_resumo(c, hoje)
        if len(atual) + len(bloco) + len(rodape) > LIMITE:
            mensagens.append(atual)
            atual = bloco.lstrip()
        else:
            atual += bloco
    mensagens.append(atual + rodape)
    return mensagens
