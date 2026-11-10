# 🖥 Concursos TI Bot

**Todo concurso público com vaga de TI, no seu Telegram, já lido e resumido.**

Você não precisa mais abrir dezenas de editais de prefeitura para descobrir se há um cargo de tecnologia lá dentro. O bot faz isso várias vezes por dia e entrega só o que interessa: o cargo, o salário, a taxa, as datas, a banca, o edital e o que estudar.

Grátis, sem servidor, no ar em 5 minutos.

## O que chega no seu Telegram

```
🖥 TRF3 - Tribunal Regional Federal da 3ª Região · SP/MS
🔥 Salário alto · 🗓 Faltam 14 dias

💼 Cargos de TI
• Analista Judiciário, especialidade: Análise de Sistemas de Informação (1 vaga)
• Analista Judiciário, especialidade: Suporte em Tecnologia da Informação (1 vaga)
• Técnico Judiciário, especialidade: Desenvolvimento de Sistemas de Informação (5 vagas)
• Técnico Judiciário, especialidade: Suporte Técnico (4 vagas)

💰 Salário: até R$ 20.013,11
👥 Vagas no concurso: 11 vagas
🎓 Nível: Técnico / Superior
🗓 Inscrições: até 23/11/2026
💳 Taxa: R$ 100,00 a R$ 160,00
🏛 Banca: Vunesp — www.vunesp.com.br
📄 Edital: Edital Nº 1 — baixar na página do concurso

📚 O que estudar
Desenvolvimento: Lógica e algoritmos, Estruturas de dados, POO, SQL e modelagem, APIs REST…
Suporte: Hardware e manutenção, Windows e Linux, Redes, ITIL e atendimento ao usuário…
Base comum: Língua Portuguesa, Raciocínio lógico, Legislação do órgão, Inglês técnico
🎯 Estilo Vunesp: questões diretas, com muito português e interpretação

👥 Comunidade: https://t.me/sua_comunidade

[ 📄 Edital e inscrição ]  [ 📤 Compartilhar ]
[ 👥 Entrar na comunidade ]
```

Cada mensagem vem com botão de **compartilhar** e com o link da **sua comunidade**.

## Por que usar

| | |
|---|---|
| 🎯 **Só TI** | Lê a lista de cargos de cada concurso e mostra apenas os de tecnologia: desenvolvimento, redes, suporte, dados, segurança e docência. |
| 🧠 **Já analisado** | Salário, vagas, taxa, prazo, data da prova, banca e edital extraídos e organizados. |
| 📚 **O que estudar** | Guia de estudo pelo perfil do cargo e dica do estilo da banca. |
| ⏳ **Sem perder prazo** | Destaca últimos dias e avisa de novo quando a inscrição é prorrogada. |
| 🔕 **Sem repetição** | Cada concurso chega uma vez. |
| 💸 **Custo zero** | Roda no GitHub Actions. Sem servidor, sem cartão. |

## Comece em 5 minutos (grátis, no GitHub Actions)

1. **Crie o bot.** No Telegram, fale com [@BotFather](https://t.me/BotFather), envie `/newbot` e guarde o token.
2. **Escolha o destino.** Crie um canal ou grupo e adicione o bot como administrador. Ou use uma conversa privada: mande qualquer mensagem ao bot e pegue seu ID com [@userinfobot](https://t.me/userinfobot).
3. **Faça um fork** deste repositório.
4. **Cadastre os segredos** em *Settings → Secrets and variables → Actions*:

   | Tipo | Nome | Valor |
   |---|---|---|
   | Secret | `TELEGRAM_BOT_TOKEN` | o token do BotFather |
   | Secret | `TELEGRAM_CHAT_ID` | `@seu_canal`, o ID do grupo (`-100…`) ou o seu ID |
   | Variable (opcional) | `COMMUNITY_URL` | link da sua comunidade |
   | Variable (opcional) | `UFS` | estados que interessam, ex.: `SP,MS` |

5. **Ligue.** Na aba *Actions*, habilite os workflows e rode **Enviar concursos** em *Run workflow*.

Pronto. O bot passa a rodar sozinho às 7h, 11h, 15h e 19h (Brasília) e envia até 10 concursos por rodada, começando pelos que encerram antes.

> Para várias pessoas receberem ao mesmo tempo, use um **canal**: todos os inscritos recebem a mesma mensagem, sem limite de participantes.

## Modo interativo (com comandos)

No GitHub Actions o bot só envia. Para ele também **responder comandos**, deixe-o rodando em qualquer máquina que fique ligada — seu computador, um Raspberry Pi ou uma VPS gratuita.

```bash
git clone https://github.com/Magnumja/concursos-ti-bot.git
```

```bash
cd concursos-ti-bot && cp .env.example .env
```

Preencha o `.env` e suba com Docker:

```bash
docker compose up -d --build
```

Ou sem Docker:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m concursos_ti run
```

Nesse modo, cada pessoa que mandar `/start` ao bot passa a receber os avisos, e todos podem consultar ao mesmo tempo:

| Comando | O que faz |
|---|---|
| `/concursos` | Todos os concursos de TI abertos, por prazo |
| `/novos` | Os que entraram nos últimos 7 dias |
| `/prazo` | Inscrições que encerram em até 7 dias |
| `/top` | Maiores salários |
| `/uf SP` | Filtra por estado |
| `/buscar analista de dados` | Busca por órgão, cargo ou cidade |
| `/ver_abc123` | Cartão completo de um concurso (o link vem nas listas) |
| `/comunidade` | Link da comunidade |
| `/parar` | Para de receber os avisos |

> Use **um modo por bot**. Se rodar os dois com o mesmo token, os avisos chegam em dobro.

## Veja antes de configurar

Sem token nenhum, mostra no terminal o que seria enviado:

```bash
python -m concursos_ti preview
```

## Configuração

| Variável | Padrão | Para quê |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Token do bot (obrigatório) |
| `TELEGRAM_CHAT_ID` | — | Destino dos avisos; aceita vários, separados por vírgula |
| `COMMUNITY_URL` | — | Link da comunidade em cada mensagem |
| `UFS` | todos | Só avisa concursos destes estados, além dos nacionais |
| `MAX_ENVIO` | `10` | Máximo de concursos por rodada |
| `INTERVALO_HORAS` | `6` | Intervalo entre rodadas no modo interativo |

## Como funciona

```
PCI Concursos ──▶ coleta ──▶ filtro de TI ──▶ análise ──▶ Telegram
 (15 buscas)      pci.py     analise.py      analise.py   formato.py + telegram.py
```

1. **Coleta** — busca os concursos abertos por 15 termos de cargo no [PCI Concursos](https://www.pciconcursos.com.br).
2. **Filtro** — abre a página de cada concurso novo e mantém só os que têm cargo de TI.
3. **Análise** — extrai taxa, prova e banca do texto e monta o guia de estudo pelo perfil do cargo.
4. **Envio** — formata o cartão e envia. O que já foi enviado fica em `data/estado.json`.

O bot se identifica no `User-Agent`, espera entre as requisições e só baixa cada página uma vez.

## Limites, para você saber

- **O edital não é anexado.** O PCI protege os PDFs com captcha, e o bot não contorna isso: ele leva você à página onde o edital está, a um clique.
- **"O que estudar" é um guia**, montado pelo perfil do cargo. O conteúdo programático oficial é sempre o do edital.
- **A fonte é uma só.** Se o PCI Concursos mudar o layout, a coleta precisa de ajuste em `concursos_ti/pci.py`.
- **Taxa e data da prova** saem do texto da notícia. Quando não aparecem lá, o cartão mostra "ver edital".

## Desenvolvimento

```bash
pip install -r requirements.txt pytest && python -m pytest -q
```

Os testes usam páginas reais salvas em `tests/fixtures` e um servidor local no lugar do Telegram; não acessam a rede.

Achou um cargo de TI que o bot ignorou, ou um que não é de TI? Abra uma issue com o link do concurso — o filtro fica em `concursos_ti/analise.py`.

## Licença

[MIT](LICENSE). Os dados dos concursos pertencem aos respectivos órgãos e ao PCI Concursos.
