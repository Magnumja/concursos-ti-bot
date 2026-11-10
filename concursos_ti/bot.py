"""Regras do bot: atualizar concursos, enviar novidades e responder comandos."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import formato
from .analise import ESTADOS, analisar, norm, uf_de, ufs_do_concurso
from .modelos import Concurso
from .pci import Cliente, listar_candidatos, parse_detalhe
from .telegram import Telegram, TelegramErro

log = logging.getLogger(__name__)

AJUDA = """🖥 <b>Concursos de TI</b>
Concursos públicos abertos com vagas de tecnologia, já filtrados e analisados.

/concursos — todos os abertos, por prazo
/novos — os que entraram nos últimos 7 dias
/prazo — inscrições que encerram em até 7 dias
/top — maiores salários
/estado MS ou /estado Mato Grosso do Sul — filtra por estado
/estado — quantos concursos há em cada estado
/buscar termo — órgão, cargo ou cidade
/comunidade — link da comunidade
/parar — deixa de receber os avisos

Cada concurso traz cargos de TI, salário, taxa, datas, banca, edital e o que estudar."""

COMANDOS = [
    ("concursos", "Concursos de TI abertos"),
    ("novos", "Novidades da semana"),
    ("prazo", "Encerram em até 7 dias"),
    ("top", "Maiores salários"),
    ("estado", "Filtrar: /estado MS ou /estado Mato Grosso do Sul"),
    ("buscar", "Buscar: /buscar analista"),
    ("comunidade", "Link da comunidade"),
    ("ajuda", "Como usar"),
]


def hoje_br() -> date:
    """Data em Brasília (UTC-3, sem horário de verão)."""
    return datetime.now(timezone(timedelta(hours=-3))).date()


@dataclass
class Config:
    token: str = ""
    chats: list[str] = field(default_factory=list)
    comunidade: str = ""
    max_envio: int = 10
    intervalo_horas: float = 6
    ufs: set[str] = field(default_factory=set)
    data_dir: Path = Path("data")
    api_base: str = "https://api.telegram.org"

    @classmethod
    def do_ambiente(cls, env=os.environ) -> "Config":
        def lista(nome: str) -> list[str]:
            return [x.strip() for x in env.get(nome, "").split(",") if x.strip()]

        return cls(
            token=env.get("TELEGRAM_BOT_TOKEN", "").strip(),
            chats=lista("TELEGRAM_CHAT_ID"),
            comunidade=env.get("COMMUNITY_URL", "").strip(),
            max_envio=int(env.get("MAX_ENVIO") or 10),
            intervalo_horas=float(env.get("INTERVALO_HORAS") or 6),
            ufs={uf_de(u) or u.upper() for u in lista("UFS")},
            data_dir=Path(env.get("DATA_DIR") or "data"),
            api_base=env.get("TELEGRAM_API_BASE") or "https://api.telegram.org",
        )


class Estado:
    """Concursos conhecidos, o que já foi enviado e quem está inscrito (JSON em disco)."""

    def __init__(self, pasta: Path):
        self.pasta = Path(pasta)
        self.concursos: dict[str, Concurso] = {}
        self.ignorados: dict[str, str] = {}  # url sem vaga de TI -> fim das inscrições
        self.enviados: dict[str, str] = {}  # chave -> fim das inscrições já avisado
        self.inscritos: list[int] = []
        self._trava = threading.Lock()

    @classmethod
    def carregar(cls, pasta: Path) -> "Estado":
        e = cls(pasta)
        d = _ler(e.pasta / "estado.json", {})
        e.concursos = {k: Concurso.de_dict(v) for k, v in d.get("concursos", {}).items()}
        e.ignorados = d.get("ignorados", {})
        e.enviados = d.get("enviados", {})
        e.inscritos = _ler(e.pasta / "inscritos.json", [])
        return e

    def salvar(self) -> None:
        with self._trava:
            self.pasta.mkdir(parents=True, exist_ok=True)
            _gravar(self.pasta / "estado.json", {
                "concursos": {k: c.para_dict() for k, c in sorted(self.concursos.items())},
                "ignorados": dict(sorted(self.ignorados.items())),
                "enviados": dict(sorted(self.enviados.items())),
            })
            _gravar(self.pasta / "inscritos.json", self.inscritos)


def _ler(caminho: Path, padrao):
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def _gravar(caminho: Path, dados) -> None:
    tmp = caminho.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(caminho)


def atualizar(estado: Estado, cliente: Cliente, hoje: date) -> None:
    """Sincroniza o estado com o site. Só baixa a página de concursos ainda não vistos."""
    iso = hoje.isoformat()
    candidatos = listar_candidatos(cliente)
    por_url = {c.url: c for c in estado.concursos.values()}
    concursos: dict[str, Concurso] = {}
    ignorados: dict[str, str] = {}
    for item in candidatos:
        if item.inscricao_fim and item.inscricao_fim < iso:
            continue
        if item.url in estado.ignorados:
            ignorados[item.url] = item.inscricao_fim
            continue
        c = por_url.get(item.url)
        if c:  # já analisado: só refresca o que muda na listagem (ex.: prorrogação)
            c.inscricao_inicio, c.inscricao_fim = item.inscricao_inicio, item.inscricao_fim
            c.vagas, c.salario_max = item.vagas, item.salario_max
        else:
            try:
                c = analisar(item, parse_detalhe(cliente.get(item.url)), hoje)
            except RuntimeError as e:
                log.warning("%s", e)
                continue
            if c is None:
                ignorados[item.url] = item.inscricao_fim
                continue
            # Retificação costuma virar notícia nova (URL nova) do mesmo órgão:
            # se o prazo não mudou, não avisa de novo.
            for antigo in estado.concursos.values():
                if (antigo.orgao, antigo.uf) == (c.orgao, c.uf) and \
                        estado.enviados.get(antigo.chave) == c.inscricao_fim:
                    estado.enviados[c.chave] = c.inscricao_fim
        concursos[c.chave] = c
    estado.concursos, estado.ignorados = concursos, ignorados
    estado.enviados = {k: f for k, f in estado.enviados.items() if not f or f >= iso}
    log.info("%d concursos de TI abertos", len(concursos))


def ordenados(concursos) -> list[Concurso]:
    """Por prazo de inscrição (os sem data ficam no fim)."""
    return sorted(concursos, key=lambda c: (c.inscricao_fim or "9999", c.orgao))


def _na_uf(c: Concurso, ufs: set[str]) -> bool:
    return not ufs or c.uf == "Nacional" or bool(ufs & ufs_do_concurso(c.uf))


def pendentes(estado: Estado, cfg: Config) -> list[Concurso]:
    """Concursos novos ou com prazo alterado, ainda não avisados."""
    return ordenados(
        c for c in estado.concursos.values()
        if estado.enviados.get(c.chave) != c.inscricao_fim and _na_uf(c, cfg.ufs)
    )


def enviar_novidades(tg: Telegram, estado: Estado, cfg: Config, hoje: date, pausa: float = 1.2) -> int:
    """Envia até ``max_envio`` cartões para os chats configurados e inscritos."""
    chats = list(dict.fromkeys([*cfg.chats, *estado.inscritos]))
    if not chats:
        log.warning("nenhum chat para enviar: defina TELEGRAM_CHAT_ID ou mande /start ao bot")
        return 0
    enviados = 0
    for c in pendentes(estado, cfg)[: cfg.max_envio]:
        texto = formato.card(c, hoje, cfg.comunidade, atualizado=c.chave in estado.enviados)
        entregue = False
        for chat in chats:
            try:
                tg.enviar(chat, texto, formato.teclado(c, cfg.comunidade))
                entregue = True
            except TelegramErro as e:
                log.warning("chat %s: %s", chat, e)
                if e.codigo == 403 and chat in estado.inscritos:  # bloqueou o bot
                    estado.inscritos.remove(chat)
            time.sleep(pausa)
        if entregue:
            estado.enviados[c.chave] = c.inscricao_fim
            enviados += 1
    return enviados


def responder(tg: Telegram, estado: Estado, cfg: Config, msg: dict, hoje: date) -> None:
    """Trata um comando recebido."""
    texto = (msg.get("text") or "").strip()
    if not texto.startswith("/"):
        return
    chat = msg["chat"]["id"]
    cmd, _, arg = texto.partition(" ")
    cmd, arg = cmd[1:].split("@")[0].lower(), arg.strip()
    todos = ordenados(estado.concursos.values())

    def listar(itens, titulo):
        for m in formato.lista(itens, hoje, titulo, cfg.comunidade):
            tg.enviar(chat, m)

    if cmd == "start":
        if chat not in estado.inscritos:
            estado.inscritos.append(chat)
            estado.salvar()
        tg.enviar(chat, AJUDA + f"\n\n✅ Você vai receber os novos concursos aqui. Há {len(todos)} abertos agora: /concursos")
    elif cmd in ("ajuda", "help"):
        tg.enviar(chat, AJUDA)
    elif cmd == "parar":
        if chat in estado.inscritos:
            estado.inscritos.remove(chat)
            estado.salvar()
        tg.enviar(chat, "Avisos desativados. Para voltar, envie /start.")
    elif cmd == "concursos":
        listar(todos, "Concursos de TI abertos")
    elif cmd == "novos":
        corte = (hoje - timedelta(days=7)).isoformat()
        listar([c for c in todos if c.visto_em >= corte], "Novos nos últimos 7 dias")
    elif cmd == "prazo":
        limite = (hoje + timedelta(days=7)).isoformat()
        listar([c for c in todos if c.inscricao_fim and c.inscricao_fim <= limite], "Encerram em até 7 dias")
    elif cmd == "top":
        top = sorted((c for c in todos if c.salario_max), key=lambda c: -c.salario_max)[:10]
        listar(top, "Maiores salários")
    elif cmd in ("estado", "uf"):
        if not arg:
            contagem = Counter(uf for c in todos for uf in ufs_do_concurso(c.uf))
            linhas = [f"{uf} — {ESTADOS[uf]}: {n}" for uf, n in contagem.most_common()]
            tg.enviar(chat, "<b>Concursos de TI por estado</b>\n\n" + "\n".join(linhas or ["Nenhum agora."])
                      + "\n\nEnvie /estado MS ou /estado Mato Grosso do Sul")
            return
        uf = uf_de(arg)
        if not uf:
            tg.enviar(chat, "Não reconheci esse estado. Use a sigla ou o nome: /estado RJ ou /estado Rio de Janeiro")
        else:
            listar([c for c in todos if uf in ufs_do_concurso(c.uf)], f"Concursos de TI — {ESTADOS[uf]} ({uf})")
    elif cmd == "buscar":
        if not arg:
            tg.enviar(chat, "Informe o termo. Exemplo: /buscar analista de dados")
        else:
            alvo = norm(arg)
            achados = [c for c in todos if alvo in norm(" ".join([c.orgao, c.uf, c.titulo, *c.cargos_ti]))]
            listar(achados, f"Busca: {arg}")
    elif cmd == "comunidade":
        tg.enviar(chat, f"👥 Comunidade: {cfg.comunidade}" if cfg.comunidade else "Nenhuma comunidade configurada.")
    elif cmd.startswith("ver_"):
        c = next((c for c in todos if formato.id_curto(c) == cmd[4:]), None)
        if c:
            tg.enviar(chat, formato.card(c, hoje, cfg.comunidade), formato.teclado(c, cfg.comunidade))
        else:
            tg.enviar(chat, "Esse concurso não está mais aberto. Veja a lista atual: /concursos")
    else:
        tg.enviar(chat, "Não conheço esse comando. Veja /ajuda")


def digest(cfg: Config, simular: bool = False) -> int:
    """Uma rodada: atualiza e envia as novidades (uso no GitHub Actions / cron)."""
    hoje = hoje_br()
    estado = Estado.carregar(cfg.data_dir)
    atualizar(estado, Cliente(), hoje)
    if simular:
        novos = pendentes(estado, cfg)
        for c in novos[: cfg.max_envio]:
            print(formato.card(c, hoje, cfg.comunidade), "\n" + "─" * 40)
        print(f"{len(novos)} pendentes de envio; {len(estado.concursos)} concursos de TI abertos.")
        estado.salvar()
        return 0
    n = enviar_novidades(Telegram(cfg.token, cfg.api_base), estado, cfg, hoje)
    estado.salvar()
    log.info("%d concursos enviados", n)
    return n


def executar(cfg: Config) -> None:
    """Modo contínuo: responde comandos e envia novidades a cada ``intervalo_horas``."""
    tg = Telegram(cfg.token, cfg.api_base)
    estado = Estado.carregar(cfg.data_dir)
    tg.chamar("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMANDOS])

    def ciclo():
        while True:
            try:
                atualizar(estado, Cliente(), hoje_br())
                enviar_novidades(tg, estado, cfg, hoje_br())
                estado.salvar()
            except Exception:  # o bot não pode cair por uma falha de coleta
                log.exception("falha no ciclo de atualização")
            time.sleep(cfg.intervalo_horas * 3600)

    threading.Thread(target=ciclo, daemon=True).start()
    log.info("bot no ar; aguardando comandos")
    offset = 0
    while True:
        try:
            for up in tg.atualizacoes(offset):
                offset = up["update_id"] + 1
                msg = up.get("message") or up.get("channel_post")
                if msg:
                    try:
                        responder(tg, estado, cfg, msg, hoje_br())
                    except TelegramErro as e:
                        log.warning("resposta falhou: %s", e)
        except TelegramErro as e:
            log.warning("%s", e)
            time.sleep(5)
