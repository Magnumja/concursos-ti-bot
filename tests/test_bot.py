"""Testes com páginas reais salvas em tests/fixtures (sem acesso à rede)."""
import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from concursos_ti import analise, formato, pci
from concursos_ti.bot import Config, Estado, atualizar, enviar_novidades, pendentes, responder
from concursos_ti.modelos import Concurso
from concursos_ti.telegram import Telegram, TelegramErro

FIX = Path(__file__).parent / "fixtures"
HOJE = date(2026, 11, 9)
SEM_TI = "<article><h1>Prefeitura abre concurso</h1><ul><li>Motorista (2 vagas)</li></ul><p>Nada de tecnologia.</p></article>"


def fixture(nome: str) -> str:
    return (FIX / nome).read_text(encoding="utf-8")


class ClienteFalso:
    """Devolve os fixtures no lugar do site."""

    def __init__(self):
        self.pedidos = []
        self.lista = fixture("lista.html")

    def get(self, url: str) -> str:
        self.pedidos.append(url)
        if "/vagas/" in url:
            return self.lista
        for trecho, arq in (("trf3", "trf3"), ("birigui", "birigui"), ("dpe-am", "dpe_am")):
            if trecho in url:
                return fixture(f"detalhe_{arq}.html")
        return SEM_TI


class TelegramFalso:
    def __init__(self, falhar_em=()):
        self.enviadas, self.falhar_em = [], set(falhar_em)

    def enviar(self, chat, texto, teclado=None):
        if chat in self.falhar_em:
            raise TelegramErro(403, "Forbidden: bot was blocked by the user")
        self.enviadas.append((chat, texto, teclado))


@pytest.fixture
def estado(tmp_path):
    e = Estado(tmp_path)
    atualizar(e, ClienteFalso(), HOJE)
    return e


# ---------- coleta ----------

def test_lista_separa_abertos_de_encerrados():
    itens = pci.parse_lista(fixture("lista.html"))
    assert len(itens) == 7
    assert [i.aberto for i in itens].count(False) == 2
    trf3 = itens[0]
    assert trf3.orgao.startswith("TRF3")
    assert (trf3.vagas, trf3.salario_max, trf3.inscricao_fim) == ("11 vagas", 20013.11, "2026-11-23")
    jandira = itens[1]
    assert (jandira.uf, jandira.inscricao_inicio, jandira.inscricao_fim) == ("SP", "2026-11-16", "2027-01-04")


def test_detalhe_extrai_cargos_links_e_editais():
    det = pci.parse_detalhe(fixture("detalhe_trf3.html"))
    assert det.titulo.startswith("TRF3 - SP/MS")
    assert any("Suporte Técnico" in c for c in det.cargos)
    assert ("www.vunesp.com.br" in [t for t, _ in det.links])
    assert det.editais[0] == "EDITAL Nº 1"


# ---------- filtro de TI ----------

@pytest.mark.parametrize("cargo", [
    "Analista de Tecnologia da Informação (1 vaga)",
    "Técnico em Informática (1 vaga)",
    "Analista de TI (1 vaga)",
    "Assistente de T.I. - Vitória",
    "Analista Judiciário, especialidade: Análise de Sistemas de Informação",
    "Programador (cadastro reserva)",
    "Analista Desenvolvedor de Sistema",
    "Administrador de Banco de Dados",
    "Analista de Rede (cadastro de reserva)",
    "Analista da Defensoria - Segurança da Informação",
    "Cientista de Dados",
    "Professor de Ciência da Computação",
    "Técnico Judiciário, especialidade: Suporte Técnico (4 vagas)",
])
def test_reconhece_cargo_de_ti(cargo):
    assert analise.eh_cargo_ti(cargo)


@pytest.mark.parametrize("cargo", [
    "Motorista de Veículos Pesados (5 vagas)",
    "Técnico em Enfermagem",
    "Analista Judiciário - Área Judiciária",
    "Engenheiro Civil (CR)",
    "Operador de Estação de Tratamento de Água",
    "Profissional de Suporte Técnico (PST) - Assistente Administrativo - Vitória",
    "Técnico de Suporte Administrativo Educacional - Técnico em Nutrição Escolar",
    "Professor assistente em Neurociência Teórica e Computacional",
    "Assistente Social (4 vagas)",
    "Fiscal de Tributos",
])
def test_descarta_cargo_fora_de_ti(cargo):
    assert not analise.eh_cargo_ti(cargo)


def test_perfis_de_estudo():
    assert analise.perfis_de(["Programador", "Analista de Rede"]) == ["dev", "infra"]
    assert analise.perfis_de(["Analista de TI"]) == ["geral"]
    assert analise.perfis_de(["Professor de Desenvolvimento Web"]) == ["docencia"]


# ---------- análise ----------

def test_taxa_pega_faixa_de_valores():
    p = ["As inscrições vão até 23 de novembro. A taxa varia de R$ 100,00 a R$ 160,00."]
    assert analise.extrair_taxa(p) == "R$ 100,00 a R$ 160,00"


def test_taxa_ignora_salario_citado_antes():
    p = [
        "Uma retificação alterou o vencimento de Motorista para R$ 4.912,43 e a isenção da taxa de inscrição.",
        "As inscrições vão até 7 de dezembro. As taxas são de R$ 70,00 para o nível fundamental e R$ 150,00 para o superior.",
    ]
    assert analise.extrair_taxa(p) == "R$ 70,00 a R$ 150,00"


def test_taxa_escrita_como_valor():
    p = ["As inscrições serão reabertas pelo site. O valor é de R$ 80,00 para nível médio e R$ 150,00 para superior. "
         "O pedido de isenção da taxa pode ser feito até 10 de novembro."]
    assert analise.extrair_taxa(p) == "R$ 80,00 a R$ 150,00"


def test_taxa_ausente():
    assert analise.extrair_taxa(["Os salários vão de R$ 1.621,00 a R$ 13.530,00."]) == ""


def test_data_da_prova():
    p = ["As inscrições vão de 15 de outubro de 2026 até 17 de novembro de 2026.",
         "As provas objetivas estão previstas para o dia 17 de janeiro de 2027."]
    assert analise.extrair_prova(p) == "17 de janeiro de 2027"
    assert analise.extrair_prova(["A seleção terá prova objetiva e prova discursiva."]) == ""


def test_analise_completa_do_trf3():
    item = pci.parse_lista(fixture("lista.html"))[0]
    c = analise.analisar(item, pci.parse_detalhe(fixture("detalhe_trf3.html")), HOJE)
    assert len(c.cargos_ti) == 5
    assert (c.uf, c.banca, c.site_inscricao) == ("SP/MS", "Vunesp", "www.vunesp.com.br")
    assert c.taxa == "R$ 100,00 a R$ 160,00"
    assert c.perfis[:2] == ["dev", "suporte"]


def test_concurso_sem_ti_e_descartado():
    item = pci.parse_lista(fixture("lista.html"))[1]
    assert analise.analisar(item, pci.parse_detalhe(SEM_TI), HOJE) is None


# ---------- mensagens ----------

def test_card_traz_tudo_e_cabe_no_telegram(estado):
    c = next(c for c in estado.concursos.values() if c.orgao.startswith("TRF3"))
    texto = formato.card(c, HOJE, "https://t.me/minha_comunidade")
    for trecho in ("Cargos de TI", "R$ 20.013,11", "23/11/2026", "R$ 100,00 a R$ 160,00", "Vunesp",
                   "Edital Nº 1", "O que estudar", "Desenvolvimento", "Faltam 14 dias",
                   "https://t.me/minha_comunidade", c.url):
        assert trecho in texto
    assert len(texto) < 4096
    assert texto.count("<b>") == texto.count("</b>")


def test_card_escapa_html():
    c = Concurso(url="https://x/noticias/a", orgao="Órgão <A&B>", uf="SP", cargos_ti=["Analista <TI>"], perfis=["geral"])
    texto = formato.card(c, HOJE)
    assert "&lt;A&amp;B&gt;" in texto and "<A&B>" not in texto


def test_teclado_tem_edital_compartilhar_e_comunidade(estado):
    c = next(iter(estado.concursos.values()))
    botoes = [b for linha in formato.teclado(c, "https://t.me/grupo")["inline_keyboard"] for b in linha]
    assert botoes[0]["url"] == c.url
    assert botoes[1]["url"].startswith("https://t.me/share/url?url=https%3A%2F%2F")
    assert botoes[2]["url"] == "https://t.me/grupo"
    assert len(formato.teclado(c)["inline_keyboard"]) == 1


def test_lista_longa_e_dividida():
    cs = [Concurso(url=f"https://x/noticias/c{i}", orgao=f"Prefeitura {i} " + "x" * 60, uf="SP",
                   inscricao_fim="2026-12-01") for i in range(120)]
    msgs = formato.lista(cs, HOJE, "Abertos")
    assert len(msgs) > 1 and all(len(m) <= 4096 for m in msgs)
    assert sum(m.count("/ver_") for m in msgs) == 120


# ---------- ciclo do bot ----------

def test_atualizar_guarda_so_ti_aberto(estado):
    orgaos = sorted(c.orgao.split(" ")[0] for c in estado.concursos.values())
    assert orgaos == ["DPE", "Prefeitura", "TRF3"]  # Birigui, DPE-AM e TRF3
    assert len(estado.ignorados) == 2  # Jandira e Contagem (fixture sem TI)


def test_segunda_atualizacao_nao_rebaixa_paginas(estado):
    cliente = ClienteFalso()
    atualizar(estado, cliente, HOJE)
    assert all("/vagas/" in u for u in cliente.pedidos)
    assert len(estado.concursos) == 3


def test_envia_uma_vez_por_prazo_e_reavisa_prorrogacao(estado):
    cfg, tg = Config(chats=["@canal"], max_envio=2), TelegramFalso()
    assert enviar_novidades(tg, estado, cfg, HOJE, pausa=0) == 2
    assert tg.enviadas[0][1].startswith("🖥 <b>TRF3")  # prazo mais próximo primeiro
    assert enviar_novidades(tg, estado, cfg, HOJE, pausa=0) == 1  # o que sobrou do limite
    assert enviar_novidades(tg, estado, cfg, HOJE, pausa=0) == 0

    trf3 = next(c for c in estado.concursos.values() if c.orgao.startswith("TRF3"))
    trf3.inscricao_fim = "2026-11-30"
    assert enviar_novidades(tg, estado, cfg, HOJE, pausa=0) == 1
    assert "Prazo atualizado" in tg.enviadas[-1][1]


def test_filtro_de_uf_no_envio(estado):
    assert [c.uf for c in pendentes(estado, Config(ufs={"AM"}))] == ["AM"]
    assert {c.uf for c in pendentes(estado, Config(ufs={"MS"}))} == {"SP/MS"}


def test_remove_inscrito_que_bloqueou_o_bot(estado):
    estado.inscritos = [111, 222]
    tg = TelegramFalso(falhar_em=[111])
    enviar_novidades(tg, estado, Config(max_envio=1), HOJE, pausa=0)
    assert estado.inscritos == [222] and tg.enviadas[0][0] == 222


def test_estado_sobrevive_a_reinicio(estado):
    estado.enviados["x"] = "2026-12-01"
    estado.inscritos = [42]
    estado.salvar()
    novo = Estado.carregar(estado.pasta)
    assert novo.concursos.keys() == estado.concursos.keys()
    assert novo.enviados == {"x": "2026-12-01"} and novo.inscritos == [42]


def comando(estado, texto, cfg=None, chat=7):
    tg = TelegramFalso()
    responder(tg, estado, cfg or Config(comunidade="https://t.me/grupo"), {"chat": {"id": chat}, "text": texto}, HOJE)
    return tg.enviadas


def test_start_inscreve_e_parar_remove(estado):
    assert "Você vai receber" in comando(estado, "/start")[0][1]
    assert estado.inscritos == [7]
    comando(estado, "/start")
    assert estado.inscritos == [7]
    comando(estado, "/parar")
    assert estado.inscritos == []


def test_comandos_de_consulta(estado):
    assert comando(estado, "/concursos")[0][1].count("/ver_") == 3
    assert comando(estado, "/concursos@MeuBot")[0][1].count("/ver_") == 3
    assert "DPE" in comando(estado, "/uf am")[0][1]  # atalho antigo continua valendo
    assert "Birigui" in comando(estado, "/buscar birigui")[0][1]
    assert "Nada encontrado" in comando(estado, "/buscar xyzzy")[0][1]
    assert comando(estado, "/top")[0][1].index("TRF3") < comando(estado, "/top")[0][1].index("Birigui")
    assert "https://t.me/grupo" in comando(estado, "/comunidade")[0][1]
    assert "/ajuda" in comando(estado, "/naoexiste")[0][1]
    assert comando(estado, "bom dia") == []


@pytest.mark.parametrize("texto,uf", [
    ("MS", "MS"), ("ms", "MS"), ("Mato Grosso do Sul", "MS"), ("mato grosso do sul", "MS"),
    ("Mato Grosso", "MT"), ("RJ", "RJ"), ("Rio de Janeiro", "RJ"), ("sao paulo", "SP"),
    ("São Paulo", "SP"), ("Estado do Amazonas", "AM"), ("distrito federal", "DF"),
    ("Narnia", ""), ("XX", ""), ("", ""),
])
def test_reconhece_estado_por_sigla_ou_nome(texto, uf):
    assert analise.uf_de(texto) == uf


def test_siglas_do_concurso():
    assert analise.ufs_do_concurso("SP/MS") == {"SP", "MS"}
    assert analise.ufs_do_concurso("SP, MT e MS") == {"SP", "MT", "MS"}
    assert analise.ufs_do_concurso("Nacional") == set()


def test_comando_estado(estado):
    for pedido in ("/estado MS", "/estado Mato Grosso do Sul", "/estado mato grosso do sul"):
        texto = comando(estado, pedido)[0][1]
        assert "Mato Grosso do Sul (MS)" in texto and "TRF3" in texto  # TRF3 é SP/MS
    am = comando(estado, "/estado Amazonas")[0][1]
    assert "DPE" in am and "TRF3" not in am
    assert "Nada encontrado" in comando(estado, "/estado Rio de Janeiro")[0][1]
    assert "Não reconheci" in comando(estado, "/estado Narnia")[0][1]
    resumo = comando(estado, "/estado")[0][1]
    assert "SP — São Paulo: 2" in resumo and "AM — Amazonas: 1" in resumo


def test_filtro_ufs_aceita_nome_do_estado():
    cfg = Config.do_ambiente({"UFS": "Mato Grosso do Sul, rj"})
    assert cfg.ufs == {"MS", "RJ"}


def test_ver_mostra_o_card(estado):
    c = next(iter(estado.concursos.values()))
    _, texto, teclado = comando(estado, f"/ver_{formato.id_curto(c)}")[0]
    assert "O que estudar" in texto and teclado
    assert "não está mais aberto" in comando(estado, "/ver_000000")[0][1]


# ---------- cliente do Telegram contra um servidor local ----------

@pytest.fixture
def api_falsa():
    recebidos, respostas = [], []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recebidos.append((self.path, corpo))
            status, dados = respostas.pop(0) if respostas else (200, {"ok": True, "result": {"message_id": 1}})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(dados).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", recebidos, respostas
    srv.shutdown()


def test_envio_real_por_http(api_falsa, estado):
    base, recebidos, _ = api_falsa
    n = enviar_novidades(Telegram("TOKEN", base), estado, Config(chats=["@canal"]), HOJE, pausa=0)
    assert n == 3
    caminho, corpo = recebidos[0]
    assert caminho == "/botTOKEN/sendMessage"
    assert corpo["chat_id"] == "@canal" and corpo["parse_mode"] == "HTML"
    assert corpo["reply_markup"]["inline_keyboard"]


def test_espera_e_repete_quando_o_telegram_limita(api_falsa, monkeypatch):
    base, recebidos, respostas = api_falsa
    monkeypatch.setattr("concursos_ti.telegram.time.sleep", lambda s: None)
    respostas.append((429, {"ok": False, "error_code": 429, "description": "Too Many Requests", "parameters": {"retry_after": 1}}))
    assert Telegram("T", base).enviar(1, "oi") == {"message_id": 1}
    assert len(recebidos) == 2


def test_erro_do_telegram_nao_vaza_o_token(api_falsa):
    base, _, respostas = api_falsa
    respostas.append((400, {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}))
    with pytest.raises(TelegramErro) as e:
        Telegram("SEGREDO", base).enviar(1, "oi")
    assert e.value.codigo == 400 and "SEGREDO" not in str(e.value)
    with pytest.raises(TelegramErro) as e:
        Telegram("SEGREDO", "http://127.0.0.1:1").enviar(1, "oi")
    assert "SEGREDO" not in str(e.value)
