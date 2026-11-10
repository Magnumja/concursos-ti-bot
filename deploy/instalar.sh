#!/usr/bin/env bash
# Instala (ou atualiza) o Concursos TI Bot numa VPS Ubuntu/Debian, como serviço que reinicia sozinho.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/Magnumja/concursos-ti-bot/main/deploy/instalar.sh)
#
# Rodar de novo atualiza o código e reinicia o bot, sem perder o que já foi enviado.
set -euo pipefail

REPO="https://github.com/Magnumja/concursos-ti-bot.git"
PASTA="$HOME/concursos-ti-bot"
DADOS="$HOME/.concursos-ti-bot"
SERVICO="concursos-ti-bot"

echo "==> Instalando dependências do sistema"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-venv >/dev/null

if [ -d "$PASTA/.git" ]; then
  echo "==> Atualizando o código"
  git -C "$PASTA" pull -q --ff-only
else
  echo "==> Baixando o código"
  git clone -q "$REPO" "$PASTA"
fi

echo "==> Preparando o Python"
python3 -m venv "$PASTA/.venv"
"$PASTA/.venv/bin/pip" install -q --upgrade pip
"$PASTA/.venv/bin/pip" install -q -r "$PASTA/requirements.txt"

# Começa com o histórico do GitHub para não reenviar o que o canal já recebeu.
mkdir -p "$DADOS"
if [ ! -f "$DADOS/estado.json" ] && [ -f "$PASTA/data/estado.json" ]; then
  cp "$PASTA/data/estado.json" "$DADOS/estado.json"
fi

ENV="$PASTA/.env"
if [ ! -f "$ENV" ]; then
  echo "==> Configuração (fica só nesta máquina, em $ENV)"
  read -r -s -p "Token do bot (do @BotFather; não aparece ao digitar): " TOKEN </dev/tty; echo
  read -r -p "Canal ou chat de destino [@concursos_ti]: " CHAT </dev/tty
  read -r -p "Link da comunidade [https://t.me/concursos_ti]: " COMUNIDADE </dev/tty
  umask 077
  cat >"$ENV" <<EOF
TELEGRAM_BOT_TOKEN=$TOKEN
TELEGRAM_CHAT_ID=${CHAT:-@concursos_ti}
COMMUNITY_URL=${COMUNIDADE:-https://t.me/concursos_ti}
DATA_DIR=$DADOS
MAX_ENVIO=10
INTERVALO_HORAS=6
EOF
fi

echo "==> Registrando o serviço"
sudo tee "/etc/systemd/system/$SERVICO.service" >/dev/null <<EOF
[Unit]
Description=Concursos TI Bot (Telegram)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PASTA
ExecStart=$PASTA/.venv/bin/python -m concursos_ti run
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q "$SERVICO"
sudo systemctl restart "$SERVICO"

sleep 5
if systemctl is-active -q "$SERVICO"; then
  echo
  echo "✅ Bot no ar. Mande /estado MS para ele no Telegram."
  echo "   Ver o que ele está fazendo:  journalctl -u $SERVICO -f"
  echo "   Trocar o token ou o canal:   nano $ENV && sudo systemctl restart $SERVICO"
  echo "   Atualizar para a versão nova: rode este mesmo comando de novo"
else
  echo "❌ O bot não subiu. Últimas linhas do log:"
  journalctl -u "$SERVICO" -n 30 --no-pager
  exit 1
fi
